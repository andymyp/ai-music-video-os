"""SQLite engine bootstrap.

SQLite stores application metadata (MAD-001 §10, §53); binary media lives on
the filesystem. This module only establishes connectivity — Phase 02 adds the
SQLAlchemy models, repositories, and Alembic migrations.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.config.settings import AppSettings


def _sqlite_path_from_url(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None
    return Path(url[len("sqlite:///"):])


def create_engine_from_settings(settings: AppSettings) -> Engine:
    """Create a SQLAlchemy engine for the configured database URL."""
    url = settings.resolved_database_url()
    kwargs: dict[str, object] = {}
    if url.startswith("sqlite"):
        db_path = _sqlite_path_from_url(url)
        if db_path is not None:
            parent = db_path.parent
            if str(parent) and str(parent) != ".":
                parent.mkdir(parents=True, exist_ok=True)
        # SQLite is used from FastAPI's async threadpool; allow cross-thread use.
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def verify_database(engine: Engine) -> None:
    """Raise if the database is not reachable."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def connect_database(settings: AppSettings) -> Engine:
    """Create an engine and verify connectivity."""
    engine = create_engine_from_settings(settings)
    verify_database(engine)
    return engine
