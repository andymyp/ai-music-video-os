"""ProductionWorkflow — the primary Temporal workflow (MASTER §20, MAD-001 §9).

The workflow is a deterministic stage driver. It validates the input first
(TDD-001 §25), then executes the 18 pipeline stages in the canonical order
(MASTER §20), advancing the production state machine one forward step after
each stage that owns a status transition. The stage table is fixed and
deterministic — the orchestrator agent (Phase 08) is *not* consulted for the
base flow, so replay is stable and the whole pipeline works with mock
providers. Media-pipeline work (audio analysis, rendering) is real: each stage
is an activity that performs its external call against
:class:`~api.activities.services.WorkflowServices`.

Every external call happens inside an activity; the workflow itself only calls
``workflow.execute_activity`` with fixed arguments, so replay is stable
(TDD-001 §23).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from temporalio import workflow

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
    # non-deterministic / heavy dependencies such as numpy via the media and
    # agent layers, and they are already loaded in the outer process by the
    # worker); only the workflow defn below executes in the sandbox.
    from api.activities.models import WorkflowRunRecord
    from api.activities.production import (
        advance_production,
        load_production_status,
        record_workflow_run,
        validate_production_input,
    )
    from api.activities.pipeline import (
        analyze_audio,
        complete_production,
        generate_background,
        generate_manifest,
        generate_metadata,
        generate_music,
        generate_music_strategy,
        generate_visual_strategy,
        generate_visualizer,
        master_audio,
        render_master,
        render_short,
        resolve_creative_direction,
        resolve_radio,
        run_qc,
        select_short_segment,
        validate_master,
        validate_music,
        validate_short,
    )


@dataclass(frozen=True)
class _Stage:
    """One pipeline stage: its name, the activity to run and whether it owns a
    status transition (``advance=True`` -> the production moves one forward step
    after the stage succeeds)."""

    name: str
    activity: Any
    advance: bool


#: The deterministic Phase 10 stage table (MASTER §20). ``complete_production``
#: performs the final two transitions (QUALITY_CHECK -> COMPLETED) internally and
#: therefore does not advance through the workflow's one-step helper.
PIPELINE_STAGES: tuple[_Stage, ...] = (
    _Stage("resolve_creative_direction", resolve_creative_direction, advance=True),
    _Stage("generate_music_strategy", generate_music_strategy, advance=True),
    _Stage("generate_music", generate_music, advance=True),
    _Stage("validate_music", validate_music, advance=False),
    _Stage("master_audio", master_audio, advance=False),
    _Stage("generate_visual_strategy", generate_visual_strategy, advance=True),
    _Stage("generate_background", generate_background, advance=True),
    _Stage("resolve_radio", resolve_radio, advance=False),
    _Stage("analyze_audio", analyze_audio, advance=True),
    _Stage("generate_visualizer", generate_visualizer, advance=False),
    _Stage("render_master", render_master, advance=True),
    _Stage("validate_master", validate_master, advance=True),
    _Stage("select_short_segment", select_short_segment, advance=True),
    _Stage("render_short", render_short, advance=True),
    _Stage("validate_short", validate_short, advance=True),
    _Stage("generate_metadata", generate_metadata, advance=True),
    _Stage("run_qc", run_qc, advance=True),
    _Stage("generate_manifest", generate_manifest, advance=False),
    _Stage("complete_production", complete_production, advance=False),
)

#: Stage names in pipeline order (exported for tests and reporting).
PIPELINE_STAGE_NAMES: tuple[str, ...] = tuple(stage.name for stage in PIPELINE_STAGES)

#: Statuses that end a workflow run: never continued, never resumed past.
_TERMINAL_RUN_STATUSES = frozenset(
    {ProductionStatus.COMPLETED, ProductionStatus.FAILED, ProductionStatus.CANCELLED}
)


def should_continue_as_new(
    completed_steps: int,
    max_steps: int,
    status: ProductionStatus,
) -> bool:
    """Whether the workflow must bound its history with ``continue_as_new``.

    A run continues when it reached the per-run step cap without the production
    reaching a terminal state. The next run re-reads the persisted status and
    resumes exactly where this one stopped (TDD-001 §116-117), so the decision
    is a pure function of run-local counters plus the persisted state.
    """
    if status in _TERMINAL_RUN_STATUSES:
        return False
    return completed_steps >= max_steps


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
    """Drive a production through its 19 stages via activities."""

    @workflow.run
    async def run(self, input: ProductionWorkflowInput) -> ProductionWorkflowOutput:
        # The default JSON data converter hands the sandbox a plain mapping
        # unless a pydantic converter is wired on the client. Normalize so the
        # body below always sees the model regardless of the caller's converter
        # (temporalio.contrib.pydantic handles it; the guard is defense-in-depth).
        input = ProductionWorkflowInput.model_validate(input)
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
            for stage in PIPELINE_STAGES:
                result = await workflow.execute_activity(
                    stage.activity,
                    input.production_id,
                    start_to_close_timeout=config.step_timeout,
                    retry_policy=provider_retry_policy(),
                )
                completed.append(f"{stage.name}:{result.summary or 'ok'}")
                if stage.advance:
                    status = ProductionStatus(
                        await self._advance(config, input.production_id, completed)
                    )
                    if status in (
                        ProductionStatus.COMPLETED,
                        ProductionStatus.FAILED,
                        ProductionStatus.CANCELLED,
                    ):
                        break
        except asyncio.CancelledError:
            # Cancellation requested (POST /api/productions/{id}/cancel). The
            # API already transitioned the production to CANCELLED before asking
            # Temporal to cancel; here we persist the run's terminal status so
            # cancel/progress endpoints see a complete lifecycle, then let the
            # cancellation propagate to the in-flight activities (TDD-001 §86).
            await self._record_cancelled_run(config, input, workflow_id, attempt)
            raise
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

        # ``complete_production`` performs its final QUALITY_CHECK -> COMPLETED
        # transition inside the activity (the last stage has advance=False), so
        # the local ``status`` is one step behind. Re-read the authoritative
        # persisted status so the returned output and the continue-as-new check
        # reflect the production's true terminal state (MASTER §20, §69).
        status = ProductionStatus(
            await workflow.execute_activity(
                load_production_status,
                input.production_id,
                start_to_close_timeout=config.validation_timeout,
                retry_policy=default_activity_retry_policy(),
            )
        )

        # Bound workflow history on very long runs; the production's persisted
        # status lets the new run pick up exactly where this one stopped
        # (TDD-001 §116-117: application restart -> load status -> resume).
        if should_continue_as_new(len(completed), config.max_steps_per_run, status):
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

    async def _record_cancelled_run(
        self,
        config: WorkflowConfig,
        input: ProductionWorkflowInput,
        workflow_id: str,
        attempt: int,
    ) -> None:
        """Persist the run's terminal ``cancelled`` status during cleanup.

        Called from the ``CancelledError`` handler. The record activity is
        shielded so the cancellation that triggered cleanup cannot cancel the
        write itself (TDD-001 §86: cancellation propagates through Temporal to
        the activity and media process).
        """
        await asyncio.shield(
            self._record_run(
                config,
                WorkflowRunRecord(
                    workflow_id=workflow_id,
                    production_id=input.production_id,
                    task_queue=config.task_queue,
                    status="cancelled",
                    attempt=attempt,
                ),
            )
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
