"""Music Generation Agent (MAD-001 §34; PRD-001 §64).

Selects an available music capability through the registered ``music_generate``
tool and returns the generated instrumental audio. Provider selection and
failover live inside the tool (PRD-001 §64.5); the agent never resolves a
provider itself.
"""
from __future__ import annotations

from api.agents.tools import ToolRegistry
from api.capabilities import GeneratedAudio, MusicGenerationRequest


class MusicGenerationAgent:
    """Generates (or obtains) the instrumental source audio."""

    name = "music_generation"
    version = "music_generation_v1"
    description = "Generates the instrumental audio via the music capability."

    def __init__(self, tools: ToolRegistry) -> None:
        self._tools = tools

    async def execute(self, request: MusicGenerationRequest) -> GeneratedAudio:
        tool = self._tools.get("music_generate")
        return await tool.run(request)
