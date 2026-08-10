"""Agent runtime (TDD-001 §38, §93).

The runtime owns the :class:`ToolRegistry` (the only side-effect surface) and
the registered :class:`Agent` set. The workflow layer (Phase 09+) drives
productions through ``runtime.run(name, typed_input)``; nothing else may invoke
agents. ``build_agent_runtime`` wires the standard tool + agent set over a
:class:`ProviderRegistry` and, optionally, a media engine.
"""
from __future__ import annotations

from typing import Any

from api.agents.base import Agent
from api.agents.tools import (
    AudioAnalysisTool,
    CapabilityStatusTool,
    ImageGenerationTool,
    LLMGenerationTool,
    MusicGenerationTool,
    Tool,
    ToolRegistry,
    TrendSearchTool,
)
from api.capabilities import ProviderRegistry
from api.core.errors import ConfigurationError
from api.media.audio import AudioAnalysisEngine
from api.agents.orchestrator import OrchestratorAgent
from api.agents.trend import TrendResearchAgent
from api.agents.music_strategy import MusicStrategyAgent
from api.agents.music_generation import MusicGenerationAgent
from api.agents.visual_strategy import VisualStrategyAgent
from api.agents.visual_generation import VisualGenerationAgent
from api.agents.short_selection import ShortSelectionAgent
from api.agents.metadata import MetadataAgent
from api.agents.quality_control import QualityControlAgent


class AgentRuntime:
    """Registry of registered tools + agents; the agent execution facade."""

    def __init__(self) -> None:
        self._tools = ToolRegistry()
        self._agents: dict[str, Agent[Any, Any]] = {}

    # --- tools -------------------------------------------------------------

    @property
    def tools(self) -> ToolRegistry:
        return self._tools

    def register_tool(self, tool: Tool[Any, Any]) -> None:
        self._tools.register(tool)

    def tool_names(self) -> list[str]:
        return self._tools.names()

    # --- agents ------------------------------------------------------------

    def register_agent(self, agent: Agent[Any, Any]) -> None:
        if not agent.name:
            raise ConfigurationError("agent must declare a name")
        if agent.name in self._agents:
            raise ConfigurationError(f"agent already registered: {agent.name!r}")
        self._agents[agent.name] = agent

    def get_agent(self, name: str) -> Agent[Any, Any]:
        if name not in self._agents:
            raise ConfigurationError(f"agent not registered: {name!r}")
        return self._agents[name]

    def agent_names(self) -> list[str]:
        return sorted(self._agents)

    def available(self, name: str) -> bool:
        return name in self._agents

    async def run(self, agent_name: str, input: Any) -> Any:
        """Execute the named agent with *input* and return its typed output."""
        agent = self.get_agent(agent_name)
        return await agent.execute(input)


def build_agent_runtime(
    provider_registry: ProviderRegistry,
    *,
    audio_engine: AudioAnalysisEngine | None = None,
) -> AgentRuntime:
    """Wire the standard tools + nine agents over *provider_registry*."""
    runtime = AgentRuntime()

    runtime.register_tool(TrendSearchTool(provider_registry))
    runtime.register_tool(LLMGenerationTool(provider_registry))
    runtime.register_tool(MusicGenerationTool(provider_registry))
    runtime.register_tool(ImageGenerationTool(provider_registry))
    runtime.register_tool(CapabilityStatusTool(provider_registry))
    runtime.register_tool(AudioAnalysisTool(audio_engine or AudioAnalysisEngine()))

    agents: list[Agent[Any, Any]] = [
        OrchestratorAgent(runtime.tools),
        TrendResearchAgent(runtime.tools),
        MusicStrategyAgent(runtime.tools),
        MusicGenerationAgent(runtime.tools),
        VisualStrategyAgent(runtime.tools),
        VisualGenerationAgent(runtime.tools),
        ShortSelectionAgent(runtime.tools),
        MetadataAgent(runtime.tools),
        QualityControlAgent(runtime.tools),
    ]
    for agent in agents:
        runtime.register_agent(agent)
    return runtime


__all__ = ["AgentRuntime", "build_agent_runtime"]
