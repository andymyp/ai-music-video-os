"""Production pipeline activities (MASTER §20, MAD-001 §9).

Each stage of the Phase 10 base workflow is one ``@activity.defn``: the
workflow drives the 19-stage sequence in order and each activity performs one
deterministic step — a creative agent call, a media operation or an artifact
write — against the :class:`~api.activities.services.WorkflowServices`
container. Creative stages route through the agent runtime (which calls the
mock providers); media stages use the media/audio engines; every produced file
lands in the production's artifact directory (TDD-001 §63) under a canonical
:class:`~api.storage.artifacts.ArtifactKind` name.

The activities are deliberately thin: they resolve the services container,
derive the stage's inputs from the persisted production state, and return a
:class:`~api.activities.models.PipelineStageResult`. Heavy side effects stay in
the engines/providers so replay stays deterministic.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from temporalio import activity

from api.activities.models import PipelineStageResult
from api.activities.production import get_activity_services
from api.capabilities import ImageGenerationRequest, MusicGenerationRequest
from api.core.clock import utc_now
from api.core.errors import ConfigurationError, QualityCheckError, WorkflowError
from api.core.observability import get_metrics, instrument
from api.core.system import sample_system_resources
from api.domain.agents import (
    MetadataRequest,
    MusicStrategyRequest,
    QualityControlRequest,
    ShortSelectionRequest,
    TechnicalCheck,
    TrendResearchRequest,
    VisualStrategyRequest,
)
from api.domain.audio import AudioAnalysis
from api.domain.creative import CreativeConcept
from api.domain.enums import ProductionMode
from api.domain.outputs import ShortSegment
from api.domain.production import BrandingConfig
from api.media import (
    VisualizerLayer,
    branding_pixels,
    radio_overlay_pixels,
    slice_visualizer,
    vertical_layout,
    visualizer_region_pixels,
)
from api.media.models import (
    MediaExpectations,
    OverlaySpec,
    RenderRequest,
    VisualizerInput,
    master_render_profile,
    short_render_profile,
)
from api.storage.artifacts import ArtifactKind

#: All pipeline activities a Temporal worker must register (Phase 10).
PIPELINE_ACTIVITIES = [
    "resolve_creative_direction",
    "generate_music_strategy",
    "generate_music",
    "validate_music",
    "master_audio",
    "generate_visual_strategy",
    "generate_background",
    "resolve_radio",
    "analyze_audio",
    "generate_visualizer",
    "render_master",
    "validate_master",
    "select_short_segment",
    "render_short",
    "validate_short",
    "generate_metadata",
    "run_qc",
    "generate_manifest",
    "complete_production",
]


def _result(stage: str, summary: str) -> PipelineStageResult:
    return PipelineStageResult(stage=stage, ok=True, summary=summary)


async def _genre_mood(services, production_id: str) -> tuple[str, str]:
    """Resolve (genre, mood) from the persisted concept, falling back to the
    production's own genre so every stage is deterministic and self-contained."""
    production = await asyncio.to_thread(services.get_production, production_id)
    concept = await asyncio.to_thread(services.get_concept, production_id)
    genre = (concept.genre if concept else None) or (production.genre or "instrumental")
    mood = (concept.mood if concept else None) or f"{genre} atmosphere"
    return genre, mood


# --- Creative stages ---------------------------------------------------------


@activity.defn
async def resolve_creative_direction(production_id: str) -> PipelineStageResult:
    """Turn the production's genre (or a trend pick in trending mode) into a
    persisted :class:`CreativeConcept` that later stages consume."""
    services = get_activity_services()
    production = await asyncio.to_thread(services.get_production, production_id)

    genre = production.genre or "instrumental"
    if production.mode is ProductionMode.TRENDING:
        result = await services.agent_runtime.run(
            "trend_research",
            TrendResearchRequest(genre_hint=None if genre == "instrumental" else genre),
        )
        genre = result.selected_genre or genre
        if result.recommendations:
            trend = result.recommendations[0]
            await asyncio.to_thread(services.save_trend_result, production_id, trend)
            await asyncio.to_thread(
                services.artifact_service.write_text,
                production_id,
                ArtifactKind.TREND_RESULT,
                trend.model_dump_json(indent=2),
            )
        # Persist the selected genre so the production entity reflects the trending choice
        await asyncio.to_thread(services.update_production_genre, production_id, genre)

    mood = f"{genre} atmosphere"
    concept = CreativeConcept(
        genre=genre,
        mood=mood,
        theme=f"{genre} {mood} instrumental music video",
        audience="instrumental music listeners",
        music_direction=f"Produce a {genre} instrumental track with a {mood} mood.",
        visual_direction=f"Create ambient {genre} visuals for a music video.",
    )
    await asyncio.to_thread(services.save_concept, production_id, concept)
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.CREATIVE_CONCEPT,
        concept.model_dump_json(indent=2),
    )
    return _result("resolve_creative_direction", f"concept {genre!r} / {mood!r}")


@activity.defn
async def generate_music_strategy(production_id: str) -> PipelineStageResult:
    """Run the Music Strategy Agent and persist the long-form blueprint."""
    services = get_activity_services()
    config = await asyncio.to_thread(services.get_production_config, production_id)
    genre, mood = await _genre_mood(services, production_id)
    strategy = await services.agent_runtime.run(
        "music_strategy",
        MusicStrategyRequest(
            genre=genre,
            mood=mood,
            duration_target_minutes=config.long_form_duration_minutes if config else 60,
        ),
    )
    await asyncio.to_thread(services.save_music_strategy, production_id, strategy)
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.MUSIC_STRATEGY,
        strategy.model_dump_json(indent=2),
    )
    return _result(
        "generate_music_strategy",
        f"genre {strategy.genre!r} / bpm {strategy.bpm_range}",
    )


@activity.defn
@instrument("pipeline", "generate_music")
async def generate_music(production_id: str) -> PipelineStageResult:
    """Generate the instrumental source audio according to the music strategy.

    Only the raw provider output is persisted (``AUDIO_SOURCE``); the master is
    produced by the subsequent :func:`master_audio` normalization stage
    (MASTER §22: Audio Asset → Music Validation → Master Audio). The strategy's
    BPM range and instruments shape the request (PRD-001 FR-014).
    """
    services = get_activity_services()
    config = await asyncio.to_thread(services.get_production_config, production_id)
    genre, mood = await _genre_mood(services, production_id)
    strategy = await asyncio.to_thread(services.get_music_strategy, production_id)
    prompt = f"instrumental {genre} track, {mood}"
    style_hints = [mood]
    if strategy is not None:
        if strategy.bpm_range:
            low, high = strategy.bpm_range
            prompt += f", {low}-{high} bpm"
        style_hints = [hint for hint in [mood, *strategy.instruments] if hint]
    audio = await services.agent_runtime.run(
        "music_generation",
        MusicGenerationRequest(
            prompt=prompt,
            genre=genre,
            duration_seconds=max(config.short_form_duration_seconds if config else 45, 30),
            style_hints=style_hints,
        ),
    )
    data = audio.audio_bytes
    if not data:
        raise WorkflowError(f"music provider returned no audio for production {production_id!r}")
    await asyncio.to_thread(services.artifact_service.write, production_id, ArtifactKind.AUDIO_SOURCE, data)
    return _result("generate_music", f"source wav {len(data)} bytes")


@activity.defn
async def validate_music(production_id: str) -> PipelineStageResult:
    """Probe the generated audio and reject a production whose audio is invalid.

    PRD-001 §18: existence, readability, duration, format, sample rate and
    channel configuration are checked before the audio may proceed to mastering
    or rendering.
    """
    services = get_activity_services()
    path = services.artifact_service.path_for(production_id, ArtifactKind.AUDIO_SOURCE)
    result = await services.media_engine.validate_media(
        path,
        expectations=MediaExpectations(
            require_audio=True,
            min_duration=5.0,
            min_sample_rate=22050,
            min_channels=1,
            audio_codec="pcm_s16le",
        ),
    )
    if not result.valid:
        failures = [check.name for check in result.failures]
        raise QualityCheckError(f"music validation failed: {failures}")
    return _result("validate_music", "audio validated")


@activity.defn
async def master_audio(production_id: str) -> PipelineStageResult:
    """Normalize the source audio into the master (MAD-001 §19, PRD-001 §19).

    Runs the Audio Mastering pipeline — sample rate, channel and loudness
    normalization plus silence detection — writing ``AUDIO_MASTER`` and a
    structural report artifact. The master is what rendering consumes.
    """
    services = get_activity_services()
    source = services.artifact_service.path_for(production_id, ArtifactKind.AUDIO_SOURCE)
    output = services.artifact_service.path_for(production_id, ArtifactKind.AUDIO_MASTER)
    report = await services.audio_mastering_engine.master(source, output)
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.AUDIO_MASTER_REPORT,
        report.model_dump_json(indent=2),
    )
    if not services.artifact_service.exists(production_id, ArtifactKind.AUDIO_MASTER):
        raise QualityCheckError("audio mastering produced no master file")
    return _result(
        "master_audio",
        f"{report.output_sample_rate} Hz / {report.output_channels}ch "
        f"@ {report.loudness_db} dB",
    )


@activity.defn
async def generate_visual_strategy(production_id: str) -> PipelineStageResult:
    """Run the Visual Strategy Agent and persist the visual blueprint.

    The request is derived from the creative concept (genre, mood, theme, music
    direction, branding) per PRD-001 FR-015, so the strategy reflects the full
    creative direction rather than just the genre.
    """
    services = get_activity_services()
    production = await asyncio.to_thread(services.get_production, production_id)
    concept = await asyncio.to_thread(services.get_concept, production_id)
    genre = (concept.genre if concept else None) or (production.genre or "instrumental")
    mood = (concept.mood if concept else None) or f"{genre} atmosphere"
    strategy = await services.agent_runtime.run(
        "visual_strategy",
        VisualStrategyRequest(
            genre=genre,
            mood=mood,
            theme=concept.theme if concept else None,
            music_direction=concept.music_direction if concept else None,
            branding=production.branding_text,
        ),
    )
    await asyncio.to_thread(services.save_visual_strategy, production_id, strategy)
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.VISUAL_STRATEGY,
        strategy.model_dump_json(indent=2),
    )
    return _result("generate_visual_strategy", f"theme {strategy.theme!r}")


@activity.defn
async def generate_background(production_id: str) -> PipelineStageResult:
    """Generate the 16:9 background image, validate it, and persist it.

    The prompt is derived from the persisted visual strategy (theme,
    environment, lighting, style, palette) so the background matches the
    creative direction (MASTER §23; PRD-001 FR-016). The generated PNG is
    validated structurally (aspect ratio, minimum resolution) *before* it is
    committed as the background asset (TDD-001 §47). Generation is idempotent
    (MAD-001 §3.5): a valid background produced by the same strategy prompt is
    reused instead of regenerated.
    """
    services = get_activity_services()
    genre, mood = await _genre_mood(services, production_id)
    strategy = await asyncio.to_thread(services.get_visual_strategy, production_id)

    if strategy is not None:
        prompt = services.visual_prompt_builder.background_prompt(strategy, genre, mood)
        prompt_hash = services.visual_prompt_builder.prompt_hash(strategy)
    else:
        prompt = services.visual_prompt_builder.generic_background_prompt(genre, mood)
        prompt_hash = services.visual_prompt_builder.hash_text(prompt)

    # Idempotency: reuse a background already produced by this strategy.
    if (
        services.artifact_service.exists(production_id, ArtifactKind.BACKGROUND)
        and services.artifact_service.exists(production_id, ArtifactKind.BACKGROUND_PROMPT)
    ):
        try:
            sidecar = json.loads(
                await asyncio.to_thread(
                    services.artifact_service.read_text, production_id, ArtifactKind.BACKGROUND_PROMPT
                )
            )
        except ValueError:
            sidecar = {}
        if sidecar.get("prompt_hash") == prompt_hash:
            data = await asyncio.to_thread(
                services.artifact_service.read, production_id, ArtifactKind.BACKGROUND
            )
            return _result(
                "generate_background",
                f"reused background png {len(data)} bytes (hash {prompt_hash[:8]})",
            )

    image = await services.agent_runtime.run(
        "visual_generation",
        ImageGenerationRequest(
            prompt=prompt,
            aspect_ratio="16:9",
            style_hints=["ambient", genre, strategy.style] if strategy else ["ambient", genre],
        ),
    )
    data = image.image_bytes
    if not data:
        raise WorkflowError(f"image provider returned no background for production {production_id!r}")

    # Structural validation before committing the asset (TDD-001 §47).
    validation = services.image_validator.validate(
        data, expected_aspect="16:9", min_width=1280, min_height=720
    )
    if not validation.valid:
        failures = "; ".join(
            f"{check.name}:{check.actual}" for check in validation.failures
        )
        raise QualityCheckError(
            f"background failed validation for production {production_id!r}: {failures}"
        )

    await asyncio.to_thread(services.artifact_service.write, production_id, ArtifactKind.BACKGROUND, data)
    sidecar = {
        "prompt": prompt,
        "prompt_hash": prompt_hash,
        "theme": strategy.theme if strategy else None,
        "style": strategy.style if strategy else None,
    }
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.BACKGROUND_PROMPT,
        json.dumps(sidecar, indent=2),
    )
    return _result(
        "generate_background",
        f"png {len(data)} bytes hash {prompt_hash[:8]} ({validation.width}x{validation.height})",
    )


@activity.defn
async def resolve_radio(production_id: str) -> PipelineStageResult:
    """Resolve the radio/visualizer focal image from the shared asset registry.

    The strategy's radio_style selects a reusable asset; existing assets are
    reused and only new styles trigger generation (MAD-001 §22, TDD-001 §48).
    """
    services = get_activity_services()
    if services.radio_registry is None:
        raise ConfigurationError("radio asset registry is not configured")
    strategy = await asyncio.to_thread(services.get_visual_strategy, production_id)
    radio_style = (strategy.radio_style if strategy else None) or "vintage"
    asset = await services.radio_registry.resolve(radio_style)
    await asyncio.to_thread(services.artifact_service.write, production_id, ArtifactKind.RADIO, asset.data)
    verb = "reused" if asset.reused else "generated"
    return _result("resolve_radio", f"{verb} {radio_style} radio")


# --- Audio analysis / visualizer ---------------------------------------------


@activity.defn
@instrument("pipeline", "analyze_audio")
async def analyze_audio(production_id: str) -> PipelineStageResult:
    """Analyze the master audio and persist the analysis document."""
    services = get_activity_services()
    path = services.artifact_service.path_for(production_id, ArtifactKind.AUDIO_MASTER)
    analysis = await services.audio_engine.analyze(str(path))
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.AUDIO_ANALYSIS,
        analysis.model_dump_json(),
    )
    bpm = f"bpm {analysis.bpm}" if analysis.bpm is not None else "no tempo"
    return _result("analyze_audio", f"{bpm}, {analysis.duration_seconds:.1f}s")


@activity.defn
async def generate_visualizer(production_id: str) -> PipelineStageResult:
    """Derive FFT band frames from the actual master audio and persist the layer.

    The engine reads the master WAV and computes normalized 5-band values via a
    fixed FFT (MAD-001 §23), so the visualizer is synchronized with the real
    audio (PRD-001 FR-018/§24). Style comes from the visual strategy; the
    sensitivity/smoothing tuning stays at engine defaults (MAD-001 §23 config),
    and the composed layer (TDD-001 §52 radio region layout) is persisted
    alongside the data for the Phase 15 renderer.
    """
    services = get_activity_services()
    analysis = AudioAnalysis.model_validate_json(
        await asyncio.to_thread(
            services.artifact_service.read_text, production_id, ArtifactKind.AUDIO_ANALYSIS
        )
    )
    config = await asyncio.to_thread(services.get_production_config, production_id)
    strategy = await asyncio.to_thread(services.get_visual_strategy, production_id)
    style = (strategy.visualizer_style if strategy else None) or "bars"
    master_path = services.artifact_service.path_for(production_id, ArtifactKind.AUDIO_MASTER)

    visualizer = await services.visualizer_engine.generate_data(
        analysis,
        master_path=master_path,
        style=style,
        position="radio-center",
    )
    # The layout's visualizer region is the radio's inner 70% computed in the
    # production's master pixel space, so the region always fits the radio
    # square for the configured resolution (TDD-001 §52, §128).
    layer = services.visualizer_engine.render(
        visualizer,
        frame_width=config.master_width if config else 1920,
        frame_height=config.master_height if config else 1080,
    )
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.VISUALIZER_DATA,
        visualizer.model_dump_json(),
    )
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.VISUALIZER_LAYER,
        layer.model_dump_json(),
    )
    return _result(
        "generate_visualizer",
        f"{len(visualizer.frames)} frames x {len(visualizer.band_names)} bands ({style})",
    )


# --- Rendering ----------------------------------------------------------------

#: Candidate system fonts for the drawtext overlay (TDD-001 §53). The first one
#: that exists is used; rendering is skipped when none is available.
_BRANDING_FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
)


def _resolve_branding_font() -> Path | None:
    for candidate in _BRANDING_FONT_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def _visualizer_frames_dir(services, production_id: str) -> Path:
    """Deterministic temp dir for the master's per-frame visualizer sprites.

    Lives under the production's ``render`` subdirectory so it respects the
    container's data root (tests inject isolated settings) and is transient —
    never a canonical artifact (MAD-001 §44).
    """
    return services.artifact_service.subdir(production_id, "render") / "visualizer"


@activity.defn
@instrument("pipeline", "render_master")
async def render_master(production_id: str) -> PipelineStageResult:
    """Compose background + radio + visualizer + branding + audio (MAD-001 §24).

    Holds a :class:`~api.core.resources.RenderGate` permit for the duration of
    the FFmpeg encode so at most ``max_render_workers`` heavy renders run
    concurrently on the target laptop (MASTER §40, TDD-001 §87).
    """
    services = get_activity_services()
    async with services.render_gate:
        return await _render_master(services, production_id)


async def _render_master(services, production_id: str) -> PipelineStageResult:
    """Compose background + radio + visualizer + branding + audio (MAD-001 §24).

    Geometry (radio position/scale, visualizer region, branding anchor) comes
    from the persisted VISUALIZER_LAYER layout (TDD-001 §52); the per-frame bar
    sprites are rendered from the visualizer data and overlaid inside the radio
    (TDD-001 §52). Encoding honors the production's configured master
    resolution/FPS through a render profile (PRD-001 §27, MAD-001 §56).
    """
    production = await asyncio.to_thread(services.get_production, production_id)
    config = await asyncio.to_thread(services.get_production_config, production_id)
    profile = master_render_profile(config)
    branding = config.branding if config else BrandingConfig()

    # The visualizer layer pins the composition layout; productions without one
    # (pre-Phase 14 data) fall back to the legacy centered radio placement.
    layer: VisualizerLayer | None = None
    if services.artifact_service.exists(production_id, ArtifactKind.VISUALIZER_LAYER):
        layer = VisualizerLayer.model_validate_json(
            await asyncio.to_thread(
                services.artifact_service.read_text, production_id, ArtifactKind.VISUALIZER_LAYER
            )
        )

    overlays: list[OverlaySpec] = []
    visualizer: VisualizerInput | None = None
    if layer is not None:
        rx, ry, rw, rh = radio_overlay_pixels(layer.layout, width=profile.width, height=profile.height)
        overlays.append(
            OverlaySpec(
                path=services.artifact_service.path_for(production_id, ArtifactKind.RADIO),
                x=rx,
                y=ry,
                width=rw,
                height=rh,
                opacity=0.85,
            )
        )
        if layer.visualizer.frames:
            duration = await _master_duration_seconds(services, production_id, config)
            vx, vy, vw, vh = visualizer_region_pixels(
                layer.layout, width=profile.width, height=profile.height
            )
            frames_dir = _visualizer_frames_dir(services, production_id)
            shutil.rmtree(frames_dir, ignore_errors=True)
            frames_dir.mkdir(parents=True, exist_ok=True)
            for index, sprite in enumerate(
                services.visualizer_engine.render_frames(
                    layer.visualizer, width=vw, height=vh
                ),
                start=1,
            ):
                (frames_dir / f"{index:05d}.png").write_bytes(sprite)
            visualizer = VisualizerInput(
                frames_dir=frames_dir,
                fps=layer.visualizer.fps,
                region_x=vx,
                region_y=vy,
                region_width=vw,
                region_height=vh,
                duration_seconds=duration,
            )
    else:
        overlays.append(
            OverlaySpec(
                path=services.artifact_service.path_for(production_id, ArtifactKind.RADIO),
                x=720,
                y=300,
                width=480,
                height=480,
                opacity=0.85,
            )
        )

    bx, by = (
        branding_pixels(layer.layout, width=profile.width, height=profile.height)
        if layer is not None
        else (0, 0)
    )
    font = _resolve_branding_font()
    request = RenderRequest(
        background=services.artifact_service.path_for(production_id, ArtifactKind.BACKGROUND),
        audio=services.artifact_service.path_for(production_id, ArtifactKind.AUDIO_MASTER),
        overlays=overlays,
        visualizer=visualizer,
        branding_text=(production.branding_text or branding.text) or None,
        branding_font=font,
        branding_x=bx,
        branding_y=by,
        branding_size=branding.font_size,
        branding_opacity=branding.opacity,
        output_path=services.artifact_service.path_for(production_id, ArtifactKind.MASTER_VIDEO),
    )
    output = await services.media_engine.render_master(request, profile=profile)
    return _result("render_master", f"master {output.name}")


async def _master_duration_seconds(services, production_id: str, config) -> float | None:
    """Master audio duration for bounding the visualizer overlay (TDD-001 §52)."""
    if services.artifact_service.exists(production_id, ArtifactKind.AUDIO_ANALYSIS):
        analysis = AudioAnalysis.model_validate_json(
            await asyncio.to_thread(
                services.artifact_service.read_text, production_id, ArtifactKind.AUDIO_ANALYSIS
            )
        )
        return analysis.duration_seconds
    if config is not None:
        return float(config.long_form_duration_minutes * 60)
    return None


@activity.defn
async def validate_master(production_id: str) -> PipelineStageResult:
    """Probe the master render against the master profile expectations."""
    services = get_activity_services()
    config = await asyncio.to_thread(services.get_production_config, production_id)
    profile = master_render_profile(config)
    path = services.artifact_service.path_for(production_id, ArtifactKind.MASTER_VIDEO)
    result = await services.media_engine.validate_media(
        path,
        expectations=MediaExpectations(
            require_video=True,
            width=profile.width,
            height=profile.height,
            fps=profile.fps,
            min_duration=5.0,
        ),
    )
    if not result.valid:
        failures = [check.name for check in result.failures]
        raise QualityCheckError(f"master validation failed: {failures}")
    return _result("validate_master", "master validated")


@activity.defn
async def select_short_segment(production_id: str) -> PipelineStageResult:
    """Pick the strongest short-form window of the master audio."""
    services = get_activity_services()
    config = await asyncio.to_thread(services.get_production_config, production_id)
    segment = await services.agent_runtime.run(
        "short_selection",
        ShortSelectionRequest(
            audio_path=str(
                services.artifact_service.path_for(production_id, ArtifactKind.AUDIO_MASTER)
            ),
            target_duration_seconds=float(config.short_form_duration_seconds if config else 45),
            min_duration_seconds=20.0,
            max_duration_seconds=60.0,
        ),
    )
    await _validate_short_segment(services, production_id, segment, config)
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.SHORT_SEGMENT,
        segment.model_dump_json(),
    )
    return _result(
        "select_short_segment",
        f"start {segment.start_seconds:g}s / {segment.duration_seconds:g}s",
    )


async def _validate_short_segment(services, production_id: str, segment: ShortSegment, config) -> None:
    """Reject a short segment that cannot be rendered (MAD-001 §26).

    The clip must be structurally valid (non-negative start, positive duration),
    within the platform short-form ceiling (MAD-001 §25: 30-60s target, bounded
    at 60s), and lie entirely inside the master audio — a window past the end
    would render silence/tail frames. The selection agent already clamps to the
    audio length, so no floor is imposed: a short master yields a short clip.
    """
    if segment.start_seconds < 0 or segment.duration_seconds <= 0:
        raise QualityCheckError(
            f"short segment invalid for production {production_id!r}: "
            f"start {segment.start_seconds:g}s / {segment.duration_seconds:g}s"
        )
    if segment.duration_seconds > 60.0:
        raise QualityCheckError(
            f"short segment out of bounds for production {production_id!r}: "
            f"duration {segment.duration_seconds:g}s exceeds the 60s platform ceiling"
        )
    if services.artifact_service.exists(production_id, ArtifactKind.AUDIO_ANALYSIS):
        analysis = AudioAnalysis.model_validate_json(
            await asyncio.to_thread(
                services.artifact_service.read_text, production_id, ArtifactKind.AUDIO_ANALYSIS
            )
        )
        master_duration = analysis.duration_seconds
    elif config is not None:
        master_duration = float(config.long_form_duration_minutes * 60)
    else:
        master_duration = None
    if master_duration is not None and segment.start_seconds + segment.duration_seconds > master_duration + 1.0:
        raise QualityCheckError(
            f"short segment exceeds master for production {production_id!r}: "
            f"end {segment.start_seconds + segment.duration_seconds:g}s > {master_duration:g}s"
        )


def _short_frames_dir(services, production_id: str) -> Path:
    """Deterministic temp dir for the short's per-frame visualizer sprites.

    Lives under the production's ``render`` subdirectory like the master's
    sprites but in its own subdir so a short render never clobbers master
    sprites mid-render. Transient — never a canonical artifact (MAD-001 §44).
    """
    return services.artifact_service.subdir(production_id, "render") / "short-visualizer"


@activity.defn
@instrument("pipeline", "render_short")
async def render_short(production_id: str) -> PipelineStageResult:
    """Trim the selected segment into the 9:16 short render (MAD-001 §25-27).

    Holds a :class:`~api.core.resources.RenderGate` permit for the duration of
    the FFmpeg encode so at most ``max_render_workers`` heavy renders run
    concurrently on the target laptop (MASTER §40, TDD-001 §87).
    """
    services = get_activity_services()
    async with services.render_gate:
        return await _render_short(services, production_id)


async def _render_short(services, production_id: str) -> PipelineStageResult:
    """Trim the selected segment into the 9:16 short render (MAD-001 §25-27).

    The short reuses the master's visualizer data — never regenerates
    independent music (PRD-001 §24) — sliced to the segment window so the bars
    stay synchronized with the trimmed audio (TDD-001 §129), and composes the
    dedicated vertical layout: radio in the upper third, visualizer inside its
    display area, branding bottom-center (MAD-001 §27, TDD-001 §128). Encoding
    honors the production's configured short resolution/FPS (PRD-001 §28,
    MAD-001 §56).
    """
    production = await asyncio.to_thread(services.get_production, production_id)
    config = await asyncio.to_thread(services.get_production_config, production_id)
    profile = short_render_profile(config)
    branding = config.branding if config else BrandingConfig()
    segment = ShortSegment.model_validate_json(
        await asyncio.to_thread(
            services.artifact_service.read_text, production_id, ArtifactKind.SHORT_SEGMENT
        )
    )

    # The visualizer layer pins the composition layout; productions without one
    # (pre-Phase 14 data) fall back to the legacy centered radio placement.
    layer: VisualizerLayer | None = None
    if services.artifact_service.exists(production_id, ArtifactKind.VISUALIZER_LAYER):
        layer = VisualizerLayer.model_validate_json(
            await asyncio.to_thread(
                services.artifact_service.read_text, production_id, ArtifactKind.VISUALIZER_LAYER
            )
        )

    overlays: list[OverlaySpec] = []
    visualizer: VisualizerInput | None = None
    if layer is not None:
        # Dedicated 9:16 composition (MAD-001 §27); style comes from the visual
        # strategy carried by the persisted layer.
        layout = vertical_layout(layer.visualizer.style, width=profile.width, height=profile.height)
        rx, ry, rw, rh = radio_overlay_pixels(layout, width=profile.width, height=profile.height)
        overlays.append(
            OverlaySpec(
                path=services.artifact_service.path_for(production_id, ArtifactKind.RADIO),
                x=rx,
                y=ry,
                width=rw,
                height=rh,
                opacity=0.85,
            )
        )
        if layer.visualizer.frames:
            vx, vy, vw, vh = visualizer_region_pixels(
                layout, width=profile.width, height=profile.height
            )
            # The segment's window of the master's visualizer, timestamps rebased
            # to short t=0 (TDD-001 §129) — never regenerated independent music.
            sliced = slice_visualizer(
                layer.visualizer,
                start_seconds=segment.start_seconds,
                duration_seconds=segment.duration_seconds,
            )
            frames_dir = _short_frames_dir(services, production_id)
            shutil.rmtree(frames_dir, ignore_errors=True)
            frames_dir.mkdir(parents=True, exist_ok=True)
            for index, sprite in enumerate(
                services.visualizer_engine.render_frames(sliced, width=vw, height=vh),
                start=1,
            ):
                (frames_dir / f"{index:05d}.png").write_bytes(sprite)
            visualizer = VisualizerInput(
                frames_dir=frames_dir,
                fps=sliced.fps,
                region_x=vx,
                region_y=vy,
                region_width=vw,
                region_height=vh,
                duration_seconds=segment.duration_seconds,
            )
    else:
        overlays.append(
            OverlaySpec(
                path=services.artifact_service.path_for(production_id, ArtifactKind.RADIO),
                x=270,
                y=696,
                width=540,
                height=540,
                opacity=0.85,
            )
        )

    font = _resolve_branding_font()
    bx, by = (
        branding_pixels(layout, width=profile.width, height=profile.height)
        if layer is not None
        else (0, 0)
    )
    request = RenderRequest(
        background=services.artifact_service.path_for(production_id, ArtifactKind.BACKGROUND),
        audio=services.artifact_service.path_for(production_id, ArtifactKind.AUDIO_MASTER),
        overlays=overlays,
        visualizer=visualizer,
        branding_text=(production.branding_text or branding.text) or None,
        branding_font=font,
        branding_x=bx,
        branding_y=by,
        branding_size=branding.font_size,
        branding_opacity=branding.opacity,
        branding_align="center",
        output_path=services.artifact_service.path_for(production_id, ArtifactKind.SHORT_VIDEO),
        segment=segment,
    )
    output = await services.media_engine.render_short(request, profile=profile)
    return _result("render_short", f"short {output.name}")


@activity.defn
async def validate_short(production_id: str) -> PipelineStageResult:
    """Probe the short render against the short profile expectations."""
    services = get_activity_services()
    config = await asyncio.to_thread(services.get_production_config, production_id)
    path = services.artifact_service.path_for(production_id, ArtifactKind.SHORT_VIDEO)
    result = await services.media_engine.validate_media(
        path,
        expectations=MediaExpectations(
            require_video=True,
            width=config.short_width if config else 1080,
            height=config.short_height if config else 1920,
            fps=config.fps if config else 30,
            min_duration=5.0,
        ),
    )
    if not result.valid:
        failures = [check.name for check in result.failures]
        raise QualityCheckError(f"short validation failed: {failures}")
    return _result("validate_short", "short validated")


# --- Metadata / QC / manifest -------------------------------------------------


@activity.defn
async def generate_metadata(production_id: str) -> PipelineStageResult:
    """Generate platform metadata for master and short and persist it.

    The request is built from the actual production information (TDD-001 §57):
    the CreativeConcept (theme, audience, music/visual direction), the
    MusicStrategy (BPM, instruments), the VisualStrategy (environment, lighting,
    style, palette), trend context in trending mode, and the selected
    ShortSegment — so the generated package corresponds to the production
    (TDD-001 §58) rather than the genre alone (MASTER §27).
    """
    services = get_activity_services()
    production = await asyncio.to_thread(services.get_production, production_id)
    genre, mood = await _genre_mood(services, production_id)
    concept = await asyncio.to_thread(services.get_concept, production_id)
    music = await asyncio.to_thread(services.get_music_strategy, production_id)
    visual = await asyncio.to_thread(services.get_visual_strategy, production_id)
    trend = await asyncio.to_thread(services.get_trend_result, production_id)

    music_concept = _music_concept_summary(concept, music)
    visual_concept = _visual_concept_summary(concept, visual)
    trend_context = ""
    if trend is not None and trend.topic:
        trend_context = f"{trend.topic} (genre {trend.genre or 'n/a'})"

    segment = None
    if services.artifact_service.exists(production_id, ArtifactKind.SHORT_SEGMENT):
        segment = ShortSegment.model_validate_json(
            await asyncio.to_thread(
                services.artifact_service.read_text, production_id, ArtifactKind.SHORT_SEGMENT
            )
        )

    package = await services.agent_runtime.run(
        "metadata",
        MetadataRequest(
            genre=genre,
            mood=mood,
            theme=concept.theme if concept else "",
            audience=concept.audience if concept and concept.audience else "",
            music_concept=music_concept,
            visual_concept=visual_concept,
            trend_context=trend_context,
            branding=production.branding_text,
            short_segment=segment,
        ),
    )
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.METADATA,
        package.model_dump_json(indent=2),
    )
    return _result("generate_metadata", package.master.title)


def _music_concept_summary(concept, music) -> str:
    """Flatten MusicStrategy into a prompt-ready concept summary (TDD-001 §57)."""
    parts: list[str] = []
    if concept is not None and concept.music_direction:
        parts.append(concept.music_direction)
    if music is not None:
        if music.bpm_range:
            parts.append(f"{music.bpm_range[0]}-{music.bpm_range[1]} bpm")
        if music.key:
            parts.append(f"key {music.key}")
        if music.instruments:
            parts.append("instruments: " + ", ".join(music.instruments))
        if music.structure:
            parts.append(music.structure)
    return " ".join(parts)


def _visual_concept_summary(concept, visual) -> str:
    """Flatten VisualStrategy into a prompt-ready concept summary (TDD-001 §57)."""
    parts: list[str] = []
    if concept is not None and concept.visual_direction:
        parts.append(concept.visual_direction)
    if visual is not None:
        if visual.environment:
            parts.append(visual.environment)
        if visual.lighting:
            parts.append(visual.lighting)
        if visual.style:
            parts.append(visual.style)
        if visual.era:
            parts.append(visual.era)
        if visual.palette:
            parts.append("palette: " + ", ".join(visual.palette))
    return " ".join(parts)


@activity.defn
@instrument("pipeline", "run_qc")
async def run_qc(production_id: str) -> PipelineStageResult:
    """Run the Quality Control Agent over the produced artifacts (MAD-001 §33).

    Deterministic technical checks (existence, integrity, media expectations
    derived from the render profiles) always run first; the agent then performs
    the AI-assisted creative assessment against the actual creative brief and
    records the structured result in the QC report (TDD-001 §59-61).
    """
    services = get_activity_services()
    checks = await _qc_technical_checks(services, production_id)
    decision = await services.agent_runtime.run(
        "quality_control",
        QualityControlRequest(
            production_id=production_id,
            technical_checks=checks,
            mandatory_checks=["music.valid", "master.valid", "short.valid"],
            creative_context=await _qc_creative_context(services, production_id),
        ),
    )
    report = {
        "production_id": production_id,
        "passed": decision.passed,
        "score": decision.score,
        "issues": decision.issues,
        "warnings": decision.warnings,
        "creative": decision.creative.model_dump() if decision.creative else None,
        "technical_checks": [check.model_dump() for check in checks],
        "created_at": utc_now().isoformat(),
    }
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.QC_REPORT,
        json.dumps(report, indent=2),
    )
    if not decision.passed:
        raise QualityCheckError(f"quality control failed: {decision.issues}")
    return _result("run_qc", f"passed, score {decision.score:.2f}")


@activity.defn
async def generate_manifest(production_id: str) -> PipelineStageResult:
    """Write the production + manifest documents that describe the deliverables."""
    services = get_activity_services()
    production = await asyncio.to_thread(services.get_production, production_id)
    config = await asyncio.to_thread(services.get_production_config, production_id)
    concept = await asyncio.to_thread(services.get_concept, production_id)
    music = await asyncio.to_thread(services.get_music_strategy, production_id)
    visual = await asyncio.to_thread(services.get_visual_strategy, production_id)

    production_doc = {
        "production_id": production_id,
        "mode": production.mode.value,
        "genre": production.genre,
        "config": config.to_row_values() if config else None,
        "concept": concept.to_row_values() if concept else None,
        "music_strategy": music.to_row_values() if music else None,
        "visual_strategy": visual.to_row_values() if visual else None,
        "metadata": _read_json(services, production_id, ArtifactKind.METADATA),
        "qc_report": _read_json(services, production_id, ArtifactKind.QC_REPORT),
        "short_segment": _read_json(services, production_id, ArtifactKind.SHORT_SEGMENT),
    }
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.PRODUCTION,
        json.dumps(production_doc, indent=2),
    )

    # Build the artifact index over every canonical kind: each entry carries the
    # deterministic path plus hash/size when the file exists, so the manifest is
    # the complete production catalogue (TDD-001 §63) even for a mode that does
    # not produce a given kind (e.g. trend-result.json in genre mode).
    artifacts: dict[str, object] = {}
    for kind in ArtifactKind:
        entry: dict[str, object] = {
            "path": str(services.artifact_service.path_for(production_id, kind)),
            "present": services.artifact_service.exists(production_id, kind),
        }
        if entry["present"]:
            entry["sha256"] = services.artifact_service.hash(production_id, kind)
            entry["size"] = services.artifact_service.size(production_id, kind)
        artifacts[kind.value] = entry

    manifest = {
        "schema_version": 1,
        "production_id": production_id,
        "status": production.status.value,
        "generated_at": utc_now().isoformat(),
        "artifacts": artifacts,
    }
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.MANIFEST,
        json.dumps(manifest, indent=2),
    )
    return _result("generate_manifest", f"{len(artifacts)} artifacts")


@activity.defn
@instrument("pipeline", "complete_production")
async def complete_production(production_id: str) -> PipelineStageResult:
    """Drive the production to COMPLETED (idempotent final transition)."""
    services = get_activity_services()
    status = await asyncio.to_thread(services.complete_production, production_id)
    # Phase 25: capture a final RAM/CPU/disk snapshot so the performance budget
    # includes the full render footprint (MASTER §40, TDD-001 §145).
    get_metrics().record_performance_sample(
        production_id,
        sample_system_resources(services.settings.app_data_dir),
    )
    return _result("complete_production", status.value)


# --- helpers ------------------------------------------------------------------


async def _qc_technical_checks(services, production_id: str) -> list[TechnicalCheck]:
    """Deterministic technical checks fed to the QC Agent (MAD-001 §33).

    Coverage mirrors PRD-001 FR-023 / TDD-001 §60: file existence, file
    integrity (non-zero byte; a probeable file), and media-stream expectations
    derived from the production's render profiles rather than hard-coded
    dimensions (MAD-001 §31.1, §56). Expected codecs are the encoded
    profiles' H.264/AAC streams as ffprobe reports them.
    """
    config = await asyncio.to_thread(services.get_production_config, production_id)
    master_profile = master_render_profile(config)
    short_profile = short_render_profile(config)

    required = (
        ArtifactKind.AUDIO_MASTER,
        ArtifactKind.BACKGROUND,
        ArtifactKind.RADIO,
        ArtifactKind.MASTER_VIDEO,
        ArtifactKind.SHORT_VIDEO,
        ArtifactKind.METADATA,
        ArtifactKind.MANIFEST,
    )
    checks: list[TechnicalCheck] = []
    for kind in required:
        present = services.artifact_service.exists(production_id, kind)
        size = services.artifact_service.size(production_id, kind) if present else 0
        checks.append(TechnicalCheck(name=f"{kind.value}.exists", passed=present, detail=kind.value))
        # MAD-001 §31.1 / PRD-001 FR-023: no zero-byte files, files not corrupted.
        checks.append(
            TechnicalCheck(name=f"{kind.value}.integrity", passed=present and size > 0, detail=kind.value)
        )

    # The mastered audio is a normalized PCM WAV (MAD-001 §19); the rendered
    # videos carry H.264 video + AAC audio as configured by their profiles.
    media_checks = (
        (
            ArtifactKind.AUDIO_MASTER,
            MediaExpectations(
                require_audio=True,
                min_duration=5.0,
                min_sample_rate=44100,
                min_channels=2,
                audio_codec="pcm_s16le",
            ),
            "music.valid",
        ),
        (
            ArtifactKind.MASTER_VIDEO,
            MediaExpectations(
                require_audio=True,
                require_video=True,
                width=master_profile.width,
                height=master_profile.height,
                fps=master_profile.fps,
                audio_codec="aac",
                video_codec="h264",
            ),
            "master.valid",
        ),
        (
            ArtifactKind.SHORT_VIDEO,
            MediaExpectations(
                require_audio=True,
                require_video=True,
                width=short_profile.width,
                height=short_profile.height,
                fps=short_profile.fps,
                audio_codec="aac",
                video_codec="h264",
            ),
            "short.valid",
        ),
    )
    for kind, expectations, name in media_checks:
        result = await services.media_engine.validate_media(
            services.artifact_service.path_for(production_id, kind),
            expectations=expectations,
        )
        detail = ",".join(check.name for check in result.failures)
        checks.append(TechnicalCheck(name=name, passed=result.valid, detail=detail))
    return checks


async def _qc_creative_context(services, production_id: str) -> str:
    """Flatten the persisted creative brief for the creative QC assessment.

    Gives the AI assessor the actual creative direction — concept, music and
    visual strategy, branding, metadata and the selected short segment — so the
    five dimensions of MASTER §28 are judged against the production rather than
    a bare genre label (TDD-001 §61). Reuses the same flatteners as the
    metadata prompt (TDD-001 §57).
    """
    production = await asyncio.to_thread(services.get_production, production_id)
    config = await asyncio.to_thread(services.get_production_config, production_id)
    concept = await asyncio.to_thread(services.get_concept, production_id)
    music = await asyncio.to_thread(services.get_music_strategy, production_id)
    visual = await asyncio.to_thread(services.get_visual_strategy, production_id)
    metadata = _read_json(services, production_id, ArtifactKind.METADATA)
    segment = _read_json(services, production_id, ArtifactKind.SHORT_SEGMENT)

    parts: list[str] = []
    genre = (concept.genre if concept else None) or (production.genre or "instrumental")
    mood = (concept.mood if concept else None) or f"{genre} atmosphere"
    parts.append(f"genre: {genre}, mood: {mood}")
    if concept is not None and concept.theme:
        parts.append(f"theme: {concept.theme}")
    music_summary = _music_concept_summary(concept, music)
    if music_summary:
        parts.append(f"music: {music_summary}")
    visual_summary = _visual_concept_summary(concept, visual)
    if visual_summary:
        parts.append(f"visual: {visual_summary}")
    branding = (production.branding_text or (config.branding.text if config is not None else None)) or None
    if branding:
        parts.append(f"branding: {branding}")
    if isinstance(metadata, dict):
        master = metadata.get("master") or {}
        short = metadata.get("short") or {}
        if master.get("title"):
            parts.append(f"master metadata title: {master['title']!r}")
        if short.get("title"):
            parts.append(f"short metadata title: {short['title']!r}")
    if isinstance(segment, dict) and segment.get("duration_seconds"):
        parts.append(
            f"short segment: {segment['duration_seconds']}s clip starting at "
            f"{segment.get('start_seconds', 0)}s"
        )
    return "; ".join(parts)


def _read_json(services, production_id: str, kind: ArtifactKind) -> object:
    if not services.artifact_service.exists(production_id, kind):
        return None
    try:
        return json.loads(services.artifact_service.read_text(production_id, kind))
    except (ValueError, OSError):
        return None
