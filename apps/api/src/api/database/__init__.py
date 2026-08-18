"""Database layer (TDD-001 §18-21, §123; MAD-001 §10, ADR-005).

Phase 02 adds the SQLAlchemy models for the twelve metadata tables, repository
interfaces + SQLite implementations, a transactional session scope, and Alembic
migrations. Binary media stays on the filesystem (MAD-001 §53).
"""
from __future__ import annotations

from api.database.base import Base, utc_aware, utc_naive
from api.database.engine import connect_database, create_engine_from_settings, verify_database
from api.database.repositories import (
    AssetRepository,
    ProviderRun,
    ProviderRunRepository,
    ProductionRepository,
    SQLiteAssetRepository,
    SQLiteProductionRepository,
    SQLiteProviderRunRepository,
    SQLiteWorkflowRepository,
    WorkflowRepository,
    WorkflowRun,
    make_asset_repository,
    make_production_repository,
    make_provider_run_repository,
    make_workflow_repository,
)
from api.database.session import create_session_factory, session_scope

__all__ = [
    # engine
    "connect_database",
    "create_engine_from_settings",
    "verify_database",
    # base + session
    "Base",
    "utc_aware",
    "utc_naive",
    "create_session_factory",
    "session_scope",
    # repositories
    "ProductionRepository",
    "AssetRepository",
    "WorkflowRepository",
    "ProviderRunRepository",
    "SQLiteProductionRepository",
    "SQLiteAssetRepository",
    "SQLiteWorkflowRepository",
    "SQLiteProviderRunRepository",
    "make_production_repository",
    "make_asset_repository",
    "make_workflow_repository",
    "make_provider_run_repository",
    "WorkflowRun",
    "ProviderRun",
]
