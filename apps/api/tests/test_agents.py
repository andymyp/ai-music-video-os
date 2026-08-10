"""Phase 08: agent runtime (TDD-001 §38-41, §93; MAD-001 §33-34, §67-69; PRD-001 §60-70).

Covers the typed agent contract, the strict tool registry (the only side-effect
surface), the runtime facade, each of the nine agents over deterministic mock
providers, provider failover, determinism, and the no-fs/no-shell/no-db/no-secret
guardrails via a source scan.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from api.agents import (
    Agent,
    AudioAnalysisTool,
    AgentRuntime,
    CapabilityStatusTool,
    ImageGenerationTool,
    LLMGenerationTool,
    MusicGenerationTool,
    Tool,
    ToolRegistry,
    TrendSearchTool,
    build_agent_runtime,
)
from api.capabilities import (
    Capability,
    InMemoryProviderRegistry,
    MusicGenerationRequest,
    ProviderConfig,
)
from api.core.errors import ConfigurationError, ProviderError, ToolError
from api.domain import (
    AudioAnalysis,
    MusicStrategyRequest,
    OrchestratorRequest,
    QualityControlRequest,
    ShortSelectionRequest,
    TrendResearchRequest,
    VisualStrategyRequest,
)
from api.domain.enums import ProductionMode, ProductionStatus
from api.providers import register_mock_providers

FFMPEG_PRESENT = shutil.which("ffmpeg") is not None

AGENT_NAMES = [
    "orchestrator",
    "trend_research",
    "music_strategy",
    "music_generation",
    "visual_strategy",
    "visual_generation",
    "short_selection",
    "metadata",
    "quality_control",
]
TOOL_NAMES = [
    "audio_analyze",
    "capability_status",
    "image_generate",
    "llm_generate",
    "music_generate",
    "trend_search",
]


@pytest.fixture
def runtime() -> AgentRuntime:
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    return build_agent_runtime(registry)


# --- Agent contract (TDD-001 §39) --------------------------------------------

def test_all_agents_conform_to_agent_protocol(runtime):
    for name in AGENT_NAMES:
        agent = runtime.get_agent(name)
        assert isinstance(agent, Agent), name
        assert agent.name == name
        assert agent.version and agent.description


def test_all_tools_conform_to_tool_contract(runtime):
    for name in TOOL_NAMES:
        tool = runtime.tools.get(name)
        assert isinstance(tool, Tool), name
        assert tool.name == name
        assert tool.description
        assert tool.input_schema is not None
        assert tool.output_schema is not None


def test_runtime_exposes_exactly_the_registered_surface(runtime):
    assert set(runtime.agent_names()) == set(AGENT_NAMES)
    assert set(runtime.tool_names()) == set(TOOL_NAMES)


# --- Registry & runtime behaviour --------------------------------------------

def test_tool_registry_register_and_lookup():
    registry = ToolRegistry()
    assert registry.names() == []
    registry.register(TrendSearchTool(InMemoryProviderRegistry()))
    assert registry.available("trend_search")
    assert registry.get("trend_search").name == "trend_search"
    with pytest.raises(ToolError):
        registry.get("nope")
    with pytest.raises(ConfigurationError):
        registry.register(TrendSearchTool(InMemoryProviderRegistry()))  # duplicate


async def test_agent_runtime_register_lookup_and_run(runtime):
    assert runtime.available("metadata")
    assert runtime.get_agent("orchestrator").name == "orchestrator"
    with pytest.raises(ConfigurationError):
        runtime.get_agent("nope")
    decision = await runtime.run("orchestrator", OrchestratorRequest(
        current_status=ProductionStatus.CREATED,
        mode=ProductionMode.GENRE,
        genre="lofi",
    ))
    assert decision.next_agent == "music_strategy"


def test_agent_runtime_rejects_duplicate_registration(runtime):
    from api.agents.orchestrator import OrchestratorAgent

    with pytest.raises(ConfigurationError):
        runtime.register_agent(OrchestratorAgent(runtime.tools))


# --- Tool failover & no-provider handling (PRD-001 §64.5) ---------------------

class FailingLLMProvider:
    async def generate_structured(self, request):
        raise ProviderError("simulated outage")


def _registry_with(extra=None) -> InMemoryProviderRegistry:
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    if extra:
        capability, provider, config = extra
        registry.register(capability, provider, config)
    return registry


async def test_tool_failover_skips_failing_provider():
    registry = _registry_with((
        Capability.LLM,
        FailingLLMProvider(),
        ProviderConfig(provider_id="failing-llm", capability=Capability.LLM, priority=10),
    ))
    tool = LLMGenerationTool(registry)
    from api.capabilities import StructuredGenerationRequest

    result = await tool.run(StructuredGenerationRequest(task="t", prompt="hello"))
    assert result.data  # came from the mock fallback


async def test_tool_raises_when_all_providers_fail():
    from api.capabilities import StructuredGenerationRequest

    registry = InMemoryProviderRegistry()
    registry.register(
        Capability.LLM,
        FailingLLMProvider(),
        ProviderConfig(provider_id="failing", capability=Capability.LLM, priority=10),
    )
    tool = LLMGenerationTool(registry)
    with pytest.raises(ToolError, match="all providers failed"):
        await tool.run(StructuredGenerationRequest(task="t", prompt="hello"))


async def test_tool_raises_when_no_enabled_provider():
    tool = LLMGenerationTool(InMemoryProviderRegistry())
    from api.capabilities import StructuredGenerationRequest

    with pytest.raises(ToolError, match="all providers failed"):
        await tool.run(StructuredGenerationRequest(task="t", prompt="hello"))


# --- Orchestrator Agent (PRD-001 §61) ----------------------------------------

async def test_orchestrator_maps_genre_flow(runtime):
    decision = await runtime.run("orchestrator", OrchestratorRequest(
        current_status=ProductionStatus.GENERATING_MUSIC,
        mode=ProductionMode.GENRE,
    ))
    assert decision.next_agent == "music_generation"
    assert decision.capability == "music"
    assert not decision.regenerate


async def test_orchestrator_trending_mode_selects_trend_research(runtime):
    decision = await runtime.run("orchestrator", OrchestratorRequest(
        current_status=ProductionStatus.CREATED,
        mode=ProductionMode.TRENDING,
    ))
    assert decision.next_agent == "trend_research"
    assert decision.capability == "trend"
    assert decision.creative_direction == "trending"


async def test_orchestrator_media_stages_have_no_agent(runtime):
    for status in (ProductionStatus.VISUAL_READY, ProductionStatus.RENDERING_MASTER,
                   ProductionStatus.SELECTING_SHORT, ProductionStatus.COMPLETED):
        decision = await runtime.run("orchestrator", OrchestratorRequest(
            current_status=status,
            mode=ProductionMode.GENRE,
        ))
        assert decision.next_agent == "", status.value


async def test_orchestrator_honours_regeneration_request(runtime):
    decision = await runtime.run("orchestrator", OrchestratorRequest(
        current_status=ProductionStatus.QUALITY_CHECK,
        mode=ProductionMode.GENRE,
        context={"regenerate": True, "regenerate_agent": "music_generation"},
    ))
    assert decision.regenerate
    assert decision.next_agent == "music_generation"


# --- Trend Research Agent (PRD-001 §62) --------------------------------------

async def test_trend_research_produces_ranked_recommendations(runtime):
    result = await runtime.run("trend_research", TrendResearchRequest(genre_hint="chillhop"))
    assert result.selected_genre == "chillhop"
    assert 0.0 <= result.confidence <= 1.0
    assert result.recommendations
    scores = [r.score for r in result.recommendations]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 100.0 for s in scores)
    assert result.reasoning


async def test_trend_research_is_deterministic(runtime):
    request = TrendResearchRequest(genre_hint="chillhop")
    first = await runtime.run("trend_research", request)
    second = await runtime.run("trend_research", request)
    assert first == second


# --- Music Strategy Agent (PRD-001 §63) --------------------------------------

async def test_music_strategy_is_valid_and_instrumental(runtime):
    strategy = await runtime.run("music_strategy", MusicStrategyRequest(genre="lofi", mood="calm"))
    assert strategy.genre == "lofi"
    assert strategy.vocal_policy == "none"  # PRD-001 §15
    assert strategy.bpm_range[0] < strategy.bpm_range[1]
    assert strategy.duration_target_minutes == 60


async def test_music_strategy_invalid_llm_output_raises():
    class BadLLM:
        async def generate_structured(self, request):
            from api.capabilities import StructuredResult
            return StructuredResult(data={"genre": "x"})  # missing required fields

    registry = InMemoryProviderRegistry()
    registry.register(Capability.LLM, BadLLM(),
                      ProviderConfig(provider_id="bad", capability=Capability.LLM, priority=10))
    runtime = build_agent_runtime(registry)
    with pytest.raises(Exception, match="invalid music strategy"):
        await runtime.run("music_strategy", MusicStrategyRequest(genre="lofi", mood="calm"))


async def test_music_strategy_is_deterministic(runtime):
    request = MusicStrategyRequest(genre="lofi", mood="calm")
    first = await runtime.run("music_strategy", request)
    second = await runtime.run("music_strategy", request)
    assert first == second


# --- Visual Strategy Agent (PRD-001 §65) -------------------------------------

async def test_visual_strategy_is_valid(runtime):
    strategy = await runtime.run("visual_strategy", VisualStrategyRequest(genre="lofi", mood="calm"))
    assert strategy.theme
    assert strategy.radio_style
    assert strategy.visualizer_style == "bars"


# --- Generation Agents (PRD-001 §64, §66) ------------------------------------

async def test_music_generation_returns_audio(runtime):
    audio = await runtime.run("music_generation", MusicGenerationRequest(
        prompt="lofi beat", duration_seconds=30,
    ))
    assert audio.audio_bytes and audio.audio_bytes.startswith(b"RIFF")


async def test_visual_generation_returns_image(runtime):
    from api.capabilities import ImageGenerationRequest

    image = await runtime.run("visual_generation", ImageGenerationRequest(prompt="night sky"))
    assert image.image_bytes and image.image_bytes.startswith(b"\x89PNG")


# --- Short Selection Agent (PRD-001 §67) -------------------------------------

def _stub_analysis() -> AudioAnalysis:
    import numpy as np
    from api.domain.audio import AudioSection

    energy = np.full(200, 0.1)
    energy[40:80] = 0.9  # high-energy window at ~20s
    times = np.arange(200) * 0.5 + 0.25
    return AudioAnalysis(
        duration_seconds=100.0,
        bpm=120.0,
        loudness_db=-12.0,
        energy_curve=[round(float(v), 6) for v in energy],
        spectral_curve=[0.3] * 200,
        beats=[5.0, 5.5],
        sections=[AudioSection(start_seconds=0.0, end_seconds=100.0, label="loud")],
        timestamps=[round(float(t), 3) for t in times],
    )


class StubAudioTool(AudioAnalysisTool):
    def __init__(self, analysis: AudioAnalysis) -> None:
        self._analysis = analysis

    async def run(self, input):
        return self._analysis


async def test_short_selection_picks_highest_energy_window():
    runtime = AgentRuntime()
    from api.agents.short_selection import ShortSelectionAgent
    from api.agents.tools import AudioAnalysisRequest

    runtime.register_tool(StubAudioTool(_stub_analysis()))
    runtime.register_agent(ShortSelectionAgent(runtime.tools))
    segment = await runtime.run("short_selection", ShortSelectionRequest(
        audio_path="stub.wav", target_duration_seconds=20.0,
    ))
    assert abs(segment.start_seconds - 20.0) <= 0.6
    assert abs(segment.duration_seconds - 20.0) <= 0.6
    assert segment.score > 0.9
    assert segment.reason


@pytest.mark.skipif(not FFMPEG_PRESENT, reason="FFmpeg not on PATH")
async def test_short_selection_integration_with_real_analysis(tmp_path, runtime):
    import numpy as np
    from api.providers.mock import _encode_wav

    sr = 22050
    n = int(60 * sr)
    signal = np.zeros(n, dtype=np.float64)
    # loud segment 30-45s at 0.9 amplitude, rest quiet
    loud = np.arange(int(15 * sr))
    tone = 0.9 * np.sin(2 * np.pi * 330.0 * loud / sr)
    signal[int(30 * sr):int(45 * sr)] += tone[: int(15 * sr)]
    samples = (signal * 32767).astype(np.int16).tolist()
    path = tmp_path / "staged.wav"
    path.write_bytes(_encode_wav(samples, sample_rate=sr, channels=1, bits=16))

    segment = await runtime.run("short_selection", ShortSelectionRequest(
        audio_path=str(path), target_duration_seconds=10.0, min_duration_seconds=5.0,
    ))
    assert 27.0 <= segment.start_seconds <= 33.0
    assert abs(segment.duration_seconds - 10.0) <= 1.0


# --- Metadata Agent (PRD-001 §68) --------------------------------------------

async def test_metadata_produces_valid_package(runtime):
    from api.domain import MetadataRequest

    package = await runtime.run("metadata", MetadataRequest(
        genre="lofi", mood="calm", theme="night drive", branding="MY CHANNEL",
    ))
    assert package.master.title and package.master.description
    assert package.short.title and package.short.description
    assert package.master.hashtags == package.short.hashtags == ["#lofi", "#calm"]


async def test_metadata_hashtags_never_empty(runtime):
    from api.domain import MetadataRequest

    package = await runtime.run("metadata", MetadataRequest(genre="lo-fi beats!!", mood=".."))
    assert package.master.hashtags  # sanitized, never an empty list


# --- Quality Control Agent (PRD-001 §69) -------------------------------------

async def test_qc_rejects_when_mandatory_check_fails():
    runtime = AgentRuntime()
    from api.agents.quality_control import QualityControlAgent
    from api.domain import TechnicalCheck

    runtime.register_agent(QualityControlAgent(runtime.tools))
    decision = await runtime.run("quality_control", QualityControlRequest(
        technical_checks=[
            TechnicalCheck(name="resolution", passed=True),
            TechnicalCheck(name="codec", passed=False),
        ],
        mandatory_checks=["codec"],
    ))
    assert not decision.passed
    assert decision.issues == ["codec"]
    assert decision.score < 1.0


async def test_qc_warns_on_non_mandatory_failure():
    runtime = AgentRuntime()
    from api.agents.quality_control import QualityControlAgent
    from api.domain import TechnicalCheck

    runtime.register_agent(QualityControlAgent(runtime.tools))
    decision = await runtime.run("quality_control", QualityControlRequest(
        technical_checks=[TechnicalCheck(name="loudness", passed=False)],
        mandatory_checks=["codec"],
    ))
    assert decision.passed
    assert decision.warnings == ["loudness"]


async def test_qc_passes_clean_technical_report(runtime):
    from api.domain import TechnicalCheck

    decision = await runtime.run("quality_control", QualityControlRequest(
        creative_context="lofi night drive",
        technical_checks=[
            TechnicalCheck(name="resolution", passed=True),
            TechnicalCheck(name="codec", passed=True),
        ],
        mandatory_checks=["resolution", "codec"],
    ))
    assert decision.passed
    assert decision.issues == []


# --- Guardrails: registered tools only (TDD-001 §93) -------------------------

async def test_agent_without_required_tool_raises():
    runtime = AgentRuntime()
    from api.agents.music_strategy import MusicStrategyAgent

    runtime.register_agent(MusicStrategyAgent(runtime.tools))  # no llm_generate registered
    with pytest.raises(ToolError, match="not registered"):
        await runtime.run("music_strategy", MusicStrategyRequest(genre="lofi", mood="calm"))


def test_agents_never_import_forbidden_modules():
    """No agent file may import OS/shell/db/secret/fs modules (TDD §93, MAD §68)."""
    forbidden_roots = {
        "os", "subprocess", "sqlalchemy", "secrets", "pathlib",
        "tempfile", "shutil", "socket",
    }
    # Agents may import api.core.errors (their own error types) but must not
    # reach capability/media/storage layers directly, nor the core modules that
    # touch the filesystem, secrets or clock.
    forbidden_packages = (
        "api.database",
        "api.storage",
        "api.providers",
        "api.media",
        "api.core.ids",
        "api.core.hashing",
        "api.core.paths",
        "api.core.clock",
        "api.core.logging",
    )
    infra = {"__init__.py", "base.py", "tools.py", "runtime.py"}  # plumbing, not agent decision code
    agent_dir = Path(__file__).resolve().parents[1] / "src/api/agents"
    pattern = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z_][\w.]*)")
    offenders: list[str] = []
    for path in sorted(agent_dir.glob("*.py")):
        if path.name in infra:
            continue  # wiring/bridge layer, not an agent decision file
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            match = pattern.match(line)
            if not match:
                continue
            module = match.group(1)
            root = module.split(".")[0]
            if root in forbidden_roots or module.startswith(forbidden_packages):
                offenders.append(f"{path.name}: {line.strip()}")
    assert offenders == [], "agents must not import forbidden modules:\n" + "\n".join(offenders)
