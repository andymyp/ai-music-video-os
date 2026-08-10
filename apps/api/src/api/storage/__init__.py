"""Filesystem storage.

Phase 00 establishes the runtime directory layout. Artifact/hash services are
added in Phase 03 (Filesystem Storage).
"""

from api.storage.layout import ensure_runtime_dirs, runtime_dirs

__all__ = ["ensure_runtime_dirs", "runtime_dirs"]
