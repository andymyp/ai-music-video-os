"""Runtime directory layout under the application data directory.

Structure mirrors MAD-001 §11:

    data/
    ├── database/
    ├── productions/
    ├── assets/
    ├── cache/
    ├── logs/
    └── temp/
"""

from __future__ import annotations

from pathlib import Path

from api.config.settings import AppSettings

RUNTIME_DIR_NAMES: tuple[str, ...] = (
    "database",
    "productions",
    "assets",
    "cache",
    "logs",
    "temp",
)


def runtime_dirs(settings: AppSettings) -> dict[str, Path]:
    return {name: settings.app_data_dir / name for name in RUNTIME_DIR_NAMES}


def ensure_runtime_dirs(settings: AppSettings) -> list[Path]:
    """Create every runtime directory, returning the created paths."""
    created: list[Path] = []
    for path in runtime_dirs(settings).values():
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    return created
