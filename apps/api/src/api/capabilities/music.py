"""Music generation capability contract (TDD-001 §30, MAD-001 §18-19).

Music provider adapters implement :class:`MusicProvider`. The product is
strictly instrumental (MAD-001 §17), so ``instrumental`` defaults to ``True``
and requests may not override it to allow vocals.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator


class MusicGenerationRequest(BaseModel):
    """A request to generate an instrumental audio track."""

    prompt: str
    genre: str | None = None
    duration_seconds: int = Field(default=120, ge=15, le=600)
    instrumental: bool = True
    style_hints: list[str] = Field(default_factory=list)
    model: str | None = None

    @field_validator("prompt")
    @classmethod
    def _prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt must not be empty")
        return value

    @field_validator("genre")
    @classmethod
    def _genre(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value.lower() or None

    @model_validator(mode="after")
    def _instrumental_only(self) -> "MusicGenerationRequest":
        # PRD-001 §15 forbids vocals/lyrics; this product never requests them.
        if not self.instrumental:
            raise ValueError("this product only generates instrumental music")
        return self


class GeneratedAudio(BaseModel):
    """Audio a provider produced, referenced either inline or by download URL.

    The music pipeline downloads/normalizes the result before it becomes an
    artifact (MAD-001 §19); the contract only guarantees one retrievable source.
    """

    url: str | None = None
    audio_bytes: bytes | None = None
    format: str = "wav"
    duration_seconds: float | None = Field(default=None, gt=0)
    mime_type: str | None = None
    sample_rate: int | None = Field(default=None, gt=0)
    channels: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _has_source(self) -> "GeneratedAudio":
        if self.url is None and self.audio_bytes is None:
            raise ValueError("GeneratedAudio must provide either url or audio_bytes")
        return self


@runtime_checkable
class MusicProvider(Protocol):
    """A provider that generates instrumental audio tracks."""

    async def generate(
        self,
        request: MusicGenerationRequest,
    ) -> GeneratedAudio:
        """Generate audio for *request* and return a retrievable result."""
        ...
