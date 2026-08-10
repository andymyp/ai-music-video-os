"""Trend engine (Phase 11; MASTER §21, MAD-001 §15-16, TDD-001 §27-29 + §108).

A pure-in-process pipeline that aggregates trend signals across providers,
scores them with the configurable weighted composite (MAD-001 §16), ranks them
deterministically and caches the results for a short TTL. The workflow calls it
through the ``trend_search`` tool so the agent boundary stays intact (TDD-001
§93).
"""
from __future__ import annotations

from api.trend.aggregator import RawTrendSignal, TrendAggregator
from api.trend.cache import TrendCache, TrendCacheEntry
from api.trend.engine import TrendEngine
from api.trend.scoring import TrendScoringEngine
from api.trend.weights import (
    COMPONENTS,
    DEFAULT_TREND_WEIGHTS,
    TrendWeights,
)

__all__ = [
    "COMPONENTS",
    "DEFAULT_TREND_WEIGHTS",
    "RawTrendSignal",
    "TrendAggregator",
    "TrendCache",
    "TrendCacheEntry",
    "TrendEngine",
    "TrendScoringEngine",
    "TrendWeights",
]
