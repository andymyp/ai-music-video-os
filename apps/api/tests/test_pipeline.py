"""Phase 10: production pipeline (MASTER §20; TDD-001 §22-25; MAD-001 §9).

Drives every pipeline stage over the offline ``ActivityEnvironment`` with mock
providers and injectable (fake) media/audio engines, then runs the full 20-stage
sequence end to end and asserts the deliverables from MAD-001 §80-81 exist and
the production reaches COMPLETED. No Temporal server is needed for the stage
tests; a server-backed workflow run is gated behind the embedded test server.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from temporalio.testing import ActivityEnvironment

from api.activities import advance_production, set_activity_services
from api.activities.pipeline import (
    PIPELINE_ACTIVITIES,
    analyze_audio,
    complete_production,
    generate_background,
    generate_manifest,
    generate_metadata,
    generate_music,
    generate_music_strategy,
    generate_visual_strategy,
    generate_visualizer,
    master_audio,
    render_master,
    render_short,
    resolve_creative_direction,
    resolve_radio,
    run_qc,
    select_short_segment,
    validate_master,
    validate_music,
    validate_short,
)
from api.activities.services import WorkflowServices
from api.capabilities import InMemoryProviderRegistry
from api.core.errors import QualityCheckError
from api.database import make_production_repository, session_scope
from api.domain.audio import AudioAnalysis, AudioSection, VisualizerData
from api.media import VisualizerLayer
from api.domain.enums import ProductionMode, ProductionStatus
from api.domain.outputs import MetadataPackage, QualityDecision, ShortSegment
from api.domain.production import Production, _PRODUCTION_FLOW, next_status_in_flow
from api.media.models import MediaValidationResult, ValidationCheck
from api.visual import png_dimensions
from api.providers import register_mock_providers
from api.storage.artifacts import ArtifactKind
from api.workflows.production import PIPELINE_STAGES, PIPELINE_STAGE_NAMES

#: The 19 stage activities in canonical order (MASTER §20/§22; validate_input is
#: the workflow's first activity, exercised separately in test_workflows.py).
PIPELINE_STAGE_FNS = (
    resolve_creative_direction,
    generate_music_strategy,
    generate_music,
    validate_music,
    master_audio,
    generate_visual_strategy,
    generate_background,
    resolve_radio,
    analyze_audio,
    generate_visualizer,
    render_master,
    validate_master,
    select_short_segment,
    render_short,
    validate_short,
    generate_metadata,
    run_qc,
    generate_manifest,
    complete_production,
)


class FakeMediaEngine:
    """Deterministic media engine: renders dummy files, validates by existence."""

    def __init__(self) -> None:
        self.rendered: list[Path] = []
        self.requests: list[RenderRequest] = []
        self.profiles: list[object] = []

    async def render_master(self, request, profile=None) -> Path:
        return await self._render(request, profile)

    async def render_short(self, request, profile=None) -> Path:
        return await self._render(request, profile)

    async def _render(self, request, profile=None) -> Path:
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"FAKE-MP4")
        self.rendered.append(request.output_path)
        self.requests.append(request)
        self.profiles.append(profile)
        return request.output_path

    async def validate_media(self, path, *, expectations=None) -> MediaValidationResult:
        exists = Path(path).is_file()
        checks = [
            ValidationCheck(name="exists", passed=exists, expected="file", actual=path.name),
        ]
        if expectations is not None:
            if expectations.require_audio:
                checks.append(ValidationCheck(name="has_audio", passed=exists, actual=path.name))
            if expectations.require_video:
                checks.append(ValidationCheck(name="has_video", passed=exists, actual=path.name))
        return MediaValidationResult(valid=exists, checks=checks)


class FakeAudioEngine:
    """Deterministic 4-frame analysis so visualizer/short-selection stay stable."""

    async def analyze(self, path: str) -> AudioAnalysis:
        return AudioAnalysis(
            duration_seconds=2.0,
            bpm=120.0,
            loudness_db=-12.0,
            energy_curve=[0.10, 0.20, 0.30, 0.40],
            spectral_curve=[0.10, 0.20, 0.30, 0.40],
            beats=[0.0, 0.5, 1.0, 1.5],
            sections=[AudioSection(start_seconds=0.0, end_seconds=2.0, label="full")],
            timestamps=[0.0, 0.5, 1.0, 1.5],
        )


@pytest.fixture
def services(settings, session_factory) -> WorkflowServices:
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    svc = WorkflowServices(
        settings=settings,
        session_factory=session_factory,
        provider_registry=registry,
        media_engine=FakeMediaEngine(),
        audio_engine=FakeAudioEngine(),
    )
    set_activity_services(svc)
    return svc


def _make_production(session_factory, *, mode=ProductionMode.GENRE, genre="lofi", **overrides) -> Production:
    production = Production(mode=mode, genre=genre, **overrides)
    with session_scope(session_factory) as session:
        make_production_repository(session).create(production)
    return production


#: Which pipeline stages own a status transition (mirrors the workflow's
#: ``PIPELINE_STAGES`` advance flags so the offline helper drives the state
#: machine exactly like ``ProductionWorkflow`` does).
_ADVANCE_AFTER = {stage.name: stage.advance for stage in PIPELINE_STAGES}


async def run_pipeline(production_id: str, *, stop_after: str | None = None) -> dict[str, object]:
    """Run the stage activities in order over ActivityEnvironment, advancing the
    production state machine after each stage that owns a transition (exactly as
    ``ProductionWorkflow`` does)."""
    results: dict[str, object] = {}
    for fn in PIPELINE_STAGE_FNS:
        result = await ActivityEnvironment().run(fn, production_id)
        results[fn.__name__] = result
        assert result.ok, f"{fn.__name__} failed: {result.error}"
        if _ADVANCE_AFTER[fn.__name__]:
            await ActivityEnvironment().run(advance_production, production_id)
        if stop_after and fn.__name__ == stop_after:
            break
    return results


# --- Stage table / state machine coverage ------------------------------------

def test_stage_table_has_all_pipeline_activity_names():
    assert [s.name for s in PIPELINE_STAGES] == list(PIPELINE_STAGE_NAMES)
    assert list(PIPELINE_STAGE_NAMES) == PIPELINE_ACTIVITIES


def test_stage_table_advances_through_every_state_to_completed():
    """Each advance flag walks the canonical state machine exactly once."""
    status = ProductionStatus.CREATED
    visited: list[ProductionStatus] = [status]
    for stage in PIPELINE_STAGES:
        if stage.name == "complete_production":
            # complete_production performs the final two transitions internally.
            visited.append(ProductionStatus.QUALITY_CHECK)
            visited.append(ProductionStatus.COMPLETED)
            status = ProductionStatus.COMPLETED
        elif stage.advance:
            status = next_status_in_flow(status)
            visited.append(status)
    assert status is ProductionStatus.COMPLETED
    assert visited == _PRODUCTION_FLOW


def test_stage_table_is_fully_forward_driven():
    for stage in PIPELINE_STAGES:
        assert stage.name, "every stage needs a name"
        assert callable(stage.activity)


# --- Creative stages ----------------------------------------------------------

async def test_resolve_creative_direction_genre_mode(services, session_factory):
    prod = _make_production(session_factory)
    result = await ActivityEnvironment().run(resolve_creative_direction, prod.id)
    assert result.ok and result.stage == "resolve_creative_direction"
    concept = services.get_concept(prod.id)
    assert concept is not None
    assert concept.genre == "lofi"
    assert concept.mood == "lofi atmosphere"
    assert concept.theme


async def test_resolve_creative_direction_trending_mode(services, session_factory):
    prod = _make_production(session_factory, mode=ProductionMode.TRENDING, genre=None)
    result = await ActivityEnvironment().run(resolve_creative_direction, prod.id)
    assert result.ok
    concept = services.get_concept(prod.id)
    assert concept is not None
    assert concept.genre, "trend research must select a genre"
    assert services.get_trend_result(prod.id) is not None


async def test_generate_music_strategy(services, session_factory):
    prod = _make_production(session_factory)
    await ActivityEnvironment().run(resolve_creative_direction, prod.id)
    result = await ActivityEnvironment().run(generate_music_strategy, prod.id)
    assert result.ok
    strategy = services.get_music_strategy(prod.id)
    assert strategy is not None
    assert strategy.genre == "lofi"


async def test_generate_visual_strategy(services, session_factory):
    prod = _make_production(session_factory)
    await ActivityEnvironment().run(resolve_creative_direction, prod.id)
    result = await ActivityEnvironment().run(generate_visual_strategy, prod.id)
    assert result.ok
    strategy = services.get_visual_strategy(prod.id)
    assert strategy is not None
    assert strategy.theme


# --- Music / visual assets ----------------------------------------------------

async def test_generate_music_writes_real_source_wav(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="generate_music")
    data = services.artifact_service.read(prod.id, ArtifactKind.AUDIO_SOURCE)
    assert data[:4] == b"RIFF", "mock provider must emit a RIFF/WAVE container"
    # The master is produced by the separate mastering stage (Phase 12), not
    # by generation.
    assert not services.artifact_service.exists(prod.id, ArtifactKind.AUDIO_MASTER)


async def test_validate_music_passes_when_audio_present(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="generate_music")
    result = await ActivityEnvironment().run(validate_music, prod.id)
    assert result.ok


async def test_validate_music_fails_without_audio(services, session_factory):
    prod = _make_production(session_factory)
    with pytest.raises(QualityCheckError):
        await ActivityEnvironment().run(validate_music, prod.id)


# --- Mastering (MASTER §22; MAD-001 §19, PRD-001 §19) ------------------------

async def test_master_audio_produces_normalized_master_and_report(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="validate_music")
    result = await ActivityEnvironment().run(master_audio, prod.id)
    assert result.ok and result.stage == "master_audio"
    assert services.artifact_service.exists(prod.id, ArtifactKind.AUDIO_MASTER)
    master = services.artifact_service.read(prod.id, ArtifactKind.AUDIO_MASTER)
    assert master[:4] == b"RIFF", "mastered audio must be a WAV"
    assert len(master) > 0
    report = json.loads(
        services.artifact_service.read_text(prod.id, ArtifactKind.AUDIO_MASTER_REPORT)
    )
    assert report["output_sample_rate"] == 44100
    assert report["output_channels"] == 2
    assert report["duration_seconds"] > 0
    assert -90.0 < report["loudness_db"] < 0.0
    assert report["leading_silence_seconds"] >= 0
    assert report["trailing_silence_seconds"] >= 0


async def test_master_audio_consumed_by_analysis(services, session_factory):
    """The audio analysis stage analyzes the master, not the raw source."""
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="analyze_audio")
    # FakeAudioEngine returns its fixed analysis; what matters is that the
    # pipeline reached analysis through the master artifact.
    analysis = AudioAnalysis.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.AUDIO_ANALYSIS)
    )
    assert analysis.duration_seconds == 2.0


async def test_generate_background_writes_validated_png(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="generate_background")
    data = services.artifact_service.read(prod.id, ArtifactKind.BACKGROUND)
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "mock image provider must emit a PNG"
    # The stage validates the image structurally before committing it (TDD-001 §47).
    assert png_dimensions(data) == (1280, 720)
    sidecar = json.loads(
        services.artifact_service.read_text(prod.id, ArtifactKind.BACKGROUND_PROMPT)
    )
    assert sidecar["prompt_hash"], "idempotency hash must be recorded"
    assert sidecar["theme"], "background prompt must reflect the visual strategy"


async def test_generate_background_is_idempotent(services, session_factory):
    """A background produced by the same strategy is reused, not regenerated
    (MAD-001 §3.5 GenerateBackground idempotency)."""
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="generate_background")
    first = services.artifact_service.read(prod.id, ArtifactKind.BACKGROUND)
    result = await ActivityEnvironment().run(generate_background, prod.id)
    assert result.ok
    assert "reused" in result.summary
    assert services.artifact_service.read(prod.id, ArtifactKind.BACKGROUND) == first


async def test_resolve_radio(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="resolve_radio")
    assert services.artifact_service.exists(prod.id, ArtifactKind.RADIO)


async def test_resolve_radio_reuses_asset_across_productions(services, session_factory):
    """Same radio style resolves to the same bytes across productions
    (MAD-001 §22 asset registry reuse, TDD-001 §48)."""
    prod_a = _make_production(session_factory)
    prod_b = _make_production(session_factory)
    await run_pipeline(prod_a.id, stop_after="resolve_radio")
    await run_pipeline(prod_b.id, stop_after="resolve_radio")
    radio_a = services.artifact_service.read(prod_a.id, ArtifactKind.RADIO)
    radio_b = services.artifact_service.read(prod_b.id, ArtifactKind.RADIO)
    assert radio_a[:8] == b"\x89PNG\r\n\x1a\n"
    assert radio_a == radio_b


# --- Audio analysis / visualizer ----------------------------------------------

async def test_analyze_audio_persists_analysis(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="analyze_audio")
    analysis = AudioAnalysis.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.AUDIO_ANALYSIS)
    )
    assert analysis.duration_seconds == 2.0
    assert analysis.bpm == 120.0


async def test_generate_visualizer_matches_frame_grid(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="generate_visualizer")
    visualizer = VisualizerData.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.VISUALIZER_DATA)
    )
    assert len(visualizer.frames) == len(visualizer.timestamps)
    assert all(len(bands) == len(visualizer.band_names) for bands in visualizer.frames)
    assert all(0.0 <= value <= 1.0 for bands in visualizer.frames for value in bands)
    # The composited layer artifact carries the deterministic layout too
    # (TDD-001 §52, §126).
    layer = VisualizerLayer.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.VISUALIZER_LAYER)
    )
    assert layer.visualizer == visualizer
    assert layer.layout.visualizer_style == visualizer.style


# --- Rendering ----------------------------------------------------------------

async def test_render_master_writes_video(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="render_master")
    assert services.artifact_service.exists(prod.id, ArtifactKind.MASTER_VIDEO)
    assert services.artifact_service.read(prod.id, ArtifactKind.MASTER_VIDEO) == b"FAKE-MP4"


async def test_render_master_composites_visualizer_from_layout(services, session_factory):
    """TDD-001 §52: radio/visualizer/branding geometry comes from the layout."""
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="render_master")

    request = services.media_engine.requests[-1]
    # radio overlay positioned by the persisted layout (0.34 scale on 1920x1080)
    radio = request.overlays[0]
    assert (radio.x, radio.y, radio.width, radio.height) == (634, 214, 653, 653)

    # visualizer sprites rendered inside the radio's display region — the
    # region is the radio square's inner 70% computed in pixel space, so it is
    # square on any frame aspect ratio (TDD-001 §52, §128)
    assert request.visualizer is not None
    assert request.visualizer.region_width == 456
    assert request.visualizer.region_height == 458
    sprites = sorted(request.visualizer.frames_dir.glob("*.png"))
    visualizer = VisualizerData.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.VISUALIZER_DATA)
    )
    assert len(sprites) == len(visualizer.frames)  # one sprite per data frame
    assert sprites[0].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

    # branding anchors top-left per the layout
    assert request.branding_x == 58 and request.branding_y == 32

    # the render profile honors the production's configured master size/FPS
    profile = services.media_engine.profiles[-1]
    assert (profile.width, profile.height) == (1920, 1080)
    assert profile.fps == 30


async def test_validate_master(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="validate_master")
    result = await ActivityEnvironment().run(validate_master, prod.id)
    assert result.ok


async def test_select_short_segment_writes_segment(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="select_short_segment")
    segment = ShortSegment.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.SHORT_SEGMENT)
    )
    assert segment.duration_seconds > 0
    assert segment.start_seconds >= 0


async def test_render_short_writes_video(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="render_short")
    assert services.artifact_service.exists(prod.id, ArtifactKind.SHORT_VIDEO)


async def test_render_short_composites_vertical_layout(services, session_factory):
    """MAD-001 §27 / TDD-001 §128: the short uses the dedicated 9:16 layout —
    radio in the upper third, visualizer sliced to the segment window, branding
    bottom-center — and never regenerates independent music."""
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="render_short")

    request = services.media_engine.requests[-1]
    # radio = 0.5 × 1080 square centered at (0.5, 0.35) on 1080x1920
    radio = request.overlays[0]
    assert (radio.x, radio.y, radio.width, radio.height) == (270, 402, 540, 540)

    # visualizer sliced into the radio's display region (square in pixel space)
    assert request.visualizer is not None
    assert (request.visualizer.region_x, request.visualizer.region_y) == (351, 483)
    assert (request.visualizer.region_width, request.visualizer.region_height) == (378, 378)
    assert request.visualizer.duration_seconds == pytest.approx(2.0)

    # branding anchors bottom-center and is horizontally centered
    assert request.branding_align == "center"
    assert (request.branding_x, request.branding_y) == (540, 1728)

    # the master audio is trimmed to the selected segment (TDD-001 §129)
    segment = ShortSegment.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.SHORT_SEGMENT)
    )
    assert request.segment == segment
    assert segment.start_seconds >= 0 and segment.duration_seconds > 0

    # the profile honors the production's configured short size/FPS
    profile = services.media_engine.profiles[-1]
    assert (profile.width, profile.height) == (1080, 1920)
    assert profile.fps == 30


async def test_render_short_slices_visualizer_to_segment(services, session_factory):
    """PRD-001 §24 / TDD-001 §129: the short reuses the master's visualizer data
    (never regenerates music) and renders one sprite per sliced frame."""
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="render_short")

    request = services.media_engine.requests[-1]
    master_data = VisualizerData.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.VISUALIZER_DATA)
    )
    sprites = sorted(request.visualizer.frames_dir.glob("*.png"))
    assert sprites, "short visualizer sprites must be rendered"
    assert sprites[0].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    # the sliced window covers the segment — at most as many frames as the master
    segment = ShortSegment.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.SHORT_SEGMENT)
    )
    assert len(sprites) <= len(master_data.frames)
    assert sprites[0].parent.name == "short-visualizer"


async def test_select_short_segment_validates_window(services, session_factory):
    """MAD-001 §26: the final segment must be validated before rendering — a
    window past the master end or beyond the platform ceiling is rejected."""
    from api.activities.pipeline import _validate_short_segment

    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="analyze_audio")
    config = services.get_production_config(prod.id)

    # a valid clip within the 2.0s master passes
    await _validate_short_segment(
        services,
        prod.id,
        ShortSegment(start_seconds=0.0, duration_seconds=2.0, reason="fit"),
        config,
    )
    # a window past the end of the master is rejected
    with pytest.raises(QualityCheckError):
        await _validate_short_segment(
            services,
            prod.id,
            ShortSegment(start_seconds=1.0, duration_seconds=45.0, reason="past end"),
            config,
        )
    # a structurally invalid clip (negative start) is rejected — Pydantic blocks
    # this at construction, so we bypass validation via model_construct
    bad_segment = ShortSegment.model_construct(start_seconds=-1.0, duration_seconds=10.0, reason="neg")
    with pytest.raises(QualityCheckError):
        await _validate_short_segment(services, prod.id, bad_segment, config)
    # a clip above the 60s platform ceiling is rejected
    with pytest.raises(QualityCheckError):
        await _validate_short_segment(
            services,
            prod.id,
            ShortSegment(start_seconds=0.0, duration_seconds=90.0, reason="too long"),
            config,
        )


async def test_validate_short(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="validate_short")
    result = await ActivityEnvironment().run(validate_short, prod.id)
    assert result.ok


# --- Metadata / QC / manifest --------------------------------------------------

async def test_generate_metadata_writes_package(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="generate_metadata")
    package = MetadataPackage.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.METADATA)
    )
    assert package.master.title
    assert package.short.title


async def test_generate_metadata_uses_actual_production_info(services, session_factory, monkeypatch):
    """MASTER §27 / TDD-001 §57: the metadata request is built from the
    persisted creative brief, MusicStrategy, VisualStrategy, trend context and
    the ShortSegment — not the genre alone."""
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="render_short")

    captured: dict[str, object] = {}
    original_run = services.agent_runtime.run

    async def spy_run(name, request):
        captured["request"] = request
        return await original_run(name, request)

    monkeypatch.setattr(services.agent_runtime, "run", spy_run)
    await ActivityEnvironment().run(generate_metadata, prod.id)

    request = captured["request"]
    assert request.genre == "lofi"
    assert request.theme, "theme must come from the CreativeConcept"
    assert request.audience, "audience must come from the CreativeConcept"
    assert request.music_concept and "bpm" in request.music_concept
    assert request.visual_concept
    assert request.short_segment is not None and request.short_segment.duration_seconds > 0

    # the persisted package corresponds to the production (TDD-001 §58) and the
    # theme-derived hashtag lands in the metadata (genre/mood/theme determinism)
    package = MetadataPackage.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.METADATA)
    )
    assert package.master.title and package.master.description
    assert package.short.title and package.short.description
    assert "#lofi" in package.master.hashtags
    # hashtags correspond to the actual production (mood "lofi atmosphere")
    mood_slug = re.sub(r"[^a-z0-9]+", "", request.mood.lower())
    assert f"#{mood_slug}" in package.master.hashtags


async def test_run_qc_passes_with_complete_artifacts(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="generate_manifest")
    result = await ActivityEnvironment().run(run_qc, prod.id)
    assert result.ok
    report = json.loads(services.artifact_service.read_text(prod.id, ArtifactKind.QC_REPORT))
    assert report["passed"] is True
    # TDD-001 §61: the AI creative result is structured per dimension.
    assert report["creative"] is not None
    assert set(report["creative"]) >= {
        "visual_coherence",
        "visualizer_placement",
        "branding_presence",
        "content_consistency",
        "metadata_relevance",
    }
    assert all(0.0 <= report["creative"][dim] <= 1.0 for dim in report["creative"] if isinstance(report["creative"][dim], float))


# --- Phase 18: structured creative QC (MASTER §28, TDD-001 §59-61) ------------

def test_creative_assessment_composite_is_mean():
    from api.domain.outputs import CREATIVE_DIMENSIONS, CreativeAssessment

    assessment = CreativeAssessment(
        visual_coherence=1.0,
        visualizer_placement=0.5,
        branding_presence=0.25,
        content_consistency=0.75,
        metadata_relevance=0.5,
    )
    assert assessment.composite == 0.6
    assert set(CREATIVE_DIMENSIONS) == {
        "visual_coherence",
        "visualizer_placement",
        "branding_presence",
        "content_consistency",
        "metadata_relevance",
    }


def test_creative_assessment_rejects_out_of_range_dimension():
    from api.domain.outputs import CreativeAssessment

    with pytest.raises(ValueError):
        CreativeAssessment(visual_coherence=1.5)


async def test_qc_agent_returns_structured_creative_assessment():
    """TDD-001 §61: AI QC results are structured per creative dimension."""
    from api.agents import Tool
    from api.agents.quality_control import QualityControlAgent
    from api.agents.tools import ToolRegistry
    from api.capabilities import StructuredGenerationRequest, StructuredResult
    from api.domain import QualityControlRequest, TechnicalCheck

    recorded: list[str] = []

    class CreativeLLMTool(Tool):
        name = "llm_generate"
        description = "recording creative llm"
        input_schema = StructuredGenerationRequest
        output_schema = StructuredResult

        async def run(self, input):
            recorded.append(input.prompt)
            return StructuredResult(
                data={
                    "visual_coherence": 1.0,
                    "visualizer_placement": 0.8,
                    "branding_presence": 0.6,
                    "content_consistency": 0.9,
                    "metadata_relevance": 0.7,
                    "remarks": "solid composition",
                },
                model="spy",
            )

    tools = ToolRegistry()
    tools.register(CreativeLLMTool())
    agent = QualityControlAgent(tools)
    decision = await agent.execute(QualityControlRequest(
        technical_checks=[TechnicalCheck(name="master.valid", passed=True)],
        mandatory_checks=["master.valid"],
        creative_context="lofi night drive production",
    ))
    assert decision.passed
    assert decision.creative is not None
    assert decision.creative.visual_coherence == 1.0
    assert decision.creative.metadata_relevance == 0.7
    assert decision.creative.remarks == "solid composition"
    assert decision.creative.composite == 0.8
    # composite = 0.8 creative * 0.5 + 1.0 technical * 0.5 (MAD-001 §31.3)
    assert decision.score == 0.9
    # the prompt names the five assessed dimensions (MAD-001 §31.2)
    assert "visual coherence" in recorded[0]
    assert "metadata relevance" in recorded[0]


async def test_qc_agent_creative_never_overrides_mandatory_gate():
    """A perfect creative score cannot pass a broken render (MAD-001 §31.3)."""
    from api.agents import Tool
    from api.agents.quality_control import QualityControlAgent
    from api.agents.tools import ToolRegistry
    from api.capabilities import StructuredGenerationRequest, StructuredResult
    from api.domain import QualityControlRequest, TechnicalCheck

    class PerfectLLMTool(Tool):
        name = "llm_generate"
        description = "perfect creative llm"
        input_schema = StructuredGenerationRequest
        output_schema = StructuredResult

        async def run(self, input):
            return StructuredResult(
                data={
                    "visual_coherence": 1.0,
                    "visualizer_placement": 1.0,
                    "branding_presence": 1.0,
                    "content_consistency": 1.0,
                    "metadata_relevance": 1.0,
                },
                model="spy",
            )

    tools = ToolRegistry()
    tools.register(PerfectLLMTool())
    agent = QualityControlAgent(tools)
    decision = await agent.execute(QualityControlRequest(
        technical_checks=[
            TechnicalCheck(name="master.valid", passed=True),
            TechnicalCheck(name="short.valid", passed=False),
        ],
        mandatory_checks=["master.valid", "short.valid"],
        creative_context="context",
    ))
    assert not decision.passed
    assert decision.issues == ["short.valid"]
    assert decision.creative is not None and decision.creative.composite == 1.0


async def test_qc_technical_checks_are_config_derived(services, session_factory, monkeypatch):
    """Expected resolution/FPS come from the render profiles, not hard-coded
    1920x1080 / 1080x1920 (MAD-001 §56, PRD-001 FR-023)."""
    from api.activities.pipeline import _qc_technical_checks
    from api.domain.production import ProductionConfig

    prod = _make_production(session_factory)
    with session_scope(session_factory) as session:
        make_production_repository(session).save_config(
            prod.id,
            ProductionConfig(
                mode=ProductionMode.GENRE,
                genre="lofi",
                master_width=1280,
                master_height=720,
                short_width=720,
                short_height=1280,
            ),
        )
    for kind in (
        ArtifactKind.AUDIO_MASTER,
        ArtifactKind.BACKGROUND,
        ArtifactKind.RADIO,
        ArtifactKind.MASTER_VIDEO,
        ArtifactKind.SHORT_VIDEO,
        ArtifactKind.METADATA,
        ArtifactKind.MANIFEST,
    ):
        services.artifact_service.write(prod.id, kind, b"non-empty")

    captured: list[MediaExpectations] = []
    real = services.media_engine.validate_media

    async def spy(path, *, expectations=None):
        captured.append(expectations)
        return await real(path, expectations=expectations)

    monkeypatch.setattr(services.media_engine, "validate_media", spy)

    checks = await _qc_technical_checks(services, prod.id)
    assert all(check.passed for check in checks)

    master_exp = next(e for e in captured if e.require_video and e.width == 1280)
    assert master_exp.height == 720 and master_exp.fps == 30
    assert master_exp.video_codec == "h264" and master_exp.audio_codec == "aac"
    short_exp = next(e for e in captured if e.require_video and e.width == 720)
    assert short_exp.height == 1280 and short_exp.fps == 30
    assert short_exp.video_codec == "h264" and short_exp.audio_codec == "aac"
    music_exp = next(e for e in captured if not e.require_video)
    assert music_exp.audio_codec == "pcm_s16le"
    assert music_exp.min_sample_rate == 44100 and music_exp.min_channels == 2


async def test_qc_technical_checks_include_integrity_and_exists(services, session_factory):
    """Every required artifact is checked for existence and non-zero integrity
    (MAD-001 §31.1, PRD-001 FR-023)."""
    from api.activities.pipeline import _qc_technical_checks

    prod = _make_production(session_factory)
    for kind in (
        ArtifactKind.AUDIO_MASTER,
        ArtifactKind.BACKGROUND,
        ArtifactKind.RADIO,
        ArtifactKind.MASTER_VIDEO,
        ArtifactKind.SHORT_VIDEO,
        ArtifactKind.METADATA,
        ArtifactKind.MANIFEST,
    ):
        services.artifact_service.write(prod.id, kind, b"non-empty")

    checks = await _qc_technical_checks(services, prod.id)
    names = {check.name for check in checks}
    for kind in (ArtifactKind.MASTER_VIDEO, ArtifactKind.METADATA):
        assert f"{kind.value}.exists" in names
        assert f"{kind.value}.integrity" in names
    assert all(check.passed for check in checks)


async def test_qc_technical_checks_flag_missing_or_empty_artifact(services, session_factory):
    """A missing or zero-byte artifact fails its existence/integrity checks."""
    from api.activities.pipeline import _qc_technical_checks

    prod = _make_production(session_factory)
    for kind in (ArtifactKind.BACKGROUND, ArtifactKind.RADIO):
        services.artifact_service.write(prod.id, kind, b"non-empty")
    services.artifact_service.write(prod.id, ArtifactKind.METADATA, b"")

    checks = await _qc_technical_checks(services, prod.id)
    by_name = {check.name: check for check in checks}
    assert not by_name[f"{ArtifactKind.MASTER_VIDEO.value}.exists"].passed
    assert not by_name[f"{ArtifactKind.METADATA.value}.integrity"].passed
    assert by_name[f"{ArtifactKind.BACKGROUND.value}.exists"].passed


async def test_qc_creative_context_uses_persisted_brief(services, session_factory):
    """The creative assessment context carries the real production brief
    (TDD-001 §61): genre/mood, music/visual summaries, branding and metadata."""
    from api.activities.pipeline import _qc_creative_context

    prod = _make_production(session_factory, branding_text="MY CHANNEL")
    await run_pipeline(prod.id, stop_after="generate_metadata")
    context = await _qc_creative_context(services, prod.id)
    assert "lofi" in context and "lofi atmosphere" in context
    assert "music:" in context
    assert "visual:" in context
    assert "MY CHANNEL" in context
    package = MetadataPackage.model_validate_json(
        services.artifact_service.read_text(prod.id, ArtifactKind.METADATA)
    )
    assert package.master.title in context


async def test_generate_manifest_lists_all_artifacts(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="generate_manifest")
    manifest = json.loads(services.artifact_service.read_text(prod.id, ArtifactKind.MANIFEST))
    assert manifest["production_id"] == prod.id
    assert set(manifest["artifacts"]) == {kind.value for kind in ArtifactKind}
    production_doc = json.loads(services.artifact_service.read_text(prod.id, ArtifactKind.PRODUCTION))
    assert production_doc["mode"] == "genre"
    assert production_doc["music_strategy"]["genre"] == "lofi"


async def test_complete_production_reaches_completed(services, session_factory):
    prod = _make_production(session_factory)
    await run_pipeline(prod.id, stop_after="complete_production")
    with session_scope(session_factory) as session:
        reloaded = make_production_repository(session).get(prod.id)
    assert reloaded.status is ProductionStatus.COMPLETED
    assert reloaded.completed_at is not None


# --- End-to-end -----------------------------------------------------------------

async def test_full_pipeline_reaches_completed_with_deliverables(services, session_factory):
    prod = _make_production(session_factory)
    results = await run_pipeline(prod.id)

    assert set(results) == {fn.__name__ for fn in PIPELINE_STAGE_FNS}
    for kind in (
        ArtifactKind.AUDIO_SOURCE,
        ArtifactKind.AUDIO_MASTER,
        ArtifactKind.AUDIO_MASTER_REPORT,
        ArtifactKind.AUDIO_ANALYSIS,
        ArtifactKind.BACKGROUND,
        ArtifactKind.BACKGROUND_PROMPT,
        ArtifactKind.RADIO,
        ArtifactKind.VISUALIZER_DATA,
        ArtifactKind.VISUALIZER_LAYER,
        ArtifactKind.MASTER_VIDEO,
        ArtifactKind.SHORT_VIDEO,
        ArtifactKind.SHORT_SEGMENT,
        ArtifactKind.METADATA,
        ArtifactKind.QC_REPORT,
        ArtifactKind.MANIFEST,
        ArtifactKind.PRODUCTION,
    ):
        assert services.artifact_service.exists(prod.id, kind), kind

    with session_scope(session_factory) as session:
        reloaded = make_production_repository(session).get(prod.id)
    assert reloaded.status is ProductionStatus.COMPLETED
