"""Toolchain availability tests (MASTER_EXECUTION Phase 00 validation)."""

from __future__ import annotations

import shutil


def test_ffmpeg_available():
    assert shutil.which("ffmpeg") is not None, "ffmpeg must be on PATH"


def test_ffprobe_available():
    assert shutil.which("ffprobe") is not None, "ffprobe must be on PATH"


def test_core_python_imports():
    import fastapi  # noqa: F401
    import pydantic  # noqa: F401
    import sqlalchemy  # noqa: F401
    import temporalio  # noqa: F401
