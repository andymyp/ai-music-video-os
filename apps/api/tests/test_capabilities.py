"""Phase 04: provider contracts (MAD-001 §35-36, §62, §67; TDD-001 §27-37, §78).

Covers the six capability protocols (LLM, Music, Image, Vision, Embedding,
Trend), their request/response contracts, the ProviderConfig model, the
ProviderRegistry, and the rule that the capabilities and domain layers never
import provider SDKs.
"""
from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.capabilities import (
    Capability,
    EmbeddingProvider,
    GeneratedAudio,
    GeneratedImage,
    ImageGenerationRequest,
    ImageProvider,
    InMemoryProviderRegistry,
    LLMProvider,
    MusicGenerationRequest,
    MusicProvider,
    ProviderConfig,
    StructuredGenerationRequest,
    StructuredResult,
    TrendProvider,
    TrendQuery,
    TrendSignal,
    VisionProvider,
    VisionRequest,
    VisionResult,
)

# --- Capability identifiers (MAD-001 §35) -------------------------------------


def test_six_capabilities_match_mad():
    assert set(Capability) == {
        Capability.LLM,
        Capability.MUSIC,
        Capability.IMAGE,
        Capability.VISION,
        Capability.EMBEDDING,
        Capability.TREND,
    }


def test_capability_values_are_lowercase_slugs():
    for capability in Capability:
        assert capability.value == capability.name.lower()


# --- ProviderConfig (TDD-001 §78) ----------------------------------------------


def test_provider_config_defaults():
    config = ProviderConfig(provider_id="mock_llm", capability=Capability.LLM)
    assert config.priority == 100
    assert config.enabled is True
    assert config.cost_mode == "balanced"
    assert config.model is None
    assert config.credentials_reference is None


def test_provider_config_rejects_empty_provider_id():
    with pytest.raises(ValidationError):
        ProviderConfig(provider_id="  ", capability=Capability.LLM)


def test_provider_config_accepts_all_cost_modes():
    for mode in ("mock", "free", "balanced", "quality", "custom"):
        config = ProviderConfig(provider_id="p", capability=Capability.LLM, cost_mode=mode)
        assert config.cost_mode == mode


def test_provider_config_rejects_unknown_cost_mode():
    with pytest.raises(ValidationError):
        ProviderConfig(provider_id="p", capability=Capability.LLM, cost_mode="ultra")


# --- LLM contract (TDD-001 §32) ------------------------------------------------


def test_structured_request_defaults_and_validation():
    request = StructuredGenerationRequest(task="metadata", prompt="write tags", output_schema={"type": "object"})
    assert request.system_prompt is None
    assert request.temperature is None
    assert request.max_tokens is None


def test_structured_request_rejects_empty_prompt():
    with pytest.raises(ValidationError):
        StructuredGenerationRequest(task="metadata", prompt="   ")


def test_structured_request_rejects_out_of_range_temperature():
    with pytest.raises(ValidationError):
        StructuredGenerationRequest(task="t", prompt="p", temperature=3)


def test_structured_result_carries_data_model_and_raw():
    result = StructuredResult(data={"genre": "lofi"}, model="mock", raw='{"genre":"lofi"}')
    assert result.data["genre"] == "lofi"
    assert result.model == "mock"
    assert result.raw is not None


# --- Music contract (TDD-001 §30, MAD-001 §17) ---------------------------------


def test_music_request_defaults_to_instrumental_120s():
    request = MusicGenerationRequest(prompt="chill beat")
    assert request.instrumental is True
    assert request.duration_seconds == 120
    assert request.style_hints == []


def test_music_request_rejects_vocals():
    # The product is strictly instrumental (MAD-001 §17, PRD-001 §15).
    with pytest.raises(ValidationError):
        MusicGenerationRequest(prompt="song with lyrics", instrumental=False)


def test_music_request_rejects_out_of_range_duration():
    with pytest.raises(ValidationError):
        MusicGenerationRequest(prompt="x", duration_seconds=10)
    with pytest.raises(ValidationError):
        MusicGenerationRequest(prompt="x", duration_seconds=900)


def test_music_request_normalizes_genre():
    request = MusicGenerationRequest(prompt="x", genre=" Lo-Fi ")
    assert request.genre == "lo-fi"


def test_generated_audio_requires_a_source():
    with pytest.raises(ValidationError):
        GeneratedAudio()
    assert GeneratedAudio(audio_bytes=b"\x01").format == "wav"
    assert GeneratedAudio(url="https://example.test/x.wav").duration_seconds is None


def test_generated_audio_rejects_invalid_duration():
    with pytest.raises(ValidationError):
        GeneratedAudio(audio_bytes=b"x", duration_seconds=-1)


# --- Image contract (TDD-001 §31, MAD-001 §78) ---------------------------------


def test_image_request_default_aspect_ratio():
    request = ImageGenerationRequest(prompt="aurora background")
    assert request.aspect_ratio == "16:9"


def test_image_request_rejects_unknown_aspect_ratio():
    with pytest.raises(ValidationError):
        ImageGenerationRequest(prompt="x", aspect_ratio="7:13")


def test_generated_image_requires_a_source():
    with pytest.raises(ValidationError):
        GeneratedImage()
    assert GeneratedImage(image_bytes=b"\x00").format == "png"
    assert GeneratedImage(url="https://example.test/x.png").width is None


# --- Vision contract (TDD-001 §33) ---------------------------------------------


def test_vision_request_rejects_empty_image_or_question():
    with pytest.raises(ValidationError):
        VisionRequest(image=b"", question="what is this?")
    with pytest.raises(ValidationError):
        VisionRequest(image=b"\x00", question="  ")


def test_vision_result_defaults():
    result = VisionResult(summary="a radio composition")
    assert result.findings == {}
    assert result.model is None


# --- Trend contract (TDD-001 §27-29) -------------------------------------------


def test_trend_query_requires_keyword_or_genre():
    with pytest.raises(ValidationError):
        TrendQuery()
    assert TrendQuery(keyword="lofi").genre is None
    assert TrendQuery(genre="lofi").keyword is None


def test_trend_query_bounds():
    with pytest.raises(ValidationError):
        TrendQuery(keyword="x", limit=0)
    with pytest.raises(ValidationError):
        TrendQuery(keyword="x", time_window_days=0)


def test_trend_signal_score_is_normalized():
    assert TrendSignal(topic="lofi", score=0.5).score == 0.5
    with pytest.raises(ValidationError):
        TrendSignal(topic="lofi", score=1.5)
    with pytest.raises(ValidationError):
        TrendSignal(topic="lofi", score=-0.1)
    with pytest.raises(ValidationError):
        TrendSignal(topic="  ")


# --- Protocol conformance (TDD-001 §96: every provider implements the contract) -


async def test_llm_provider_protocol_conformance():
    class MockLLM(LLMProvider):
        async def generate_structured(self, request):
            return StructuredResult(data={"ok": True}, model="mock")

    provider = MockLLM()
    assert isinstance(provider, LLMProvider)
    result = await provider.generate_structured(
        StructuredGenerationRequest(task="t", prompt="p")
    )
    assert result.data["ok"] is True


async def test_music_provider_protocol_conformance():
    class MockMusic(MusicProvider):
        async def generate(self, request):
            return GeneratedAudio(audio_bytes=b"\x00" * 4, format="wav")

    provider = MockMusic()
    assert isinstance(provider, MusicProvider)
    result = await provider.generate(MusicGenerationRequest(prompt="beat"))
    assert result.audio_bytes is not None


async def test_image_provider_protocol_conformance():
    class MockImage(ImageProvider):
        async def generate(self, request):
            return GeneratedImage(image_bytes=b"\x00" * 4, width=1920, height=1080)

    provider = MockImage()
    assert isinstance(provider, ImageProvider)
    result = await provider.generate(ImageGenerationRequest(prompt="bg"))
    assert result.width == 1920


async def test_vision_provider_protocol_conformance():
    class MockVision(VisionProvider):
        async def analyze(self, request):
            return VisionResult(summary="ok", findings={"branding": True})

    provider = MockVision()
    assert isinstance(provider, VisionProvider)
    result = await provider.analyze(VisionRequest(image=b"\x00", question="branding?"))
    assert result.findings["branding"] is True


async def test_embedding_provider_protocol_conformance():
    class MockEmbedding(EmbeddingProvider):
        async def embed(self, text):
            return [1.0, 0.0]

    provider = MockEmbedding()
    assert isinstance(provider, EmbeddingProvider)
    vector = await provider.embed("lofi beat")
    assert len(vector) == 2


async def test_trend_provider_protocol_conformance():
    class MockTrend(TrendProvider):
        async def discover(self, query):
            return [TrendSignal(topic="lofi", platform="tiktok", score=0.9)]

    provider = MockTrend()
    assert isinstance(provider, TrendProvider)
    signals = await provider.discover(TrendQuery(keyword="lofi"))
    assert signals[0].topic == "lofi"


# --- Provider registry (TDD-001 §35, MAD-001 §52) ------------------------------


@pytest.fixture
def registry():
    return InMemoryProviderRegistry()


def test_register_and_resolve(registry):
    provider = object()
    registry.register(
        Capability.MUSIC,
        provider,
        ProviderConfig(provider_id="mock", capability=Capability.MUSIC),
    )
    assert registry.resolve(Capability.MUSIC) is provider
    assert registry.available(Capability.MUSIC) is True


def test_resolve_missing_capability_raises(registry):
    with pytest.raises(Exception) as exc:
        registry.resolve(Capability.IMAGE)
    assert "no enabled provider" in str(exc.value)


def test_resolve_prefers_lower_priority(registry):
    backup = object()
    primary = object()
    registry.register(
        Capability.LLM,
        backup,
        ProviderConfig(provider_id="backup", capability=Capability.LLM, priority=10),
    )
    registry.register(
        Capability.LLM,
        primary,
        ProviderConfig(provider_id="primary", capability=Capability.LLM, priority=1),
    )
    assert registry.resolve(Capability.LLM) is primary
    assert registry.resolve_all(Capability.LLM) == [primary, backup]


def test_resolve_skips_disabled_provider(registry):
    disabled = object()
    enabled = object()
    registry.register(
        Capability.TREND,
        disabled,
        ProviderConfig(provider_id="off", capability=Capability.TREND, enabled=False),
    )
    with pytest.raises(Exception):
        registry.resolve(Capability.TREND)
    registry.register(
        Capability.TREND,
        enabled,
        ProviderConfig(provider_id="on", capability=Capability.TREND),
    )
    assert registry.resolve(Capability.TREND) is enabled
    assert disabled not in registry.resolve_all(Capability.TREND)


def test_register_config_must_match_capability(registry):
    with pytest.raises(Exception):
        registry.register(
            Capability.IMAGE,
            object(),
            ProviderConfig(provider_id="p", capability=Capability.MUSIC),
        )


def test_configs_ordered_by_priority(registry):
    registry.register(
        Capability.EMBEDDING,
        object(),
        ProviderConfig(provider_id="b", capability=Capability.EMBEDDING, priority=5),
    )
    registry.register(
        Capability.EMBEDDING,
        object(),
        ProviderConfig(provider_id="a", capability=Capability.EMBEDDING, priority=1),
    )
    assert [c.provider_id for c in registry.configs(Capability.EMBEDDING)] == ["a", "b"]


# --- Layering rule: no provider SDKs in capabilities/ or domain/ (MAD-001 §62) --

VENDOR_SDK_MODULES = (
    "openai",
    "anthropic",
    "google",
    "groq",
    "replicate",
    "stability",
    "requests",
    "httpx",
    "boto3",
)


@pytest.mark.parametrize("package", ["api.capabilities", "api.domain"])
def test_packages_never_import_provider_sdks(package):
    module = importlib.import_module(package)
    package_dir = Path(inspect.getsourcefile(module)).parent
    import_pattern = re.compile(r"^\s*(?:from\s+|import\s+)(?:\.*[a-zA-Z_][\w]*)")
    for source_file in package_dir.glob("*.py"):
        for line in source_file.read_text(encoding="utf-8").splitlines():
            # Only inspect real import statements, not prose mentioning SDKs.
            if not import_pattern.match(line):
                continue
            for vendor in VENDOR_SDK_MODULES:
                assert vendor not in line, f"{source_file.name} imports provider SDK {vendor!r}"
