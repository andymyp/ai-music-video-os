"""Shared fixtures for backend tests.

Each test runs against an isolated data directory under the pytest ``tmp_path``
so tests never write into the real ``data/`` directory.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.config.settings import AppSettings
from api.database.base import Base


@pytest.fixture
def db_engine():
    """An isolated in-memory SQLite engine with all tables created."""
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(db_engine) -> sessionmaker:
    """A session factory bound to the isolated in-memory engine."""
    return sessionmaker(bind=db_engine)


@pytest.fixture
def db_session(session_factory):
    """A bare session for direct ORM assertions (caller controls the transaction)."""
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def settings(tmp_path) -> AppSettings:
    data_dir = tmp_path / "data"
    return AppSettings(
        app_env="test",
        provider_mode="mock",
        log_level="WARNING",
        app_data_dir=data_dir,
        database_url=f"sqlite:///{(data_dir / 'database' / 'test.db').as_posix()}",
        temporal_address="localhost:7233",
    )


@pytest.fixture
def env_marker() -> Iterator[None]:
    """Placeholder for future environment-scoped fixtures."""
    yield
