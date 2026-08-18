"""Project path discovery.

The backend source lives under ``apps/api/src``; runtime data defaults to the
repository root ``data/`` directory. Locating the root from ``pyproject.toml``
keeps the layout portable (MAD-001 §90: no hard-coded paths).
"""

from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    """Return the repository root, identified by the root ``pyproject.toml``."""
    current = (start or Path(__file__).resolve()).parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    # Fallback: deepest known directory rather than raising.
    return current
