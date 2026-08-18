"""Production workflow activities (TDD-001 §24-25, MAD-001 §9).

Activities are the only place external calls happen; the workflow coordinates
them. ``WorkflowServices`` is the dependency container; ``set_activity_services``
binds it for the ``@activity.defn`` wrappers (the Temporal worker does this at
startup, tests do it directly). Phase 09 contributed the core activities; Phase
10 adds the 18-stage pipeline (MASTER §20).
"""
from __future__ import annotations

from collections.abc import Sequence

from api.activities.models import (
    AgentStep,
    AgentStepResult,
    PipelineStageResult,
    ValidationReport,
    WorkflowRunRecord,
)
from api.activities.pipeline import PIPELINE_ACTIVITIES
from api.activities.production import (
    CORE_ACTIVITIES,
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

#: Every activity a Temporal worker must register for the production workflow.
ALL_ACTIVITIES = CORE_ACTIVITIES + PIPELINE_ACTIVITIES


def resolve_activity_functions(names: Sequence[str] = ALL_ACTIVITIES) -> list[object]:
    """Resolve registered activity *names* to their ``@activity.defn`` callables.

    ``CORE_ACTIVITIES``/``PIPELINE_ACTIVITIES`` are name lists because the two
    activity modules cannot import each other; the Temporal worker and the Phase
    26 acceptance E2E both need the decorated functions. Each name is looked up
    in the core module then the pipeline module and returned in order.
    """
    from api.activities import pipeline as _pipeline
    from api.activities import production as _production

    funcs: list[object] = []
    for name in names:
        for module in (_production, _pipeline):
            func = getattr(module, name, None)
            if func is not None:
                funcs.append(func)
                break
        else:
            raise KeyError(f"no activity named {name!r}")
    return funcs


__all__ = [
    "ALL_ACTIVITIES",
    "resolve_activity_functions",
    "CORE_ACTIVITIES",
    "PIPELINE_ACTIVITIES",
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
    "PipelineStageResult",
    "ValidationReport",
    "WorkflowRunRecord",
]
