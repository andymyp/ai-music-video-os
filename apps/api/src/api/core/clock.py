"""Time helpers (MAD-001 §61, §140: all persisted timestamps are UTC).

Kept dependency-free so domain models can rely on it without pulling in
infrastructure concerns. ``utc_now`` is the single source of "now" for the
backend so tests can patch it deterministically.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware ``datetime``."""
    return datetime.now(timezone.utc)


def utc_naive(value: datetime) -> datetime:
    """Return *value* as a naive UTC datetime (SQLite loses tzinfo)."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
