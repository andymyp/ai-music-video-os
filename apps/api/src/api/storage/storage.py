"""StorageService — low-level filesystem operations under a bounded root.

Binary media lives on the filesystem (MAD-001 §11, §53; ADR-006); this service
owns every file operation a production needs (write/read/exists/delete/hash/
size/metadata, per MASTER_EXECUTION.md §13). All paths are resolved relative to
the configured root and verified to stay inside it (MAD-001 §1745: filenames
must be sanitized), so ``../`` traversal cannot escape the production directory.
"""
from __future__ import annotations

import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path

from api.core.errors import StorageError
from api.core.hashing import HashService


class StorageService:
    """Filesystem operations confined to a root directory."""

    def __init__(self, root: Path, hasher: HashService | None = None) -> None:
        self._root = Path(root).resolve()
        self._hasher = hasher or HashService()

    @property
    def root(self) -> Path:
        return self._root

    # --- path safety ------------------------------------------------------

    def _resolve(self, rel_path: str | Path) -> Path:
        """Resolve *rel_path* under the root, rejecting anything that escapes it."""
        candidate = (self._root / Path(rel_path)).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError:
            raise StorageError(f"path escapes storage root: {rel_path!r}") from None
        return candidate

    # --- lifecycle ---------------------------------------------------------

    def ensure_root(self) -> Path:
        """Create the root directory if needed, returning it."""
        self._root.mkdir(parents=True, exist_ok=True)
        return self._root

    # --- write --------------------------------------------------------------

    def write(self, rel_path: str | Path, data: bytes) -> Path:
        """Write raw bytes, creating parent directories. Returns the written path."""
        target = self._resolve(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_bytes(data)
        except OSError as exc:
            raise StorageError(f"failed to write {rel_path!r}: {exc}") from exc
        return target

    def write_text(self, rel_path: str | Path, text: str, encoding: str = "utf-8") -> Path:
        """Write a UTF-8 string. Returns the written path."""
        return self.write(rel_path, text.encode(encoding))

    # --- read ----------------------------------------------------------------

    def read(self, rel_path: str | Path) -> bytes:
        """Read raw bytes. Raises StorageError if the file is missing."""
        target = self._resolve(rel_path)
        if not target.is_file():
            raise StorageError(f"not a file: {rel_path!r}")
        try:
            return target.read_bytes()
        except OSError as exc:
            raise StorageError(f"failed to read {rel_path!r}: {exc}") from exc

    def read_text(self, rel_path: str | Path, encoding: str = "utf-8") -> str:
        """Read a text file as a string."""
        return self.read(rel_path).decode(encoding)

    # --- exists / delete -------------------------------------------------------

    def exists(self, rel_path: str | Path) -> bool:
        """Return True if the resolved path exists on disk."""
        return self._resolve(rel_path).exists()

    def delete(self, rel_path: str | Path) -> bool:
        """Delete a file. Returns True if something was removed."""
        target = self._resolve(rel_path)
        if not target.is_file():
            return False
        try:
            target.unlink()
        except OSError as exc:
            raise StorageError(f"failed to delete {rel_path!r}: {exc}") from exc
        return True

    # --- size / hash ------------------------------------------------------------

    def size(self, rel_path: str | Path) -> int:
        """Return the size in bytes of the file at *rel_path*."""
        target = self._resolve(rel_path)
        if not target.is_file():
            raise StorageError(f"not a file: {rel_path!r}")
        return target.stat().st_size

    def hash(self, rel_path: str | Path) -> str:
        """Return the SHA-256 digest of the file at *rel_path*."""
        target = self._resolve(rel_path)
        if not target.is_file():
            raise StorageError(f"not a file: {rel_path!r}")
        return self._hasher.sha256_file(target)

    # --- metadata -------------------------------------------------------------

    def metadata(self, rel_path: str | Path) -> dict[str, object]:
        """Return size, sha256, mtime and a guessed MIME type for *rel_path*."""
        target = self._resolve(rel_path)
        if not target.is_file():
            raise StorageError(f"not a file: {rel_path!r}")
        stat = target.stat()
        mime_type, _ = mimetypes.guess_type(target.name)
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return {
            "path": str(target.relative_to(self._root)).replace(os.sep, "/"),
            "size_bytes": stat.st_size,
            "sha256": self._hasher.sha256_file(target),
            "mime_type": mime_type,
            "modified_at": modified_at.isoformat(),
        }
