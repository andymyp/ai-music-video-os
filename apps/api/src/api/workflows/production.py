"""ProductionWorkflow — the primary Temporal workflow (MAD-001 §9, TDD-001 §22-23).

The workflow is a deterministic stage driver. It validates input first
(TDD-001 §25), then loops: the Orchestrator Agent (Phase 08) decides the next
agent/capability, the workflow executes the corresponding *activity*, and the
production advances one state-machine step (TDD-001 §10). Every external call
happens inside an activity; the workflow itself only calls
``workflow.execute_activity`` with fixed arguments, so replay is stable.

Media-pipeline stages (audio analysis, rendering) have no creative agent yet —
the orchestrator reports ``next_agent == ""`` and the workflow returns a partial
completion result at that boundary; the media pipeline phases fill those stages.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from temporalio import workflow

from api.activities.models import AgentStep, WorkflowRunRecord
from api.domain.enums import ProductionMode, ProductionStatus
from api.domain.production import next_status_in_flow
from api.workflows.config import (
    WorkflowConfig,
    default_activity_retry_policy,
    default_workflow_config,
    provider_retry_policy,
)

with workflow.unsafe.imports_passed_through():
    # These modules must not be imported during workflow replay (they pull in
    # non-deterministic / heavy dependencies); only the workflow defn below
    # executes in the sandbox.
    from api.activities.production import (
        advance_production,
        execute_agent_step,
        load_production_status,
        plan_next_step,
        record_workflow_run,
        validate_production_input,
    )


class ProductionWorkflowInput(BaseModel):
    """Bootstrap payload for a production run."""

    production_id: str = Field(min_length=1, max_length=40)
    mode: ProductionMode
    genre: str | None = Field(default=None, max_length=64)
    branding_text: str | None = Field(default=None, max_length=80)
    provider_mode: str = "mock"
    target_duration_minutes: int = Field(default=60, ge=1, le=600)


class ProductionWorkflowOutput(BaseModel):
    """Result of a workflow run returned to the caller."""

    production_id: str
    status: ProductionStatus
    completed_steps: list[str] = Field(default_factory=list)
    attempt: int = 1
    workflow_id: str = ""
    error: str = ""


@workflow.defn
class ProductionWorkflow:
    """Drive a production through its creative stages via activities."""

    @workflow.run
    async def run(self, input: ProductionWorkflowInput) -> ProductionWorkflowOutput:
        config: WorkflowConfig = default_workflow_config()
        attempt = workflow.info().attempt
        workflow_id = workflow.info().workflow_id

        # 1. Cheap validation gate before any generation (TDD-001 §25).
        report = await workflow.execute_activity(
            validate_production_input,
            input,
            start_to_close_timeout=config.validation_timeout,
            retry_policy=default_activity_retry_policy(),
        )
        if not report.ok:
            await self._record_run(
                config,
                WorkflowRunRecord(
                    workflow_id=workflow_id,
                    production_id=input.production_id,
                    task_queue=config.task_queue,
                    status="failed",
                    attempt=attempt,
                    error="; ".join(report.errors),
                ),
            )
            return ProductionWorkflowOutput(
                production_id=input.production_id,
                status=ProductionStatus.FAILED,
                attempt=attempt,
                workflow_id=workflow_id,
                error="; ".join(report.errors),
            )

        await self._record_run(
            config,
            WorkflowRunRecord(
                workflow_id=workflow_id,
                production_id=input.production_id,
                task_queue=config.task_queue,
                status="running",
                attempt=attempt,
            ),
        )

        completed: list[str] = []
        status = await self._load_status(config, input.production_id, completed)

        try:
            while len(completed) < config.max_steps_per_run:
                decision = await workflow.execute_activity(
                    plan_next_step,
                    input.production_id,
                    start_to_close_timeout=config.step_timeout,
                    retry_policy=default_activity_retry_policy(),
                )

                # Media-pipeline stage (audio analysis / rendering): no creative
                # agent — the workflow returns partial completion; the media
                # pipeline phases implement these stages.
                if not decision.next_agent:
                    return await self._finish(
                        config, input, workflow_id, attempt, completed, status,
                        error=f"stopped at media stage {status.value!r}",
                    )

                result = await workflow.execute_activity(
                    execute_agent_step,
                    AgentStep(
                        production_id=input.production_id,
                        agent=decision.next_agent,
                        regenerate=decision.regenerate,
                        reason=decision.reason,
                    ),
                    start_to_close_timeout=config.step_timeout,
                    retry_policy=provider_retry_policy(),
                )
                completed.append(f"{result.agent}:{result.summary or 'ok'}")

                status = ProductionStatus(
                    await self._advance(config, input.production_id, completed)
                )
                if status in (ProductionStatus.COMPLETED, ProductionStatus.FAILED, ProductionStatus.CANCELLED):
                    break
        except Exception as exc:
            await self._record_run(
                config,
                WorkflowRunRecord(
                    workflow_id=workflow_id,
                    production_id=input.production_id,
                    task_queue=config.task_queue,
                    status="failed",
                    attempt=attempt,
                    error=str(exc),
                ),
            )
            raise

        # Bound workflow history on very long runs; the production's persisted
        # status lets the new run pick up exactly where this one stopped.
        if len(completed) >= config.max_steps_per_run and status not in (
            ProductionStatus.COMPLETED,
            ProductionStatus.FAILED,
            ProductionStatus.CANCELLED,
        ):
            workflow.continue_as_new(input)

        return await self._finish(config, input, workflow_id, attempt, completed, status)

    # --- helpers -------------------------------------------------------------

    async def _record_run(self, config: WorkflowConfig, record: WorkflowRunRecord) -> None:
        await workflow.execute_activity(
            record_workflow_run,
            record,
            start_to_close_timeout=config.validation_timeout,
            retry_policy=default_activity_retry_policy(),
        )

    async def _load_status(self, config: WorkflowConfig, production_id: str, completed: list[str]) -> ProductionStatus:
        status = await workflow.execute_activity(
            load_production_status,
            production_id,
            start_to_close_timeout=config.validation_timeout,
            retry_policy=default_activity_retry_policy(),
        )
        value = ProductionStatus(status)
        completed.append(value)
        return value

    async def _advance(self, config: WorkflowConfig, production_id: str, completed: list[str]) -> str:
        status = await workflow.execute_activity(
            advance_production,
            production_id,
            start_to_close_timeout=config.validation_timeout,
            retry_policy=default_activity_retry_policy(),
        )
        completed.append(status)
        return status

    async def _finish(
        self,
        config: WorkflowConfig,
        input: ProductionWorkflowInput,
        workflow_id: str,
        attempt: int,
        completed: list[str],
        status: ProductionStatus,
        error: str = "",
    ) -> ProductionWorkflowOutput:
        run_status = "failed" if status is ProductionStatus.FAILED else "completed"
        await self._record_run(
            config,
            WorkflowRunRecord(
                workflow_id=workflow_id,
                production_id=input.production_id,
                task_queue=config.task_queue,
                status=run_status,
                attempt=attempt,
                error=error or None,
            ),
        )
        return ProductionWorkflowOutput(
            production_id=input.production_id,
            status=status,
            completed_steps=completed,
            attempt=attempt,
            workflow_id=workflow_id,
            error=error,
        )
