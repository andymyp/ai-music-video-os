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

Phase 15 adds the deterministic *Video Renderer* step (MAD-001 §23): per-frame
transparent bar sprites (:meth:`VisualizerEngine.render_frames`) that FFmpeg
composites over the radio display, and normalized→pixel geometry helpers
(:func:`radio_overlay_pixels`, :func:`visualizer_region_pixels`,
:func:`branding_pixels`) so the master composition is driven entirely by the
persisted layout (TDD-001 §52).
"""
from __future__ import annotations

import binascii
import struct
import zlib
from pathlib import Path
from typing import Callable

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

#: Short (9:16) vertical composition (MAD-001 §27; TDD-001 §56, §127-128).
SHORT_RADIO_POSITION = (0.5, 0.35)
SHORT_RADIO_SCALE = 0.5
SHORT_BRANDING_POSITION = (0.5, 0.9)

#: Fraction of the radio square used for the visualizer region (TDD-001 §52).
VISUALIZER_REGION_FRACTION = 0.7


def _region_from_radio(
    radio_position: tuple[float, float],
    radio_scale: float,
    *,
    width: int,
    height: int,
    inner: float = VISUALIZER_REGION_FRACTION,
) -> tuple[float, float, float, float]:
    """Normalized region = the radio square's inner ``inner`` portion.

    The radio is a square of ``radio_scale`` × frame *width*; its inner 70% is
    computed in pixels and re-normalized per axis so the region always stays
    inside the radio on any aspect ratio (TDD-001 §52, §128 safe margins).
    """
    half_x = radio_scale * 0.5 * inner  # fraction of the frame width
    half_y = half_x * width / height  # same pixels, re-scaled to the height
    cx, cy = radio_position
    return (
        round(cx - half_x, 4),
        round(cy - half_y, 4),
        round(cx + half_x, 4),
        round(cy + half_y, 4),
    )


def vertical_layout(style: str = "bars", *, width: int = 1080, height: int = 1920) -> VisualizerLayout:
    """Dedicated 9:16 composition (MAD-001 §27; TDD-001 §56, §127-128).

    The radio/wave sits centered in the upper third, branding anchors
    bottom-center, and the visualizer region stays inside the radio square for
    any short size (TDD-001 §128 — important elements never cropped).
    """
    return VisualizerLayout(
        radio_position=(round(SHORT_RADIO_POSITION[0], 4), round(SHORT_RADIO_POSITION[1], 4)),
        radio_scale=SHORT_RADIO_SCALE,
        visualizer_region=_region_from_radio(
            SHORT_RADIO_POSITION, SHORT_RADIO_SCALE, width=width, height=height
        ),
        visualizer_style=style,
        branding_position=(round(SHORT_BRANDING_POSITION[0], 4), round(SHORT_BRANDING_POSITION[1], 4)),
    )


def slice_visualizer(
    data: VisualizerData,
    *,
    start_seconds: float,
    duration_seconds: float,
) -> VisualizerData:
    """The visualizer window matching an audio segment ``[start, start+duration)``.

    Shares the master's deterministic band data (TDD-001 §127) but keeps only
    the frames the segment covers, with timestamps rebased to the short's t=0 so
    the bars stay synchronized with the trimmed audio (PRD-001 §24; TDD-001 §129
    — never regenerates independent music).
    """
    if not data.frames or duration_seconds <= 0:
        return data
    start_idx = max(int(round(start_seconds * data.fps)), 0)
    end_idx = max(int(round((start_seconds + duration_seconds) * data.fps)), start_idx + 1)
    frames = data.frames[start_idx:end_idx]
    timestamps = [round(t - start_seconds, 3) for t in data.timestamps[start_idx:end_idx]]
    return data.model_copy(update={"frames": frames, "timestamps": timestamps})


def radio_overlay_pixels(layout: "VisualizerLayout", *, width: int, height: int) -> tuple[int, int, int, int]:
    """Normalized layout → (x, y, w, h) pixels for the radio asset overlay.

    The radio is a square sized at ``radio_scale`` × frame *width*, centered on
    ``radio_position`` (TDD-001 §52). Deterministic and testable.
    """
    size = round(layout.radio_scale * width)
    x = round(layout.radio_position[0] * width - size / 2)
    y = round(layout.radio_position[1] * height - size / 2)
    return x, y, size, size


def visualizer_region_pixels(layout: "VisualizerLayout", *, width: int, height: int) -> tuple[int, int, int, int]:
    """Normalized ``visualizer_region`` → (x, y, w, h) pixels in the master frame."""
    x0, y0, x1, y1 = layout.visualizer_region
    left = round(x0 * width)
    top = round(y0 * height)
    return left, top, round(x1 * width) - left, round(y1 * height) - top


def branding_pixels(layout: "VisualizerLayout", *, width: int, height: int) -> tuple[int, int]:
    """Normalized ``branding_position`` anchor → (x, y) pixels (TDD-001 §52)."""
    return round(layout.branding_position[0] * width), round(layout.branding_position[1] * height)


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
        frame_width: int = 1920,
        frame_height: int = 1080,
    ) -> VisualizerLayer:
        """Compose the visualizer layer layout for a ``frame_width``×``frame_height`` frame.

        The visualizer region is the inner ~70% of the radio square computed in
        pixel space, so the bars always render inside the radio's central
        display area regardless of the frame's aspect ratio (TDD-001 §52, §128).
        """
        layout = VisualizerLayout(
            radio_position=(round(radio_position[0], 4), round(radio_position[1], 4)),
            radio_scale=radio_scale,
            visualizer_region=_region_from_radio(
                radio_position, radio_scale, width=frame_width, height=frame_height
            ),
            visualizer_style=visualizer_data.style,
            branding_position=(round(branding_position[0], 4), round(branding_position[1], 4)),
        )
        return VisualizerLayer(visualizer=visualizer_data, layout=layout)

    # --- video renderer (MAD-001 §23: Visualizer Data → Video Renderer) -----

    def render_frames(
        self,
        data: VisualizerData,
        *,
        width: int,
        height: int,
        bar_color: tuple[int, int, int] = (255, 255, 255),
        opacity: float = 0.9,
        gap_ratio: float = 0.4,
    ) -> list[bytes]:
        """Render each data frame as a transparent ``width``×``height`` PNG sprite.

        One PNG per frame (indexed 1..N) so FFmpeg's image2 demuxer can overlay
        them as a time-aligned video stream at ``data.fps``. Bars sit on the
        bottom baseline, growing upward with the normalized band value; the rest
        of the sprite is transparent so it composites over the radio's central
        display area (TDD-001 §52). Deterministic: identical data → identical
        bytes (TDD-001 §113).
        """
        if width < 1 or height < 1:
            raise ValueError("visualizer sprite dimensions must be >= 1")
        n = len(data.band_names) or 1
        slot = width / n
        bar_w = max(int(round(slot * (1.0 - gap_ratio))), 1)
        bar_x0 = [round(i * slot + (slot - bar_w) / 2) for i in range(n)]
        rgba = bytes(bar_color) + bytes([round(opacity * 255)])
        bar_row = rgba * bar_w
        frames: list[bytes] = []
        for frame in data.frames:
            buf = bytearray(width * height * 4)
            for i, value in enumerate(frame):
                bar_h = int(round(max(0.0, min(1.0, value)) * height))
                if bar_h <= 0:
                    continue
                y0 = height - bar_h
                for y in range(y0, height):
                    offset = (y * width + bar_x0[i]) * 4
                    buf[offset : offset + bar_w * 4] = bar_row
            frames.append(self._encode_rgba(width, height, buf))
        return frames

    @staticmethod
    def _png_chunk(typ: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + typ
            + payload
            + struct.pack(">I", binascii.crc32(typ + payload) & 0xFFFFFFFF)
        )

    @staticmethod
    def _encode_rgba(width: int, height: int, buf: bytearray) -> bytes:
        """Pack an RGBA buffer into a minimal 8-bit RGBA PNG (color type 6)."""
        stride = width * 4
        raw = bytearray()
        for y in range(height):
            raw.append(0)  # filter type: none
            raw += buf[y * stride : (y + 1) * stride]
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n"
            + VisualizerEngine._png_chunk(b"IHDR", ihdr)
            + VisualizerEngine._png_chunk(b"IDAT", zlib.compress(bytes(raw), 1))
            + VisualizerEngine._png_chunk(b"IEND", b"")
        )

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
