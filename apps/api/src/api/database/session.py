"""Session management (TDD-001 §24: DB operations happen inside activities;
this module gives those activities a session factory + transactional scope)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from api.config.settings import AppSettings
from api.database.engine import create_engine_from_settings


def create_session_factory(settings: AppSettings, engine: Engine | None = None) -> sessionmaker[Session]:
    """Build a bound ``sessionmaker`` from settings (or a provided engine)."""
    return sessionmaker(bind=engine or create_engine_from_settings(settings))


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional session, committing on success / rolling back on error.

    This is the single transaction boundary: an exception rolls back the whole
    scope (MASTER_EXECUTION.md §12 validation requires transactional safety).
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
