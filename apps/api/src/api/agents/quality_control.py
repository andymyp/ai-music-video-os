"""Quality Control Agent (MAD-001 §34; PRD-001 §69; TDD-001 §59-61).

Receives the technical QC results, applies the deterministic mandatory-check
policy (failed mandatory checks are issues, other failures degrade to warnings)
and, when the ``llm_generate`` tool is available, inspects creative quality
across the five structured dimensions of MAD-001 §31.2 / TDD-001 §61 — visual
coherence, visualizer placement, branding presence, content consistency and
metadata relevance — returning a :class:`CreativeAssessment` with one 0-1 score
per dimension plus the mean composite. The final :class:`QualityDecision`
approves or rejects the production; a production may only pass when no
mandatory issue exists (MAD-001 §33). Deterministic checks always run before
AI-assisted checks, and the AI score never overrides a mandatory failure
(MAD-001 §31.3, PRD-001 §35).
"""
from __future__ import annotations

from typing import Any

from api.agents.tools import ToolRegistry
from api.capabilities import StructuredGenerationRequest
from api.domain.agents import QualityControlRequest
from api.domain.outputs import CREATIVE_DIMENSIONS, CreativeAssessment, QualityDecision

_CREATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "visual_coherence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "visualizer_placement": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "branding_presence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "content_consistency": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "metadata_relevance": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "remarks": {"type": "string"},
    },
    "required": list(CREATIVE_DIMENSIONS),
}

#: Weight of the AI-assisted creative score vs the deterministic technical score
#: in the reported composite (MAD-001 §31.3). The pass/fail gate is unaffected.
_CREATIVE_WEIGHT = 0.5


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

        creative = await self._assess_creative(request.creative_context)
        base_score = self._technical_score(request.technical_checks)
        if creative is not None:
            score = round(
                creative.composite * _CREATIVE_WEIGHT + base_score * (1 - _CREATIVE_WEIGHT),
                3,
            )
        else:
            score = round(base_score, 3)

        # TDD-001 §131: a production cannot complete when mandatory QC failures
        # exist; warnings are allowed by policy. The score is part of the report
        # but mandatory issues are the gate — a high creative score never passes
        # a broken render (MAD-001 §31.3).
        passed = not issues
        return QualityDecision(
            passed=passed, issues=issues, warnings=warnings, score=score, creative=creative
        )

    @staticmethod
    def _technical_score(checks) -> float:
        if not checks:
            return 1.0
        return sum(1 for check in checks if check.passed) / len(checks)

    async def _assess_creative(self, context: str) -> CreativeAssessment | None:
        """Return the structured creative assessment, or ``None`` when no LLM is
        available (creative QC is AI-assisted and optional; MAD-001 §31.2)."""
        if not context or not self._tools.available("llm_generate"):
            return None
        llm = self._tools.get("llm_generate")
        result = await llm.run(
            StructuredGenerationRequest(
                task="creative_qc",
                prompt=(
                    "Judge the creative quality of this production. Score each of "
                    "the five dimensions 0-1 against the creative brief: visual "
                    "coherence, visualizer placement, branding presence, content "
                    "consistency, metadata relevance.\n"
                    f"{context}"
                ),
                system_prompt="Return one 0-1 score per creative dimension.",
                output_schema=_CREATIVE_SCHEMA,
            )
        )
        values: dict[str, float] = {}
        for dim in CREATIVE_DIMENSIONS:
            try:
                value = float(result.data.get(dim, 0.5))
            except (TypeError, ValueError):
                value = 0.5
            values[dim] = round(min(max(value, 0.0), 1.0), 3)
        remarks = str(result.data.get("remarks", "")).strip()
        return CreativeAssessment(remarks=remarks, **values)
