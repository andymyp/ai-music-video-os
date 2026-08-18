"""Capability identifiers and provider configuration (TDD-001 §35, §78).

This package is the abstraction boundary between agents/workflows and concrete
AI providers (MAD-001 §35, §62; PRD-001 §44). The six capabilities below mirror
MAD-001 §35 and the ``capabilities/`` backend structure (MAD-001 §58). Provider
adapters (later phases) implement the protocols in the sibling modules; agents
depend on capabilities, never on vendor SDKs.

This module — like the whole package — must never import a provider SDK.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from api.core.secrets import is_valid_reference

# The five provider cost modes from MAD-001 §59 / PRD-001 §46.
ProviderMode = Literal["mock", "free", "balanced", "quality", "custom"]


class Capability(str, Enum):
    """A capability a provider can satisfy (MAD-001 §35, TDD-001 §35)."""

    LLM = "llm"
    MUSIC = "music"
    IMAGE = "image"
    VISION = "vision"
    EMBEDDING = "embedding"
    TREND = "trend"

    def __str__(self) -> str:  # pragma: no cover - explicit for readability
        return self.value


class ProviderConfig(BaseModel):
    """Static configuration for one registered provider (TDD-001 §78).

    Fields follow TDD-001 §78. ``credentials_reference`` is an indirection (an
    env var name / credential-store key), never the secret itself: secrets must
    not be stored in plaintext configuration (TDD-001 §79).
    """

    provider_id: str
    capability: Capability
    model: str | None = None
    priority: int = Field(default=100, ge=0)
    enabled: bool = True
    cost_mode: ProviderMode = "balanced"
    credentials_reference: str | None = None

    @field_validator("provider_id")
    @classmethod
    def _provider_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("provider_id must not be empty")
        return value

    @field_validator("credentials_reference")
    @classmethod
    def _credentials_reference(cls, value: str | None) -> str | None:
        """A reference is an env-var *name*, never the secret itself (TDD §79).

        Rejecting anything that is not a well-formed env-var name makes it
        structurally impossible to store a literal API key or a path in
        configuration — secrets only ever arrive at call time via
        :func:`api.core.secrets.resolve_credentials`.
        """
        if value is None:
            return value
        if not is_valid_reference(value):
            raise ValueError(
                "credentials_reference must be an env-var name (e.g. OPENAI_API_KEY), "
                "never a secret value"
            )
        return value
