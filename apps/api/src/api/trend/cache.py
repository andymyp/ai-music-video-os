"""Trend data caching (TDD-001 §108).

Trend results may be cached for a short configurable period. Each cache entry
records the provider(s), the query, the fetch timestamp, the result and the
expiration. Entries past their expiration are never returned — stale trend
information is treated as a cache miss (TDD-001 §108: "The system must not
treat stale trend information as current").
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Callable

from pydantic import BaseModel

from api.capabilities import TrendQuery
from api.core.clock import utc_now
from api.domain.creative import TrendResult


class TrendCacheEntry(BaseModel):
    """A cached trend result for one provider set + query (TDD-001 §108)."""

    provider_ids: list[str]
    query: TrendQuery
    timestamp: datetime
    result: list[TrendResult]
    expiration: datetime


def _cache_key(provider_ids: list[str], query: TrendQuery) -> str:
    return f"{tuple(sorted(provider_ids))}|{query.model_dump_json()}"


class TrendCache:
    """In-memory TTL cache of scored trend results."""

    def __init__(
        self,
        ttl_seconds: int = 300,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if ttl_seconds < 1:
            raise ValueError("trend cache TTL must be positive")
        self._ttl = timedelta(seconds=ttl_seconds)
        self._clock = clock or utc_now
        self._entries: dict[str, TrendCacheEntry] = {}
        self._lock = threading.Lock()

    @property
    def ttl(self) -> timedelta:
        return self._ttl

    def get(self, provider_ids: list[str], query: TrendQuery) -> TrendCacheEntry | None:
        """Return the fresh entry for *query*, or None when absent/expired."""
        now = self._clock()
        key = _cache_key(provider_ids, query)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expiration <= now:
                del self._entries[key]  # evict stale — never served as current
                return None
            return entry

    def put(self, provider_ids: list[str], query: TrendQuery, result: list[TrendResult]) -> TrendCacheEntry:
        """Store *result* under the provider set + query, expiring after the TTL."""
        now = self._clock()
        entry = TrendCacheEntry(
            provider_ids=sorted(provider_ids),
            query=query,
            timestamp=now,
            result=result,
            expiration=now + self._ttl,
        )
        with self._lock:
            self._entries[_cache_key(provider_ids, query)] = entry
        return entry

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


__all__ = ["TrendCache", "TrendCacheEntry"]
