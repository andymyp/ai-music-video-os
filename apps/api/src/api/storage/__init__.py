"""Filesystem storage (MAD-001 §11, ADR-006; TDD-001 §62-65).

Phase 00 establishes the runtime directory layout; Phase 03 adds the production
artifact layout, the low-level :class:`StorageService`, the
:class:`ArtifactService`, and the core :class:`~api.core.hashing.HashService`.
"""
from __future__ import annotations

from api.storage.artifacts import (
    PRODUCTION_SUBDIRS,
    ArtifactKind,
    ArtifactService,
)
from api.storage.layout import ensure_runtime_dirs, runtime_dirs
from api.storage.storage import StorageService

__all__ = [
    "ensure_runtime_dirs",
    "runtime_dirs",
    "StorageService",
    "ArtifactService",
    "ArtifactKind",
    "PRODUCTION_SUBDIRS",
]
