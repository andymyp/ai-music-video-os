"""Phase 05: mock providers (MAD-001 §58-59, TDD-001 §100-101).

Verifies that the six mock providers conform to the Phase04 capability
protocols, produce deterministic valid outputs (real WAV/PNG bytes, JSON that
satisfies the requested schema), require no credentials, and register cleanly
under a ProviderRegistry for mock mode.
"""
from __future__ import annotations

import json
import struct
import zlib

import pytest

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
    StructuredGenerationRequest,
    TrendProvider,
    TrendQuery,
    TrendSignal,
    VisionProvider,
    VisionRequest,
    VisionResult,
)
from api.providers.mock import (
    MockEmbeddingProvider,
    MockImageProvider,
    MockLLMProvider,
    MockMusicProvider,
    MockTrendProvider,
    MockVisionProvider,
    register_mock_providers,
)


# --- Protocol conformance (TDD-001 §100) --------------------------------------

def test_mock_llm_conforms():
    assert isinstance(MockLLMProvider(), LLMProvider)


def test_mock_music_conforms():
    assert isinstance(MockMusicProvider(), MusicProvider)


def test_mock_image_conforms():
    assert isinstance(MockImageProvider(), ImageProvider)


def test_mock_vision_conforms():
    assert isinstance(MockVisionProvider(), VisionProvider)


def test_mock_embedding_conforms():
    assert isinstance(MockEmbeddingProvider(), EmbeddingProvider)


def test_mock_trend_conforms():
    assert isinstance(MockTrendProvider(), TrendProvider)


# --- Mock LLM ----------------------------------------------------------------

async def test_mock_llm_is_deterministic():
    provider = MockLLMProvider()
    request = StructuredGenerationRequest(
        task="music_strategy",
        prompt="lofi",
        output_schema={"type": "object", "properties": {"genre": {"type": "string"}}},
    )
    first = await provider.generate_structured(request)
    second = await provider.generate_structured(request)
    assert first.data == second.data
    assert first.raw == second.raw


async def test_mock_llm_changes_with_prompt():
    provider = MockLLMProvider()
    a = await provider.generate_structured(StructuredGenerationRequest(task="t", prompt="lofi"))
    b = await provider.generate_structured(StructuredGenerationRequest(task="t", prompt="house"))
    assert a.data != b.data


async def test_mock_llm_fills_object_schema():
    provider = MockLLMProvider()
    schema = {
        "type": "object",
        "properties": {
            "genre": {"type": "string"},
            "bpm_range": {"type": "array", "items": {"type": "integer"}, "minItems": 2},
            "active": {"type": "boolean"},
            "energy": {"type": "number", "minimum": 0, "maximum": 1},
            "tag": {"enum": ["a", "b", "c"]},
            "label": {"type": "string", "default": "default-label"},
        },
        "required": ["genre", "bpm_range"],
    }
    result = await provider.generate_structured(
        StructuredGenerationRequest(task="music_strategy", prompt="x", output_schema=schema)
    )
    data = result.data
    assert isinstance(data["genre"], str) and data["genre"]
    assert len(data["bpm_range"]) == 2
    assert all(isinstance(v, int) for v in data["bpm_range"])
    assert data["active"] is True
    assert 0 <= data["energy"] <= 1
    assert data["tag"] == "a"
    assert data["label"] == "default-label"
    json.dumps(data)  # must be JSON-serializable


async def test_mock_llm_wraps_non_object_schema():
    provider = MockLLMProvider()
    result = await provider.generate_structured(
        StructuredGenerationRequest(task="t", prompt="p", output_schema={"type": "string"})
    )
    assert isinstance(result.data, dict)
    assert isinstance(result.data["value"], str)


# --- Mock Music --------------------------------------------------------------

def _wav_fields(wav: bytes) -> dict:
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    fields = {"riff_size": struct.unpack("<I", wav[4:8])[0]}
    offset = 12
    chunks = {}
    while offset + 8 <= len(wav):
        typ = wav[offset : offset + 4]
        size = struct.unpack("<I", wav[offset + 4 : offset + 8])[0]
        body = wav[offset + 8 : offset + 8 + size]
        chunks[typ] = body
        offset += 8 + size
    fmt = struct.unpack("<HHIIHH", chunks[b"fmt "])
    fields.update(
        audio_format=fmt[0],
        channels=fmt[1],
        sample_rate=fmt[2],
        bits_per_sample=fmt[5],
    )
    fields["data_size"] = len(chunks[b"data"])
    return fields


async def test_mock_music_returns_valid_wav():
    provider = MockMusicProvider(sample_rate=8000)
    audio = await provider.generate(MusicGenerationRequest(prompt="lofi", duration_seconds=15))
    assert isinstance(audio, GeneratedAudio)
    wav = _wav_fields(audio.audio_bytes)
    assert wav["audio_format"] == 1  # PCM
    assert wav["channels"] == 1
    assert wav["sample_rate"] == 8000
    assert wav["bits_per_sample"] == 16
    assert wav["data_size"] == 15 * 8000 * 2
    assert wav["riff_size"] == wav["data_size"] + 36
    assert audio.mime_type == "audio/wav"
    assert audio.duration_seconds == 15


async def test_mock_music_is_deterministic():
    provider = MockMusicProvider(sample_rate=8000)
    request = MusicGenerationRequest(prompt="lofi", duration_seconds=15)
    a = await provider.generate(request)
    b = await provider.generate(request)
    assert a.audio_bytes == b.audio_bytes
    c = await provider.generate(MusicGenerationRequest(prompt="house", duration_seconds=15))
    assert a.audio_bytes != c.audio_bytes


# --- Mock Image --------------------------------------------------------------

def _png_info(png: bytes) -> dict:
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    width = height = bit_depth = color_type = None
    crc_ok = True
    scanline_bytes = None
    decompressed = b""
    while offset + 8 <= len(png):
        size = struct.unpack(">I", png[offset : offset + 4])[0]
        typ = png[offset + 4 : offset + 8]
        body = png[offset + 8 : offset + 8 + size]
        stored = struct.unpack(">I", png[offset + 8 + size : offset + 12 + size])[0]
        if stored != (zlib.crc32(typ + body) & 0xFFFFFFFF):
            crc_ok = False
        if typ == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", body[:10])
        if typ == b"IDAT":
            decompressed += body
        offset += 12 + size
    if crc_ok:
        raw = zlib.decompress(decompressed)
        scanline_bytes = len(raw) // height if height else 0
    return {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
        "crc_ok": crc_ok,
        "scanline_bytes": scanline_bytes,
    }


async def test_mock_image_returns_valid_png():
    provider = MockImageProvider()
    image = await provider.generate(
        ImageGenerationRequest(prompt="bg", width=32, height=18)
    )
    assert isinstance(image, GeneratedImage)
    info = _png_info(image.image_bytes)
    assert info["width"] == 32
    assert info["height"] == 18
    assert info["bit_depth"] == 8
    assert info["color_type"] == 2  # RGB
    assert info["crc_ok"] is True
    assert info["scanline_bytes"] == 1 + 32 * 3  # filter byte + RGB per pixel
    assert image.mime_type == "image/png"


async def test_mock_image_aspect_ratio_mapping():
    provider = MockImageProvider()
    landscape = await provider.generate(ImageGenerationRequest(prompt="bg", aspect_ratio="16:9"))
    portrait = await provider.generate(ImageGenerationRequest(prompt="bg", aspect_ratio="9:16"))
    assert (landscape.width, landscape.height) == (1280, 720)
    assert (portrait.width, portrait.height) == (720, 1280)


async def test_mock_image_is_deterministic():
    provider = MockImageProvider()
    request = ImageGenerationRequest(prompt="bg", width=32, height=18)
    a = await provider.generate(request)
    b = await provider.generate(request)
    assert a.image_bytes == b.image_bytes
    c = await provider.generate(ImageGenerationRequest(prompt="other", width=32, height=18))
    assert a.image_bytes != c.image_bytes


# --- Mock Vision -------------------------------------------------------------

async def test_mock_vision_is_deterministic_and_reports_size():
    provider = MockVisionProvider()
    request = VisionRequest(image=b"\x00" * 100, question="branding?")
    a = await provider.analyze(request)
    b = await provider.analyze(request)
    assert a.model_dump() == b.model_dump()
    assert a.findings["image_bytes"] == 100
    c = await provider.analyze(VisionRequest(image=b"\x00" * 100, question="text?"))
    assert a.summary != c.summary
    assert isinstance(a, VisionResult)


# --- Mock Embedding ----------------------------------------------------------

async def test_mock_embedding_is_deterministic_and_unit_norm():
    provider = MockEmbeddingProvider(dimensions=8)
    v1 = await provider.embed("lofi beat")
    v2 = await provider.embed("lofi beat")
    assert v1 == v2
    assert len(v1) == 8
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-9
    v3 = await provider.embed("house beat")
    assert v1 != v3


# --- Mock Trend --------------------------------------------------------------

async def test_mock_trend_respects_limit_and_scores():
    provider = MockTrendProvider()
    signals = await provider.discover(TrendQuery(keyword="lofi", limit=5))
    assert len(signals) == 5
    assert all(isinstance(s, TrendSignal) for s in signals)
    assert all(0 <= s.score <= 1 for s in signals)
    assert [s.score for s in signals] == sorted((s.score for s in signals), reverse=True)
    assert all(s.topic.startswith("lofi-") for s in signals)


async def test_mock_trend_respects_platforms():
    provider = MockTrendProvider()
    signals = await provider.discover(
        TrendQuery(keyword="lofi", platforms=["tiktok"], limit=3)
    )
    assert {s.platform for s in signals} == {"tiktok"}


async def test_mock_trend_is_deterministic():
    provider = MockTrendProvider()
    query = TrendQuery(keyword="lofi", limit=3)
    a = await provider.discover(query)
    b = await provider.discover(query)
    assert [s.model_dump() for s in a] == [s.model_dump() for s in b]


# --- Mock mode wiring (MAD-001 §59) -------------------------------------------

def test_register_mock_providers_covers_all_capabilities():
    registry = InMemoryProviderRegistry()
    registered = register_mock_providers(registry)
    assert set(registered) == set(Capability)
    for capability in Capability:
        assert registry.available(capability) is True
        provider = registry.resolve(capability)
        assert provider is registered[capability]


def test_mock_configs_require_no_credentials():
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    for capability in Capability:
        for config in registry.configs(capability):
            assert config.credentials_reference is None
            assert config.enabled is True
            assert config.priority == 0
            assert config.cost_mode == "mock"
            assert config.provider_id == f"mock_{capability.value}"


def test_register_mock_providers_honors_cost_mode():
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry, cost_mode="free")
    for config in registry.configs(Capability.LLM):
        assert config.cost_mode == "free"
