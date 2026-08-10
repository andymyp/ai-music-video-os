"""Visual Strategy Agent (MAD-001 §34; PRD-001 §65).

Produces the structured visual blueprint (environment, radio style, composition,
visualizer placement) using the same MAD-001 §67 LLM flow as the music strategy
agent, validated into the :class:`VisualStrategy` domain model.
"""
from __future__ import annotations

from pydantic import ValidationError

from api.agents.base import generation_schema
from api.agents.tools import ToolRegistry
from api.capabilities import StructuredGenerationRequest
from api.core.errors import AgentError
from api.domain.agents import VisualStrategyRequest
from api.domain.creative import VisualStrategy


class VisualStrategyAgent:
    """Creates the structured visual blueprint for a production."""

    name = "visual_strategy"
    version = "visual_strategy_v1"
    description = "Creates the structured visual/radio blueprint."

    def __init__(self, tools: ToolRegistry) -> None:
        self._tools = tools

    async def execute(self, request: VisualStrategyRequest) -> VisualStrategy:
        llm = self._tools.get("llm_generate")
        prompt = (
            f"Design the visual direction for an instrumental music video in {request.genre!r} "
            f"with a {request.mood!r} mood. Include a central radio that can host a beat-reactive "
            f"visualizer."
        )
        result = await llm.run(
            StructuredGenerationRequest(
                task="visual_strategy",
                prompt=prompt,
                system_prompt=(
                    "Return a JSON object describing the visual blueprint. "
                    "radio_style and composition must be non-empty."
                ),
                output_schema=generation_schema(VisualStrategy),
            )
        )
        try:
            return VisualStrategy(**result.data)
        except ValidationError as exc:
            raise AgentError(f"LLM produced an invalid visual strategy: {exc}") from exc
