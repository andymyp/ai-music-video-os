"""Temporal worker entry point (MAD-001 §9, TDD-001 §22-25).

Starts a worker on the configured task queue with the production workflow
(Phase 10) and all activities. The Phase 00 ``FoundationSmokeWorkflow`` is
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

    # Resolve the actual activity functions by name from the core and pipeline
    # activity modules (avoids circular imports at worker startup).
    activity_modules = [
        __import__("api.activities.production", fromlist=["_ACTIVITY_DISPATCH"]),
        __import__("api.activities.pipeline", fromlist=["_ACTIVITY_DISPATCH"]),
    ]
    activity_funcs: list[object] = []
    for name in _ALL_ACTIVITY_NAMES:
        for module in activity_modules:
            func = getattr(module, name, None)
            if func is not None:
                activity_funcs.append(func)
                break

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
