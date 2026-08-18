"""Provider abstraction layer (MAD-001 §35-36, §62; TDD-001 §27-37).

Capabilities sit between agents/workflows and concrete provider adapters: agents
depend on the protocols here, never on vendor SDKs (PRD-001 §44). The package
layout mirrors MAD-001 §58 (``capabilities/llm|music|image|trend|embedding|
vision``). No provider SDK may be imported below.
"""
from __future__ import annotations

from api.capabilities.base import Capability, ProviderConfig
from api.capabilities.embedding import EmbeddingProvider
from api.capabilities.image import AspectRatio, GeneratedImage, ImageGenerationRequest, ImageProvider
from api.capabilities.llm import LLMProvider, StructuredGenerationRequest, StructuredResult
from api.capabilities.music import GeneratedAudio, MusicGenerationRequest, MusicProvider
from api.capabilities.registry import InMemoryProviderRegistry, ProviderRegistry
from api.capabilities.trend import TrendProvider, TrendQuery, TrendSignal
from api.capabilities.vision import VisionProvider, VisionRequest, VisionResult

__all__ = [
    # base
    "Capability",
    "ProviderConfig",
    # registry
    "ProviderRegistry",
    "InMemoryProviderRegistry",
    # llm
    "LLMProvider",
    "StructuredGenerationRequest",
    "StructuredResult",
    # music
    "MusicProvider",
    "MusicGenerationRequest",
    "GeneratedAudio",
    # image
    "ImageProvider",
    "ImageGenerationRequest",
    "GeneratedImage",
    "AspectRatio",
    # vision
    "VisionProvider",
    "VisionRequest",
    "VisionResult",
    # embedding
    "EmbeddingProvider",
    # trend
    "TrendProvider",
    "TrendQuery",
    "TrendSignal",
]
