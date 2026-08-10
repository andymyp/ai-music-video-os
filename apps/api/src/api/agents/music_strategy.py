"""Music Strategy Agent (MAD-001 §34; PRD-001 §63).

Creates the structured music blueprint. It follows the MAD-001 §67 flow — LLM →
JSON Schema → Pydantic validation → domain object — through the registered
``llm_generate`` tool, then validates the output into the :class:`MusicStrategy`
model, which enforces the instrumental-only policy (``vocal_policy="none"``,
PRD-001 §15). Invalid AI output raises :class:`AgentError` instead of silently
entering the pipeline (PRD-001 §70).
"""
from __future__ import annotations

from pydantic import ValidationError

from api.agents.base import generation_schema
from api.agents.tools import ToolRegistry
from api.capabilities import StructuredGenerationRequest
from api.core.errors import AgentError
from api.domain.agents import MusicStrategyRequest
from api.domain.creative import MusicStrategy


class MusicStrategyAgent:
    """Produces the instrumental music blueprint for a production."""

    name = "music_strategy"
    version = "music_strategy_v1"
    description = "Creates the structured instrumental music blueprint."

    def __init__(self, tools: ToolRegistry) -> None:
        self._tools = tools

    async def execute(self, request: MusicStrategyRequest) -> MusicStrategy:
        llm = self._tools.get("llm_generate")
        prompt = (
            f"Design the music blueprint for an instrumental {request.genre!r} "
            f"track with a {request.mood!r} mood"
            + (f", informed by the trending direction {request.trend.selected_genre!r}" if request.trend else "")
            + f", targeting {request.duration_target_minutes} minutes."
        )
        result = await llm.run(
            StructuredGenerationRequest(
                task="music_strategy",
                prompt=prompt,
                system_prompt=(
                    "Return a JSON object describing an instrumental-only music blueprint. "
                    "vocal_policy must be \"none\"."
                ),
                output_schema=generation_schema(
                    MusicStrategy,
                    genre={"default": request.genre},
                    mood={"default": request.mood},
                ),
            )
        )
        try:
            return MusicStrategy(**result.data)
        except ValidationError as exc:
            raise AgentError(f"LLM produced an invalid music strategy: {exc}") from exc
