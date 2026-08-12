"""System resource sampling (MASTER §40, MAD-001 §43, TDD-001 §87-89).

Thin psutil-based helpers for the Phase 25 performance telemetry: RAM usage,
CPU utilization, disk usage and the worker's own resident-set footprint. Values
are sampled on demand; nothing here loads media into memory — it only reads
operating-system counters, so it is safe to call at any point in the pipeline.

``SystemResourceSample`` is a plain frozen dataclass so it round-trips into the
metrics store's JSON ``detail`` column without pulling pydantic into the hot
path.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

import psutil


@dataclass(frozen=True)
class SystemResourceSample:
    """A point-in-time snapshot of the machine's resource state.

    All percentages are 0..100. ``disk_percent`` is the fraction of the volume
    holding ``data_root`` (default: the process working directory's volume).
    """

    memory_percent: float
    cpu_percent: float
    disk_percent: float
    rss_bytes: int

    def to_dict(self) -> dict[str, float | int]:
        """Plain mapping for JSON serialization into the metrics store."""
        return asdict(self)


def memory_usage_percent() -> float:
    """Fraction of physical RAM currently in use (0..100)."""
    return float(psutil.virtual_memory().percent)


def cpu_usage_percent(interval: float = 0.0) -> float:
    """Instantaneous CPU utilization across all cores (0..100).

    With ``interval=0.0`` (the default) the value is since the last call, so a
    single isolated sample is an approximation; callers that want a stable
    number should pass a small nonzero interval or average several samples.
    """
    return float(psutil.cpu_percent(interval=interval))


def process_rss_bytes() -> int:
    """Resident set size of this process in bytes (0 if unavailable)."""
    try:
        return int(psutil.Process().memory_info().rss)
    except (psutil.Error, OSError):
        return 0


def disk_usage_percent(path: Path | str | None = None) -> float:
    """Fraction of the ``path`` volume that is in use (0..100)."""
    probe = Path(path) if path is not None else Path.cwd()
    try:
        # psutil's C extension wants a native str (Windows rejects Path objects).
        return float(psutil.disk_usage(str(probe)).percent)
    except (psutil.Error, OSError):
        return 0.0


def sample_system_resources(path: Path | str | None = None) -> SystemResourceSample:
    """Capture a consistent one-shot resource snapshot (RAM/CPU/disk/RSS)."""
    return SystemResourceSample(
        memory_percent=memory_usage_percent(),
        cpu_percent=cpu_usage_percent(),
        disk_percent=disk_usage_percent(path),
        rss_bytes=process_rss_bytes(),
    )


__all__ = [
    "SystemResourceSample",
    "cpu_usage_percent",
    "disk_usage_percent",
    "memory_usage_percent",
    "process_rss_bytes",
    "sample_system_resources",
]
