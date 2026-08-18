"""Phase 21: recovery & cancellation (MASTER §34; TDD-001 §83-88, §116-118; MAD-001 §52).

Covers durable-execution behaviour that can be exercised offline (no Temporal
server):

* the workflow-resume boundary (``should_continue_as_new``) that restarts a run
  from the persisted status instead of duplicating work (TDD-001 §116-117);
* the cancellation record path — a cancelled workflow run persists its terminal
  ``cancelled`` status (TDD-001 §86);
* restart recovery — activities continue forward from the persisted status and
  the final transitions are idempotent;
* failure classification — provider/media failures retry, permanent errors do
  not (MAD-001 §52).

A server-backed end-to-end cancellation run (real Temporal dev server) stays
with the gated e2e in ``test_workflows.py``; everything here runs offline.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.testing import ActivityEnvironment

from api.activities import (
    WorkflowServices,
    advance_production,
    record_workflow_run,
    set_activity_services,
)
from api.activities.models import WorkflowRunRecord
from api.activities.pipeline import complete_production
from api.agents import build_agent_runtime
from api.capabilities import InMemoryProviderRegistry
from api.core.errors import MediaProcessingError, ProviderError, RateLimitError, ValidationError
from api.core.ids import new_production_id
from api.database import make_production_repository, session_scope
from api.domain.enums import ProductionMode, ProductionStatus
from api.domain.production import Production
from api.providers import register_mock_providers
from api.workflows.config import is_retryable
from api.workflows.production import should_continue_as_new

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


def _make_production(session_factory, *, mode=ProductionMode.GENRE, genre="lofi") -> Production:
    production = Production(mode=mode, genre=genre)
    with session_scope(session_factory) as session:
        make_production_repository(session).create(production)
    return production


def _set_status(session_factory, production_id: str, status: ProductionStatus) -> None:
    """Persist a status directly (simulates where a crashed run left off)."""
    with session_scope(session_factory) as session:
        repo = make_production_repository(session)
        production = repo.get(production_id)
        production.status = status
        repo.update(production)


def _status(session_factory, production_id: str) -> ProductionStatus:
    with session_scope(session_factory) as session:
        production = make_production_repository(session).get(production_id)
    assert production is not None
    return production.status


# --- Workflow resume / restart (TDD-001 §116-117) -----------------------------

def test_should_continue_as_new_boundary():
    """A run continues (bounds history) only past the per-run step cap while the
    production is still active; terminal statuses never continue."""
    assert should_continue_as_new(49, 50, ProductionStatus.PLANNING) is False
    assert should_continue_as_new(50, 50, ProductionStatus.PLANNING) is True
    assert should_continue_as_new(60, 50, ProductionStatus.RENDERING_MASTER) is True
    for terminal in (
        ProductionStatus.COMPLETED,
        ProductionStatus.FAILED,
        ProductionStatus.CANCELLED,
    ):
        assert should_continue_as_new(60, 50, terminal) is False


async def test_advance_resumes_from_persisted_status(services, session_factory):
    """After a crash, the next run reads the persisted status and advances from
    there — restart resumes forward instead of restarting at CREATED."""
    prod = _make_production(session_factory)
    _set_status(session_factory, prod.id, ProductionStatus.RENDERING_MASTER)

    status = await ActivityEnvironment().run(advance_production, prod.id)
    assert status == ProductionStatus.MASTER_READY.value
    assert _status(session_factory, prod.id) is ProductionStatus.MASTER_READY


async def test_complete_production_resumes_final_transition(services, session_factory):
    """A crash between the last two transitions (QUALITY_CHECK) resumes to
    COMPLETED on the next run — the final transition is idempotent (MAD-001 §33)."""
    prod = _make_production(session_factory)
    _set_status(session_factory, prod.id, ProductionStatus.QUALITY_CHECK)

    result = await ActivityEnvironment().run(complete_production, prod.id)
    assert result.ok
    assert _status(session_factory, prod.id) is ProductionStatus.COMPLETED


# --- Cancellation (TDD-001 §86) -----------------------------------------------

async def test_cancelled_workflow_run_persists(services):
    """The run record a cancelled workflow leaves behind carries the terminal
    ``cancelled`` status (the API marks the production CANCELLED first; the
    workflow's CancelledError handler records the run's lifecycle)."""
    record = WorkflowRunRecord(
        workflow_id="wf-cancel-1",
        production_id=SAMPLE_PRODUCTION_ID,
        task_queue="production",
        status="cancelled",
        attempt=1,
    )
    await ActivityEnvironment().run(record_workflow_run, record)

    run = services.get_workflow_run("wf-cancel-1")
    assert run is not None
    assert run.status == "cancelled"
    assert run.attempts == 1
    # Cancellation is a terminal run state but not a completion: no completed_at.
    assert run.completed_at is None


def test_production_workflow_cancellation_and_resume_wired():
    """The workflow source wires the durable-execution guarantees: a
    CancelledError handler that records the cancelled run and re-raises, plus the
    continue_as_new resume boundary (TDD-001 §86, §116)."""
    path = Path(__file__).resolve().parents[1] / "src/api/workflows/production.py"
    text = path.read_text(encoding="utf-8")
    assert "asyncio.CancelledError" in text
    assert 'status="cancelled"' in text
    assert "workflow.continue_as_new(input)" in text
    assert "should_continue_as_new(len(completed)" in text


# --- Failure classification (MAD-001 §52) -------------------------------------

def test_retryable_failures_are_retried():
    """Transient provider failures and media failures retry with backoff."""
    assert is_retryable(ProviderError("temporary provider outage"))
    assert is_retryable(RateLimitError("rate limited"))
    assert is_retryable(MediaProcessingError("ffmpeg exit 1 on retryable render"))


def test_permanent_failures_are_not_retried():
    """Validation/auth/config failures terminate the run immediately."""
    assert not is_retryable(ValidationError("invalid input"))
