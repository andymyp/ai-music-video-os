"""Tests for the ORM models (TDD-001 §18-21): table creation, domain
round-trips, relationships, constraints and cascade behavior."""
from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from api.database.models import (
    AssetRow,
    ProductionConfigRow,
    ProductionRow,
)
from api.domain.assets import Asset
from api.domain.enums import AssetStatus, AssetType, ProductionStatus
from api.domain.production import Production, ProductionConfig

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


def test_all_twelve_tables_created(db_engine):
    assert set(inspect(db_engine).get_table_names()) == EXPECTED_TABLES


# --- domain round-trips -------------------------------------------------------

def test_production_round_trip(db_session):
    production = Production(mode="genre", genre="Lo-fi", branding_text="  MY CHANNEL ")
    db_session.add(ProductionRow.from_domain(production))
    db_session.flush()

    back = db_session.get(ProductionRow, production.id).to_domain()
    assert back.id == production.id
    assert back.genre == "lo-fi"
    assert back.branding_text == "MY CHANNEL"
    assert back.status is ProductionStatus.CREATED
    assert back.created_at == production.created_at


def test_status_stored_as_string(db_session):
    production = Production(mode="trending")
    db_session.add(ProductionRow.from_domain(production))
    db_session.flush()

    raw = db_session.execute(
        text("SELECT mode, status FROM productions WHERE id = :id"),
        {"id": production.id},
    ).one()
    assert raw[0] == "trending"
    assert raw[1] == "created"


def test_config_round_trip(db_session):
    production = Production(mode="genre", genre="ambient")
    db_session.add(ProductionRow.from_domain(production))
    db_session.flush()

    config = ProductionConfig(mode="genre", genre="ambient", fps=24, provider_profile="balanced")
    db_session.add(ProductionConfigRow.from_domain(production.id, config))
    db_session.flush()

    row = db_session.execute(
        text("SELECT * FROM production_configs WHERE production_id = :pid"),
        {"pid": production.id},
    ).mappings().one()
    assert row["fps"] == 24
    assert row["provider_profile"] == "balanced"
    assert row["branding_position"] == "bottom-right"


# --- relationships --------------------------------------------------------------

def test_config_one_to_one_relationship(db_session):
    production = Production(mode="trending")
    db_session.add(ProductionRow.from_domain(production))
    db_session.flush()
    db_session.add(
        ProductionConfigRow.from_domain(production.id, ProductionConfig(mode="trending"))
    )
    db_session.flush()

    row = db_session.get(ProductionRow, production.id)
    assert row.config is not None
    assert row.config.to_domain().provider_profile == "mock"


def test_assets_relationship(db_session):
    production = Production(mode="trending")
    db_session.add(ProductionRow.from_domain(production))
    db_session.flush()
    db_session.add(AssetRow.from_domain(Asset(production_id=production.id, type=AssetType.AUDIO_MASTER)))
    db_session.add(AssetRow.from_domain(Asset(production_id=production.id, type=AssetType.MASTER_VIDEO)))
    db_session.flush()

    row = db_session.get(ProductionRow, production.id)
    assert len(row.assets) == 2
    assert {a.type for a in row.assets} == {"audio_master", "master_video"}


def test_asset_round_trip(db_session):
    asset = Asset(
        production_id="prod_" + "A" * 26,
        type=AssetType.MASTER_VIDEO,
        path="data/productions/x/render/master.mp4",
        mime_type="video/mp4",
        size_bytes=2048,
        sha256="ab" * 32,
        status=AssetStatus.READY,
    )
    db_session.add(AssetRow.from_domain(asset))
    db_session.flush()

    back = db_session.get(AssetRow, asset.id).to_domain()
    assert back.path == asset.path
    assert back.type is AssetType.MASTER_VIDEO
    assert back.status is AssetStatus.READY


# --- constraints ----------------------------------------------------------------

def test_duplicate_config_for_production_rejected(db_session):
    production = Production(mode="trending")
    db_session.add(ProductionRow.from_domain(production))
    db_session.flush()
    db_session.add(ProductionConfigRow.from_domain(production.id, ProductionConfig(mode="trending")))
    db_session.flush()
    # Second snapshot for the same production violates the unique constraint.
    db_session.add(ProductionConfigRow.from_domain(production.id, ProductionConfig(mode="trending")))
    with pytest.raises(IntegrityError):
        db_session.flush()


# --- cascade delete --------------------------------------------------------------

def test_production_delete_cascades_children(db_session):
    production = Production(mode="trending")
    db_session.add(ProductionRow.from_domain(production))
    db_session.flush()
    db_session.add(ProductionConfigRow.from_domain(production.id, ProductionConfig(mode="trending")))
    db_session.add(AssetRow.from_domain(Asset(production_id=production.id, type=AssetType.RADIO)))
    db_session.flush()

    db_session.delete(db_session.get(ProductionRow, production.id))
    db_session.flush()

    assert db_session.get(ProductionRow, production.id) is None
    assert db_session.query(AssetRow).filter_by(production_id=production.id).count() == 0
    assert db_session.query(ProductionConfigRow).filter_by(production_id=production.id).count() == 0
