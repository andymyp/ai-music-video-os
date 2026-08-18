"""Embedding capability contract (TDD-001 §34).

Embedding providers map text to a dense vector for semantic similarity and
deduplication (ADR-010 selects LanceDB for local semantic memory; providers
supply the vectors it stores).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """A provider that embeds text into a dense vector."""

    async def embed(self, text: str) -> list[float]:
        """Return the embedding vector for *text*."""
        ...
