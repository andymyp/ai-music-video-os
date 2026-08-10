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

from temporalio import activity

from api.activities.models import PipelineStageResult
from api.activities.production import get_activity_services
from api.capabilities import ImageGenerationRequest, MusicGenerationRequest
from api.core.clock import utc_now
from api.core.errors import QualityCheckError, WorkflowError
from api.domain.agents import (
    MetadataRequest,
    MusicStrategyRequest,
    QualityControlRequest,
    ShortSelectionRequest,
    TechnicalCheck,
    TrendResearchRequest,
    VisualStrategyRequest,
)
from api.domain.audio import AudioAnalysis, VisualizerData
from api.domain.creative import CreativeConcept
from api.domain.enums import ProductionMode
from api.domain.outputs import ShortSegment
from api.media.models import MediaExpectations, OverlaySpec, RenderRequest
from api.storage.artifacts import ArtifactKind

#: All pipeline activities a Temporal worker must register (Phase 10).
PIPELINE_ACTIVITIES = [
    "resolve_creative_direction",
    "generate_music_strategy",
    "generate_music",
    "validate_music",
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
async def generate_music(production_id: str) -> PipelineStageResult:
    """Generate the instrumental source audio and persist it as artifacts."""
    services = get_activity_services()
    config = await asyncio.to_thread(services.get_production_config, production_id)
    genre, mood = await _genre_mood(services, production_id)
    audio = await services.agent_runtime.run(
        "music_generation",
        MusicGenerationRequest(
            prompt=f"instrumental {genre} track, {mood}",
            genre=genre,
            duration_seconds=max(config.short_form_duration_seconds if config else 45, 30),
            style_hints=[mood],
        ),
    )
    data = audio.audio_bytes
    if not data:
        raise WorkflowError(f"music provider returned no audio for production {production_id!r}")
    await asyncio.to_thread(services.artifact_service.write, production_id, ArtifactKind.AUDIO_SOURCE, data)
    await asyncio.to_thread(services.artifact_service.write, production_id, ArtifactKind.AUDIO_MASTER, data)
    return _result("generate_music", f"wav {len(data)} bytes")


@activity.defn
async def validate_music(production_id: str) -> PipelineStageResult:
    """Probe the master audio and reject a production whose audio is invalid."""
    services = get_activity_services()
    path = services.artifact_service.path_for(production_id, ArtifactKind.AUDIO_MASTER)
    result = await services.media_engine.validate_media(
        path,
        expectations=MediaExpectations(require_audio=True, min_duration=5.0),
    )
    if not result.valid:
        failures = [check.name for check in result.failures]
        raise QualityCheckError(f"music validation failed: {failures}")
    return _result("validate_music", "audio validated")


@activity.defn
async def generate_visual_strategy(production_id: str) -> PipelineStageResult:
    """Run the Visual Strategy Agent and persist the visual blueprint."""
    services = get_activity_services()
    genre, mood = await _genre_mood(services, production_id)
    strategy = await services.agent_runtime.run(
        "visual_strategy",
        VisualStrategyRequest(genre=genre, mood=mood),
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
    """Generate the 16:9 background image and persist it as an artifact."""
    services = get_activity_services()
    genre, mood = await _genre_mood(services, production_id)
    image = await services.agent_runtime.run(
        "visual_generation",
        ImageGenerationRequest(
            prompt=f"{genre} ambient background for a music video",
            aspect_ratio="16:9",
            style_hints=["ambient", genre],
        ),
    )
    data = image.image_bytes
    if not data:
        raise WorkflowError(f"image provider returned no background for production {production_id!r}")
    await asyncio.to_thread(services.artifact_service.write, production_id, ArtifactKind.BACKGROUND, data)
    return _result("generate_background", f"png {len(data)} bytes")


@activity.defn
async def resolve_radio(production_id: str) -> PipelineStageResult:
    """Resolve the radio/visualizer focal image (mock: generated 1:1 PNG)."""
    services = get_activity_services()
    genre, mood = await _genre_mood(services, production_id)
    strategy = await asyncio.to_thread(services.get_visual_strategy, production_id)
    radio_style = (strategy.radio_style if strategy else None) or "glow"
    image = await services.agent_runtime.run(
        "visual_generation",
        ImageGenerationRequest(
            prompt=f"{radio_style} radio visualizer orb, {genre} {mood}",
            aspect_ratio="1:1",
            style_hints=["radio", "neon", radio_style],
        ),
    )
    data = image.image_bytes
    if not data:
        raise WorkflowError(f"image provider returned no radio for production {production_id!r}")
    await asyncio.to_thread(services.artifact_service.write, production_id, ArtifactKind.RADIO, data)
    return _result("resolve_radio", "radio png")


# --- Audio analysis / visualizer ---------------------------------------------


@activity.defn
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
    """Derive per-frame 5-band visualizer data from the audio analysis."""
    services = get_activity_services()
    analysis = AudioAnalysis.model_validate_json(
        await asyncio.to_thread(
            services.artifact_service.read_text, production_id, ArtifactKind.AUDIO_ANALYSIS
        )
    )
    frames: list[list[float]] = []
    for index, timestamp in enumerate(analysis.timestamps):
        energy = analysis.energy_curve[index] if index < len(analysis.energy_curve) else 0.0
        spectral = analysis.spectral_curve[index] if index < len(analysis.spectral_curve) else 0.5
        frames.append(
            [
                round(energy * (1.0 - spectral), 4),
                round(energy * 0.9, 4),
                round(energy * 0.75, 4),
                round(energy * 0.5, 4),
                round(energy * spectral, 4),
            ]
        )
    visualizer = VisualizerData(
        style="bars",
        frames=frames,
        timestamps=[round(float(timestamp), 3) for timestamp in analysis.timestamps],
    )
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.VISUALIZER_DATA,
        visualizer.model_dump_json(),
    )
    return _result("generate_visualizer", f"{len(frames)} frames x {len(visualizer.band_names)} bands")


# --- Rendering ----------------------------------------------------------------


@activity.defn
async def render_master(production_id: str) -> PipelineStageResult:
    """Compose background + radio + audio into the 16:9 master render."""
    services = get_activity_services()
    production = await asyncio.to_thread(services.get_production, production_id)
    config = await asyncio.to_thread(services.get_production_config, production_id)
    request = RenderRequest(
        background=services.artifact_service.path_for(production_id, ArtifactKind.BACKGROUND),
        audio=services.artifact_service.path_for(production_id, ArtifactKind.AUDIO_MASTER),
        overlays=[
            OverlaySpec(
                path=services.artifact_service.path_for(production_id, ArtifactKind.RADIO),
                x=720,
                y=300,
                width=480,
                height=480,
                opacity=0.85,
            )
        ],
        branding_text=production.branding_text,
        branding_size=config.branding.font_size if config else 48,
        output_path=services.artifact_service.path_for(production_id, ArtifactKind.MASTER_VIDEO),
    )
    output = await services.media_engine.render_master(request)
    return _result("render_master", f"master {output.name}")


@activity.defn
async def validate_master(production_id: str) -> PipelineStageResult:
    """Probe the master render against the master profile expectations."""
    services = get_activity_services()
    path = services.artifact_service.path_for(production_id, ArtifactKind.MASTER_VIDEO)
    result = await services.media_engine.validate_media(
        path,
        expectations=MediaExpectations(
            require_video=True,
            width=1920,
            height=1080,
            fps=30,
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


@activity.defn
async def render_short(production_id: str) -> PipelineStageResult:
    """Trim the selected segment into the 9:16 short render."""
    services = get_activity_services()
    segment = ShortSegment.model_validate_json(
        await asyncio.to_thread(
            services.artifact_service.read_text, production_id, ArtifactKind.SHORT_SEGMENT
        )
    )
    request = RenderRequest(
        background=services.artifact_service.path_for(production_id, ArtifactKind.BACKGROUND),
        audio=services.artifact_service.path_for(production_id, ArtifactKind.AUDIO_MASTER),
        overlays=[
            OverlaySpec(
                path=services.artifact_service.path_for(production_id, ArtifactKind.RADIO),
                x=270,
                y=696,
                width=540,
                height=540,
                opacity=0.85,
            )
        ],
        output_path=services.artifact_service.path_for(production_id, ArtifactKind.SHORT_VIDEO),
        segment=segment,
    )
    output = await services.media_engine.render_short(request)
    return _result("render_short", f"short {output.name}")


@activity.defn
async def validate_short(production_id: str) -> PipelineStageResult:
    """Probe the short render against the short profile expectations."""
    services = get_activity_services()
    path = services.artifact_service.path_for(production_id, ArtifactKind.SHORT_VIDEO)
    result = await services.media_engine.validate_media(
        path,
        expectations=MediaExpectations(
            require_video=True,
            width=1080,
            height=1920,
            fps=30,
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
    """Generate platform metadata for master and short and persist it."""
    services = get_activity_services()
    production = await asyncio.to_thread(services.get_production, production_id)
    genre, mood = await _genre_mood(services, production_id)
    package = await services.agent_runtime.run(
        "metadata",
        MetadataRequest(
            genre=genre,
            mood=mood,
            branding=production.branding_text,
        ),
    )
    await asyncio.to_thread(
        services.artifact_service.write_text,
        production_id,
        ArtifactKind.METADATA,
        package.model_dump_json(indent=2),
    )
    return _result("generate_metadata", package.master.title)


@activity.defn
async def run_qc(production_id: str) -> PipelineStageResult:
    """Run the Quality Control Agent over the produced artifacts (MAD-001 §33)."""
    services = get_activity_services()
    genre, mood = await _genre_mood(services, production_id)
    checks = await _qc_technical_checks(services, production_id)
    decision = await services.agent_runtime.run(
        "quality_control",
        QualityControlRequest(
            production_id=production_id,
            technical_checks=checks,
            mandatory_checks=["music.valid", "master.valid", "short.valid"],
            creative_context=f"{genre} {mood} production",
        ),
    )
    report = {
        "production_id": production_id,
        "passed": decision.passed,
        "score": decision.score,
        "issues": decision.issues,
        "warnings": decision.warnings,
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
async def complete_production(production_id: str) -> PipelineStageResult:
    """Drive the production to COMPLETED (idempotent final transition)."""
    services = get_activity_services()
    status = await asyncio.to_thread(services.complete_production, production_id)
    return _result("complete_production", status.value)


# --- helpers ------------------------------------------------------------------


async def _qc_technical_checks(services, production_id: str) -> list[TechnicalCheck]:
    """Deterministic technical checks fed to the QC Agent (MAD-001 §33)."""
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
        checks.append(TechnicalCheck(name=f"{kind.value}.exists", passed=present, detail=kind.value))

    media_checks = (
        (ArtifactKind.AUDIO_MASTER, MediaExpectations(require_audio=True, min_duration=5.0), "music.valid"),
        (
            ArtifactKind.MASTER_VIDEO,
            MediaExpectations(require_video=True, width=1920, height=1080, fps=30),
            "master.valid",
        ),
        (
            ArtifactKind.SHORT_VIDEO,
            MediaExpectations(require_video=True, width=1080, height=1920, fps=30),
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


def _read_json(services, production_id: str, kind: ArtifactKind) -> object:
    if not services.artifact_service.exists(production_id, kind):
        return None
    try:
        return json.loads(services.artifact_service.read_text(production_id, kind))
    except (ValueError, OSError):
        return None
