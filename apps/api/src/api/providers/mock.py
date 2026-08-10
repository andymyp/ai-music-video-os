"""Deterministic mock providers for development and testing (MAD-001 §58, TDD-001 §100-101).

Each mock implements the same capability protocol as a production provider
(TDD-001 §100), requires no credentials, and returns deterministic, valid
outputs — the artifacts the later media pipeline consumes (``mock-music.wav``,
``mock-background.png``, ``mock-metadata.json`` per MAD-001 §58). Determinism is
seeded from the request text so identical requests yield identical bytes, which
keeps tests and E2E runs reproducible. ``register_mock_providers`` wires all six
under a :class:`~api.capabilities.registry.ProviderRegistry` for mock mode
(MAD-001 §59).
"""
from __future__ import annotations

import binascii
import json
import math
import struct
import zlib
from typing import Any

from api.capabilities import (
    Capability,
    EmbeddingProvider,
    GeneratedAudio,
    GeneratedImage,
    ImageGenerationRequest,
    ImageProvider,
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
from api.capabilities.registry import ProviderRegistry


def _seed(*parts: str) -> str:
    """Deterministic seed string derived from request content."""
    return "|".join(parts)


def _crc(seed: str) -> int:
    """Stable 0..2^32-1 integer from a seed (deterministic across runs)."""
    return binascii.crc32(seed.encode("utf-8"))


def _digest(seed: str | bytes, length: int = 8) -> str:
    """Short deterministic lowercase hex digest used for mock ids/tokens."""
    from hashlib import sha256

    payload = seed.encode("utf-8") if isinstance(seed, str) else seed
    return sha256(payload).hexdigest()[:length]


# --- Mock LLM ---------------------------------------------------------------


def _fill_value(schema: dict[str, Any] | None, seed: str) -> Any:
    """Deterministically fill a JSON Schema (pragmatic subset, MAD-001 §67).

    Supports ``type`` object/string/number/integer/boolean/array plus ``default``,
    ``enum``, ``minimum``/``maximum``, ``minItems``, ``properties``/``required``
    and ``format: date-time``. ``$ref``/``oneOf``/``anyOf`` resolve to the first
    candidate. This gives downstream agents schema-shaped data they can validate.
    """
    schema = schema or {}
    if "default" in schema:
        return schema["default"]
    if "enum" in schema:
        return schema["enum"][0]
    if "$ref" in schema or "oneOf" in schema or "anyOf" in schema:
        candidate = schema.get("oneOf") or schema.get("anyOf") or [{}]
        return _fill_value(candidate[0], seed)
    typ = schema.get("type")
    if typ == "object":
        result: dict[str, Any] = {}
        for name, prop in (schema.get("properties") or {}).items():
            result[name] = _fill_value(prop, f"{seed}:{name}")
        for name in schema.get("required") or []:
            if name not in result:
                result[name] = _fill_value({}, f"{seed}:{name}")
        return result
    if typ == "array":
        items = schema.get("items") or {}
        count = schema.get("minItems") or 2
        if count > 6:
            count = 6
        return [_fill_value(items, f"{seed}:{i}") for i in range(int(count))]
    if typ == "string":
        if schema.get("format") == "date-time":
            return "2024-01-01T00:00:00Z"
        if schema.get("pattern"):
            return "mock-pattern-value"
        return f"mock-{_digest(seed, 6)}"
    if typ in ("number", "integer"):
        value = (_crc(seed) % 1000) / 10.0
        if schema.get("minimum") is not None:
            value = max(value, schema["minimum"])
        if schema.get("maximum") is not None:
            value = min(value, schema["maximum"])
        return int(value) if typ == "integer" else value
    if typ == "boolean":
        return True
    return None


class MockLLMProvider(LLMProvider):
    """Returns schema-shaped, deterministic structured output."""

    def __init__(self, model: str = "mock-llm") -> None:
        self.model = model

    async def generate_structured(
        self,
        request: StructuredGenerationRequest,
    ) -> StructuredResult:
        seed = _seed(request.task, request.prompt, request.model or self.model)
        if not request.output_schema:
            data: dict[str, Any] = {"result": f"mock-{_digest(seed, 10)}"}
        else:
            data = _fill_value(request.output_schema, seed)
            if not isinstance(data, dict):  # contract requires a dict payload
                data = {"value": data}
        return StructuredResult(
            data=data,
            model=self.model,
            raw=json.dumps(data, sort_keys=True),
        )


# --- Mock Music -------------------------------------------------------------


def _encode_wav(samples: list[int], sample_rate: int = 22050, channels: int = 1, bits: int = 16) -> bytes:
    """Build a minimal valid PCM WAV (RIFF) from mono samples (MAD-001 §19)."""
    byte_depth = bits // 8
    block_align = channels * byte_depth
    byte_rate = sample_rate * block_align
    data = bytearray()
    for sample in samples:
        data += struct.pack(f"<{channels}h", sample)
    fmt = struct.pack(
        "<HHIIHH",
        1,  # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
    )
    header = b"RIFF" + struct.pack("<I", 4 + (8 + len(fmt)) + (8 + len(data))) + b"WAVE"
    header += b"fmt " + struct.pack("<I", len(fmt)) + fmt
    header += b"data" + struct.pack("<I", len(data)) + bytes(data)
    return header


class MockMusicProvider(MusicProvider):
    """Generates a deterministic sine-tone WAV (instrumental only)."""

    def __init__(self, model: str = "mock-music", sample_rate: int = 22050) -> None:
        self.model = model
        self.sample_rate = sample_rate

    async def generate(self, request: MusicGenerationRequest) -> GeneratedAudio:
        seed = _seed(
            request.prompt,
            request.genre or "",
            str(request.duration_seconds),
            ",".join(request.style_hints),
        )
        freq = 110 + (_crc(seed) % 880)  # 110..989 Hz
        seconds = request.duration_seconds
        count = int(seconds * self.sample_rate)
        samples = [
            int(0.25 * 32767 * math.sin(2 * math.pi * freq * t / self.sample_rate))
            for t in range(count)
        ]
        return GeneratedAudio(
            audio_bytes=_encode_wav(samples, self.sample_rate),
            format="wav",
            duration_seconds=seconds,
            mime_type="audio/wav",
            sample_rate=self.sample_rate,
            channels=1,
            metadata={
                "provider": "mock",
                "model": self.model,
                "tone_freq_hz": freq,
                "seed": seed,
            },
        )


# --- Mock Image -------------------------------------------------------------


def _png_chunk(typ: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + typ
        + data
        + struct.pack(">I", binascii.crc32(typ + data) & 0xFFFFFFFF)
    )


def _encode_png(width: int, height: int, pixel_fn: Any) -> bytes:
    """Build a minimal valid 24-bit RGB PNG (signature, IHDR, IDAT, IEND)."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type: none
        for x in range(width):
            raw += bytes(pixel_fn(x, y))
    idat = zlib.compress(bytes(raw))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )


_ASPECT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "1:1": (1024, 1024),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
}


class MockImageProvider(ImageProvider):
    """Generates a deterministic textured PNG honoring the aspect ratio."""

    def __init__(self, model: str = "mock-image") -> None:
        self.model = model

    async def generate(self, request: ImageGenerationRequest) -> GeneratedImage:
        seed = _seed(request.prompt, request.aspect_ratio, ",".join(request.style_hints))
        width, height = (
            (request.width, request.height)
            if request.width and request.height
            else _ASPECT_DIMENSIONS[request.aspect_ratio]
        )
        salt = _crc(seed)

        def pixel(x: int, y: int) -> tuple[int, int, int]:
            h = _crc(f"{salt}:{x}:{y}")
            return ((h >> 16) & 0xFF, (h >> 8) & 0xFF, h & 0xFF)

        return GeneratedImage(
            image_bytes=_encode_png(width, height, pixel),
            format="png",
            width=width,
            height=height,
            mime_type="image/png",
            metadata={"provider": "mock", "model": self.model, "seed": seed},
        )


# --- Mock Vision ------------------------------------------------------------


class MockVisionProvider(VisionProvider):
    """Returns a deterministic analysis without actually reading the image."""

    def __init__(self, model: str = "mock-vision") -> None:
        self.model = model

    async def analyze(self, request: VisionRequest) -> VisionResult:
        seed = _seed(request.question, request.detail, _digest(bytes(request.image)))
        return VisionResult(
            summary=f"Deterministic mock analysis: {request.question}",
            findings={
                "image_bytes": len(request.image),
                "image_sha256_prefix": _digest(bytes(request.image), 16),
                "detail": request.detail,
                "mock": True,
            },
            model=self.model,
        )


# --- Mock Embedding ---------------------------------------------------------


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic hash-based dense vector (unit norm)."""

    def __init__(self, model: str = "mock-embedding", dimensions: int = 8) -> None:
        self.model = model
        self.dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        seed = _seed(text, self.model)
        # Expand the seed hash into `dimensions` deterministic values in [-5, 5).
        vector = [(_crc(f"{seed}:{i}") % 1000) / 100.0 - 5.0 for i in range(self.dimensions)]
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


# --- Mock Trend -------------------------------------------------------------

_PLATFORMS = ("tiktok", "youtube", "instagram", "spotify")

_EPOCH = 1_700_000_000  # 2023-11-14 UTC anchor for deterministic mock recency


def _trend_recency(seed: str):
    """Deterministic UTC datetime derived from *seed* (stable across runs)."""
    from datetime import datetime, timezone

    offset = _crc(seed) % (365 * 24 * 3600)
    return datetime.fromtimestamp(_EPOCH + offset, tz=timezone.utc)


class MockTrendProvider(TrendProvider):
    """Returns deterministic trend signals derived from the query anchor."""

    def __init__(self, model: str = "mock-trend") -> None:
        self.model = model

    async def discover(self, query: TrendQuery) -> list[TrendSignal]:
        anchor = query.keyword or query.genre or "music"
        platforms = query.platforms or list(_PLATFORMS)
        signals: list[TrendSignal] = []
        for i in range(query.limit):
            platform = platforms[i % len(platforms)]
            seed = _seed(anchor, platform, str(i))
            score = round(1.0 - (i / max(query.limit, 1)) * 0.9, 3)
            recency = _trend_recency(f"{seed}:recency")
            signals.append(
                TrendSignal(
                    topic=f"{anchor}-concept-{i + 1}",
                    platform=platform,
                    score=score,
                    growth=round((_crc(f"{seed}:growth") % 200) / 100.0, 2),
                    volume=1000 + (_crc(f"{seed}:volume") % 9000),
                    recency=recency,
                    summary=f"Mock trend #{i + 1} for {anchor!r} on {platform}",
                )
            )
        return signals


# --- Mock mode wiring (MAD-001 §59) ------------------------------------------


def register_mock_providers(
    registry: ProviderRegistry,
    *,
    cost_mode: str = "mock",
) -> dict[Capability, Any]:
    """Register all six mock providers under *registry* (mock mode).

    Returns the created providers keyed by capability. Configurations use the
    deterministic mock ids, no credentials, and top priority so mock mode is the
    default resolution when no real provider is configured.
    """
    providers = [
        (Capability.LLM, MockLLMProvider()),
        (Capability.MUSIC, MockMusicProvider()),
        (Capability.IMAGE, MockImageProvider()),
        (Capability.VISION, MockVisionProvider()),
        (Capability.EMBEDDING, MockEmbeddingProvider()),
        (Capability.TREND, MockTrendProvider()),
    ]
    registered: dict[Capability, Any] = {}
    for capability, provider in providers:
        registry.register(
            capability,
            provider,
            ProviderConfig(
                provider_id=f"mock_{capability.value}",
                capability=capability,
                model=getattr(provider, "model", None),
                priority=0,
                enabled=True,
                cost_mode=cost_mode,
                credentials_reference=None,
            ),
        )
        registered[capability] = provider
    return registered
