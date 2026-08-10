"""Temporal worker entry point.

Starts a worker on the configured task queue. The full activity/workflow set is
registered in Phase 09/10 (Workflow Runtime / Production Workflow).
"""

from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from api.config.settings import AppSettings, get_settings
from api.core.logging import configure_logging
from api.worker.smoke import FoundationSmokeWorkflow


async def run_worker(settings: AppSettings | None = None) -> None:
    settings = settings or get_settings()
    configure_logging(settings)
    client = await Client.connect(settings.temporal_address)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[FoundationSmokeWorkflow],
        activities=[],
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
