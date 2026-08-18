"""Trend Research Agent (MAD-001 §34; PRD-001 §62; TDD-001 §28-29).

Receives scored, ranked trend results through the registered ``trend_search``
tool (which runs the Phase 11 Trend Engine), selects the strongest genre
direction and produces structured recommendations. The weighted composite
(MAD-001 §16) is computed inside the engine, so the agent interprets evidence
rather than re-normalizing raw signals.
"""
from __future__ import annotations

from api.agents.tools import ToolRegistry, TrendSearchOutput
from api.capabilities import TrendQuery
from api.core.errors import AgentError
from api.domain.agents import TrendResearchRequest, TrendResearchResult
from api.domain.creative import TrendResult


class TrendResearchAgent:
    """Interprets trend signals and picks a creative direction."""

    name = "trend_research"
    version = "trend_research_v1"
    description = "Ranks trend signals and selects the strongest genre direction."

    def __init__(self, tools: ToolRegistry) -> None:
        self._tools = tools

    async def execute(self, request: TrendResearchRequest) -> TrendResearchResult:
        trend_tool = self._tools.get("trend_search")
        anchor = request.genre_hint or "instrumental music"
        output: TrendSearchOutput = await trend_tool.run(
            TrendQuery(
                keyword=None if request.genre_hint else anchor,
                genre=request.genre_hint,
                limit=request.limit,
                time_window_days=request.time_window_days,
            )
        )
        results = list(output.results)
        if not results:
            raise AgentError("trend search returned no fresh signals")

        # The engine already ranks deterministically; re-sort defensively so the
        # agent never depends on tool ordering (TDD-001 §29).
        results.sort(key=lambda r: r.score, reverse=True)
        top = results[0]
        selected_genre = request.genre_hint or top.genre or top.topic
        confidence = round(float(sum(r.score for r in results) / 100.0 / len(results)), 3)

        return TrendResearchResult(
            recommendations=results,
            selected_genre=selected_genre,
            confidence=confidence,
            reasoning=(
                f"top {len(results)} signals ranked by weighted trend score; "
                f"leading: {top.topic} ({top.score:.1f}/100)"
            ),
        )
