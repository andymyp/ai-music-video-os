#!/usr/bin/env python
"""Phase 25 performance benchmark (MASTER §40, TDD-001 §145).

Runs one full mock-provider production through the *real* media engines and
reports the §40 performance-budget metrics:

* RAM usage        — process RSS + system memory % before/after the run
* CPU utilization  — instantaneous utilization sampled before/after
* Disk usage       — volume utilization + free bytes before/after
* FFmpeg performance — per-render wall clock (render_master / render_short)
* AI request latency — mock provider latency from the metrics store
* workflow duration  — total wall clock from validation to COMPLETED

The run uses an isolated temp data directory and mock providers (no network),
so it is safe to run on the development laptop whenever a budget needs to be
recorded. The bounded-concurrency default (one heavy render at a time,
``max_render_workers=1``) is enforced by the render gate and reported.

Usage:
    uv run python scripts/benchmark_performance.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import time
from pathlib import Path

from temporalio.testing import ActivityEnvironment

from api.activities import advance_production, set_activity_services
from api.activities.production import validate_production_input
from api.activities.services import MIN_DISK_FREE_BYTES, WorkflowServices
from api.capabilities import InMemoryProviderRegistry
from api.config.settings import AppSettings
from api.core.metrics import MetricsStore
from api.core.observability import set_metrics
from api.core.system import SystemResourceSample, sample_system_resources
from api.database import create_session_factory, make_production_repository, session_scope
from api.database.base import Base
from api.database.engine import create_engine_from_settings
from api.domain.enums import ProductionMode
from api.domain.production import Production
from api.providers import register_mock_providers
from api.workflows.production import PIPELINE_STAGES, ProductionWorkflowInput


def _build_settings(data_dir: Path) -> AppSettings:
    return AppSettings(
        app_env="test",
        provider_mode="mock",
        log_level="WARNING",
        app_data_dir=data_dir,
        database_url=f"sqlite:///{(data_dir / 'database' / 'benchmark.db').as_posix()}",
    )


def _report(
    stages: list[dict[str, object]],
    metrics: MetricsStore,
    *,
    start: SystemResourceSample,
    end: SystemResourceSample,
    disk_free: int,
    gate_max_workers: int,
    total_ms: float,
) -> None:
    """Print the §40 performance budget as a plain text report."""
    summary = metrics.summary()
    renders = [s for s in stages if s["name"] in ("render_master", "render_short")]

    print()
    print("-" * 62)
    print("PERFORMANCE BUDGET (Phase 25, MASTER §40)")
    print("-" * 62)
    print(f"  workflow duration            : {total_ms / 1000.0:9.2f} s")
    print(f"  AI request latency (avg)     : {summary.provider_latency_avg_ms:9.2f} ms "
          f"({summary.provider_calls} mock provider calls)")
    print(f"  FFmpeg render duration (avg) : {summary.render_duration_avg_ms:9.2f} ms "
          f"({len(renders)} renders)")
    for stage in renders:
        print(f"      {stage['name']:24s}: {stage['duration_ms']:9.2f} ms")
    print(f"  bounded concurrency          : {gate_max_workers} heavy render(s) at a time "
          f"(MASTER §40, TDD-001 §87)")

    print()
    print("  SYSTEM RESOURCES (sampled)")
    print("-" * 62)
    print(f"  RAM  : {start.memory_percent:5.1f}% -> {end.memory_percent:5.1f}% system | "
          f"RSS {start.rss_bytes / 1e6:.1f} -> {end.rss_bytes / 1e6:.1f} MB")
    print(f"  CPU  : {start.cpu_percent:5.1f}% -> {end.cpu_percent:5.1f}% (instantaneous)")
    print(f"  DISK : {start.disk_percent:5.1f}% -> {end.disk_percent:5.1f}% of volume | "
          f"free {disk_free / 1e6:.0f} MB (minimum required {MIN_DISK_FREE_BYTES / 1e6:.0f} MB)")

    print()
    print("  METRICS SUMMARY (metrics.db aggregates)")
    print("-" * 62)
    print(f"  total operations : {summary.total_operations}")
    print(f"  failures         : {summary.failures}  (provider {summary.provider_failures}, "
          f"workflow {summary.workflow_failures}, qc {summary.qc_failures})")
    print(f"  completed prod.  : {summary.completed_productions}")
    print(f"  workflow runs    : {summary.workflow_runs}")
    print(f"  healthy          : {summary.healthy}")
    print()


async def _run(data_dir: Path) -> int:
    settings = _build_settings(data_dir)
    metrics = MetricsStore(data_dir / "database" / "metrics.db")
    set_metrics(metrics)

    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    engine = create_engine_from_settings(settings)
    # Standalone script: create the schema directly (the API does this in its
    # lifespan; the benchmark runs outside the API process).
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings, engine=engine)
    svc = WorkflowServices(
        settings=settings,
        session_factory=session_factory,
        provider_registry=registry,
        metrics=metrics,
    )
    set_activity_services(svc)

    production = Production(mode=ProductionMode.GENRE, genre="lofi")
    with session_scope(session_factory) as session:
        make_production_repository(session).create(production)
    production_id = production.id
    wf_input = ProductionWorkflowInput(
        production_id=production_id,
        mode=ProductionMode.GENRE,
        genre="lofi",
    )

    print("=" * 62)
    print(f"Phase 25 performance benchmark | production {production_id}")
    print("mock providers | real media engines (FFmpeg) | isolated temp data dir")
    print("=" * 62)

    env = ActivityEnvironment()
    start_sample = sample_system_resources(settings.app_data_dir)
    t_start = time.perf_counter()
    metrics.record_production_start(production_id)

    report = await env.run(validate_production_input, wf_input)
    if not report.ok:
        print(f"validation failed: {report.errors}")
        return 1

    stages: list[dict[str, object]] = []
    for stage in PIPELINE_STAGES:
        t0 = time.perf_counter()
        result = await env.run(stage.activity, production_id)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        if not result.ok:
            print(f"[FAIL] {stage.name}: {result.error}")
            return 1
        stages.append({"name": stage.name, "duration_ms": duration_ms, "summary": result.summary})
        if stage.advance:
            await env.run(advance_production, production_id)

    end_sample = sample_system_resources(settings.app_data_dir)
    total_ms = (time.perf_counter() - t_start) * 1000.0
    metrics.record_production_completed(production_id)
    disk_free = svc.disk_free_bytes()

    print()
    print("STAGE TIMING (wall clock, ms)")
    print("-" * 62)
    for stage in sorted(stages, key=lambda s: float(s["duration_ms"]), reverse=True):
        print(f"  {stage['name']:28s}: {stage['duration_ms']:9.2f} ms")
    print(f"  {'TOTAL':28s}: {total_ms:9.2f} ms")

    _report(
        stages,
        metrics,
        start=start_sample,
        end=end_sample,
        disk_free=disk_free,
        gate_max_workers=svc.render_gate.max_workers,
        total_ms=total_ms,
    )
    return 0


def main() -> int:
    # The report uses UTF-8 punctuation (§); make Windows consoles not mangle it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data_dir = Path(tempfile.mkdtemp(prefix="amv-benchmark-"))
    try:
        return asyncio.run(_run(data_dir))
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
