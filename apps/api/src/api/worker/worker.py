"""Temporal worker entry point (MAD-001 §9, TDD-001 §22-25).

Starts a worker on the configured task queue with the production workflow
(Phase 09) and all activities. The Phase 00 ``FoundationSmokeWorkflow`` is
retained so ``scripts/run-temporal-smoke.sh`` keeps working; the real workflow
is ``ProductionWorkflow`` (MAD-001 §9).
"""

from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from api.activities import WorkflowServices, set_activity_services
from api.activities import ALL_ACTIVITIES as _ALL_ACTIVITY_NAMES
from api.config.settings import AppSettings, get_settings
from api.core.logging import configure_logging
from api.worker.smoke import FoundationSmokeWorkflow
from api.workflows.production import ProductionWorkflow


async def run_worker(settings: AppSettings | None = None) -> None:
    settings = settings or get_settings()
    configure_logging(settings)

    # Build the services container (registers mock providers in dev/test).
    services = WorkflowServices(settings=settings)
    set_activity_services(services)

    # Resolve the actual activity functions by name (avoids circular
    # imports when modules are loaded at worker startup).
    activity_module = __import__("api.activities.production", fromlist=["_ACTIVITY_DISPATCH"])
    activity_dispatch: dict[str, object] = {
        name: getattr(activity_module, name)
        for name in _ALL_ACTIVITY_NAMES
    }
    activity_funcs = list(activity_dispatch.values())

    client = await Client.connect(settings.temporal_address)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[ProductionWorkflow, FoundationSmokeWorkflow],
        activities=activity_funcs,
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
