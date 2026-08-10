"""SHA-256 hashing (MAD-001 §61, TDD-001 §65).

Every final artifact is hashed so the system can verify integrity, deduplicate
binaries, and reproduce outputs deterministically. Files are streamed in chunks
so multi-GB renders are hashed without loading them into memory.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


class HashService:
    """Streaming SHA-256 helpers for files and in-memory data."""

    def __init__(self, chunk_size: int = 1024 * 1024) -> None:
        self._chunk_size = chunk_size

    def sha256_file(self, path: Path) -> str:
        """Return the lowercase hex SHA-256 digest of *path* (streamed)."""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(self._chunk_size), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def sha256_bytes(self, data: bytes) -> str:
        """Return the lowercase hex SHA-256 digest of a byte string."""
        return hashlib.sha256(data).hexdigest()

    def sha256_text(self, text: str) -> str:
        """Return the lowercase hex SHA-256 digest of a UTF-8 string."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def verify(self, path: Path, expected: str) -> bool:
        """Return True if *path*'s digest matches *expected* (case-insensitive)."""
        return self.sha256_file(path) == expected.lower()
