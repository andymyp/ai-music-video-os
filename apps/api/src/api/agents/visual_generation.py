"""Visual Generation Agent (MAD-001 §34; PRD-001 §66).

Produces a usable visual asset (background) through the registered
``image_generate`` tool. Asset search and validation happen in later pipeline
phases; here the agent returns the generated :class:`GeneratedImage`.
"""
from __future__ import annotations

from api.agents.tools import ToolRegistry
from api.capabilities import GeneratedImage, ImageGenerationRequest


class VisualGenerationAgent:
    """Generates the background/visual asset via the image capability."""

    name = "visual_generation"
    version = "visual_generation_v1"
    description = "Generates the background image via the image capability."

    def __init__(self, tools: ToolRegistry) -> None:
        self._tools = tools

    async def execute(self, request: ImageGenerationRequest) -> GeneratedImage:
        tool = self._tools.get("image_generate")
        return await tool.run(request)
