"""Operational metrics store (MASTER §35, MAD-001 §49-50).

A small SQLite-backed store that records one row per measurable operation and
rolls the raw rows up into :class:`MetricsSummary` aggregates. The store is
deliberately dependency-free (plain :mod:`sqlite3`) so the API and the Temporal
worker can both write to it without any extra service.

Recorded operations carry a fixed vocabulary (operation, component, status,
provider, model, production_id, workflow_id, stage, duration_ms, detail,
recorded_at) matching the structured-log fields in :mod:`api.core.logging`, so a
metric row and a log line for the same event line up 1:1.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from api.core.clock import utc_now

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    operation     TEXT    NOT NULL,
    component     TEXT,
    status        TEXT    NOT NULL,
    provider      TEXT,
    model         TEXT,
    production_id TEXT,
    workflow_id   TEXT,
    stage         TEXT,
    duration_ms   REAL,
    detail        TEXT,
    recorded_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_operation ON metrics(operation);
CREATE INDEX IF NOT EXISTS idx_metrics_recorded_at ON metrics(recorded_at);
"""


class MetricsSummary(BaseModel):
    """Aggregates over the recorded operations (MAD-001 §50).

    All averages are ``0.0`` and counts ``0`` on an empty store, so a caller can
    render the summary without special-casing "no data yet".
    """

    total_operations: int = 0
    failures: int = 0
    provider_calls: int = 0
    provider_failures: int = 0
    provider_latency_avg_ms: float = 0.0
    provider_failure_rate: float = 0.0
    render_duration_avg_ms: float = 0.0
    qc_failures: int = 0
    workflow_runs: int = 0
    workflow_failures: int = 0
    completed_productions: int = 0
    production_duration_avg_s: float = 0.0

    @property
    def healthy(self) -> bool:
        """Production-healthy iff no recorded failure of any kind."""
        return self.failures == 0


class MetricsStore:
    """SQLite-backed append-only metrics store.

    Writes are serialized with a process lock and use autocommit transactions
    (``isolation_level=None``) so a write is durable even if another worker
    thread records concurrently. ``detail`` is stored as JSON.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        #: In-process start times keyed by production_id, used to measure
        #: production wall-clock duration. Lost on process restart, which is fine
        #: for an observability aggregate.
        self._production_start: dict[str, datetime] = {}
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(_SCHEMA)
            finally:
                conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10.0, isolation_level=None)

    # --- recording -----------------------------------------------------------

    def record(
        self,
        operation: str,
        *,
        component: str | None = None,
        status: str = "ok",
        provider: str | None = None,
        model: str | None = None,
        production_id: str | None = None,
        workflow_id: str | None = None,
        stage: str | None = None,
        duration_ms: float | None = None,
        detail: Any = None,
    ) -> None:
        """Insert one operation row."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO metrics (operation, component, status, provider, model,"
                    " production_id, workflow_id, stage, duration_ms, detail, recorded_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        operation,
                        component,
                        status,
                        provider,
                        model,
                        production_id,
                        workflow_id,
                        stage,
                        duration_ms,
                        json.dumps(detail, default=str) if detail is not None else None,
                        utc_now().isoformat(),
                    ),
                )
            finally:
                conn.close()

    def record_production_start(self, production_id: str) -> None:
        """Mark the start of a production's lifecycle (first run this process)."""
        if production_id in self._production_start:
            return
        self._production_start[production_id] = utc_now()
        self.record("production.start", production_id=production_id)

    def record_production_completed(self, production_id: str) -> float | None:
        """Close the production's lifecycle, measuring total duration.

        Returns the elapsed duration in ms (or ``None`` if the start was never
        recorded in this process), so the caller can reuse it for the
        ``workflow.run`` row that shares the same lifecycle.
        """
        started = self._production_start.pop(production_id, None)
        duration_ms = (utc_now() - started).total_seconds() * 1000.0 if started else None
        self.record(
            "production.completed",
            production_id=production_id,
            status="ok",
            duration_ms=duration_ms,
        )
        if duration_ms is not None:
            self.record(
                "production.duration",
                production_id=production_id,
                duration_ms=duration_ms,
            )
        return duration_ms

    # --- inspection ----------------------------------------------------------

    def count(self) -> int:
        with self._lock:
            conn = self._connect()
            try:
                return int(conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0])
            finally:
                conn.close()

    def rows(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT operation, component, status, provider, model, production_id,"
                    " workflow_id, stage, duration_ms, recorded_at FROM metrics"
                    " ORDER BY id LIMIT ?",
                    (limit,),
                )
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def clear(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM metrics")
            finally:
                conn.close()

    # --- aggregates (MAD-001 §50) -------------------------------------------

    def _scalar(self, query: str, params: tuple[Any, ...] = ()) -> Any:
        with self._lock:
            conn = self._connect()
            try:
                return conn.execute(query, params).fetchone()[0]
            finally:
                conn.close()

    def summary(self) -> MetricsSummary:
        total = int(self._scalar("SELECT COUNT(*) FROM metrics") or 0)
        failures = int(self._scalar("SELECT COUNT(*) FROM metrics WHERE status != 'ok'") or 0)

        provider_calls = int(
            self._scalar("SELECT COUNT(*) FROM metrics WHERE operation = 'provider.call'") or 0
        )
        provider_failures = int(
            self._scalar(
                "SELECT COUNT(*) FROM metrics WHERE operation = 'provider.call' AND status != 'ok'"
            )
            or 0
        )
        provider_latency = float(
            self._scalar(
                "SELECT AVG(duration_ms) FROM metrics"
                " WHERE operation = 'provider.call' AND duration_ms IS NOT NULL"
            )
            or 0.0
        )
        render_avg = float(
            self._scalar(
                "SELECT AVG(duration_ms) FROM metrics"
                " WHERE operation IN ('stage.render_master', 'stage.render_short')"
                " AND duration_ms IS NOT NULL"
            )
            or 0.0
        )
        qc_failures = int(
            self._scalar(
                "SELECT COUNT(*) FROM metrics WHERE operation = 'stage.run_qc' AND status != 'ok'"
            )
            or 0
        )
        workflow_runs = int(
            self._scalar("SELECT COUNT(*) FROM metrics WHERE operation = 'workflow.run'") or 0
        )
        workflow_failures = int(
            self._scalar(
                "SELECT COUNT(*) FROM metrics WHERE operation = 'workflow.run' AND status != 'ok'"
            )
            or 0
        )
        completed = int(
            self._scalar(
                "SELECT COUNT(*) FROM metrics WHERE operation = 'production.duration'"
            )
            or 0
        )
        duration_avg = float(
            self._scalar(
                "SELECT AVG(duration_ms) FROM metrics"
                " WHERE operation = 'production.duration' AND duration_ms IS NOT NULL"
            )
            or 0.0
        )

        return MetricsSummary(
            total_operations=total,
            failures=failures,
            provider_calls=provider_calls,
            provider_failures=provider_failures,
            provider_latency_avg_ms=round(provider_latency, 3),
            provider_failure_rate=round(provider_failures / provider_calls, 4) if provider_calls else 0.0,
            render_duration_avg_ms=round(render_avg, 3),
            qc_failures=qc_failures,
            workflow_runs=workflow_runs,
            workflow_failures=workflow_failures,
            completed_productions=completed,
            production_duration_avg_s=round(duration_avg / 1000.0, 3),
        )
