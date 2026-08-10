"""Production workflow activities (TDD-001 §24-25, MAD-001 §9).

Activities are the only place external calls happen; the workflow coordinates
them. ``WorkflowServices`` is the dependency container; ``set_activity_services``
binds it for the ``@activity.defn`` wrappers (the Temporal worker does this at
startup, tests do it directly).
"""
from __future__ import annotations

from api.activities.models import AgentStep, AgentStepResult, ValidationReport, WorkflowRunRecord
from api.activities.production import (
    ALL_ACTIVITIES,
    advance_production,
    execute_agent_step,
    get_activity_services,
    load_production_status,
    plan_next_step,
    record_workflow_run,
    set_activity_services,
    validate_production_input,
)
from api.activities.services import WorkflowServices

__all__ = [
    "ALL_ACTIVITIES",
    "WorkflowServices",
    "set_activity_services",
    "get_activity_services",
    "validate_production_input",
    "load_production_status",
    "plan_next_step",
    "execute_agent_step",
    "advance_production",
    "record_workflow_run",
    "AgentStep",
    "AgentStepResult",
    "ValidationReport",
    "WorkflowRunRecord",
]
