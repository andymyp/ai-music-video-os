"""Typed agent input/output contracts (TDD-001 §39; MAD-001 §33-34, §67).

Every agent communicates with the runtime through a Pydantic input model and a
Pydantic output model (PRD-001 §70: AI output is validated before it is
consumed downstream). These contracts live in the domain layer so the runtime
and the workflow layers agree on shapes without reaching into capabilities;
agents that bridge to a capability (music/image generation) reuse the
capability request/response types directly from :mod:`api.capabilities`.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from api.domain.audio import AudioAnalysis
from api.domain.creative import MusicStrategy, TrendResult, VisualStrategy
from api.domain.enums import ProductionMode, ProductionStatus
from api.domain.outputs import MetadataPackage, QualityDecision, ShortSegment


# --- Trend research -----------------------------------------------------------

class TrendResearchRequest(BaseModel):
    """Input for the Trend Research Agent (PRD-001 §62)."""

    genre_hint: str | None = Field(default=None, max_length=60)
    source: str = "trends"
    limit: int = Field(default=5, ge=1, le=20)
    time_window_days: int = Field(default=7, ge=1, le=365)

    @field_validator("genre_hint")
    @classmethod
    def _genre(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        return value or None


class TrendResearchResult(BaseModel):
    """Structured trend recommendations (PRD-001 §62.3-62.5)."""

    recommendations: list[TrendResult] = Field(default_factory=list)
    selected_genre: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = Field(default="", max_length=1000)


# --- Music strategy -----------------------------------------------------------

class MusicStrategyRequest(BaseModel):
    """Input for the Music Strategy Agent (PRD-001 §63)."""

    genre: str
    mood: str
    trend: TrendResearchResult | None = None
    duration_target_minutes: int = Field(default=60, ge=1, le=600)

    @field_validator("genre", "mood")
    @classmethod
    def _text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("genre/mood must not be empty")
        return value


# --- Visual strategy ----------------------------------------------------------

class VisualStrategyRequest(BaseModel):
    """Input for the Visual Strategy Agent (PRD-001 §65).

    ``theme`` / ``music_direction`` come from the resolved CreativeConcept and
    ``branding`` from the production, so the strategy reflects the full creative
    direction (PRD-001 FR-015: genre, mood, theme, music direction, branding).
    """

    genre: str
    mood: str
    music_strategy: MusicStrategy | None = None
    trend: TrendResearchResult | None = None
    theme: str | None = Field(default=None, max_length=120)
    music_direction: str | None = Field(default=None, max_length=200)
    branding: str | None = Field(default=None, max_length=80)

    @field_validator("genre", "mood")
    @classmethod
    def _text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("genre/mood must not be empty")
        return value

    @field_validator("theme", "music_direction", "branding")
    @classmethod
    def _optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


# --- Short selection ----------------------------------------------------------

class ShortSelectionRequest(BaseModel):
    """Input for the Short Selection Agent (PRD-001 §67)."""

    audio_path: str
    target_duration_seconds: float = Field(default=45.0, gt=0.0, le=600.0)
    min_duration_seconds: float = Field(default=20.0, ge=0.0)
    max_duration_seconds: float = Field(default=60.0, ge=0.0)


# --- Metadata -----------------------------------------------------------------

class MetadataRequest(BaseModel):
    """Input for the Metadata Agent (PRD-001 §68; TDD-001 §57).

    Carries the full creative brief — CreativeConcept, MusicStrategy,
    VisualStrategy, Production Context, Trend Context and the selected
    ShortSegment — so metadata is generated from the actual production rather
    than the genre alone (MASTER §27: "metadata must be generated from actual
    production information"; TDD-001 §58 correspondence to the production).
    """

    genre: str
    mood: str
    theme: str = ""
    audience: str = ""
    music_concept: str = ""
    visual_concept: str = ""
    trend_context: str = ""
    branding: str | None = Field(default=None, max_length=60)
    title_hint: str | None = Field(default=None, max_length=120)
    short_segment: ShortSegment | None = None

    @field_validator("genre", "mood")
    @classmethod
    def _text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("genre/mood must not be empty")
        return value


# --- Quality control ----------------------------------------------------------

class TechnicalCheck(BaseModel):
    """One deterministic technical verification fed to the QC Agent."""

    name: str
    passed: bool
    detail: str = ""

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be empty")
        return value


class QualityControlRequest(BaseModel):
    """Input for the Quality Control Agent (PRD-001 §69).

    ``mandatory_checks`` names the technical checks that must pass for the
    production to be approved; other failed checks degrade to warnings.
    """

    production_id: str | None = None
    technical_checks: list[TechnicalCheck] = Field(default_factory=list)
    mandatory_checks: list[str] = Field(default_factory=list)
    creative_context: str = ""


# --- Orchestrator -------------------------------------------------------------

class OrchestratorRequest(BaseModel):
    """Input for the Orchestrator Agent (PRD-001 §61)."""

    production_id: str | None = None
    current_status: ProductionStatus
    mode: ProductionMode = ProductionMode.GENRE
    genre: str | None = Field(default=None, max_length=60)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("genre")
    @classmethod
    def _genre(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        return value or None


class OrchestratorDecision(BaseModel):
    """What the Orchestrator Agent decides next (PRD-001 §61).

    ``next_agent`` is the agent name to run, or ``""`` when the next stage is a
    media-pipeline operation (audio analysis, rendering) that runs outside the
    agent layer. ``capability`` is the capability the stage needs, if any.
    """

    next_agent: str
    capability: str | None = None
    regenerate: bool = False
    reason: str = Field(default="", max_length=1000)
    creative_direction: str = ""


__all__ = [
    "TrendResearchRequest",
    "TrendResearchResult",
    "MusicStrategyRequest",
    "VisualStrategyRequest",
    "ShortSelectionRequest",
    "MetadataRequest",
    "TechnicalCheck",
    "QualityControlRequest",
    "OrchestratorRequest",
    "OrchestratorDecision",
]
