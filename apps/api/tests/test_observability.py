"""Phase 22: observability (MASTER §35; TDD-001 §80-81; MAD-001 §49-50).

Covers the structured-logging upgrade, the SQLite metrics store + aggregates and
the two instrumentation seams (OperationLogger / instrument decorator) plus the
provider/stage/workflow wiring. Everything runs offline.
"""
from __future__ import annotations

import asyncio
import json
import logging

import pytest
from temporalio.testing import ActivityEnvironment

from api.activities.models import WorkflowRunRecord
from api.activities.pipeline import complete_production
from api.activities.production import record_workflow_run, set_activity_services
from api.agents import LLMGenerationTool
from api.capabilities import (
    Capability,
    InMemoryProviderRegistry,
    ProviderConfig,
    StructuredGenerationRequest,
)
from api.core.errors import ProviderError, ToolError
from api.core.logging import (
    StructuredFormatter,
    get_logger,
    logging_context,
)
from api.core.metrics import MetricsStore
from api.core.observability import (
    NullMetricsStore,
    OperationLogger,
    get_metrics,
    instrument,
    set_metrics,
)
from api.database import make_production_repository, session_scope
from api.domain.enums import ProductionMode, ProductionStatus
from api.domain.production import Production
from api.providers import register_mock_providers

#: Re-created per test; the fixture restores the no-op sink afterwards so
#: instrumented activities in *other* test files never write to a stale store.
_DEFAULT_NULL = NullMetricsStore()


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    set_metrics(NullMetricsStore())
    yield
    set_metrics(NullMetricsStore())


@pytest.fixture
def metrics_store(tmp_path) -> MetricsStore:
    store = MetricsStore(tmp_path / "metrics.db")
    set_metrics(store)
    return store


def _make_production(session_factory, *, status=None) -> Production:
    production = Production(mode=ProductionMode.GENRE, genre="lofi")
    with session_scope(session_factory) as session:
        make_production_repository(session).create(production)
    if status is not None:
        with session_scope(session_factory) as session:
            repo = make_production_repository(session)
            current = repo.get(production.id)
            current.status = status
            repo.update(current)
    return production


# --- Structured logging (MAD-001 §49) -----------------------------------------

def test_get_logger_tags_component():
    logger = get_logger("pipeline")
    assert logger.name == "amv.pipeline"


def test_structured_formatter_emits_context_and_extra_fields():
    record = logging.LogRecord(
        name="amv.pipeline",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="render %s",
        args=("master",),
        exc_info=None,
    )
    record.production_id = "prod-1"
    record.workflow_id = "wf-1"
    record.duration_ms = 12.5
    record.status = "ok"
    with logging_context(stage="render_master", component="pipeline"):
        line = StructuredFormatter().format(record)

    payload = json.loads(line)
    assert payload["message"] == "render master"
    assert payload["stage"] == "render_master"
    assert payload["component"] == "pipeline"
    assert payload["production_id"] == "prod-1"
    assert payload["workflow_id"] == "wf-1"
    assert payload["duration_ms"] == 12.5
    assert payload["status"] == "ok"
    assert payload["logger"] == "amv.pipeline"


def test_structured_formatter_redacts_sensitive_values():
    record = logging.LogRecord("amv.p", logging.INFO, __file__, 1, "secrets", (), None)
    record.api_key = "sk-12345"
    record.token = "abc"
    record.authorization = "Bearer xyz"
    record.payload = {"nested": {"client_secret": "s3cr3t", "count": 3}}

    payload = json.loads(StructuredFormatter().format(record))
    assert payload["api_key"] == "***"
    assert payload["token"] == "***"
    assert payload["authorization"] == "***"
    assert payload["payload"] == {"nested": {"client_secret": "***", "count": 3}}


def test_logging_context_nests_and_restores_previous_scope():
    captured: list[dict[str, object]] = []

    def emit():
        with logging_context(production_id="p1", stage="a"):
            captured.append(_snapshot())
            with logging_context(stage="b", event="nested"):
                captured.append(_snapshot())
            captured.append(_snapshot())  # restored to stage "a"
        captured.append(_snapshot())  # restored to empty

    emit()
    assert captured[0]["production_id"] == "p1" and captured[0]["stage"] == "a"
    assert captured[1]["production_id"] == "p1" and captured[1]["stage"] == "b"
    assert captured[1]["event"] == "nested"
    assert captured[2]["stage"] == "a" and "event" not in captured[2]
    assert captured[3] == {}


def _snapshot() -> dict[str, object]:
    """Read the current logging context via a formatted record."""
    record = logging.LogRecord("amv.snapshot", logging.INFO, __file__, 1, "x", (), None)
    payload = json.loads(StructuredFormatter().format(record))
    return {k: v for k, v in payload.items() if k not in {"timestamp", "level", "logger", "message"}}


async def test_logging_context_is_task_local():
    handler = _CaptureHandler()
    logger = get_logger("task_scope")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        async def emit(production_id: str) -> None:
            with logging_context(production_id=production_id, stage="s"):
                await asyncio.sleep(0)
                logger.info("hello")

        await asyncio.gather(emit("p1"), emit("p2"))
        pids = {json.loads(line)["production_id"] for line in handler.lines}
        assert pids == {"p1", "p2"}
    finally:
        logger.removeHandler(handler)


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.setFormatter(StructuredFormatter())
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


# --- Metrics store (MAD-001 §50) ----------------------------------------------

def test_empty_store_summary_is_all_zeros(metrics_store):
    summary = metrics_store.summary()
    assert summary.total_operations == 0
    assert summary.failures == 0
    assert summary.provider_failure_rate == 0.0
    assert summary.render_duration_avg_ms == 0.0
    assert summary.production_duration_avg_s == 0.0
    assert summary.healthy


def test_record_and_rows_carry_full_vocabulary(metrics_store):
    metrics_store.record(
        "provider.call",
        component="llm",
        provider="MockLLMProvider",
        model="mock-llm",
        production_id="prod-1",
        duration_ms=1.5,
    )
    assert metrics_store.count() == 1
    row = metrics_store.rows()[0]
    assert row["operation"] == "provider.call"
    assert row["component"] == "llm"
    assert row["provider"] == "MockLLMProvider"
    assert row["model"] == "mock-llm"
    assert row["production_id"] == "prod-1"
    assert row["duration_ms"] == 1.5
    assert row["status"] == "ok"
    assert row["recorded_at"]


def test_summary_aggregates_provider_render_qc_workflow(metrics_store):
    # provider calls: one ok, two failing (all failures retried -> failover)
    for _ in range(2):
        metrics_store.record("provider.call", component="music", provider="MockMusicProvider", status="error", duration_ms=10.0)
    metrics_store.record("provider.call", component="music", provider="MockMusicProvider", status="ok", duration_ms=20.0)
    # renders
    metrics_store.record("stage.render_master", production_id="p1", duration_ms=1000.0)
    metrics_store.record("stage.render_short", production_id="p1", duration_ms=500.0)
    # a failing QC gate
    metrics_store.record("stage.run_qc", production_id="p1", status="error")
    # a failed workflow run
    metrics_store.record("workflow.run", production_id="p1", workflow_id="w1", status="error", duration_ms=30.0)
    metrics_store.record("workflow.run", production_id="p2", workflow_id="w2", status="ok", duration_ms=25.0)

    summary = metrics_store.summary()
    assert summary.total_operations == 8
    assert summary.failures == 4
    assert summary.provider_calls == 3
    assert summary.provider_failures == 2
    assert summary.provider_failure_rate == 0.6667
    assert summary.provider_latency_avg_ms == 13.333  # (10+10+20)/3
    assert summary.render_duration_avg_ms == 750.0  # (1000+500)/2
    assert summary.qc_failures == 1
    assert summary.workflow_runs == 2
    assert summary.workflow_failures == 1
    assert not summary.healthy


def test_production_lifecycle_measures_duration(metrics_store):
    metrics_store.record_production_start("prod-1")
    duration_ms = metrics_store.record_production_completed("prod-1")

    assert duration_ms is not None and duration_ms >= 0
    ops = {row["operation"] for row in metrics_store.rows()}
    assert {"production.start", "production.completed", "production.duration"} <= ops
    summary = metrics_store.summary()
    assert summary.completed_productions == 1
    assert summary.production_duration_avg_s > 0


def test_production_completed_without_start_is_graceful(metrics_store):
    duration_ms = metrics_store.record_production_completed("missing")
    assert duration_ms is None
    assert metrics_store.summary().completed_productions == 0


def test_clear_empties_store(metrics_store):
    metrics_store.record("provider.call", status="ok")
    metrics_store.clear()
    assert metrics_store.count() == 0


# --- Instrumentation (OperationLogger / instrument) ----------------------------

async def test_operation_logger_records_success(metrics_store):
    async with OperationLogger("test.op", component="c", production_id="p1", event="e"):
        await asyncio.sleep(0)

    rows = metrics_store.rows()
    assert len(rows) == 1
    assert rows[0]["operation"] == "test.op"
    assert rows[0]["status"] == "ok"
    assert rows[0]["production_id"] == "p1"
    assert rows[0]["duration_ms"] >= 0


async def test_operation_logger_records_failure(metrics_store):
    with pytest.raises(ValueError, match="boom"):
        async with OperationLogger("test.op", component="c"):
            raise ValueError("boom")

    rows = metrics_store.rows()
    assert len(rows) == 1
    assert rows[0]["status"] == "error"


async def test_instrument_decorator_records_metric_and_passthrough(metrics_store):
    @instrument("pipeline", "render_master")
    async def render(production_id: str) -> str:
        return f"done:{production_id}"

    assert await render("prod-9") == "done:prod-9"
    rows = metrics_store.rows()
    assert len(rows) == 1
    assert rows[0]["operation"] == "stage.render_master"
    assert rows[0]["status"] == "ok"
    assert rows[0]["stage"] == "render_master"
    assert rows[0]["production_id"] == "prod-9"
    assert metrics_store.summary().render_duration_avg_ms >= 0


async def test_instrument_decorator_records_failure(metrics_store):
    @instrument("pipeline", "run_qc")
    async def qc(production_id: str) -> str:
        raise ValueError("qc gate failed")

    with pytest.raises(ValueError, match="qc gate failed"):
        await qc("prod-1")

    rows = metrics_store.rows()
    assert rows[0]["operation"] == "stage.run_qc"
    assert rows[0]["status"] == "error"
    assert metrics_store.summary().qc_failures == 1


# --- Provider failover instrumentation (PRD-001 §64.5) --------------------------

class _FailingProvider:
    async def generate_structured(self, request):
        raise ProviderError("simulated outage")


def _llm_registry() -> InMemoryProviderRegistry:
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    # Tie on priority (0); "failing-llm" sorts before the mock's "mock_llm", so
    # it is tried first, fails, then the mock succeeds (failover).
    registry.register(
        Capability.LLM,
        _FailingProvider(),
        ProviderConfig(provider_id="failing-llm", capability=Capability.LLM, priority=0),
    )
    return registry


async def test_provider_failover_records_each_attempt(metrics_store):
    tool = LLMGenerationTool(_llm_registry())
    result = await tool.run(StructuredGenerationRequest(task="t", prompt="hello"))
    assert result.data  # mock fallback succeeded

    rows = metrics_store.rows()
    assert len(rows) == 2  # one failed attempt + one successful
    by_status = {row["status"]: row for row in rows}
    assert by_status["error"]["component"] == "llm"
    assert by_status["error"]["provider"] == "_FailingProvider"
    assert by_status["error"]["model"] is None
    assert by_status["ok"]["provider"] == "MockLLMProvider"
    assert by_status["ok"]["model"] == "mock-llm"
    assert metrics_store.summary().provider_failure_rate == 0.5


async def test_all_providers_failed_records_failures(metrics_store):
    registry = InMemoryProviderRegistry()
    registry.register(
        Capability.LLM,
        _FailingProvider(),
        ProviderConfig(provider_id="failing", capability=Capability.LLM, priority=10),
    )
    tool = LLMGenerationTool(registry)
    with pytest.raises(ToolError, match="all providers failed"):
        await tool.run(StructuredGenerationRequest(task="t", prompt="hello"))

    summary = metrics_store.summary()
    assert summary.provider_calls == 1
    assert summary.provider_failures == 1
    assert summary.provider_failure_rate == 1.0


def test_get_metrics_defaults_to_null_sink():
    assert isinstance(get_metrics(), NullMetricsStore)
    assert get_metrics().summary().total_operations == 0


# --- Pipeline + workflow wiring -------------------------------------------------

async def test_instrumented_stage_records_metric(settings, session_factory, tmp_path):
    store = MetricsStore(tmp_path / "stage-metrics.db")
    set_metrics(store)
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    from api.activities.services import WorkflowServices

    svc = WorkflowServices(
        settings=settings,
        session_factory=session_factory,
        provider_registry=registry,
        metrics=store,
    )
    set_activity_services(svc)
    prod = _make_production(session_factory, status=ProductionStatus.GENERATING_METADATA)

    result = await ActivityEnvironment().run(complete_production, prod.id)
    assert result.ok

    rows = store.rows()
    assert any(
        row["operation"] == "stage.complete_production"
        and row["status"] == "ok"
        and row["production_id"] == prod.id
        for row in rows
    )


async def test_record_workflow_run_feeds_lifecycle_metrics(settings, session_factory, tmp_path):
    store = MetricsStore(tmp_path / "wf-metrics.db")
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    from api.activities.services import WorkflowServices

    svc = WorkflowServices(
        settings=settings,
        session_factory=session_factory,
        provider_registry=registry,
        metrics=store,
    )
    set_activity_services(svc)
    prod = _make_production(session_factory)

    env = ActivityEnvironment()
    await env.run(
        record_workflow_run,
        WorkflowRunRecord(
            workflow_id="wf-1",
            production_id=prod.id,
            task_queue="production",
            status="running",
            attempt=1,
        ),
    )
    await env.run(
        record_workflow_run,
        WorkflowRunRecord(
            workflow_id="wf-1",
            production_id=prod.id,
            task_queue="production",
            status="completed",
            attempt=1,
        ),
    )

    ops = {row["operation"]: row for row in store.rows()}
    assert "production.start" in ops
    assert "workflow.run" in ops
    assert ops["workflow.run"]["status"] == "ok"
    assert ops["workflow.run"]["workflow_id"] == "wf-1"
    summary = store.summary()
    assert summary.workflow_runs == 1
    assert summary.completed_productions == 1
