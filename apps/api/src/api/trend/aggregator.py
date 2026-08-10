"""Trend aggregation (TDD-001 §28).

Combines trend signals from every enabled TREND provider into a single stream,
deduplicates by ``(topic, platform)`` and computes the cross-platform presence
component used by the scoring engine. Providers run in parallel; a failing
provider is skipped rather than losing the others' signals (TDD-001 §28).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from api.capabilities import Capability, ProviderRegistry, TrendQuery, TrendSignal
from api.core.errors import ToolError


@dataclass(frozen=True)
class RawTrendSignal:
    """A signal tagged with the provider that produced it."""

    signal: TrendSignal
    provider_id: str


class TrendAggregator:
    """Discover + combine signals across all enabled trend providers."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    def providers(self) -> list[Any]:
        """Enabled trend providers in resolution order."""
        return self._registry.resolve_all(Capability.TREND)

    def provider_ids(self) -> list[str]:
        """Stable identifiers of the enabled providers (for cache keys)."""
        return sorted(
            getattr(provider, "model", None) or type(provider).__name__
            for provider in self.providers()
        )

    async def discover_all(self, query: TrendQuery) -> list[RawTrendSignal]:
        """Query all enabled providers in parallel and merge their signals."""
        providers = self.providers()
        if not providers:
            raise ToolError("no enabled trend provider")
        results = await asyncio.gather(
            *(provider.discover(query) for provider in providers),
            return_exceptions=True,
        )
        raw: list[RawTrendSignal] = []
        for provider, result in zip(providers, results):
            if isinstance(result, BaseException):
                continue  # skip a failing source, keep the rest (TDD-001 §28)
            provider_id = getattr(provider, "model", None) or type(provider).__name__
            for signal in result or []:
                raw.append(RawTrendSignal(signal=signal, provider_id=provider_id))
        if not raw:
            raise ToolError("all trend providers failed")
        return self._dedupe(raw)

    @staticmethod
    def _dedupe(raw: list[RawTrendSignal]) -> list[RawTrendSignal]:
        """Keep the highest-scoring signal per ``(topic, platform)`` pair."""
        best: dict[tuple[str, str | None], RawTrendSignal] = {}
        for item in raw:
            key = (item.signal.topic, item.signal.platform)
            prev = best.get(key)
            if prev is None or item.signal.score > prev.signal.score:
                best[key] = item
        return list(best.values())

    @staticmethod
    def cross_platform_scores(raw: list[RawTrendSignal], query: TrendQuery) -> dict[str, float]:
        """Fraction of the query's platforms each topic appears on (0..1)."""
        platform_set = query.platforms or sorted(
            {item.signal.platform for item in raw if item.signal.platform} or ["unknown"]
        )
        denominator = max(len(platform_set), 1)
        per_topic: dict[str, set[str | None]] = {}
        for item in raw:
            per_topic.setdefault(item.signal.topic, set()).add(item.signal.platform)
        return {
            topic: round(len(platforms) / denominator, 3)
            for topic, platforms in per_topic.items()
        }


__all__ = ["RawTrendSignal", "TrendAggregator"]
