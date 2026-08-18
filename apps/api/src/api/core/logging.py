"""Structured logging for the backend (Phase 22 — Observability, MASTER §35).

Emit one JSON object per log record with a stable field vocabulary so logs can be
shipped to a structured sink and correlated across a production run:

* identity — ``timestamp``, ``level``, ``logger``, ``message``
* operational context — ``production_id``, ``workflow_id``, ``stage``,
  ``component``, ``event``, ``severity``, ``duration_ms``, ``status``
* provider attribution — ``provider``, ``model``
* failures — ``error``, ``exception``

Context fields come from two places:

1. the :func:`logging_context` scope, a task-local (contextvars) mapping that an
   activity/request wraps itself in so concurrent productions never leak fields
   into each other's log lines (MAD-001 §49);
2. ``extra=`` keyword arguments on the logger call, merged onto the record.

Sensitive values (API keys, tokens, passwords, credentials, authorization
headers) are redacted recursively before anything is emitted.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from api.config.settings import AppSettings

#: Standard :class:`logging.LogRecord` attributes — never emitted as context
#: fields (they are identity/reserved plumbing, not structured data).
_RESERVED_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
    }
)

#: Substrings that mark a key as sensitive; any matching value is redacted.
_SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "private_key",
    "client_secret",
)

#: Task-local context. Defaults to a shared empty mapping; every scope installs a
#: fresh merged copy, so the default is never mutated.
_LOGGING_CONTEXT: contextvars.ContextVar[dict[str, object]] = contextvars.ContextVar(
    "amv_logging_context", default={}
)


@contextmanager
def logging_context(**fields: object) -> Iterator[None]:
    """Scope structured fields to the current task for the duration of the block.

    Nested scopes merge outward fields; the previous scope is restored on exit
    even when the block raises. Typical use wraps an activity body::

        with logging_context(production_id=pid, stage="render_master"):
            logger.info("render started")

    The value of ``fields`` is intentionally shallow — a whole nested document
    would defeat the point of a flat, queryable log line.
    """
    parent = _LOGGING_CONTEXT.get()
    token = _LOGGING_CONTEXT.set({**parent, **fields})
    try:
        yield
    finally:
        _LOGGING_CONTEXT.reset(token)


def _is_sensitive(key: str) -> bool:
    lowered = key.lower().replace(" ", "_")
    return any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _redact(value: Any) -> Any:
    """Replace sensitive values with ``"***"`` recursively over dicts/lists."""
    if isinstance(value, dict):
        return {key: ("***" if _is_sensitive(key) else _redact(item)) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


class StructuredFormatter(logging.Formatter):
    """Render log records as single-line JSON with context + extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_LOGGING_CONTEXT.get())
        for key, value in record.__dict__.items():
            if key in _RESERVED_ATTRS or key in payload:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(_redact(payload), default=str, sort_keys=True)


def get_logger(component: str) -> logging.Logger:
    """Return a logger tagged with ``component`` in its ``logger`` field.

    Components are dotted namespaces under ``amv`` (e.g. ``amv.pipeline``,
    ``amv.providers``) so a log line is attributable at a glance without a
    separate context field.
    """
    return logging.getLogger(f"amv.{component}")


_configured = False


def configure_logging(settings: AppSettings) -> None:
    """Install a single structured handler on the root logger (once).

    ``create_app``/worker call this per startup and pytest calls ``create_app``
    per test, so a guard keeps handler installation idempotent — replacing the
    root handler list on every call would drop pytest's ``caplog`` handler.
    """
    global _configured
    if _configured:
        return
    _configured = True
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
