"""Phase 25: performance validation & resource safety (MASTER §40-41; MAD-001 §43,
§73-74; TDD-001 §87-89, §145).

Verifies the bounded-concurrency render gate (one heavy render at a time by
default), the system-resource sampler (RAM/CPU/disk/RSS) and its metrics wiring,
and the disk-space gate that blocks production before generation. Everything
runs offline with mock providers.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3

import pytest
from temporalio.testing import ActivityEnvironment

from api.activities.pipeline import complete_production, render_master, render_short
from api.activities.production import set_activity_services, validate_production_input
from api.activities.services import MIN_DISK_FREE_BYTES, WorkflowServices
from api.capabilities import InMemoryProviderRegistry
from api.core.errors import ConfigurationError
from api.core.metrics import MetricsStore
from api.core.observability import NullMetricsStore, set_metrics
from api.core.resources import RenderGate
from api.core.system import SystemResourceSample, sample_system_resources
from api.database import make_production_repository, session_scope
from api.domain.enums import ProductionMode, ProductionStatus
from api.domain.outputs import ShortSegment
from api.domain.production import Production
from api.providers import register_mock_providers
from api.storage.artifacts import ArtifactKind
from api.workflows.production import ProductionWorkflowInput


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    """Restore the no-op metrics sink so tests never leak a store cross-file."""
    set_metrics(NullMetricsStore())
    yield
    set_metrics(NullMetricsStore())


@pytest.fixture
def metrics_store(tmp_path) -> MetricsStore:
    store = MetricsStore(tmp_path / "metrics.db")
    set_metrics(store)
    return store


@pytest.fixture
def services(settings, session_factory) -> WorkflowServices:
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    svc = WorkflowServices(
        settings=settings,
        session_factory=session_factory,
        provider_registry=registry,
    )
    # Probe engine needs the gate the container built, so install it after.
    svc.media_engine = _GateProbeEngine(svc.render_gate)
    set_activity_services(svc)
    return svc


def _make_production(session_factory, **overrides) -> Production:
    production = Production(mode=ProductionMode.GENRE, genre="lofi", **overrides)
    with session_scope(session_factory) as session:
        make_production_repository(session).create(production)
    return production


def _input(production: Production) -> ProductionWorkflowInput:
    return ProductionWorkflowInput(
        production_id=production.id,
        mode=production.mode,
        genre=production.genre,
    )


class _GateProbeEngine:
    """Media engine that records how many gate permits it held while rendering.

    While an activity holds the gate, ``permits_available`` drops below the
    maximum; a probe value of ``0`` inside ``render_*`` proves the heavy stage
    is running under the single-render default (MASTER §40).
    """

    def __init__(self, gate: RenderGate | None) -> None:
        self.gate = gate
        self.held_during_render: list[int] = []

    async def render_master(self, request, profile=None):
        self.held_during_render.append(self.gate.permits_available)
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"FAKE-MP4")
        return request.output_path

    async def render_short(self, request, profile=None):
        self.held_during_render.append(self.gate.permits_available)
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"FAKE-MP4")
        return request.output_path


# --- Bounded render concurrency (MAD-001 §43, TDD-001 §87) -------------------


async def test_render_gate_caps_concurrent_workers():
    gate = RenderGate(max_workers=2)
    active = 0
    max_active = 0
    finished: list[int] = []

    async def work(i: int) -> int:
        nonlocal active, max_active
        async with gate:
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            finished.append(i)
            active -= 1
        return i

    await asyncio.gather(*(work(i) for i in range(6)))
    assert max_active == 2
    assert len(finished) == 6


async def test_render_gate_default_one_at_a_time():
    gate = RenderGate(max_workers=1)
    active = 0
    max_active = 0

    async def work() -> None:
        nonlocal active, max_active
        async with gate:
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1

    await asyncio.gather(*(work() for _ in range(4)))
    assert max_active == 1


async def test_render_gate_run_and_context_release_permits():
    gate = RenderGate(max_workers=1)
    assert await gate.run(asyncio.sleep(0)) is None
    assert gate.permits_available == 1

    async with gate:
        assert gate.permits_available == 0
    assert gate.permits_available == 1


def test_render_gate_rejects_zero_workers():
    with pytest.raises(ConfigurationError, match="max_render_workers"):
        RenderGate(max_workers=0)


def test_workflow_services_owns_render_gate_from_settings(settings, session_factory):
    svc = WorkflowServices(settings=settings, session_factory=session_factory)
    assert isinstance(svc.render_gate, RenderGate)
    assert svc.render_gate.max_workers == settings.max_render_workers


async def test_render_master_holds_gate_permit_during_render(services, session_factory):
    prod = _make_production(session_factory)
    result = await ActivityEnvironment().run(render_master, prod.id)
    assert result.ok
    # With max_render_workers=1 the encode ran while holding the only permit.
    assert services.media_engine.held_during_render == [0]


async def test_render_short_holds_gate_permit_during_render(services, session_factory):
    prod = _make_production(session_factory)
    services.artifact_service.write_text(
        prod.id,
        ArtifactKind.SHORT_SEGMENT,
        ShortSegment(start_seconds=0.0, duration_seconds=10.0, reason="benchmark").model_dump_json(),
    )
    result = await ActivityEnvironment().run(render_short, prod.id)
    assert result.ok
    assert services.media_engine.held_during_render == [0]


# --- System resource sampling (MASTER §40, TDD-001 §88-89) -------------------


def test_sample_system_resources_reports_plausible_values(tmp_path):
    sample = sample_system_resources(tmp_path)
    assert 0.0 <= sample.memory_percent <= 100.0
    assert 0.0 <= sample.cpu_percent <= 100.0
    assert 0.0 <= sample.disk_percent <= 100.0
    assert sample.rss_bytes >= 0
    assert sample.to_dict() == {
        "memory_percent": sample.memory_percent,
        "cpu_percent": sample.cpu_percent,
        "disk_percent": sample.disk_percent,
        "rss_bytes": sample.rss_bytes,
    }


def test_sample_system_resources_defaults_to_cwd():
    sample = sample_system_resources()
    assert sample.disk_percent > 0.0


def test_metrics_store_records_performance_sample(metrics_store):
    sample = SystemResourceSample(
        memory_percent=48.5,
        cpu_percent=12.0,
        disk_percent=30.0,
        rss_bytes=1024,
    )
    metrics_store.record_performance_sample("prod-1", sample)

    rows = metrics_store.rows()
    assert len(rows) == 1
    assert rows[0]["operation"] == "performance.sample"
    assert rows[0]["production_id"] == "prod-1"
    assert rows[0]["status"] == "ok"

    with sqlite3.connect(metrics_store._path) as conn:  # detail not in rows()
        detail = conn.execute(
            "SELECT detail FROM metrics WHERE operation = 'performance.sample'"
        ).fetchone()[0]
    assert json.loads(detail) == {
        "memory_percent": 48.5,
        "cpu_percent": 12.0,
        "disk_percent": 30.0,
        "rss_bytes": 1024,
    }


async def test_complete_production_records_performance_sample(settings, session_factory, metrics_store):
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    svc = WorkflowServices(
        settings=settings,
        session_factory=session_factory,
        provider_registry=registry,
        metrics=metrics_store,
    )
    set_activity_services(svc)
    prod = _make_production(session_factory, status=ProductionStatus.GENERATING_METADATA)

    result = await ActivityEnvironment().run(complete_production, prod.id)
    assert result.ok
    assert any(
        row["operation"] == "performance.sample" and row["production_id"] == prod.id
        for row in metrics_store.rows()
    )


# --- Disk safety gate (MAD-001 §73, TDD-001 §89) -----------------------------


async def test_validate_production_input_blocks_on_low_disk(services, session_factory, monkeypatch):
    prod = _make_production(session_factory)
    monkeypatch.setattr(services, "disk_free_bytes", lambda: MIN_DISK_FREE_BYTES - 1)

    result = await ActivityEnvironment().run(validate_production_input, _input(prod))
    assert not result.ok
    assert "disk.space" in result.checked
    assert any("disk" in error.lower() for error in result.errors)


async def test_validate_production_input_passes_with_enough_disk(services, session_factory):
    prod = _make_production(session_factory)
    result = await ActivityEnvironment().run(validate_production_input, _input(prod))
    assert result.ok
    assert "disk.space" in result.checked
    assert result.errors == []
