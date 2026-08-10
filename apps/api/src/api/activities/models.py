"""Typed activity input/output payloads (MAD-001 §9, TDD-001 §23-24).

These small Pydantic models cross the Temporal activity boundary. They stay
small and JSON-serializable so workflow history records only what the workflow
needs to coordinate stages; heavy artifacts live on the filesystem/database and
are referenced by id, never passed through the workflow.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from api.domain.enums import ProductionStatus


class ValidationReport(BaseModel):
    """Result of the first activity (TDD-001 §25)."""

    ok: bool
    checked: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AgentStep(BaseModel):
    """Which agent step to run for a production (decided by the orchestrator)."""

    production_id: str
    agent: str
    regenerate: bool = False
    reason: str = ""


class AgentStepResult(BaseModel):
    """Small result a stage activity returns to the workflow."""

    production_id: str
    agent: str
    ok: bool = True
    summary: str = ""
    error: str = ""


class WorkflowRunRecord(BaseModel):
    """Status of a workflow run persisted to ``workflow_runs`` (TDD-001 §18)."""

    workflow_id: str
    production_id: str
    workflow_type: str = "ProductionWorkflow"
    task_queue: str = "production"
    status: str = "running"
    attempt: int = 1
    error: str | None = None
    completed_status: ProductionStatus | None = None
