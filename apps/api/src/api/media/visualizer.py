"""Deterministic audio-reactive visualizer engine (MAD-001 §23; TDD-001 §46, §126).

Turns the *actual master WAV* into normalized per-frame frequency-band values via
a fixed FFT window (MAD-001 §23: Master Audio → FFT → Frequency Bands →
Normalized Values → Visualizer Data), then derives the radio-composited
visualizer layer layout (TDD-001 §52: radio_position, radio_scale,
visualizer_region, visualizer_style, branding_position).

Everything is pure NumPy + stdlib ``wave`` and deterministic: identical input
yields identical output, so the visualizer is always synchronized with the
actual master audio (PRD-001 FR-018 / §24) rather than randomly animated.
Sensitivity scales the normalized values and smoothing applies an exponential
moving average across frames (MAD-001 §23 example config).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field

from api.core.errors import MediaProcessingError
from api.domain.audio import AudioAnalysis, VisualizerData
from api.media.mastering import read_wav

#: Five frequency groups (MAD-001 §23: bass, low-mid, mid, high-mid, high).
_DEFAULT_BAND_NAMES = ["bass", "low_mid", "mid", "high_mid", "high"]

#: Band edges in Hz (the final edge is clamped to the signal's Nyquist).
_DEFAULT_BAND_EDGES_HZ = [0.0, 150.0, 400.0, 1000.0, 4000.0]

#: Radio occupies ~34% of the master frame width, centered (TDD-001 §52).
RADIO_SCALE = 0.34
RADIO_POSITION = (0.5, 0.5)
BRANDING_POSITION = (0.03, 0.03)


class VisualizerLayout(BaseModel):
    """Deterministic composition layout for the visualizer (TDD-001 §52).

    All positions/regions are normalized 0-1 coordinates in the master 16:9
    frame; the visualizer region sits inside the radio's central display area.
    """

    radio_position: tuple[float, float] = RADIO_POSITION
    radio_scale: float = RADIO_SCALE
    visualizer_region: tuple[float, float, float, float]
    visualizer_style: str = "bars"
    branding_position: tuple[float, float] = BRANDING_POSITION


class VisualizerLayer(BaseModel):
    """The renderable visualizer layer (TDD-001 §126): data + layout."""

    visualizer: VisualizerData
    layout: VisualizerLayout


class VisualizerEngine:
    """Deterministic visualizer data derivation + layer composition."""

    def __init__(
        self,
        *,
        fps: int = 30,
        band_names: list[str] | None = None,
        band_edges_hz: list[float] | None = None,
        default_sensitivity: float = 0.8,
        default_smoothing: float = 0.7,
        window_seconds: float = 0.064,
    ) -> None:
        self.fps = fps
        self.band_names = band_names or list(_DEFAULT_BAND_NAMES)
        self.band_edges_hz = band_edges_hz or list(_DEFAULT_BAND_EDGES_HZ)
        self.default_sensitivity = default_sensitivity
        self.default_smoothing = default_smoothing
        self.window_seconds = window_seconds

    # --- generate_data (TDD-001 §126) ---------------------------------------

    async def generate_data(
        self,
        analysis: AudioAnalysis,
        *,
        master_path: Path,
        style: str = "bars",
        position: str = "radio-center",
        sensitivity: float | None = None,
        smoothing: float | None = None,
    ) -> VisualizerData:
        """Derive normalized per-frame bands from the actual master WAV.

        ``analysis`` anchors the frame model (TDD-001 §126 interface); the
        values themselves are computed from ``master_path`` via FFT so the
        visualizer follows the real audio (PRD-001 §24).
        """
        samples, rate, channels = read_wav(master_path)
        mono = samples.mean(axis=1) if channels > 1 else samples[:, 0]
        if mono.size == 0:
            raise MediaProcessingError(f"master audio for visualizer is empty: {master_path}")

        raw, timestamps = self._frame_bands(mono, rate)
        normalized = self._normalize(raw)
        factor = smoothing if smoothing is not None else self.default_smoothing
        smoothed = self._smooth(normalized, factor)
        gain = 1.0 + (sensitivity if sensitivity is not None else self.default_sensitivity)
        frames = [
            [min(1.0, round(value * gain, 4)) for value in frame]
            for frame in smoothed
        ]
        return VisualizerData(
            style=style,
            position=position,
            sensitivity=sensitivity if sensitivity is not None else self.default_sensitivity,
            smoothing=factor,
            fps=self.fps,
            band_names=list(self.band_names),
            frames=frames,
            timestamps=timestamps,
        )

    # --- render (TDD-001 §126) ----------------------------------------------

    def render(
        self,
        visualizer_data: VisualizerData,
        *,
        radio_scale: float = RADIO_SCALE,
        radio_position: tuple[float, float] = RADIO_POSITION,
        branding_position: tuple[float, float] = BRANDING_POSITION,
    ) -> VisualizerLayer:
        """Compose the visualizer layer layout for the master frame.

        The visualizer region is the inner ~70% of the radio square, so the bars
        render inside the radio's central display area (TDD-001 §52).
        """
        half = radio_scale * 0.5 * 0.7
        region = (
            round(radio_position[0] - half, 4),
            round(radio_position[1] - half, 4),
            round(radio_position[0] + half, 4),
            round(radio_position[1] + half, 4),
        )
        layout = VisualizerLayout(
            radio_position=(round(radio_position[0], 4), round(radio_position[1], 4)),
            radio_scale=radio_scale,
            visualizer_region=region,
            visualizer_style=visualizer_data.style,
            branding_position=(round(branding_position[0], 4), round(branding_position[1], 4)),
        )
        return VisualizerLayer(visualizer=visualizer_data, layout=layout)

    # --- FFT pipeline (MAD-001 §23) -----------------------------------------

    def _frame_bands(self, mono: np.ndarray, rate: int) -> tuple[list[list[float]], list[float]]:
        window = int(rate * self.window_seconds)
        hop = int(rate / self.fps)
        freq = np.fft.rfftfreq(window, 1.0 / rate)
        nyquist = rate // 2 + 1
        edges = [min(edge, float(nyquist)) for edge in self.band_edges_hz] + [float(nyquist)]
        band_slices = [
            (int(np.searchsorted(freq, lo)), int(np.searchsorted(freq, hi)))
            for lo, hi in zip(edges[:-1], edges[1:])
        ]
        frames: list[list[float]] = []
        timestamps: list[float] = []
        n = mono.size
        for start in range(0, n, hop):
            chunk = mono[start : start + window]
            if chunk.size < window:
                chunk = np.pad(chunk, (0, window - chunk.size))
            spectrum = np.abs(np.fft.rfft(chunk))
            frame = [
                float(np.mean(spectrum[lo:hi])) if hi > lo else 0.0
                for lo, hi in band_slices
            ]
            frames.append(frame)
            timestamps.append(round(start / rate, 3))
        return frames, timestamps

    @staticmethod
    def _normalize(raw: list[list[float]]) -> list[list[float]]:
        """Divide each band by its global max across the whole track."""
        arr = np.asarray(raw, dtype=np.float64)
        denom = np.max(arr, axis=0) if arr.size else np.zeros(arr.shape[1])
        denom = np.maximum(denom, 1e-12)
        return (arr / denom).tolist()

    @staticmethod
    def _smooth(normalized: list[list[float]], factor: float) -> list[list[float]]:
        """Exponential moving average across frames (deterministic)."""
        smoothed: list[list[float]] = []
        prev: list[float] | None = None
        for frame in normalized:
            if prev is None:
                smoothed.append(frame)
            else:
                smoothed.append([factor * p + (1.0 - factor) * c for p, c in zip(prev, frame)])
            prev = smoothed[-1]
        return smoothed
