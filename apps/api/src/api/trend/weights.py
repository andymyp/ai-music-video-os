"""Trend scoring weights (MAD-001 §16; TDD-001 §29).

The initial scoring model is a weighted composite of five normalized components
(growth, volume, cross-platform presence, recency, content relevance). Weights
must be configurable (MAD-001 §16) and are validated to be non-negative and to
sum to 1.0 so the composite stays a 0-1 score that maps onto ``TrendResult.score``
(0-100).
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

#: Default weights per MAD-001 §16.
DEFAULT_TREND_WEIGHTS: dict[str, float] = {
    "growth": 0.30,
    "volume": 0.25,
    "cross_platform": 0.20,
    "recency": 0.15,
    "content_fit": 0.10,
}

#: Names of the five score components, in the order they appear in the composite.
COMPONENTS: tuple[str, ...] = (
    "growth",
    "volume",
    "cross_platform",
    "recency",
    "content_fit",
)


class TrendWeights(BaseModel):
    """Configurable weights for the weighted trend composite (MAD-001 §16)."""

    growth: float = Field(default=DEFAULT_TREND_WEIGHTS["growth"], ge=0.0, le=1.0)
    volume: float = Field(default=DEFAULT_TREND_WEIGHTS["volume"], ge=0.0, le=1.0)
    cross_platform: float = Field(default=DEFAULT_TREND_WEIGHTS["cross_platform"], ge=0.0, le=1.0)
    recency: float = Field(default=DEFAULT_TREND_WEIGHTS["recency"], ge=0.0, le=1.0)
    content_fit: float = Field(default=DEFAULT_TREND_WEIGHTS["content_fit"], ge=0.0, le=1.0)

    @field_validator("growth", "volume", "cross_platform", "recency", "content_fit")
    @classmethod
    def _non_negative(cls, value: float) -> float:
        if value < 0.0:
            raise ValueError("trend weights must be non-negative")
        return value

    @model_validator(mode="after")
    def _sums_to_one(self) -> "TrendWeights":
        total = (
            self.growth
            + self.volume
            + self.cross_platform
            + self.recency
            + self.content_fit
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"trend weights must sum to 1.0 (got {total:.6f})")
        return self

    def to_mapping(self) -> dict[str, float]:
        """Return the weights keyed by component name."""
        return {
            "growth": self.growth,
            "volume": self.volume,
            "cross_platform": self.cross_platform,
            "recency": self.recency,
            "content_fit": self.content_fit,
        }

    def composite(self, components: dict[str, float]) -> float:
        """Weighted sum of normalized *components* (each key must be present)."""
        mapping = self.to_mapping()
        return sum(mapping[name] * components[name] for name in COMPONENTS)


__all__ = [
    "COMPONENTS",
    "DEFAULT_TREND_WEIGHTS",
    "TrendWeights",
]
