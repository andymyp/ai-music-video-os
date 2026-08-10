"""Structured logging for the backend.

Minimal structured (JSON-line) logging for Phase 00. Logging is expanded in
Phase 22 (Observability) with production/workflow context fields per MAD-001 §49.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from api.config.settings import AppSettings


class StructuredFormatter(logging.Formatter):
    """Render log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: AppSettings) -> None:
    """Install a single structured handler on the root logger."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
