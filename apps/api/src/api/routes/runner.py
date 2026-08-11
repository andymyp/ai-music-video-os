"""Workflow runner seam for the API (MASTER §29, MAD-001 §45, TDD-001 §68).

The API must not execute the production pipeline itself; it starts a Temporal
workflow and returns (MAD-001 §45: Validate → Persist → Start Workflow →
Return). :class:`ProductionRunner` is the protocol the routes depend on so
tests inject a recording fake; :class:`TemporalProductionRunner` is the real
implementation, connecting to Temporal lazily so the app boots even when no
Temporal server is reachable.
"""
from __future__ import annotations

from typing import Protocol

from api.config.settings import AppSettings
from api.workflows.config import WorkflowConfig
from api.workflows.production import ProductionWorkflow, ProductionWorkflowInput


class ProductionRunner(Protocol):
    """Starts and cancels production workflows (testable seam)."""

    async def start(
        self,
        production_id: str,
        request: ProductionWorkflowInput,
        *,
        attempt: int = 1,
    ) -> str:
        """Start/resume a production workflow and return its Temporal workflow id."""
        ...

    async def cancel(self, workflow_id: str) -> None:
        """Request cancellation of a running workflow (best-effort)."""
        ...


class TemporalProductionRunner:
    """Real Temporal-backed runner (MAD-001 §9).

    The Temporal client is created on first use so the FastAPI app starts and
    serves health/query endpoints even when the worker/server is down; only the
    start/cancel calls require a live server.
    """

    def __init__(self, settings: AppSettings, config: WorkflowConfig | None = None) -> None:
        self._settings = settings
        self._config = config or WorkflowConfig(task_queue=settings.temporal_task_queue)
        self._client = None

    async def _get_client(self):
        from temporalio.client import Client

        if self._client is None:
            self._client = await Client.connect(self._settings.temporal_address)
        return self._client

    async def start(
        self,
        production_id: str,
        request: ProductionWorkflowInput,
        *,
        attempt: int = 1,
    ) -> str:
        client = await self._get_client()
        workflow_id = self._config.workflow_id(production_id, attempt)
        await client.start_workflow(
            ProductionWorkflow,
            arg=request,
            id=workflow_id,
            task_queue=self._config.task_queue,
        )
        return workflow_id

    async def cancel(self, workflow_id: str) -> None:
        client = await self._get_client()
        handle = client.get_workflow_handle(workflow_id)
        try:
            await handle.cancel()
        except Exception:  # noqa: BLE001 - cancellation is best-effort
            # The workflow may have already completed or failed; the production's
            # CANCELLED status (persisted by the route) is the authoritative state.
            pass
