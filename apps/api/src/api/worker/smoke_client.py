"""Client that executes the Phase 00 smoke workflow.

Requires a running Temporal dev server (scripts/dev-temporal.sh) and worker
(scripts/dev-worker.sh). Prints ``SMOKE_RESULT=<value>`` on success.
"""

from __future__ import annotations

import asyncio

from temporalio.client import Client

from api.config.settings import AppSettings, get_settings
from api.worker.smoke import FoundationSmokeWorkflow

SMOKE_WORKFLOW_ID = "foundation-smoke"


async def run_smoke(settings: AppSettings | None = None) -> str:
    settings = settings or get_settings()
    client = await Client.connect(settings.temporal_address)
    handle = await client.start_workflow(
        FoundationSmokeWorkflow.run,
        arg="phase-00",
        id=SMOKE_WORKFLOW_ID,
        task_queue=settings.temporal_task_queue,
    )
    return await handle.result()


def main() -> None:
    result = asyncio.run(run_smoke())
    print(f"SMOKE_RESULT={result}")


if __name__ == "__main__":
    main()
