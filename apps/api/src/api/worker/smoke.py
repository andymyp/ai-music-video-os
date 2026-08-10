"""Phase 00 placeholder workflow.

Proves the Temporal worker can register and execute a workflow. Replaced by the
real ``ProductionWorkflow`` in Phase 09/10.
"""

from __future__ import annotations

from temporalio import workflow


@workflow.defn
class FoundationSmokeWorkflow:
    """Return a deterministic greeting used to validate the worker end-to-end."""

    @workflow.run
    async def run(self, name: str) -> str:
        return f"foundation-ok:{name}"
