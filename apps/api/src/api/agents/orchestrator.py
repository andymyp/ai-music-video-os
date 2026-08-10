"""Orchestrator Agent (MAD-001 §34; PRD-001 §61; TDD-001 §40).

High-level creative coordination: given the production state it decides which
agent to run next, which capability that stage needs, whether a result must be
regenerated and which creative direction to pursue. It performs no low-level
system operations — it only consults the registered capability-status tool and
returns a typed :class:`OrchestratorDecision`.
"""
from __future__ import annotations

from api.agents.tools import CapabilityQuery, ToolRegistry
from api.capabilities import Capability
from api.domain.agents import OrchestratorDecision, OrchestratorRequest
from api.domain.enums import ProductionMode, ProductionStatus


def _stage_map(status: ProductionStatus, mode: ProductionMode) -> tuple[str, str]:
    """Map a production status to the (agent, capability) that should run.

    Media-pipeline stages (audio analysis, rendering) have no agent; the
    workflow runs the media engine directly and the orchestrator returns ``""``.
    """
    if mode is ProductionMode.TRENDING:
        if status in (ProductionStatus.CREATED, ProductionStatus.PLANNING):
            return "trend_research", "trend"
    elif status in (ProductionStatus.CREATED, ProductionStatus.PLANNING):
        return "music_strategy", "llm"

    agents: dict[ProductionStatus, tuple[str, str]] = {
        ProductionStatus.CONCEPT_READY: ("music_strategy", "llm"),
        ProductionStatus.GENERATING_MUSIC: ("music_generation", "music"),
        ProductionStatus.MUSIC_READY: ("visual_strategy", "llm"),
        ProductionStatus.GENERATING_VISUAL: ("visual_generation", "image"),
        ProductionStatus.MASTER_READY: ("short_selection", ""),
        ProductionStatus.SHORT_READY: ("metadata", "llm"),
        ProductionStatus.GENERATING_METADATA: ("metadata", "llm"),
        ProductionStatus.QUALITY_CHECK: ("quality_control", "llm"),
    }
    return agents.get(status, ("", ""))


class OrchestratorAgent:
    """Coordinates creative stages for one production."""

    name = "orchestrator"
    version = "orchestrator_v1"
    description = "Decides which agent/capability runs next for a production stage."

    def __init__(self, tools: ToolRegistry) -> None:
        self._tools = tools

    async def execute(self, input: OrchestratorRequest) -> OrchestratorDecision:
        next_agent, capability = _stage_map(input.current_status, input.mode)
        reason = f"production status {input.current_status.value!r}"

        if input.context.get("regenerate"):
            next_agent = input.context.get("regenerate_agent", next_agent)
            regenerate = True
        else:
            regenerate = False

        if capability and self._tools.available("capability_status"):
            status = await self._tools.get("capability_status").run(
                CapabilityQuery(capability=Capability(capability))
            )
            if not status.available:
                reason += f"; capability {capability!r} has no enabled provider"

        creative_direction = "trending" if input.mode is ProductionMode.TRENDING else (input.genre or "")
        if next_agent:
            reason += f" → run {next_agent}"
        else:
            reason += " → media pipeline stage"

        return OrchestratorDecision(
            next_agent=next_agent,
            capability=capability or None,
            regenerate=regenerate,
            reason=reason,
            creative_direction=creative_direction,
        )
