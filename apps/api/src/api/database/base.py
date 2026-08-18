"""SQLAlchemy declarative base (TDD-001 §18, MAD-001 §10, ADR-005).

All persisted timestamps are UTC (TDD-001 §140). SQLite stores datetimes
without timezone info, so we persist naive UTC and re-attach ``timezone.utc``
when reconstructing domain objects.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase

from api.core.clock import utc_naive  # noqa: F401  (single source of truth)


def utc_aware(value: datetime | None) -> datetime | None:
    """Attach ``timezone.utc`` to a naive UTC datetime read from SQLite."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
