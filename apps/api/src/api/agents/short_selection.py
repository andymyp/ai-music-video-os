"""Short Selection Agent (MAD-001 §34; PRD-001 §67).

Analyzes the production audio through the registered ``audio_analyze`` tool and
identifies the strongest segment for short-form content: the window of the
requested duration whose cumulative energy is highest. Selection is
deterministic and returns a :class:`ShortSegment` with start time, duration,
score and a selection reason.
"""
from __future__ import annotations

import numpy as np

from api.agents.tools import AudioAnalysisRequest, ToolRegistry
from api.core.errors import AgentError
from api.domain.agents import ShortSelectionRequest
from api.domain.audio import AudioAnalysis
from api.domain.outputs import ShortSegment


class ShortSelectionAgent:
    """Picks the strongest window of the master audio for a short."""

    name = "short_selection"
    version = "short_selection_v1"
    description = "Selects the highest-energy segment for short-form content."

    def __init__(self, tools: ToolRegistry) -> None:
        self._tools = tools

    async def execute(self, request: ShortSelectionRequest) -> ShortSegment:
        analysis: AudioAnalysis = await self._tools.get("audio_analyze").run(
            AudioAnalysisRequest(path=request.audio_path)
        )
        target = self._clamp_target(request, analysis)
        start, duration, score = self._strongest_window(analysis, target)
        return ShortSegment(
            start_seconds=round(start, 3),
            duration_seconds=round(duration, 3),
            score=score,
            reason=(
                f"highest-energy {target:g}s window of {analysis.duration_seconds:g}s audio "
                f"(score {score:.2f})"
            ),
        )

    @staticmethod
    def _clamp_target(request: ShortSelectionRequest, analysis: AudioAnalysis) -> float:
        lo = min(request.min_duration_seconds, request.max_duration_seconds) or 0.0
        hi = max(request.min_duration_seconds, request.max_duration_seconds)
        target = request.target_duration_seconds
        if hi and target > hi:
            target = hi
        if target < lo:
            target = lo
        return min(target, max(analysis.duration_seconds, lo))

    @staticmethod
    def _strongest_window(analysis: AudioAnalysis, target: float) -> tuple[float, float, float]:
        energy = np.asarray(analysis.energy_curve, dtype=float)
        times = np.asarray(analysis.timestamps, dtype=float)
        if energy.size == 0 or times.size == 0:
            raise AgentError("audio analysis has no energy curve")
        if analysis.duration_seconds <= 0:
            raise AgentError("audio analysis has no duration")

        hop = float(times[1] - times[0]) if times.size > 1 else analysis.duration_seconds
        target_frames = max(1, int(round(target / hop))) if hop > 0 else 1
        peak = float(energy.max()) if energy.size else 0.0

        if energy.size <= target_frames:
            score = float(energy.mean() / peak) if peak > 0 else 0.0
            return float(times[0]), analysis.duration_seconds, round(min(max(score, 0.0), 1.0), 3)

        sums = np.convolve(energy, np.ones(target_frames), mode="valid")
        max_val = float(sums.max())
        # A window wider than the loud region leaves a flat plateau of equal
        # energy; argmax alone resolves it to the leftmost frame, so take the
        # center of the plateau to place the window on the peak's core.
        tol = max(abs(max_val) * 1e-9, 1e-12)
        plateau = np.flatnonzero(np.abs(sums - max_val) <= tol)
        best = int(plateau[0] + (plateau[-1] - plateau[0]) // 2)
        start = float(times[best])
        duration = min(target, analysis.duration_seconds - start)
        score = max_val / (target_frames * peak) if peak > 0 else 0.0
        return start, duration, round(min(max(score, 0.0), 1.0), 3)
