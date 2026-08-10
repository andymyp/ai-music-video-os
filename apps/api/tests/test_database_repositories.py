"""Repository tests (TDD-001 §123, MASTER_EXECUTION.md §12): create/read/update/
delete, relationships, transactions, and cascade behavior for the four
repository interfaces."""
from __future__ import annotations

import pytest

from api.core.clock import utc_now
from api.database.models import ProductionRow
from api.database.repositories import (
    ProviderRun,
    WorkflowRun,
    make_asset_repository,
    make_production_repository,
    make_provider_run_repository,
    make_workflow_repository,
)
from api.database.session import session_scope
from api.domain.assets import Asset
from api.domain.creative import CreativeConcept, MusicStrategy, TrendResult, VisualStrategy
from api.domain.enums import AssetStatus, AssetType, ProductionStatus
from api.domain.production import Production, ProductionConfig


def _create_production(session_factory) -> Production:
    with session_scope(session_factory) as session:
        return make_production_repository(session).create(Production(mode="trending"))


# --- ProductionRepository -------------------------------------------------------

def test_create_and_get(session_factory):
    production = Production(mode="genre", genre="lofi")
    with session_scope(session_factory) as session:
        make_production_repository(session).create(production)

    with session_scope(session_factory) as session:
        loaded = make_production_repository(session).get(production.id)
        assert loaded is not None
        assert loaded.id == production.id
        assert loaded.genre == "lofi"


def test_get_missing_returns_none(session_factory):
    with session_scope(session_factory) as session:
        assert make_production_repository(session).get("prod_" + "0" * 26) is None


def test_list_returns_productions(session_factory):
    with session_scope(session_factory) as session:
        repo = make_production_repository(session)
        repo.create(Production(mode="trending", branding_text="one"))
        repo.create(Production(mode="trending", branding_text="two"))

    with session_scope(session_factory) as session:
        items = make_production_repository(session).list()
        assert {item.branding_text for item in items} == {"one", "two"}


def test_update_persists_status_transition(session_factory):
    production = _create_production(session_factory)
    production.transition_to(ProductionStatus.PLANNING)

    with session_scope(session_factory) as session:
        make_production_repository(session).update(production)

    with session_scope(session_factory) as session:
        loaded = make_production_repository(session).get(production.id)
        assert loaded.status is ProductionStatus.PLANNING


def test_update_preserves_created_at(session_factory):
    production = _create_production(session_factory)
    production.transition_to(ProductionStatus.PLANNING)

    with session_scope(session_factory) as session:
        make_production_repository(session).update(production)

    with session_scope(session_factory) as session:
        loaded = make_production_repository(session).get(production.id)
        assert loaded.created_at == production.created_at


def test_delete_returns_true_and_removes(session_factory):
    production = _create_production(session_factory)
    with session_scope(session_factory) as session:
        assert make_production_repository(session).delete(production.id) is True
    with session_scope(session_factory) as session:
        assert make_production_repository(session).get(production.id) is None


def test_delete_missing_returns_false(session_factory):
    with session_scope(session_factory) as session:
        assert make_production_repository(session).delete("prod_" + "0" * 26) is False


def test_delete_cascades_children(session_factory):
    production = _create_production(session_factory)
    with session_scope(session_factory) as session:
        repo = make_production_repository(session)
        repo.save_config(production.id, ProductionConfig(mode="trending"))
        make_asset_repository(session).create(
            Asset(production_id=production.id, type=AssetType.RADIO)
        )

    with session_scope(session_factory) as session:
        assert make_production_repository(session).delete(production.id) is True

    with session_scope(session_factory) as session:
        assert make_asset_repository(session).list_for_production(production.id) == []


# --- one-to-one children ----------------------------------------------------------

def test_config_save_and_get(session_factory):
    production = _create_production(session_factory)
    config = ProductionConfig(mode="trending", fps=24, provider_profile="balanced")

    with session_scope(session_factory) as session:
        repo = make_production_repository(session)
        repo.save_config(production.id, config)
        repo.save_config(production.id, config)  # idempotent upsert

    with session_scope(session_factory) as session:
        loaded = make_production_repository(session).get_config(production.id)
        assert loaded is not None
        assert loaded.fps == 24
        assert loaded.provider_profile == "balanced"


def test_concept_save_and_get(session_factory):
    production = _create_production(session_factory)
    concept = CreativeConcept(
        genre="lofi", mood="mellow", theme="study", music_direction="warm",
        visual_direction="dim light",
    )
    with session_scope(session_factory) as session:
        make_production_repository(session).save_concept(production.id, concept)
    with session_scope(session_factory) as session:
        loaded = make_production_repository(session).get_concept(production.id)
        assert loaded is not None and loaded.theme == "study"


def test_music_strategy_save_and_get(session_factory):
    production = _create_production(session_factory)
    strategy = MusicStrategy(
        genre="lofi", mood="mellow", bpm_range=[70, 85], key="A minor",
        structure="intro-verse-outro",
    )
    with session_scope(session_factory) as session:
        make_production_repository(session).save_music_strategy(production.id, strategy)
    with session_scope(session_factory) as session:
        loaded = make_production_repository(session).get_music_strategy(production.id)
        assert loaded is not None
        assert loaded.bpm_range == [70, 85]
        assert loaded.vocal_policy == "none"


def test_visual_strategy_save_and_get(session_factory):
    production = _create_production(session_factory)
    strategy = VisualStrategy(
        theme="night", environment="city", lighting="neon", style="retro",
        color_direction="teal", radio_style="vinyl", composition="centered",
    )
    with session_scope(session_factory) as session:
        make_production_repository(session).save_visual_strategy(production.id, strategy)
    with session_scope(session_factory) as session:
        loaded = make_production_repository(session).get_visual_strategy(production.id)
        assert loaded is not None and loaded.theme == "night"


def test_trend_result_save_and_get(session_factory):
    production = _create_production(session_factory)
    result = TrendResult(source="spotify", topic="lofi 2026", genre="lofi", score=89.4, confidence=0.8)
    with session_scope(session_factory) as session:
        make_production_repository(session).save_trend_result(production.id, result)
    with session_scope(session_factory) as session:
        loaded = make_production_repository(session).get_trend_result(production.id)
        assert loaded is not None and loaded.score == pytest.approx(89.4)


def test_get_missing_children_returns_none(session_factory):
    production = _create_production(session_factory)
    with session_scope(session_factory) as session:
        repo = make_production_repository(session)
        assert repo.get_config(production.id) is None
        assert repo.get_concept(production.id) is None
        assert repo.get_music_strategy(production.id) is None
        assert repo.get_visual_strategy(production.id) is None
        assert repo.get_trend_result(production.id) is None


# --- AssetRepository --------------------------------------------------------------

def test_asset_crud(session_factory):
    production = _create_production(session_factory)
    asset = Asset(
        production_id=production.id, type=AssetType.MASTER_VIDEO,
        path="render/master.mp4", status=AssetStatus.GENERATING,
    )
    other = Asset(production_id=production.id, type=AssetType.SHORT_VIDEO)

    with session_scope(session_factory) as session:
        repo = make_asset_repository(session)
        repo.create(asset)
        repo.create(other)

    with session_scope(session_factory) as session:
        repo = make_asset_repository(session)
        assert len(repo.list_for_production(production.id)) == 2
        loaded = repo.get(asset.id)
        assert loaded.path == "render/master.mp4"
        assert loaded.status is AssetStatus.GENERATING

    asset.transition_to(AssetStatus.VALIDATING)
    with session_scope(session_factory) as session:
        make_asset_repository(session).update(asset)
    with session_scope(session_factory) as session:
        assert make_asset_repository(session).get(asset.id).status is AssetStatus.VALIDATING

    with session_scope(session_factory) as session:
        repo = make_asset_repository(session)
        assert repo.delete(other.id) is True
        assert repo.get(other.id) is None


# --- WorkflowRepository ------------------------------------------------------------

def test_workflow_crud(session_factory):
    production = _create_production(session_factory)
    run = WorkflowRun(
        id="wf-prod-1", production_id=production.id, workflow_type="ProductionWorkflow",
        task_queue="production", status="running",
    )
    with session_scope(session_factory) as session:
        created = make_workflow_repository(session).create(run)
        assert created.id == run.id

    with session_scope(session_factory) as session:
        repo = make_workflow_repository(session)
        loaded = repo.get(run.id)
        assert loaded.status == "running"
        assert len(repo.list_for_production(production.id)) == 1

    run.status = "completed"
    run.completed_at = utc_now()
    with session_scope(session_factory) as session:
        make_workflow_repository(session).update(run)
    with session_scope(session_factory) as session:
        assert make_workflow_repository(session).get(run.id).status == "completed"


def test_workflow_update_missing_raises(session_factory):
    run = WorkflowRun(
        id="missing", production_id="prod_" + "0" * 26, workflow_type="X",
        task_queue="q", status="running",
    )
    with session_scope(session_factory) as session:
        with pytest.raises(KeyError):
            make_workflow_repository(session).update(run)


# --- ProviderRunRepository ----------------------------------------------------------

def test_provider_run_crud(session_factory):
    production = _create_production(session_factory)
    run = ProviderRun(
        id="pr-1", production_id=production.id, capability="generate_music",
        provider="mock", model="mock-1", status="running",
        metadata={"attempt": 1},
    )
    with session_scope(session_factory) as session:
        created = make_provider_run_repository(session).create(run)
        assert created.id == run.id

    with session_scope(session_factory) as session:
        repo = make_provider_run_repository(session)
        loaded = repo.get(run.id)
        assert loaded.capability == "generate_music"
        assert loaded.metadata == {"attempt": 1}
        assert len(repo.list_for_production(production.id)) == 1

    run.status = "completed"
    run.completed_at = utc_now()
    run.metadata = {"attempt": 1, "duration_ms": 123}
    with session_scope(session_factory) as session:
        make_provider_run_repository(session).update(run)
    with session_scope(session_factory) as session:
        updated = make_provider_run_repository(session).get(run.id)
        assert updated.status == "completed"
        assert updated.metadata == {"attempt": 1, "duration_ms": 123}


# --- transactions / aggregate relationships ----------------------------------------

def test_session_scope_rolls_back_on_error(session_factory):
    with pytest.raises(RuntimeError):
        with session_scope(session_factory) as session:
            make_production_repository(session).create(
                Production(mode="trending", branding_text="rollback-me")
            )
            raise RuntimeError("boom")

    with session_scope(session_factory) as session:
        assert make_production_repository(session).list() == []


def test_aggregate_relationships_loaded_via_orm(session_factory):
    production = _create_production(session_factory)
    with session_scope(session_factory) as session:
        repo = make_production_repository(session)
        repo.save_config(production.id, ProductionConfig(mode="trending"))
        repo.save_concept(
            production.id,
            CreativeConcept(genre="lofi", mood="mellow", theme="study",
                            music_direction="warm", visual_direction="dim"),
        )
        repo.save_music_strategy(
            production.id,
            MusicStrategy(genre="lofi", mood="mellow", key="A minor", structure="intro"),
        )
        repo.save_visual_strategy(
            production.id,
            VisualStrategy(theme="night", environment="city", lighting="neon",
                           style="retro", color_direction="teal", radio_style="vinyl",
                           composition="centered"),
        )
        repo.save_trend_result(
            production.id, TrendResult(source="spotify", topic="t", genre="lofi")
        )
        make_asset_repository(session).create(
            Asset(production_id=production.id, type=AssetType.MASTER_VIDEO)
        )

    with session_scope(session_factory) as session:
        row = session.get(ProductionRow, production.id)
        assert row.config is not None
        assert row.concept is not None
        assert row.music_strategy is not None
        assert row.visual_strategy is not None
        assert row.trend_result is not None
        assert len(row.assets) == 1
