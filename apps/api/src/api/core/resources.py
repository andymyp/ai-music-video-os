"""Bounded-concurrency gate for heavy work (MASTER §41, MAD-001 §43, TDD-001 §87).

The target laptop must run one heavy render at a time until benchmarks justify
more (MASTER §40). :class:`RenderGate` turns the configured
``max_render_workers`` into an enforced limit: pipeline stages that compose a
video through FFmpeg hold a gate permit for the duration of the render, so only
``max_render_workers`` FFmpeg processes run concurrently regardless of how many
workflows the Temporal worker has in flight.

A single gate lives on the :class:`~api.activities.services.WorkflowServices`
container, so it is shared by every activity in the worker process (and replaced
per-test by an isolated container). ``asyncio.Semaphore`` is used because the
worker is a single event loop; no threading coordination is needed.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, TypeVar

from api.core.errors import ConfigurationError

T = TypeVar("T")


class RenderGate:
    """Limits the number of concurrent heavy renders to ``max_workers``.

    Use either as an async context manager around the heavy block, or with
    :meth:`run` for a one-shot call that acquires, awaits and releases::

        async with services.render_gate:
            await services.media_engine.render_master(request, profile=profile)

    ``max_workers`` must be ``>= 1``; the application default is 1 (one heavy
    rendering task at a time, MASTER §40). Raise ``max_workers`` only after
    benchmarks show headroom (TDD-001 §87, §145).
    """

    def __init__(self, max_workers: int) -> None:
        if max_workers < 1:
            raise ConfigurationError("max_render_workers must be >= 1")
        self.max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)

    # -- context-manager surface ---------------------------------------------

    async def __aenter__(self) -> "RenderGate":
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._semaphore.release()

    # -- one-shot surface ------------------------------------------------------

    async def run(self, coro: Awaitable[T]) -> T:
        """Acquire a permit, await ``coro``, then release it."""
        async with self:
            return await coro

    # -- inspection -------------------------------------------------------------

    @property
    def permits_available(self) -> int:
        """How many renders may still start without blocking (test/observability)."""
        return self._semaphore._value  # type: ignore[attr-defined]
