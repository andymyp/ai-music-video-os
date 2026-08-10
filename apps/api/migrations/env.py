"""Alembic environment (TDD-001 §18, ADR-005).

The database URL resolves from application settings, so ``alembic upgrade head``
targets the same SQLite database the API uses. Tests can override the URL by
pre-setting ``sqlalchemy.url`` on the Alembic Config before invoking commands.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from api.config.settings import get_settings
from api.database.models import Base  # noqa: F401  (registers all tables)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Only fall back to settings when no URL was provided (tests inject their own).
if config.get_main_option("sqlalchemy.url") is None:
    settings = get_settings()
    config.set_main_option("sqlalchemy.url", settings.resolved_database_url())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to script.output)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite ALTER requires batch mode
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (run against a live connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
