"""Runtime directory layout tests (MAD-001 §11)."""

from __future__ import annotations

from api.storage.layout import RUNTIME_DIR_NAMES, ensure_runtime_dirs, runtime_dirs


def test_runtime_dirs_created(settings):
    paths = ensure_runtime_dirs(settings)
    assert len(paths) == len(RUNTIME_DIR_NAMES)
    for name, path in runtime_dirs(settings).items():
        assert path.is_dir(), f"{name} was not created"


def test_ensure_runtime_dirs_idempotent(settings):
    first = ensure_runtime_dirs(settings)
    second = ensure_runtime_dirs(settings)
    assert [p.as_posix() for p in first] == [p.as_posix() for p in second]


def test_required_dir_names():
    assert set(RUNTIME_DIR_NAMES) == {
        "database",
        "productions",
        "assets",
        "cache",
        "logs",
        "temp",
    }
