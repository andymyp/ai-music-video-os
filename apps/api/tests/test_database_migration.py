"""Alembic migration tests (MASTER_EXECUTION.md §12: migration validation).

Runs the real migration chain against a throwaway SQLite file via the alembic
command API, then verifies the schema and that repositories work on the
migrated database.
"""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from api.database.repositories import make_production_repository
from api.database.session import session_scope
from api.domain.production import Production

ROOT = Path(__file__).resolve().parents[3]  # repo root (pyproject.toml)
EXPECTED_TABLES = {
    "productions",
    "production_configs",
    "creative_concepts",
    "music_strategies",
    "visual_strategies",
    "trend_results",
    "assets",
    "workflow_runs",
    "provider_runs",
    "metadata",
    "qc_reports",
    "events",
}


def _alembic_config(db_path: Path) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "apps" / "api" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return cfg


def test_upgrade_creates_all_tables(tmp_path):
    db_path = tmp_path / "migrated.db"
    command.upgrade(_alembic_config(db_path), "head")

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        tables = set(inspect(engine).get_table_names())
        assert EXPECTED_TABLES <= tables
    finally:
        engine.dispose()


def test_migrated_database_supports_repositories(tmp_path):
    db_path = tmp_path / "migrated.db"
    command.upgrade(_alembic_config(db_path), "head")

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    factory = sessionmaker(bind=engine)
    try:
        production = Production(mode="genre", genre="lofi", branding_text="CH")
        with session_scope(factory) as session:
            make_production_repository(session).create(production)
        with session_scope(factory) as session:
            loaded = make_production_repository(session).get(production.id)
            assert loaded is not None
            assert loaded.genre == "lofi"
            assert loaded.branding_text == "CH"
    finally:
        engine.dispose()


def test_downgrade_to_base_drops_tables(tmp_path):
    db_path = tmp_path / "migrated.db"
    cfg = _alembic_config(db_path)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        tables = set(inspect(engine).get_table_names())
        assert "productions" not in tables
        assert "assets" not in tables
    finally:
        engine.dispose()
