"""Phase 12: audio mastering (MASTER §22; MAD-001 §19; PRD-001 §19).

Covers the deterministic WAV normalization pipeline — sample rate, channel,
loudness and silence normalization — over real WAV bytes (no FFmpeg required),
plus determinism and error handling.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
import pytest

from api.core.errors import MediaProcessingError
from api.media import AudioMasteringEngine, AudioMasterReport
from api.media.mastering import (
    DEFAULT_TARGET_CHANNELS,
    DEFAULT_TARGET_LOUDNESS_DB,
    DEFAULT_TARGET_SAMPLE_RATE,
)


def _write_wav(path: Path, samples: np.ndarray, *, rate: int, channels: int) -> Path:
    """Write a 16-bit PCM WAV (samples in [-1, 1])."""
    interleaved = np.clip(samples, -1.0, 1.0) * 32767.0
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(interleaved.astype("<i2").tobytes())
    return path


def _sine(seconds: float, *, rate: int = 22050, amplitude: float = 0.25,
          freq: float = 220.0) -> np.ndarray:
    n = int(seconds * rate)
    t = np.arange(n) / rate
    return amplitude * np.sin(2.0 * math.pi * freq * t)


async def test_default_master_profile_matches_mad_normalization_targets():
    engine = AudioMasteringEngine()
    assert engine._target_rate == DEFAULT_TARGET_SAMPLE_RATE == 44100
    assert engine._target_channels == DEFAULT_TARGET_CHANNELS == 2
    assert engine._target_loudness == DEFAULT_TARGET_LOUDNESS_DB == -16.0


def test_mastering_rejects_unsupported_output_channels():
    with pytest.raises(ValueError):
        AudioMasteringEngine(target_channels=3)


async def test_master_resamples_and_upmixes_to_stereo(tmp_path):
    source = _write_wav(tmp_path / "src.wav", _sine(2.0), rate=22050, channels=1)
    output = tmp_path / "master.wav"
    engine = AudioMasteringEngine()
    report = await engine.master(source, output)
    assert report.input_sample_rate == 22050
    assert report.input_channels == 1
    assert report.output_sample_rate == 44100
    assert report.output_channels == 2
    assert output.is_file()
    with wave.open(str(output), "rb") as wav:
        assert wav.getframerate() == 44100
        assert wav.getnchannels() == 2
        assert wav.getsampwidth() == 2
        assert wav.getnframes() == pytest.approx(2.0 * 44100, rel=0.02)


async def test_master_normalizes_loudness_to_target(tmp_path):
    source = _write_wav(tmp_path / "src.wav", _sine(2.0), rate=22050, channels=1)
    output = tmp_path / "master.wav"
    engine = AudioMasteringEngine()
    report = await engine.master(source, output)
    # A 0.25-amplitude sine is ~ -15 dB RMS; after normalization it lands on the
    # -16 dB target (within quantization).
    assert report.loudness_db == pytest.approx(DEFAULT_TARGET_LOUDNESS_DB, abs=1.0)
    assert report.target_loudness_db == DEFAULT_TARGET_LOUDNESS_DB
    assert report.peak_db < 0.0  # never clipped past 0 dBFS


async def test_master_detects_leading_and_trailing_silence(tmp_path):
    silence = np.zeros(int(0.5 * 22050))
    tone = _sine(1.0)
    source = _write_wav(tmp_path / "src.wav", np.concatenate([silence, tone, silence]),
                        rate=22050, channels=1)
    output = tmp_path / "master.wav"
    report = await AudioMasteringEngine().master(source, output)
    assert report.leading_silence_seconds == pytest.approx(0.5, abs=0.03)
    assert report.trailing_silence_seconds == pytest.approx(0.5, abs=0.03)


async def test_master_is_deterministic(tmp_path):
    source = _write_wav(tmp_path / "src.wav", _sine(1.0), rate=22050, channels=1)
    out_a, out_b = tmp_path / "a.wav", tmp_path / "b.wav"
    engine = AudioMasteringEngine()
    await engine.master(source, out_a)
    await engine.master(source, out_b)
    assert out_a.read_bytes() == out_b.read_bytes()
    assert isinstance(await engine.master(source, out_a), AudioMasterReport)


async def test_master_keeps_stereo_input_stereo(tmp_path):
    stereo = np.stack(
        [_sine(1.0, rate=44100, freq=220.0), _sine(1.0, rate=44100, freq=440.0)],
        axis=1,
    )
    source = _write_wav(tmp_path / "src.wav", stereo, rate=44100, channels=2)
    output = tmp_path / "master.wav"
    report = await AudioMasteringEngine().master(source, output)
    assert report.input_sample_rate == 44100
    assert report.input_channels == 2
    assert report.output_channels == 2
    assert report.duration_seconds == pytest.approx(1.0, abs=0.02)


async def test_master_rejects_empty_or_invalid_sources(tmp_path):
    empty = _write_wav(tmp_path / "empty.wav", np.zeros(0), rate=22050, channels=1)
    with pytest.raises(MediaProcessingError, match="empty"):
        await AudioMasteringEngine().master(empty, tmp_path / "out.wav")
    bogus = tmp_path / "bogus.wav"
    bogus.write_bytes(b"not a wav at all")
    with pytest.raises(MediaProcessingError):
        await AudioMasteringEngine().master(bogus, tmp_path / "out2.wav")
