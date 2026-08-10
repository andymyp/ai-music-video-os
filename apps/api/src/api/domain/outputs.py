"""Final-output models (MAD-001 §26, §30, §82; PRD-001 §52; TDD-001 §131).

Metadata, quality decisions and short segments are the deliverables of the
last stages of a production and are validated here so bad provider output
cannot reach the filesystem.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

_MAX_HASHTAG_LEN = 30


class Metadata(BaseModel):
    """YouTube-style metadata for one deliverable (MAD-001 §30)."""

    title: str
    description: str
    hashtags: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        if len(value) > 120:
            raise ValueError("title must be at most 120 characters")
        return value

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("description must not be empty")
        return value

    @field_validator("hashtags")
    @classmethod
    def _hashtags(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in value:
            tag = tag.strip().lstrip("#")
            if not tag:
                continue
            if len(tag) > _MAX_HASHTAG_LEN or " " in tag or "#" in tag:
                raise ValueError(f"invalid hashtag {tag!r}")
            cleaned.append(f"#{tag}")
        if not cleaned:
            raise ValueError("at least one hashtag is required")
        return cleaned


class MetadataPackage(BaseModel):
    """Metadata for the master and each short (MAD-001 §82, PRD-001 §52)."""

    master: Metadata
    short: Metadata


class QualityDecision(BaseModel):
    """Outcome of quality control for a deliverable (TDD-001 §131).

    A decision cannot both pass and carry mandatory issues: a production may
    only complete when QC passes (MAD-001 §33), so the model rejects that
    contradiction instead of silently downgrading it.
    """

    passed: bool
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _consistent(self) -> "QualityDecision":
        if self.passed and self.issues:
            raise ValueError("passed must be False when issues exist")
        return self


class ShortSegment(BaseModel):
    """A candidate short-form clip within the master (MAD-001 §26)."""

    start_seconds: float = Field(ge=0.0)
    duration_seconds: float = Field(gt=0.0)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str = ""

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason must not be empty")
        return value
