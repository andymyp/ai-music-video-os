"""Quality Control Agent (MAD-001 §34; PRD-001 §69).

Receives the technical QC results, applies the deterministic mandatory-check
policy (failed mandatory checks are issues, other failures degrade to warnings)
and, when the ``llm_generate`` tool is available, inspects creative quality.
The final :class:`QualityDecision` approves or rejects the production; a
production may only pass when no mandatory issue exists (MAD-001 §33).
"""
from __future__ import annotations

from typing import Any

from api.agents.tools import ToolRegistry
from api.capabilities import StructuredGenerationRequest
from api.domain.agents import QualityControlRequest
from api.domain.outputs import QualityDecision

_CREATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "remarks": {"type": "string"},
    },
    "required": ["score"],
}


class QualityControlAgent:
    """Evaluates technical and creative quality of a production."""

    name = "quality_control"
    version = "quality_control_v1"
    description = "Produces the structured QC report and approve/reject decision."

    def __init__(self, tools: ToolRegistry) -> None:
        self._tools = tools

    async def execute(self, request: QualityControlRequest) -> QualityDecision:
        failed = [check for check in request.technical_checks if not check.passed]
        issues = [check.name for check in failed if check.name in request.mandatory_checks]
        warnings = [check.name for check in failed if check.name not in request.mandatory_checks]

        creative_score = await self._assess_creative(request.creative_context)
        base_score = self._technical_score(request.technical_checks)
        score = round(creative_score * 0.5 + base_score * 0.5, 3) if creative_score is not None else round(base_score, 3)

        # TDD-001 §131: a production cannot complete when mandatory QC failures
        # exist; warnings are allowed by policy. The score is part of the report
        # but mandatory issues are the gate.
        passed = not issues
        return QualityDecision(passed=passed, issues=issues, warnings=warnings, score=score)

    @staticmethod
    def _technical_score(checks) -> float:
        if not checks:
            return 1.0
        return sum(1 for check in checks if check.passed) / len(checks)

    async def _assess_creative(self, context: str) -> float | None:
        """Return a 0-1 creative score, or ``None`` when no LLM is available."""
        if not context or not self._tools.available("llm_generate"):
            return None
        llm = self._tools.get("llm_generate")
        result = await llm.run(
            StructuredGenerationRequest(
                task="creative_qc",
                prompt=f"Judge the creative quality of this production: {context}",
                system_prompt="Return a JSON object with a 0-1 score.",
                output_schema=_CREATIVE_SCHEMA,
            )
        )
        try:
            score = float(result.data.get("score", 0.5))
        except (TypeError, ValueError):
            score = 0.5
        return min(max(score, 0.0), 1.0)
