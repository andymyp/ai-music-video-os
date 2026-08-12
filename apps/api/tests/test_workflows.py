"""Phase 09: workflow runtime (TDD-001 §10, §18, §22-25, §83-84; MAD-001 §9, §52; PRD-001 §61).

Covers the workflow configuration + retry classification, the deterministic
forward-status helper, deterministic agent-request derivation, and every
activity over the offline ``ActivityEnvironment`` (no Temporal server needed).
A server-backed end-to-end run is gated behind a ``temporal`` CLI on PATH and
skips when the CLI is absent.
"""
from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from temporalio.common import RetryPolicy
from temporalio.testing import ActivityEnvironment

from api.agents import build_agent_runtime
from api.activities import (
    ALL_ACTIVITIES,
    AgentStep,
    AgentStepResult,
    WorkflowServices,
    advance_production,
    execute_agent_step,
    load_production_status,
    plan_next_step,
    record_workflow_run,
    set_activity_services,
    validate_production_input,
)
from api.activities.models import ValidationReport, WorkflowRunRecord
from api.activities.services import build_agent_request, stage_summary
from api.capabilities import InMemoryProviderRegistry
from api.core.errors import (
    AuthenticationError,
    ConfigurationError,
    InvalidStateTransitionError,
    ProviderError,
    QualityCheckError,
    RateLimitError,
    TimeoutError,
    ValidationError,
    WorkflowError,
)
from api.core.ids import new_production_id
from api.database import make_production_repository, session_scope
from api.domain.agents import (
    MusicStrategyRequest,
    OrchestratorDecision,
    QualityControlRequest,
    TrendResearchRequest,
)
from api.domain.enums import ProductionMode, ProductionStatus
from api.domain.production import (
    PRODUCTION_TRANSITIONS,
    TERMINAL_STATUSES,
    Production,
    ProductionConfig,
)
from api.providers import register_mock_providers
from api.workflows.config import (
    NON_RETRYABLE_TYPES,
    WorkflowConfig,
    default_activity_retry_policy,
    default_workflow_config,
    is_retryable,
    provider_retry_policy,
)
from api.workflows.production import (
    ProductionWorkflow,
    ProductionWorkflowInput,
    ProductionWorkflowOutput,
    next_status_in_flow,
)

SAMPLE_PRODUCTION_ID = new_production_id()


@pytest.fixture
def services(settings, session_factory) -> WorkflowServices:
    """A fully-wired services container bound to the process-wide activities."""
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    svc = WorkflowServices(
        settings=settings,
        session_factory=session_factory,
        provider_registry=registry,
        agent_runtime=build_agent_runtime(registry),
    )
    set_activity_services(svc)
    return svc


def _make_production(session_factory, *, mode=ProductionMode.GENRE, genre="lofi", **overrides) -> Production:
    """Persist a production (defaults: genre mode / lofi / CREATED)."""
    production = Production(mode=mode, genre=genre, **overrides)
    with session_scope(session_factory) as session:
        make_production_repository(session).create(production)
    return production


def _input(production: Production) -> ProductionWorkflowInput:
    return ProductionWorkflowInput(
        production_id=production.id,
        mode=production.mode,
        genre=production.genre,
    )


# --- Configuration & retry classification (TDD-001 §83-84) -------------------

def test_default_activity_retry_policy_shape():
    policy = default_activity_retry_policy()
    assert isinstance(policy, RetryPolicy)
    assert policy.initial_interval == timedelta(seconds=1)      # 1s -> 2s -> 4s
    assert policy.backoff_coefficient == 2.0
    assert policy.maximum_interval == timedelta(seconds=30)
    assert policy.maximum_attempts == 5
    assert set(policy.non_retryable_error_types) == set(NON_RETRYABLE_TYPES)


def test_provider_retry_policy_never_retries_permanent_errors():
    policy = provider_retry_policy()
    assert policy.maximum_attempts == 5
    assert "ValidationError" in policy.non_retryable_error_types
    assert "AuthenticationError" in policy.non_retryable_error_types


def test_is_retryable_classifies_provider_and_permanent_errors():
    # Transient provider failures are retried (MAD-001 §52).
    assert is_retryable(ProviderError("transient outage"))
    assert is_retryable(TimeoutError("provider timed out"))
    assert is_retryable(RateLimitError("rate limited"))
    # Permanent errors are never retried.
    assert not is_retryable(AuthenticationError("bad credentials"))
    assert not is_retryable(ValidationError("invalid input"))
    assert not is_retryable(ConfigurationError("bad config"))
    assert not is_retryable(InvalidStateTransitionError("a", "b"))
    assert not is_retryable(QualityCheckError("mandatory check failed"))
    # Unknown exceptions default to retryable.
    assert is_retryable(ValueError("unexpected"))


def test_workflow_config_defaults_and_workflow_id():
    config = default_workflow_config()
    assert isinstance(config, WorkflowConfig)
    assert config.task_queue == "production"
    assert config.run_timeout == timedelta(hours=24)
    assert config.max_steps_per_run == 50
    assert config.workflow_id("prod_x") == "production-prod_x-a1"
    assert config.workflow_id("prod_x", 3) == "production-prod_x-a3"


# --- Forward status helper (TDD-001 §10) -------------------------------------

def test_next_status_in_flow_follows_canonical_flow():
    assert next_status_in_flow(ProductionStatus.CREATED) is ProductionStatus.PLANNING
    assert next_status_in_flow(ProductionStatus.CONCEPT_READY) is ProductionStatus.GENERATING_MUSIC
    assert next_status_in_flow(ProductionStatus.MUSIC_READY) is ProductionStatus.GENERATING_VISUAL
    assert next_status_in_flow(ProductionStatus.GENERATING_VISUAL) is ProductionStatus.VISUAL_READY
    assert next_status_in_flow(ProductionStatus.VISUAL_READY) is ProductionStatus.ANALYZING_AUDIO
    assert next_status_in_flow(ProductionStatus.MASTER_READY) is ProductionStatus.SELECTING_SHORT
    assert next_status_in_flow(ProductionStatus.GENERATING_METADATA) is ProductionStatus.QUALITY_CHECK
    assert next_status_in_flow(ProductionStatus.QUALITY_CHECK) is ProductionStatus.COMPLETED


def test_next_status_in_flow_returns_single_deterministic_forward_step():
    """Every non-terminal stage has exactly one forward move (not self/failed/cancelled)."""
    for status in ProductionStatus:
        if status in TERMINAL_STATUSES or status is ProductionStatus.FAILED:
            assert next_status_in_flow(status) is status, status.value
            continue
        nxt = next_status_in_flow(status)
        forward = [
            target
            for target in PRODUCTION_TRANSITIONS[status]
            if target not in (ProductionStatus.FAILED, ProductionStatus.CANCELLED)
            and target is not status
        ]
        assert len(forward) == 1, f"{status.value} must have exactly one forward neighbor"
        assert nxt is forward[0], status.value


def test_next_status_in_flow_is_deterministic_across_calls():
    for status in ProductionStatus:
        expected = next_status_in_flow(status)
        for _ in range(5):
            assert next_status_in_flow(status) is expected, status.value


# --- Deterministic request derivation ---------------------------------------

def test_build_agent_request_is_deterministic():
    production = Production(mode=ProductionMode.GENRE, genre="lofi")
    config = ProductionConfig(mode=ProductionMode.GENRE, genre="lofi")
    first = build_agent_request("music_strategy", production, config)
    second = build_agent_request("music_strategy", production, config)
    assert first == second


def test_build_agent_request_music_strategy():
    production = Production(mode=ProductionMode.GENRE, genre="lofi")
    config = ProductionConfig(mode=ProductionMode.GENRE, genre="lofi")
    req = build_agent_request("music_strategy", production, config)
    assert isinstance(req, MusicStrategyRequest)
    assert req.genre == "lofi"
    assert req.mood == "lofi atmosphere"  # deterministic placeholder until Phase 10
    assert req.duration_target_minutes == config.long_form_duration_minutes


def test_build_agent_request_trend_research():
    production = Production(mode=ProductionMode.TRENDING, genre=None)
    req = build_agent_request("trend_research", production, None)
    assert isinstance(req, TrendResearchRequest)
    assert req.genre_hint is None


def test_build_agent_request_quality_control():
    production = Production(mode=ProductionMode.GENRE, genre="lofi")
    req = build_agent_request("quality_control", production, None)
    assert isinstance(req, QualityControlRequest)
    assert req.production_id == production.id
    assert req.creative_context == "lofi lofi atmosphere production"


def test_build_agent_request_unknown_agent_raises():
    production = Production(mode=ProductionMode.GENRE, genre="lofi")
    with pytest.raises(WorkflowError, match="no input builder"):
        build_agent_request("nope", production, None)


def test_stage_summary_agents():
    assert stage_summary("trend_research", SimpleNamespace(selected_genre="chillhop")) == "selected genre 'chillhop'"
    assert stage_summary("music_strategy", SimpleNamespace(genre="lofi", bpm_range=(70, 90))) == "genre lofi / bpm (70, 90)"
    assert stage_summary("visual_strategy", SimpleNamespace(theme="night drive")) == "theme 'night drive'"


def test_stage_summary_falls_back_to_ok():
    assert stage_summary("music_generation", SimpleNamespace(reasoning="")) == "ok"
    assert stage_summary("visual_generation", object()) == "ok"


# --- Activities via offline ActivityEnvironment ------------------------------

async def test_validate_production_input_ok(services, session_factory):
    prod = _make_production(session_factory)
    report = await ActivityEnvironment().run(validate_production_input, _input(prod))
    assert isinstance(report, ValidationReport)
    assert report.ok
    for check in ("production.exists", "mode", "branding", "configuration",
                  "provider.availability", "disk.space"):
        assert check in report.checked, check
    assert report.errors == []


async def test_validate_production_input_missing_production(services):
    env = ActivityEnvironment()
    report = await env.run(validate_production_input, ProductionWorkflowInput(
        production_id=SAMPLE_PRODUCTION_ID, mode=ProductionMode.GENRE, genre="lofi"))
    assert not report.ok
    assert any("production lookup failed" in error for error in report.errors)


async def test_validate_production_input_rejects_completed(services, session_factory):
    prod = _make_production(session_factory, status=ProductionStatus.COMPLETED)
    report = await ActivityEnvironment().run(validate_production_input, _input(prod))
    assert not report.ok
    assert any("production already 'completed'" in error for error in report.errors)


async def test_validate_production_input_rejects_long_branding(services, session_factory):
    prod = _make_production(session_factory, branding_text="x" * 81)
    report = await ActivityEnvironment().run(validate_production_input, _input(prod))
    assert not report.ok
    assert any("branding text exceeds 80 characters" in error for error in report.errors)


async def test_validate_production_input_trending_mode_ok(services, session_factory):
    prod = _make_production(session_factory, mode=ProductionMode.TRENDING, genre=None)
    report = await ActivityEnvironment().run(validate_production_input, _input(prod))
    assert report.ok, report.errors


async def test_validate_production_input_fails_without_provider(settings, session_factory):
    svc = WorkflowServices(
        settings=settings,
        session_factory=session_factory,
        provider_registry=InMemoryProviderRegistry(),  # no providers enabled
    )
    set_activity_services(svc)
    prod = _make_production(session_factory)
    report = await ActivityEnvironment().run(validate_production_input, _input(prod))
    assert not report.ok
    assert any("no enabled provider" in error for error in report.errors)


async def test_load_production_status(services, session_factory):
    prod = _make_production(session_factory)
    status = await ActivityEnvironment().run(load_production_status, prod.id)
    assert status == ProductionStatus.CREATED.value


async def test_plan_next_step_returns_agent_for_creative_stage(services, session_factory):
    prod = _make_production(session_factory)  # CREATED
    decision = await ActivityEnvironment().run(plan_next_step, prod.id)
    assert isinstance(decision, OrchestratorDecision)
    assert decision.next_agent == "music_strategy"


async def test_plan_next_step_stops_at_media_stage(services, session_factory):
    prod = _make_production(session_factory, status=ProductionStatus.VISUAL_READY)
    decision = await ActivityEnvironment().run(plan_next_step, prod.id)
    assert decision.next_agent == ""
    assert decision.capability is None


async def test_execute_agent_step_runs_music_strategy(services, session_factory):
    prod = _make_production(session_factory)
    result = await ActivityEnvironment().run(execute_agent_step, AgentStep(
        production_id=prod.id, agent="music_strategy"))
    assert isinstance(result, AgentStepResult)
    assert result.agent == "music_strategy"
    assert result.ok
    assert "genre" in result.summary

    with session_scope(session_factory) as session:
        strategy = make_production_repository(session).get_music_strategy(prod.id)
    assert strategy is not None
    assert strategy.genre == "lofi"


async def test_execute_agent_step_rejects_unknown_agent(services, session_factory):
    prod = _make_production(session_factory)
    with pytest.raises(WorkflowError, match="unknown agent"):
        await ActivityEnvironment().run(execute_agent_step, AgentStep(
            production_id=prod.id, agent="nope"))


async def test_advance_production_moves_one_step_forward(services, session_factory):
    prod = _make_production(session_factory)  # CREATED
    status = await ActivityEnvironment().run(advance_production, prod.id)
    assert status == ProductionStatus.PLANNING.value

    with session_scope(session_factory) as session:
        reloaded = make_production_repository(session).get(prod.id)
    assert reloaded is not None
    assert reloaded.status is ProductionStatus.PLANNING


async def test_record_workflow_run_upserts(services, session_factory):
    record = WorkflowRunRecord(
        workflow_id="wf_run_1",
        production_id=SAMPLE_PRODUCTION_ID,
        task_queue="production",
        status="running",
        attempt=1,
    )
    await ActivityEnvironment().run(record_workflow_run, record)
    run = services.get_workflow_run("wf_run_1")
    assert run is not None
    assert run.status == "running"

    record.status = "completed"
    await ActivityEnvironment().run(record_workflow_run, record)
    run = services.get_workflow_run("wf_run_1")
    assert run.status == "completed"
    assert run.completed_at is not None


# --- Workflow definition & worker wiring -------------------------------------

def test_production_workflow_is_async_and_models_validate():
    import inspect

    assert inspect.iscoroutinefunction(ProductionWorkflow.run)
    inp = ProductionWorkflowInput(
        production_id=SAMPLE_PRODUCTION_ID,
        mode=ProductionMode.GENRE,
        genre="lofi",
        target_duration_minutes=60,
    )
    assert inp.mode is ProductionMode.GENRE
    assert inp.target_duration_minutes == 60

    out = ProductionWorkflowOutput(
        production_id=SAMPLE_PRODUCTION_ID,
        status=ProductionStatus.COMPLETED,
    )
    assert out.completed_steps == []
    assert out.attempt == 1


def test_all_activities_resolve_for_worker_registration():
    """Every registered activity must resolve to a callable the worker can wire."""
    from api.activities import pipeline as pipeline_module
    from api.activities import production as production_module

    for name in ALL_ACTIVITIES:
        resolved = getattr(production_module, name, None) or getattr(pipeline_module, name, None)
        assert callable(resolved), name


def test_workflow_modules_never_import_side_effect_layers_at_top_level():
    """Workflows must stay deterministic (TDD-001 §23): no db/provider/media/fs
    imports outside the ``imports_passed_through`` block."""
    forbidden_roots = {"os", "subprocess", "pathlib", "tempfile", "shutil", "socket", "secrets"}
    forbidden_packages = ("api.database", "api.providers", "api.storage", "api.media", "sqlalchemy")
    pattern = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z_][\w.]*)")
    workflow_dir = Path(__file__).resolve().parents[1] / "src/api/workflows"
    offenders: list[str] = []
    for path in sorted(workflow_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            match = pattern.match(line)
            if not match:
                continue
            module = match.group(1)
            root = module.split(".")[0]
            if root in forbidden_roots or module.startswith(forbidden_packages):
                offenders.append(f"{path.name}: {line.strip()}")
    assert offenders == [], "workflows must not import side-effect layers:\n" + "\n".join(offenders)


# --- Server-backed end-to-end (in-process Temporal test server) --------------

async def test_production_workflow_end_to_end_with_server(services, session_factory, settings):
    """Drive ProductionWorkflow to completion through the in-process test server.

    Registers a real Worker (``ProductionWorkflow`` + ``ALL_ACTIVITIES``) against
    ``WorkflowEnvironment.start_time_skipping()`` and asserts the run reaches
    COMPLETED with every §69 Final Output Contract artifact on disk — the Phase 26
    Final Acceptance proof that the whole pipeline executes through Temporal with
    the real media engines.
    """
    from temporalio.contrib.pydantic import pydantic_data_converter
    from temporalio.testing import WorkflowEnvironment
    from temporalio.worker import Worker

    from api.activities import resolve_activity_functions
    from api.workflows.production import ProductionWorkflow, ProductionWorkflowInput

    prod = _make_production(session_factory)
    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as env:
        async with Worker(
            env.client,
            task_queue="production",
            workflows=[ProductionWorkflow],
            activities=resolve_activity_functions(),
        ):
            handle = await env.client.start_workflow(
                ProductionWorkflow,
                arg=ProductionWorkflowInput(
                    production_id=prod.id, mode=prod.mode, genre=prod.genre,
                ),
                id=f"wf-{prod.id}",
                task_queue="production",
            )
            result = await handle.result()

    # Final output contract (MASTER §69).
    assert result.production_id == prod.id
    assert result.status == ProductionStatus.COMPLETED
    root = settings.app_data_dir / "productions" / prod.id
    for rel in (
        "render/master-16x9.mp4",
        "render/short-9x16.mp4",
        "metadata/metadata.json",
        "manifest/production.json",
        "qc/qc-report.json",
    ):
        assert (root / rel).exists(), f"missing final artifact: {rel}"
