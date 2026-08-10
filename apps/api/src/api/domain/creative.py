"""Creative-direction models (MAD-001 §16-20; TDD-001 §12-15).

These are the outputs of the creative stages (trend research, music strategy,
visual strategy, concept) consumed by the provider pipeline. They are pure
data contracts with light validation: provider adapters produce them, and
later phases persist them with the production.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from api.core.clock import utc_now


def _require_text(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field} must not be empty")
    return value


class CreativeConcept(BaseModel):
    """Consolidated creative brief for a production (TDD-001 §12)."""

    genre: str
    mood: str
    theme: str
    audience: str | None = None
    music_direction: str
    visual_direction: str

    @field_validator("genre")
    @classmethod
    def _genre(cls, value: str) -> str:
        return _require_text(value, "genre").lower()

    @field_validator("mood", "theme", "audience", "music_direction", "visual_direction")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_text(value, "text")


class MusicStrategy(BaseModel):
    """Long-form music blueprint (MAD-001 §17, TDD-001 §13).

    ``vocal_policy`` is locked to ``"none"``: this product is strictly
    instrumental (PRD-001 §15 forbids vocals, lyrics and singing), so the
    type literal rejects any provider output that tries to include them.
    """

    genre: str
    mood: str
    bpm_range: list[int] = Field(default_factory=lambda: [70, 85])
    key: str
    instruments: list[str] = Field(default_factory=list)
    structure: str
    duration_target_minutes: int = Field(default=60, ge=1, le=600)
    vocal_policy: Literal["none"] = "none"

    @field_validator("genre")
    @classmethod
    def _genre(cls, value: str) -> str:
        return _require_text(value, "genre").lower()

    @field_validator("mood", "key", "structure")
    @classmethod
    def _text(cls, value: str) -> str:
        return _require_text(value, "text")

    @field_validator("bpm_range")
    @classmethod
    def _bpm_range(cls, value: list[int]) -> list[int]:
        if len(value) != 2:
            raise ValueError("bpm_range must have exactly two values [low, high]")
        low, high = value
        if low <= 0 or high < low:
            raise ValueError(f"invalid bpm_range {value!r}; need 0 < low <= high")
        return value


class VisualStrategy(BaseModel):
    """Visual-direction blueprint (MAD-001 §20, TDD-001 §14)."""

    theme: str
    environment: str
    lighting: str
    style: str
    color_direction: str
    radio_style: str
    composition: str
    visualizer_style: str = Field(default="bars", max_length=40)
    era: str = "modern"
    palette: list[str] = Field(default_factory=list)

    @field_validator("theme", "environment", "lighting", "style",
                     "color_direction", "radio_style", "composition")
    @classmethod
    def _text(cls, value: str) -> str:
        return _require_text(value, "text")

    @field_validator("palette")
    @classmethod
    def _palette(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for colour in value:
            colour = colour.strip().lower()
            if not colour:
                continue
            cleaned.append(colour)
        return cleaned


class TrendResult(BaseModel):
    """A scored trending-genre signal (MAD-001 §16, TDD-001 §15).

    ``score`` is a 0-100 weighted composite; ``confidence`` and the component
    signals (growth/volume/cross_platform/content_fit) are 0-1 normalized per
    MAD-001 §16 so the components stay comparable across sources.
    """

    source: str
    topic: str
    genre: str | None = None
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    recency: datetime = Field(default_factory=utc_now)
    evidence: list[str] = Field(default_factory=list)
    growth: float | None = Field(default=None, ge=0.0, le=1.0)
    volume: float | None = Field(default=None, ge=0.0, le=1.0)
    cross_platform: float | None = Field(default=None, ge=0.0, le=1.0)
    content_fit: float | None = Field(default=None, ge=0.0, le=1.0)
    reasoning: str = Field(default="", max_length=1000)

    @field_validator("source", "topic")
    @classmethod
    def _text(cls, value: str) -> str:
        return _require_text(value, "text")

    @field_validator("genre")
    @classmethod
    def _genre(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_text(value, "genre").lower()
