"""Registered tool boundary (TDD-001 §41, §93; MAD-001 §69).

The tool registry is the *only* surface an agent may call. Tools bridge to a
capability (via the provider registry) or to the media layer, each with a strict
input/output schema. Agent code never touches a provider SDK, the filesystem,
the shell or the database directly — it goes through these tools. Provider
failure is handled here by deterministic failover over the configured providers
(PRD-001 §64.5); tools that don't need a capability (e.g. audio analysis) wrap
the media engine directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from api.capabilities import (
    Capability,
    GeneratedAudio,
    GeneratedImage,
    ImageGenerationRequest,
    MusicGenerationRequest,
    ProviderRegistry,
    StructuredGenerationRequest,
    StructuredResult,
    TrendQuery,
)
from api.core.errors import AppError, ConfigurationError, ToolError
from api.domain.audio import AudioAnalysis
from api.domain.creative import TrendResult
from api.media.audio import AudioAnalysisEngine
from api.trend.engine import TrendEngine

ToolInputT = TypeVar("ToolInputT", contravariant=True)
ToolOutputT = TypeVar("ToolOutputT", covariant=True)


class Tool(ABC, Generic[ToolInputT, ToolOutputT]):
    """A registered capability/media operation with strict I/O schema."""

    name: str = ""
    description: str = ""
    input_schema: type[BaseModel] | None = None
    output_schema: type[BaseModel] | None = None

    @abstractmethod
    async def run(self, input: ToolInputT) -> ToolOutputT:
        """Execute the operation and return a validated result."""


class ToolRegistry:
    """Explicitly registered tools; the runtime exposes only these (TDD §93)."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool[Any, Any]] = {}

    def register(self, tool: Tool[Any, Any]) -> None:
        if not tool.name:
            raise ConfigurationError("tool must declare a name")
        if tool.name in self._tools:
            raise ConfigurationError(f"tool already registered: {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool[Any, Any]:
        if name not in self._tools:
            raise ToolError(f"tool not registered: {name!r}")
        return self._tools[name]

    def available(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools)


async def _call_with_failover(providers: list[Any], call: Any) -> Any:
    """Try each enabled provider best-first; first success wins (PRD §64.5)."""
    errors: list[str] = []
    for provider in providers:
        try:
            return await call(provider)
        except AppError as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    raise ToolError("all providers failed: " + ("; ".join(errors) or "no providers"))


class _CapabilityTool(Tool[Any, Any]):
    """Base for tools that resolve a capability through the provider registry.

    Subclasses set ``capability`` and implement :meth:`run`, calling
    :meth:`_providers` to get the enabled providers in failover order.
    """

    capability: Capability | None = None

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    def _providers(self) -> list[Any]:
        if self.capability is None:
            raise ConfigurationError(f"{type(self).__name__} has no capability")
        return self._registry.resolve_all(self.capability)


# --- I/O schemas --------------------------------------------------------------

class TrendSearchOutput(BaseModel):
    """Strict output wrapper for trend discovery (scored, ranked results).

    Phase 11 replaced the raw signal list with the engine's scored/ranked
    :class:`~api.domain.creative.TrendResult` rows so the agent consumes a
    weighted composite (MAD-001 §16) instead of raw provider scores.
    """

    results: list[TrendResult]


class AudioAnalysisRequest(BaseModel):
    """Input for audio analysis (path only — agents never touch the FS)."""

    path: str


class CapabilityQuery(BaseModel):
    """Ask the runtime about one capability's availability."""

    capability: Capability


class CapabilityStatus(BaseModel):
    """Availability of one capability for the Orchestrator Agent."""

    capability: Capability
    available: bool
    provider_count: int = 0
    provider_ids: list[str] = Field(default_factory=list)


# --- Concrete tools -----------------------------------------------------------

class TrendSearchTool(_CapabilityTool):
    """Discover, score and rank trend signals via the trend engine.

    The tool is the agent-facing boundary to the TREND capability (TDD-001 §93);
    aggregation, weighted scoring, staleness filtering and caching (Phase 11)
    happen inside the :class:`~api.trend.engine.TrendEngine`.
    """

    name = "trend_search"
    description = "Discover, score and rank current trend signals."
    input_schema = TrendQuery
    output_schema = TrendSearchOutput
    capability = Capability.TREND

    def __init__(self, registry: ProviderRegistry, *, engine: TrendEngine | None = None) -> None:
        super().__init__(registry)
        self._engine = engine or TrendEngine(registry)

    async def run(self, input: TrendQuery) -> TrendSearchOutput:
        results = await self._engine.search(input)
        return TrendSearchOutput(results=results)


class LLMGenerationTool(_CapabilityTool):
    """Generate structured output through the LLM capability (MAD-001 §67)."""

    name = "llm_generate"
    description = "Generate schema-validated structured text via the LLM capability."
    input_schema = StructuredGenerationRequest
    output_schema = StructuredResult
    capability = Capability.LLM

    async def run(self, input: StructuredGenerationRequest) -> StructuredResult:
        async def call(provider: Any) -> StructuredResult:
            return await provider.generate_structured(input)

        return await _call_with_failover(self._providers(), call)


class MusicGenerationTool(_CapabilityTool):
    """Generate instrumental audio through the MUSIC capability."""

    name = "music_generate"
    description = "Generate an instrumental audio track via the music capability."
    input_schema = MusicGenerationRequest
    output_schema = GeneratedAudio
    capability = Capability.MUSIC

    async def run(self, input: MusicGenerationRequest) -> GeneratedAudio:
        async def call(provider: Any) -> GeneratedAudio:
            return await provider.generate(input)

        return await _call_with_failover(self._providers(), call)


class ImageGenerationTool(_CapabilityTool):
    """Generate a visual asset through the IMAGE capability."""

    name = "image_generate"
    description = "Generate a background/visual image via the image capability."
    input_schema = ImageGenerationRequest
    output_schema = GeneratedImage
    capability = Capability.IMAGE

    async def run(self, input: ImageGenerationRequest) -> GeneratedImage:
        async def call(provider: Any) -> GeneratedImage:
            return await provider.generate(input)

        return await _call_with_failover(self._providers(), call)


class CapabilityStatusTool(_CapabilityTool):
    """Report capability availability for the Orchestrator Agent."""

    name = "capability_status"
    description = "Report whether a capability has an enabled provider."
    input_schema = CapabilityQuery
    output_schema = CapabilityStatus

    async def run(self, input: CapabilityQuery) -> CapabilityStatus:
        configs = self._registry.configs(input.capability)
        enabled = [config for config in configs if config.enabled]
        return CapabilityStatus(
            capability=input.capability,
            available=self._registry.available(input.capability),
            provider_count=len(enabled),
            provider_ids=[config.provider_id for config in enabled],
        )


class AudioAnalysisTool(Tool[AudioAnalysisRequest, AudioAnalysis]):
    """Analyze audio via the deterministic media engine (MAD-001 §19)."""

    name = "audio_analyze"
    description = "Compute duration, BPM, loudness, energy/spectral curves, beats and sections."
    input_schema = AudioAnalysisRequest
    output_schema = AudioAnalysis

    def __init__(self, engine: AudioAnalysisEngine | None = None) -> None:
        self._engine = engine or AudioAnalysisEngine()

    async def run(self, input: AudioAnalysisRequest) -> AudioAnalysis:
        return await self._engine.analyze(input.path)


__all__ = [
    "Tool",
    "ToolRegistry",
    "TrendSearchTool",
    "LLMGenerationTool",
    "MusicGenerationTool",
    "ImageGenerationTool",
    "CapabilityStatusTool",
    "AudioAnalysisTool",
    "AudioAnalysisRequest",
    "CapabilityQuery",
    "CapabilityStatus",
    "TrendSearchOutput",
]
