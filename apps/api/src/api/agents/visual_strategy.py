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
        parts = [
            f"Design the visual direction for an instrumental music video in {request.genre!r} "
            f"with a {request.mood!r} mood."
        ]
        if request.theme:
            parts.append(f"The creative theme is {request.theme!r}.")
        if request.music_direction:
            parts.append(f"The music direction is {request.music_direction!r}.")
        if request.branding:
            parts.append(f"Branding context: {request.branding!r}.")
        parts.append(
            "Include a central radio that can host a beat-reactive visualizer and reserve "
            "a suitable central area for it (MAD-001 §20)."
        )
        prompt = " ".join(parts)
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
