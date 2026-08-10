"""Environment profiles and provider cost modes.

Environment profiles: MAD-001 §92 (development / test / mock / production).
Provider modes:       MAD-001 §59 and §38-39 (mock / free / balanced / quality / custom).
"""

from __future__ import annotations

ENVIRONMENT_PROFILES: tuple[str, ...] = (
    "development",
    "test",
    "mock",
    "production",
)

PROVIDER_MODES: tuple[str, ...] = (
    "mock",
    "free",
    "balanced",
    "quality",
    "custom",
)
