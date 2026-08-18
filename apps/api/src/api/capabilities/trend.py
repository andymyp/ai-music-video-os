"""Trend research capability contract (TDD-001 §27-29).

Trend providers discover platform signals for a query; the Trend Research
Agent later aggregates/ranks them (TDD-001 §28-29) into a domain
:class:`~api.domain.creative.TrendResult`. Scoring is deterministic where
possible (TDD-001 §29), so providers expose raw signals with a normalized
``score`` in [0, 1].
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator


class TrendQuery(BaseModel):
    """A query for trend discovery."""

    keyword: str | None = None
    genre: str | None = None
    platforms: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)
    time_window_days: int = Field(default=7, ge=1, le=365)

    @model_validator(mode="after")
    def _has_anchor(self) -> "TrendQuery":
        if not self.keyword and not self.genre:
            raise ValueError("TrendQuery needs a keyword or a genre")
        return self


class TrendSignal(BaseModel):
    """A single observed trend from one platform (TDD-001 §29).

    ``score`` is a normalized 0-1 relevance/recency score used for ranking.
    """

    topic: str
    platform: str | None = None
    score: float = Field(ge=0, le=1)
    growth: float | None = None
    volume: int | None = Field(default=None, ge=0)
    recency: datetime | None = Field(default=None)
    summary: str | None = None

    @field_validator("topic")
    @classmethod
    def _topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("topic must not be empty")
        return value


@runtime_checkable
class TrendProvider(Protocol):
    """A provider that discovers trend signals."""

    async def discover(
        self,
        query: TrendQuery,
    ) -> list[TrendSignal]:
        """Return trend signals matching *query*."""
        ...
