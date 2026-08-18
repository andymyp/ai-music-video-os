"""Observability instrumentation helpers (MASTER §35, MAD-001 §49-50).

The two seams the whole phase is built on:

* :class:`OperationLogger` — an async context manager that times a block,
  records a metric row and emits a structured log line on exit, tagging both
  with ``production_id``/``stage``/``provider``/``model``/``event`` etc.;
* :func:`instrument` — a thin decorator that wraps an async activity with an
  ``OperationLogger`` so stage durations, failures and log lines are captured
  without touching the stage body.

The metrics store is a process-wide singleton installed by
:func:`init_metrics` (the worker does this at startup) with a
:class:`NullMetricsStore` fallback so un-instrumented tests and one-off scripts
run without a database. ``set_metrics``/``get_metrics`` mirror the
``set_activity_services`` pattern used elsewhere in the codebase.
"""

from __future__ import annotations

import functools
import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

from api.config.settings import AppSettings
from api.core.logging import get_logger, logging_context
from api.core.metrics import MetricsStore, MetricsSummary

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])

#: Logger used for instrumentation's own log lines (metrics/logging tests read
#: the ``amv.observability`` logger name from emitted records).
_INSTRUMENT_LOGGER = get_logger("observability")


class NullMetricsStore:
    """No-op metrics sink used when no store has been configured.

    Matches :class:`MetricsStore`'s public surface so instrumentation code does
    not branch on whether a store exists.
    """

    def record(self, *args: Any, **kwargs: Any) -> None:
        """No-op — nothing to record."""

    def record_production_start(self, production_id: str) -> None:
        """No-op — nothing to record."""

    def record_production_completed(self, production_id: str) -> float | None:
        """No-op — nothing to record."""
        return None

    def record_performance_sample(self, production_id: str, sample: Any) -> None:
        """No-op — nothing to record."""

    def count(self) -> int:
        return 0

    def clear(self) -> None:
        """No-op — nothing to clear."""

    def summary(self) -> MetricsSummary:
        return MetricsSummary()


_METRICS: Any = NullMetricsStore()


def set_metrics(store: Any) -> None:
    """Install the process-wide metrics store."""
    global _METRICS
    _METRICS = store


def get_metrics() -> Any:
    """Return the process-wide metrics store (never ``None``)."""
    return _METRICS


def init_metrics(settings: AppSettings | None = None, *, path: Path | str | None = None) -> MetricsStore:
    """Build and install the application metrics store.

    Defaults to ``<app_data_dir>/database/metrics.db``. Returns the store so the
    caller can keep a reference for tests/inspection.
    """
    resolved = path
    if resolved is None:
        base = settings.app_data_dir if settings is not None else Path("data")
        resolved = Path(base) / "database" / "metrics.db"
    store = MetricsStore(resolved)
    set_metrics(store)
    return store


def _production_id_from(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
    """Best-effort production_id extraction from a stage activity's call args."""
    if "production_id" in kwargs:
        return kwargs["production_id"]
    if args and isinstance(args[0], str) and len(args[0]) > 0:
        return args[0]
    return None


class OperationLogger:
    """Timed async context manager that records a metric + structured log line.

    Use directly when instrumentation needs custom fields (e.g. provider/model
    inside a failover loop)::

        async with OperationLogger("provider.call", component="music",
                                   provider=pid, model=model) as op:
            result = await call(provider)
    """

    def __init__(
        self,
        operation: str,
        *,
        component: str | None = None,
        event: str | None = None,
        production_id: str | None = None,
        workflow_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        stage: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.operation = operation
        self.component = component
        self.event = event
        self.production_id = production_id
        self.workflow_id = workflow_id
        self.provider = provider
        self.model = model
        self.stage = stage
        self.logger = logger or _INSTRUMENT_LOGGER
        self._started = time.perf_counter()
        self.duration_ms = 0.0

    async def __aenter__(self) -> "OperationLogger":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.duration_ms = (time.perf_counter() - self._started) * 1000.0
        ok = exc_type is None
        error = str(exc) if not ok else None
        fields: dict[str, Any] = {
            "component": self.component,
            "event": self.event,
            "severity": "info" if ok else "error",
            "status": "ok" if ok else "error",
            "duration_ms": round(self.duration_ms, 3),
            "provider": self.provider,
            "model": self.model,
            "production_id": self.production_id,
            "workflow_id": self.workflow_id,
            "stage": self.stage,
        }
        if error is not None:
            fields["error"] = error
        get_metrics().record(
            self.operation,
            component=self.component,
            status="ok" if ok else "error",
            provider=self.provider,
            model=self.model,
            production_id=self.production_id,
            workflow_id=self.workflow_id,
            stage=self.stage,
            duration_ms=self.duration_ms,
        )
        with logging_context(**{key: value for key, value in fields.items() if value is not None}):
            (self.logger.info if ok else self.logger.error)(
                f"{self.operation} {'ok' if ok else 'failed'}"
            )


def instrument(
    component: str,
    event: str,
    *,
    operation: str | None = None,
) -> Callable[[F], F]:
    """Decorate an async activity to time/record/log it.

    The activity's first positional arg (the ``production_id`` in the pipeline
    stages) is captured into the metric/log context. The metric operation
    defaults to ``stage.<event>`` so the stage-name aggregates in
    :class:`MetricsStore.summary` work out of the box.
    """
    metrics_operation = operation or f"stage.{event}"

    def decorate(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            production_id = _production_id_from(args, kwargs)
            async with OperationLogger(
                metrics_operation,
                component=component,
                event=event,
                stage=event,
                production_id=production_id,
            ):
                return await fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorate


__all__ = [
    "NullMetricsStore",
    "OperationLogger",
    "instrument",
    "get_metrics",
    "set_metrics",
    "init_metrics",
    "MetricsStore",
]
