"""Temporal worker entry point (MAD-001 §9, TDD-001 §22-25).

Starts a worker on the configured task queue with the production workflow
(Phase 10) and all activities. The Phase 00 ``FoundationSmokeWorkflow`` is
retained so ``scripts/run-temporal-smoke.sh`` keeps working; the real workflow
is ``ProductionWorkflow`` (MAD-001 §9).
"""

from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from api.activities import WorkflowServices, resolve_activity_functions, set_activity_services
from api.config.settings import AppSettings, get_settings
from api.core.logging import configure_logging
from api.core.observability import get_metrics, init_metrics
from api.media.audio import AudioAnalysisEngine
from api.media.ffmpeg import FFmpegMediaEngine
from api.storage.artifacts import ArtifactService
from api.storage.storage import StorageService
from api.worker.smoke import FoundationSmokeWorkflow
from api.workflows.production import ProductionWorkflow


async def run_worker(settings: AppSettings | None = None) -> None:
    settings = settings or get_settings()
    configure_logging(settings)
    # Phase 22 observability: the SQLite metrics store backs provider/stage/
    # workflow instrumentation for the life of the worker.
    init_metrics(settings)

    # Build the services container (registers mock providers in dev/test).
    services = WorkflowServices(
        settings=settings,
        media_engine=FFmpegMediaEngine(),
        audio_engine=AudioAnalysisEngine(),
        artifact_service=ArtifactService(
            StorageService(settings.app_data_dir),
            settings.app_data_dir / "productions",
        ),
        metrics=get_metrics(),
    )
    set_activity_services(services)

    # Pydantic data converter so workflow input/output and activity args
    # round-trip as models, not plain dicts (TDD-001 §23).
    client = await Client.connect(
        settings.temporal_address,
        data_converter=pydantic_data_converter,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[ProductionWorkflow, FoundationSmokeWorkflow],
        activities=resolve_activity_functions(),
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
