"""Production workflow activities (MAD-001 §9, TDD-001 §24-25).

Every external call — provider calls, database operations, filesystem checks —
lives in these activities; the workflow only coordinates them (TDD-001 §23-24).
The ``@activity.defn`` wrappers are thin: they resolve the process-wide
:class:`~api.activities.services.WorkflowServices` container and delegate.
Deterministic request derivation and side-effect methods live in ``services``
so they can be tested without a Temporal server.
"""
from __future__ import annotations

import asyncio

from temporalio import activity

from api.activities.models import AgentStep, AgentStepResult, ValidationReport, WorkflowRunRecord
from api.activities.services import MIN_DISK_FREE_BYTES, WorkflowServices
from api.domain.agents import OrchestratorDecision, OrchestratorRequest
from api.domain.enums import ProductionMode, ProductionStatus

#: All activities a Temporal worker must register for the production workflow.
ALL_ACTIVITIES = [
    "validate_production_input",
    "load_production_status",
    "plan_next_step",
    "execute_agent_step",
    "advance_production",
    "record_workflow_run",
]

_services: WorkflowServices | None = None


def set_activity_services(services: WorkflowServices) -> None:
    """Bind the process-wide services container (called by the worker at start)."""
    global _services
    _services = services


def get_activity_services() -> WorkflowServices:
    if _services is None:
        raise RuntimeError("WorkflowServices not configured; call set_activity_services() first")
    return _services


def _validation_report(*, checked: list[str], errors: list[str]) -> ValidationReport:
    return ValidationReport(ok=not errors, checked=checked, errors=errors)


@activity.defn
async def validate_production_input(input) -> ValidationReport:
    """First activity (TDD-001 §25): cheap gate before any generation.

    Validates mode, genre-when-required, branding, configuration, provider
    availability and disk space. Invalid requests terminate before expensive
    generation; permanent errors are not retried (MAD-001 §52).
    """
    services = get_activity_services()
    checked: list[str] = []
    errors: list[str] = []

    # Production must exist with a consistent, non-terminal state.
    try:
        production = await asyncio.to_thread(services.get_production, input.production_id)
        checked.append("production.exists")
    except Exception as exc:  # missing production -> permanent validation failure
        return _validation_report(checked=["production.exists"], errors=[f"production lookup failed: {exc}"])

    checked.append("mode")
    if production.mode is not ProductionMode.GENRE and production.mode is not ProductionMode.TRENDING:
        errors.append(f"unsupported production mode {production.mode!r}")
    if production.mode is ProductionMode.GENRE and not production.genre:
        errors.append("genre is required in genre mode (TDD-001 §25)")
    if production.status in (ProductionStatus.COMPLETED, ProductionStatus.CANCELLED):
        errors.append(f"production already {production.status.value!r}")

    checked.append("branding")
    if production.branding_text and len(production.branding_text) > 80:
        errors.append("branding text exceeds 80 characters")

    config = await asyncio.to_thread(services.get_production_config, input.production_id)
    checked.append("configuration")
    if config is not None and config.genre and production.genre and config.genre != production.genre:
        errors.append(f"config genre {config.genre!r} conflicts with production genre {production.genre!r}")

    availability = await asyncio.to_thread(services.provider_availability)
    checked.append("provider.availability")
    for capability, available in availability.items():
        if not available:
            errors.append(f"no enabled provider for {capability!r}")

    free = await asyncio.to_thread(services.disk_free_bytes)
    checked.append("disk.space")
    if free < MIN_DISK_FREE_BYTES:
        errors.append(f"insufficient disk space: {free} bytes free, need >= {MIN_DISK_FREE_BYTES}")

    return _validation_report(checked=checked, errors=errors)


@activity.defn
async def load_production_status(production_id: str) -> str:
    """Load the production's current status for the workflow to continue from."""
    status = await asyncio.to_thread(get_activity_services().get_production_status, production_id)
    return status.value


@activity.defn
async def plan_next_step(production_id: str) -> OrchestratorDecision:
    """Ask the Orchestrator Agent which agent/capability runs next (PRD-001 §61)."""
    services = get_activity_services()
    production = await asyncio.to_thread(services.get_production, production_id)
    decision = await services.agent_runtime.run(
        "orchestrator",
        OrchestratorRequest(current_status=production.status, mode=production.mode),
    )
    return decision


@activity.defn
async def execute_agent_step(step: AgentStep) -> AgentStepResult:
    """Run the orchestrator-decided agent (external provider calls happen here)."""
    return await get_activity_services().run_agent_step(step)


@activity.defn
async def advance_production(production_id: str) -> str:
    """Transition the production one forward step and persist it (TDD-001 §10)."""
    status = await asyncio.to_thread(
        get_activity_services().advance_production_status, production_id
    )
    return status.value


@activity.defn
async def record_workflow_run(record: WorkflowRunRecord) -> None:
    """Upsert the workflow run's lifecycle status (TDD-001 §18)."""
    await asyncio.to_thread(get_activity_services().upsert_workflow_run, record)
