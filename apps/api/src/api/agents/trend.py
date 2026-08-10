"""Trend Research Agent (MAD-001 §34; PRD-001 §62; TDD-001 §28-29).

Receives available trend data through the registered ``trend_search`` tool,
analyzes the signals and produces structured recommendations with a chosen
genre, confidence and reasoning. Aggregation is deterministic (TDD-001 §29):
signals are normalized into domain :class:`TrendResult` rows and ranked by
score.
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
        signals = output.signals
        if not signals:
            raise AgentError("trend search returned no signals")

        recommendations = [self._to_trend_result(signal, request.genre_hint) for signal in signals]
        recommendations.sort(key=lambda r: r.score, reverse=True)
        top = recommendations[0]
        selected_genre = request.genre_hint or top.genre or top.topic
        confidence = round(float(sum(r.score for r in recommendations) / 100.0 / len(recommendations)), 3)

        return TrendResearchResult(
            recommendations=recommendations,
            selected_genre=selected_genre,
            confidence=confidence,
            reasoning=f"top {len(recommendations)} signals ranked by score; leading: {top.topic}",
        )

    @staticmethod
    def _to_trend_result(signal, genre_hint: str | None) -> TrendResult:
        volume = float(signal.volume or 0)
        growth = float(signal.growth or 0.0)
        fields: dict[str, object] = dict(
            source=signal.platform or "unknown",
            topic=signal.topic,
            genre=genre_hint,
            score=round(signal.score * 100.0, 1),
            confidence=signal.score,
            growth=round(min(max(growth, 0.0), 1.0), 3),
            volume=round(min(volume / 10000.0, 1.0), 3),
            reasoning=signal.summary or "",
        )
        # Propagate a provider-supplied recency so identical requests stay
        # deterministic; otherwise the model's utc_now() default applies.
        if signal.recency is not None:
            fields["recency"] = signal.recency
        return TrendResult(**fields)
