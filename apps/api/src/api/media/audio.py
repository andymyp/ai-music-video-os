"""Deterministic audio analysis (MAD-001 §19, §23; TDD-001 §45-46).

FFmpeg decodes the source to mono float PCM at a fixed analysis rate, then pure
NumPy DSP computes the fields of the Phase01 :class:`AudioAnalysis` domain model
(duration, BPM, loudness, energy_curve, spectral_curve, beats, sections,
timestamps). All DSP is deterministic and side-effect free; the visualizer
pipeline and short selection consume the result. Only FFmpeg + NumPy are used
(MAD-001 §19 lists NumPy as a primary tool; librosa is deliberately avoided).
"""
from __future__ import annotations

import asyncio
import math

import numpy as np

from api.core.errors import MediaProcessingError
from api.domain.audio import AudioAnalysis, AudioSection
from api.media.ffmpeg import ProcessRunner, _run_process


def frame_times(n_frames: int, hop: int, frame_size: int, sample_rate: int) -> np.ndarray:
    """Centre time (seconds) of each analysis frame."""
    return (np.arange(n_frames) * hop + frame_size / 2.0) / sample_rate


def split_frames(samples: np.ndarray, frame_size: int, hop: int) -> np.ndarray:
    """(n_frames, frame_size) overlapping frames, zero-padded at the tail."""
    n = len(samples)
    if n < frame_size:
        samples = np.pad(samples, (0, frame_size - n))
        n = frame_size
    n_frames = (n - frame_size) // hop + 1
    if n_frames <= 0:
        return np.empty((0, frame_size), dtype=np.float32)
    pad = n_frames * hop + frame_size - hop - n
    if pad > 0:
        samples = np.pad(samples, (0, pad))
    return np.ascontiguousarray(
        np.lib.stride_tricks.as_strided(
            samples,
            shape=(n_frames, frame_size),
            strides=(hop * samples.itemsize, samples.itemsize),
        )
    )


def windowed_rms(frames: np.ndarray) -> np.ndarray:
    """Per-frame RMS (signal assumed in [-1, 1])."""
    return np.sqrt(np.mean(frames**2, axis=1))


def spectral_centroids(frames: np.ndarray, sample_rate: int) -> np.ndarray:
    """Per-frame spectral centroid normalized to Nyquist (0-1)."""
    windowed = frames * np.hanning(frames.shape[1])
    spec = np.abs(np.fft.rfft(windowed, axis=1))
    freqs = np.fft.rfftfreq(frames.shape[1], 1.0 / sample_rate)
    total = spec.sum(axis=1)
    safe_total = np.where(total > 1e-9, total, 1.0)
    centroid = (spec * freqs).sum(axis=1) / safe_total
    return centroid / (sample_rate / 2.0)


def onset_flux(frames: np.ndarray) -> np.ndarray:
    """Spectral-flux onset envelope; first frame is zero so it aligns with energy."""
    windowed = frames * np.hanning(frames.shape[1])
    spec = np.abs(np.fft.rfft(windowed, axis=1))
    if spec.shape[0] < 2:
        return np.zeros(spec.shape[0], dtype=np.float64)
    flux = np.maximum(spec[1:] - spec[:-1], 0.0).sum(axis=1)
    return np.concatenate((np.zeros(1), flux))


def rms_loudness_db(samples: np.ndarray) -> float:
    """Whole-signal RMS loudness in dB (clamped below at -90 dB)."""
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    return max(20.0 * math.log10(rms + 1e-12), -90.0)


def detect_beats(
    onset: np.ndarray,
    times: np.ndarray,
    *,
    min_interval: float = 0.35,
    threshold_factor: float = 1.2,
) -> list[float]:
    """Peak-pick the onset envelope with a refractory interval.

    ``min_interval`` sets a ~171 BPM ceiling on detections; ``threshold_factor``
    keeps sensitivity but rejects ripple below mean + k·std.
    """
    if onset.size < 2:
        return []
    threshold = float(onset.mean() + threshold_factor * onset.std())
    beats: list[float] = []
    last = -math.inf
    for value, time_ in zip(onset, times):
        if value > threshold and (time_ - last) >= min_interval:
            beats.append(float(time_))
            last = time_
    return beats


def bpm_from_beats(
    beats: list[float],
    *,
    bpm_min: float = 60.0,
    bpm_max: float = 200.0,
) -> float | None:
    """Tempo implied by the detected beat grid (median inter-beat interval).

    Beat times are peak-picked frames, so consecutive intervals already enforce
    the refractory ``min_interval``; the median is robust to a few missed beats.
    Returns ``None`` when there are too few beats or the tempo leaves the range.
    """
    if len(beats) < 4:
        return None
    intervals = np.diff(beats)
    intervals = intervals[intervals > 0.0]
    if intervals.size == 0:
        return None
    median_interval = float(np.median(intervals))
    if median_interval <= 0.0:
        return None
    bpm = 60.0 / median_interval
    if not (bpm_min <= bpm <= bpm_max):
        return None
    return round(bpm, 1)


def estimate_bpm(
    onset: np.ndarray,
    times: np.ndarray,
    *,
    bpm_min: float = 60.0,
    bpm_max: float = 200.0,
) -> float | None:
    """BPM from the autocorrelation lag of the onset envelope (parabolic peak)."""
    if onset.size < 4:
        return None
    hop = float(times[1] - times[0]) if times.size > 1 else 1.0
    fps = 1.0 / hop if hop > 0 else 1.0
    x = onset - float(onset.mean())
    acf = np.correlate(x, x, mode="full")[x.size - 1 :]
    lag_min = max(1, int(60.0 / bpm_max * fps))
    lag_max = min(acf.size - 1, int(60.0 / bpm_min * fps))
    if lag_max <= lag_min:
        return None
    region = acf[lag_min : lag_max + 1]
    if float(region.max()) <= 0:
        return None
    lag = lag_min + int(np.argmax(region))
    if 0 < lag < acf.size - 1:  # parabolic refinement
        a, b, c = acf[lag - 1], acf[lag], acf[lag + 1]
        denom = a - 2 * b + c
        if denom != 0:
            lag += 0.5 * (a - c) / denom
    return round(60.0 / max(lag / fps, 1e-9), 1)


def detect_sections(
    energy: np.ndarray,
    times: np.ndarray,
    *,
    min_seconds: float = 1.0,
    smooth_window: int = 11,
) -> list[AudioSection]:
    """Segments the track into quiet/loud runs from smoothed energy.

    Energy is smoothed with reflect padding (edges are not dragged down), then
    thresholded at the track's mean so a bimodal loud/quiet mix splits cleanly.
    Adjacent same-state runs are merged, and runs shorter than ``min_seconds``
    are folded into their neighbours so the section list stays musically
    meaningful.
    """
    if energy.size == 0 or times.size == 0:
        return []
    kernel = np.ones(smooth_window) / smooth_window
    pad = smooth_window // 2
    smoothed = np.convolve(np.pad(energy, pad, mode="reflect"), kernel, mode="valid")
    state = smoothed > float(smoothed.mean())
    runs: list[list[bool]] = []
    for value in state:
        if runs and runs[-1][-1] == value:
            runs[-1].append(value)
        else:
            runs.append([value])
    if len(runs) == 1:
        label = "loud" if runs[0][0] else "quiet"
        return [AudioSection(start_seconds=float(times[0]), end_seconds=float(times[-1]), label=label)]

    min_frames = max(1, int(min_seconds * times.size / max(times[-1] - times[0], 1e-9)))
    merged: list[list[bool]] = []
    for run in runs:
        if merged and len(run) < min_frames:
            merged[-1].extend(run)
        else:
            merged.append(run)
    if not merged:
        merged = [runs[0]]

    sections: list[AudioSection] = []
    start = 0
    for run in merged:
        end = start + len(run)
        label = "loud" if run[0] else "quiet"
        # end uses the next run's first frame so adjacent sections tile exactly.
        sections.append(
            AudioSection(
                start_seconds=float(times[max(start, 0)]),
                end_seconds=float(times[min(end, times.size - 1)]),
                label=label,
            )
        )
        start = end
    return sections


class AudioAnalysisEngine:
    """Analyzes an audio file into an :class:`AudioAnalysis` (TDD-001 §45)."""

    def __init__(
        self,
        *,
        ffmpeg_bin: str = "ffmpeg",
        runner: ProcessRunner | None = None,
        sample_rate: int = 22050,
        frame_size: int = 2048,
        hop: int = 512,
        bpm_min: float = 60.0,
        bpm_max: float = 200.0,
    ) -> None:
        self._ffmpeg = ffmpeg_bin
        self._runner = runner or _run_process
        self._sample_rate = sample_rate
        self._frame_size = frame_size
        self._hop = hop
        self._bpm_min = bpm_min
        self._bpm_max = bpm_max

    async def analyze(self, path: str) -> AudioAnalysis:
        """Decode *path* to mono PCM and compute the full analysis."""
        samples = await self._decode(path)
        duration = float(samples.size) / self._sample_rate
        if samples.size < self._frame_size:
            raise MediaProcessingError(
                f"audio too short to analyze: {duration:.2f}s < frame {self._frame_size}"
            )
        frames = split_frames(samples, self._frame_size, self._hop)
        times = frame_times(frames.shape[0], self._hop, self._frame_size, self._sample_rate)

        energy = windowed_rms(frames)
        spectral = spectral_centroids(frames, self._sample_rate)
        onset = onset_flux(frames)
        onset_times = frame_times(onset.size, self._hop, self._frame_size, self._sample_rate)

        beats = detect_beats(onset, onset_times)
        bpm = bpm_from_beats(beats, bpm_min=self._bpm_min, bpm_max=self._bpm_max)
        if bpm is None:  # fall back to onset autocorrelation
            bpm = estimate_bpm(onset, onset_times, bpm_min=self._bpm_min, bpm_max=self._bpm_max)
        sections = detect_sections(energy, times)

        return AudioAnalysis(
            duration_seconds=round(duration, 3),
            bpm=bpm,
            loudness_db=round(rms_loudness_db(samples), 2),
            energy_curve=[round(float(v), 6) for v in energy],
            spectral_curve=[round(float(v), 6) for v in spectral],
            beats=[round(float(t), 3) for t in beats],
            sections=sections,
            timestamps=[round(float(t), 3) for t in times],
        )

    async def _decode(self, path: str) -> np.ndarray:
        """Decode *path* to mono float32 PCM at ``self._sample_rate`` via FFmpeg."""
        cmd = [
            self._ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(self._sample_rate),
            "-f",
            "f32le",
            "-",
        ]
        stdout, _ = await self._runner(cmd)
        samples = np.frombuffer(stdout, dtype=np.float32)
        return np.clip(samples, -1.0, 1.0)
