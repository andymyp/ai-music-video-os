"""Audio mastering / normalization (MAD-001 §19; PRD-001 §19).

Generated audio must be normalized before rendering. The pipeline is

    Generated Audio → Format Validation → Sample Rate Normalization →
    Channel Normalization → Loudness Normalization → Silence Detection →
    Audio Master

This engine implements that deterministically with the stdlib ``wave`` module +
pure NumPy DSP (MAD-001 §19 lists NumPy as a primary tool; no external FFmpeg is
needed for the WAV contract used by Phase 05+). The normalized output is the
``audio-master.wav`` artifact that rendering and short selection consume.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from api.core.errors import MediaProcessingError

#: Default master profile (MAD-001 §19 / PRD-001 §19 normalization targets).
DEFAULT_TARGET_SAMPLE_RATE = 44100
DEFAULT_TARGET_CHANNELS = 2
DEFAULT_TARGET_LOUDNESS_DB = -16.0
DEFAULT_SILENCE_THRESHOLD_DB = -60.0
DEFAULT_PEAK_CEILING = 0.999

#: Frame length (seconds) for silence detection.
_SILENCE_FRAME_SECONDS = 0.01


def _rms_db(samples: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    return max(20.0 * math.log10(rms + 1e-12), -90.0)


class AudioMasterReport(BaseModel):
    """Structural + loudness report of the mastered audio (MAD-001 §19)."""

    input_sample_rate: int
    input_channels: int
    output_sample_rate: int
    output_channels: int
    duration_seconds: float
    loudness_db: float
    target_loudness_db: float
    peak_db: float
    leading_silence_seconds: float
    trailing_silence_seconds: float


def read_wav(path: Path) -> tuple[np.ndarray, int, int]:
    """Decode a PCM WAV into float samples in [-1, 1] with (n, channels).

    Shared by the mastering and visualizer engines so both stages read the same
    deterministic decode (MAD-001 §19/§23).
    """
    try:
        with wave.open(str(path), "rb") as wav:
            rate = wav.getframerate()
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            frames = wav.getnframes()
            raw = wav.readframes(frames)
    except (wave.Error, OSError) as exc:
        raise MediaProcessingError(f"cannot decode WAV master source {path}: {exc}") from exc

    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
    data = np.frombuffer(raw, dtype=dtype)
    if width == 1:  # 8-bit unsigned, centred at 128
        samples = (data.astype(np.float32) - 128.0) / 128.0
    else:
        peak = float(np.iinfo(dtype).max)
        samples = data.astype(np.float32) / peak
    return samples.reshape(-1, channels).astype(np.float64), rate, channels


class AudioMasteringEngine:
    """Normalizes a WAV source into the master audio artifact."""

    def __init__(
        self,
        *,
        target_sample_rate: int = DEFAULT_TARGET_SAMPLE_RATE,
        target_channels: int = DEFAULT_TARGET_CHANNELS,
        target_loudness_db: float = DEFAULT_TARGET_LOUDNESS_DB,
        silence_threshold_db: float = DEFAULT_SILENCE_THRESHOLD_DB,
        peak_ceiling: float = DEFAULT_PEAK_CEILING,
    ) -> None:
        if target_channels not in (1, 2):
            raise ValueError("mastering supports mono or stereo output only")
        self._target_rate = target_sample_rate
        self._target_channels = target_channels
        self._target_loudness = target_loudness_db
        self._silence_threshold = silence_threshold_db
        self._peak_ceiling = peak_ceiling

    async def master(self, source: Path, output: Path) -> AudioMasterReport:
        """Normalize *source* into a WAV *output* and return the report."""
        samples, rate, channels = self._read_wav(source)
        if samples.size == 0:
            raise MediaProcessingError(f"audio master source is empty: {source}")

        resampled = self._resample(samples, rate, self._target_rate)
        mixed = self._normalize_channels(resampled, self._target_channels)
        normalized = self._loudness_normalize(mixed)
        duration = float(resampled.shape[0]) / self._target_rate
        leading, trailing = self._silence(normalized)

        output.parent.mkdir(parents=True, exist_ok=True)
        self._write_wav(output, normalized, self._target_rate, self._target_channels)

        return AudioMasterReport(
            input_sample_rate=rate,
            input_channels=channels,
            output_sample_rate=self._target_rate,
            output_channels=self._target_channels,
            duration_seconds=round(duration, 3),
            loudness_db=round(_rms_db(normalized), 2),
            target_loudness_db=self._target_loudness,
            peak_db=round(20.0 * math.log10(max(float(np.max(np.abs(normalized))), 1e-12)), 2),
            leading_silence_seconds=round(leading, 3),
            trailing_silence_seconds=round(trailing, 3),
        )

    # --- pipeline stages -----------------------------------------------------

    @staticmethod
    def _read_wav(path: Path) -> tuple[np.ndarray, int, int]:
        return read_wav(path)

    @staticmethod
    def _resample(samples: np.ndarray, in_rate: int, out_rate: int) -> np.ndarray:
        """Linear-interpolation resampling of each channel (deterministic)."""
        if in_rate == out_rate:
            return samples
        n_in = samples.shape[0]
        n_out = max(int(round(n_in * out_rate / in_rate)), 1)
        xs = np.arange(n_out) * (n_in - 1) / max(n_out - 1, 1)
        return np.stack(
            [np.interp(xs, np.arange(n_in), samples[:, ch]) for ch in range(samples.shape[1])],
            axis=1,
        )

    @staticmethod
    def _normalize_channels(samples: np.ndarray, target_channels: int) -> np.ndarray:
        """Up/down-mix to *target_channels* (1 or 2)."""
        channels = samples.shape[1]
        if channels == target_channels:
            return samples
        mono = samples.mean(axis=1, keepdims=True) if channels > 1 else samples
        if target_channels == 1:
            return mono
        return np.repeat(mono, 2, axis=1)  # -> stereo: duplicate the mono mix

    def _loudness_normalize(self, samples: np.ndarray) -> np.ndarray:
        """RMS-normalize to the target loudness, bounded by the peak ceiling."""
        current = _rms_db(samples)
        gain = 10.0 ** ((self._target_loudness - current) / 20.0)
        out = samples * gain
        peak = float(np.max(np.abs(out)))
        if peak > self._peak_ceiling:
            out = out * (self._peak_ceiling / peak)
        return out

    def _silence(self, samples: np.ndarray) -> tuple[float, float]:
        """Leading/trailing silence seconds below the amplitude threshold."""
        mono = samples.mean(axis=1)
        frame = max(int(self._target_rate * _SILENCE_FRAME_SECONDS), 1)
        n_frames = mono.size // frame
        if n_frames == 0:
            return 0.0, 0.0
        power = mono[: n_frames * frame].reshape(n_frames, frame)
        rms = np.sqrt(np.mean(power.astype(np.float64) ** 2, axis=1))
        threshold = 10.0 ** (self._silence_threshold / 20.0)
        below = rms < threshold
        leading = 0
        while leading < n_frames and below[leading]:
            leading += 1
        trailing = 0
        while trailing < n_frames and below[n_frames - 1 - trailing]:
            trailing += 1
        seconds_per_frame = frame / self._target_rate
        return leading * seconds_per_frame, trailing * seconds_per_frame

    # --- output ---------------------------------------------------------------

    @staticmethod
    def _write_wav(path: Path, samples: np.ndarray, rate: int, channels: int) -> None:
        """Write 16-bit PCM WAV from float samples in [-1, 1]."""
        interleaved = np.clip(samples, -1.0, 1.0) * 32767.0
        pcm = interleaved.astype("<i2").tobytes()
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(pcm)


__all__ = [
    "AudioMasteringEngine",
    "AudioMasterReport",
    "DEFAULT_PEAK_CEILING",
    "DEFAULT_SILENCE_THRESHOLD_DB",
    "DEFAULT_TARGET_CHANNELS",
    "DEFAULT_TARGET_LOUDNESS_DB",
    "DEFAULT_TARGET_SAMPLE_RATE",
]
