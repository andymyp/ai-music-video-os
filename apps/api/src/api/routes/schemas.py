"""API request/response schemas (MASTER §29; MAD-001 §45; TDD-001 §68-72, §121).

These are *API* models, deliberately distinct from the domain models: the HTTP
contract is a public surface and must not leak internal architecture
(TDD-001 §121). The layer below converts them into application commands and
domain objects (``Production`` / ``ProductionConfig``).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from api.domain.enums import ProductionMode


class CreateProductionRequest(BaseModel):
    """Payload for ``POST /api/productions`` (TDD-001 §69-70).

    ``mode`` may be ``genre`` (genre required) or ``trending`` (genre optional;
    the workflow performs trend discovery). Branding text is trimmed and capped
    at 80 characters to match the persisted column and the workflow's
    validation gate (TDD-001 §25).
    """

    mode: ProductionMode
    genre: str | None = Field(default=None, max_length=64)
    branding_text: str | None = Field(default=None, max_length=80)

    @field_validator("genre")
    @classmethod
    def _normalize_genre(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        return value or None

    @field_validator("branding_text")
    @classmethod
    def _normalize_branding(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def _genre_required_for_genre_mode(self) -> "CreateProductionRequest":
        if self.mode is ProductionMode.GENRE and not self.genre:
            raise ValueError("genre is required when mode is 'genre'")
        return self


class ProductionSummary(BaseModel):
    """A production's core state (list/detail views)."""

    id: str
    mode: str
    genre: str | None
    branding_text: str | None
    status: str
    target_duration_minutes: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ProductionDetail(ProductionSummary):
    """Detail view: adds the workflow attempt/run that drives the production."""

    attempt: int = 1
    workflow_id: str | None = None


class CreateProductionResponse(BaseModel):
    """Response for ``POST /api/productions`` (TDD-001 §69)."""

    id: str
    status: str


class ProgressResponse(BaseModel):
    """Progress for ``GET /api/productions/{id}/progress`` (TDD-001 §71)."""

    production_id: str
    status: str
    progress: float
    stage: str
    attempt: int = 1


class ArtifactDescriptor(BaseModel):
    """One canonical artifact, referenced by a safe API url (TDD-001 §72).

    Absolute filesystem paths are never exposed; the frontend fetches through
    ``url`` so artifact access stays inside the application boundary.
    """

    kind: str
    url: str
    exists: bool
    size_bytes: int | None = None
    mime_type: str | None = None


class ArtifactsResponse(BaseModel):
    """Listing for ``GET /api/productions/{id}/artifacts`` (TDD-001 §72)."""

    production_id: str
    artifacts: list[ArtifactDescriptor] = Field(default_factory=list)
