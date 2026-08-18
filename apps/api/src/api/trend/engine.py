"""Trend engine facade (MASTER §21; MAD-001 §15-16; TDD-001 §28-29, §108).

Orchestrates the Phase 11 pipeline for a single query:

    TrendProvider(s) → TrendAggregator → TrendScoringEngine → ranked results

Results are cached for a short configurable TTL (TDD-001 §108) and signals whose
recency is older than the configured maximum age are dropped so stale results are
never presented as current trends (MASTER §21).
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from api.capabilities import ProviderRegistry, TrendQuery
from api.core.clock import utc_now
from api.domain.creative import TrendResult
from api.trend.aggregator import TrendAggregator
from api.trend.cache import TrendCache
from api.trend.scoring import TrendScoringEngine
from api.trend.weights import TrendWeights


class TrendEngine:
    """Aggregate → score → rank → cache trend signals for a query."""

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        weights: TrendWeights | None = None,
        cache: TrendCache | None = None,
        clock: Callable[[], datetime] | None = None,
        max_signal_age_days: int = 30,
    ) -> None:
        self._clock = clock or utc_now
        self._weights = weights or TrendWeights()
        self._max_signal_age_days = max_signal_age_days
        self._aggregator = TrendAggregator(registry)
        self._scorer = TrendScoringEngine(self._weights, clock=self._clock)
        self._cache = cache or TrendCache(clock=self._clock)

    @property
    def weights(self) -> TrendWeights:
        return self._weights

    @property
    def cache(self) -> TrendCache:
        return self._cache

    @property
    def max_signal_age_days(self) -> int:
        return self._max_signal_age_days

    async def search(self, query: TrendQuery) -> list[TrendResult]:
        """Return fresh, scored, ranked results for *query* (deterministic order)."""
        provider_ids = self._aggregator.provider_ids()
        cached = self._cache.get(provider_ids, query)
        if cached is not None:
            return cached.result

        raw = await self._aggregator.discover_all(query)
        cross = self._aggregator.cross_platform_scores(raw, query)
        scored = [
            self._scorer.score(item.signal, query, cross.get(item.signal.topic, 0.0))
            for item in raw
        ]
        now = self._clock()
        fresh = [
            result
            for result in scored
            if not self._scorer.is_stale(
                result, now=now, max_age_days=self._max_signal_age_days
            )
        ]
        fresh.sort(key=lambda r: (-r.score, r.topic))
        self._cache.put(provider_ids, query, fresh)
        return fresh


__all__ = ["TrendEngine"]
