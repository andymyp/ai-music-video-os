"""Agent layer (TDD-001 §38-41, §93; MAD-001 §33-34, §67-69).

Agents make creative decisions with typed inputs/outputs, using only the
registered tools on the :class:`~api.agents.runtime.AgentRuntime` tool registry
to reach capabilities and the media layer. No agent has filesystem, shell,
database or secret access (TDD-001 §93).
"""
from __future__ import annotations

from api.agents.base import Agent, generation_schema
from api.agents.metadata import MetadataAgent
from api.agents.music_generation import MusicGenerationAgent
from api.agents.music_strategy import MusicStrategyAgent
from api.agents.orchestrator import OrchestratorAgent
from api.agents.quality_control import QualityControlAgent
from api.agents.runtime import AgentRuntime, build_agent_runtime
from api.agents.short_selection import ShortSelectionAgent
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
from api.agents.trend import TrendResearchAgent
from api.agents.visual_generation import VisualGenerationAgent
from api.agents.visual_strategy import VisualStrategyAgent

__all__ = [
    "Agent",
    "generation_schema",
    "Tool",
    "ToolRegistry",
    "TrendSearchTool",
    "LLMGenerationTool",
    "MusicGenerationTool",
    "ImageGenerationTool",
    "CapabilityStatusTool",
    "AudioAnalysisTool",
    "AgentRuntime",
    "build_agent_runtime",
    "OrchestratorAgent",
    "TrendResearchAgent",
    "MusicStrategyAgent",
    "MusicGenerationAgent",
    "VisualStrategyAgent",
    "VisualGenerationAgent",
    "ShortSelectionAgent",
    "MetadataAgent",
    "QualityControlAgent",
]
