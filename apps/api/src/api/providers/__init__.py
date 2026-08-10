"""Provider implementations (MAD-001 §36, §58; TDD-001 §100-102).

Providers implement the capability protocols from :mod:`api.capabilities` and
never contain business logic (MAD-001 §36). Phase 05 ships the deterministic
mock family used in development/test/mock mode; real vendor adapters arrive in
later phases.
"""
from __future__ import annotations

from api.providers.mock import (
    MockEmbeddingProvider,
    MockImageProvider,
    MockLLMProvider,
    MockMusicProvider,
    MockTrendProvider,
    MockVisionProvider,
    register_mock_providers,
)

__all__ = [
    "MockLLMProvider",
    "MockMusicProvider",
    "MockImageProvider",
    "MockVisionProvider",
    "MockEmbeddingProvider",
    "MockTrendProvider",
    "register_mock_providers",
]
