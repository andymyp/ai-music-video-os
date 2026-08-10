"""Shared fixtures for backend tests.

Each test runs against an isolated data directory under the pytest ``tmp_path``
so tests never write into the real ``data/`` directory.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from api.config.settings import AppSettings


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
