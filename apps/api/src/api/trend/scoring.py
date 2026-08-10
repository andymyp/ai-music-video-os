"""Trend scoring engine (MAD-001 §16; TDD-001 §29).

Normalizes each raw trend signal into the five weighted components (growth,
volume, cross-platform presence, recency, content relevance) and produces the
deterministic 0-100 composite score that the Trend Engine ranks on. All
normalization is bounded and deterministic; the weights are configurable via
:class:`~api.trend.weights.TrendWeights`.
"""
from __future__ import annotations

import zlib
from datetime import datetime
from typing import Callable

from api.capabilities import TrendQuery, TrendSignal
from api.core.clock import utc_now
from api.domain.creative import TrendResult
from api.trend.weights import COMPONENTS, TrendWeights

#: Reference volume (matching the existing agent normalization) — a raw volume of
#: 10_000 maps to a full-volume score of 1.0.
_VOLUME_REFERENCE = 10_000.0

#: Floor for the deterministic content-fit fallback of non-matching topics.
_CONTENT_FIT_FLOOR = 0.3


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _age_days(now: datetime, recency: datetime) -> float:
    delta = now - recency
    return max(0.0, delta.total_seconds() / 86400.0)


def _deterministic_fraction(seed: str) -> float:
    """Deterministic 0.3..1.0 fraction from *seed* (stable across runs)."""
    return _CONTENT_FIT_FLOOR + (zlib.crc32(seed.encode("utf-8")) % 71) / 100.0


def _content_fit(topic: str, query: TrendQuery) -> float:
    """Deterministic relevance of *topic* to the query anchor (genre/keyword)."""
    anchor = (query.genre or query.keyword or "").strip().lower()
    if anchor and anchor in topic.lower():
        return 1.0
    return round(_deterministic_fraction(f"fit:{topic}"), 2)


def _recency_score(now: datetime, recency: datetime, time_window_days: int) -> float:
    """Recency score: 1.0 when fresh, decaying linearly to 0.0 at window edge."""
    window_days = max(float(time_window_days), 1.0)
    return round(max(0.0, 1.0 - _age_days(now, recency) / window_days), 3)


class TrendScoringEngine:
    """Computes the weighted composite score for trend signals."""

    def __init__(
        self,
        weights: TrendWeights | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._weights = weights or TrendWeights()
        self._clock = clock or utc_now

    @property
    def weights(self) -> TrendWeights:
        return self._weights

    def components(self, signal: TrendSignal, query: TrendQuery, cross_platform: float) -> dict[str, float]:
        """Return the five normalized component scores for *signal*."""
        now = self._clock()
        recency = signal.recency or now
        growth = float(signal.growth or 0.0)
        volume = float(signal.volume or 0)
        return {
            "growth": round(_clamp01(growth), 3),
            "volume": round(_clamp01(volume / _VOLUME_REFERENCE), 3),
            "cross_platform": round(_clamp01(cross_platform), 3),
            "recency": _recency_score(now, recency, query.time_window_days),
            "content_fit": _content_fit(signal.topic, query),
        }

    def score(self, signal: TrendSignal, query: TrendQuery, cross_platform: float) -> TrendResult:
        """Score a single signal into a domain :class:`TrendResult`."""
        components = self.components(signal, query, cross_platform)
        now = self._clock()
        composite = self._weights.composite(components)
        recency = signal.recency or now
        return TrendResult(
            source=signal.platform or "unknown",
            topic=signal.topic,
            genre=query.genre,
            score=round(100.0 * composite, 1),
            confidence=round(min(0.95, 0.4 + 0.6 * composite), 3),
            recency=recency,
            evidence=[
                f"{name}={components[name]:.3f}" for name in COMPONENTS
            ],
            growth=components["growth"],
            volume=components["volume"],
            cross_platform=components["cross_platform"],
            content_fit=components["content_fit"],
            reasoning=signal.summary or "",
        )

    def is_stale(self, result: TrendResult, *, now: datetime | None = None, max_age_days: int) -> bool:
        """True when *result*'s recency is older than *max_age_days*."""
        now = now or self._clock()
        return _age_days(now, result.recency) > float(max_age_days)


__all__ = ["TrendScoringEngine"]
