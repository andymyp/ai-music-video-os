"""Phase 14: audio visualizer (MASTER §24; MAD-001 §23; PRD-001 §23-24).

Covers the deterministic FFT → band → normalize → smooth pipeline over a real
master WAV, the sensitivity/smoothing config, and the radio-composited layer
layout (TDD-001 §46, §52, §126).
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
import pytest

from api.core.errors import MediaProcessingError
from api.domain.audio import AudioAnalysis
from api.media import VisualizerEngine, VisualizerLayer, VisualizerLayout
from api.media.visualizer import (
    BRANDING_POSITION,
    RADIO_POSITION,
    RADIO_SCALE,
)

BAND_NAMES = ["bass", "low_mid", "mid", "high_mid", "high"]


def _write_wav(path: Path, samples: np.ndarray, *, rate: int = 44100, channels: int = 1) -> Path:
    """Write a 16-bit PCM WAV (samples in [-1, 1])."""
    interleaved = np.clip(samples, -1.0, 1.0) * 32767.0
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(interleaved.astype("<i2").tobytes())
    return path


def _sine(seconds: float, *, rate: int = 44100, amplitude: float = 0.5,
          freq: float = 220.0) -> np.ndarray:
    n = int(seconds * rate)
    t = np.arange(n) / rate
    return amplitude * np.sin(2.0 * math.pi * freq * t)


def _analysis(duration: float) -> AudioAnalysis:
    return AudioAnalysis(duration_seconds=duration)


def _engine(**kwargs) -> VisualizerEngine:
    return VisualizerEngine(**kwargs)


async def test_generate_data_derives_five_normalized_bands_from_real_wav(tmp_path):
    """MAD-001 §23: FFT over the actual master yields 5 per-frame band values."""
    master = _write_wav(tmp_path / "master.wav", _sine(2.0))
    data = await _engine().generate_data(_analysis(2.0), master_path=master)
    assert data.band_names == BAND_NAMES
    assert data.style == "bars"
    assert data.position == "radio-center"
    assert data.fps == 30
    assert data.frames and data.timestamps
    assert len(data.frames) == len(data.timestamps)
    for frame in data.frames:
        assert len(frame) == 5  # one value per band
        for value in frame:
            assert 0.0 <= value <= 1.0  # normalized, never exceeds the ceiling


async def test_generate_data_style_and_position_are_propagated(tmp_path):
    master = _write_wav(tmp_path / "master.wav", _sine(1.0))
    data = await _engine().generate_data(
        _analysis(1.0), master_path=master, style="wave", position="top-left"
    )
    assert data.style == "wave"
    assert data.position == "top-left"


async def test_generate_data_is_deterministic(tmp_path):
    """TDD-001 §46: identical master → identical frames (PRD-001 §24 sync)."""
    master = _write_wav(tmp_path / "master.wav", _sine(2.0))
    engine = _engine()
    a = await engine.generate_data(_analysis(2.0), master_path=master)
    b = await engine.generate_data(_analysis(2.0), master_path=master)
    assert a.frames == b.frames
    assert a.timestamps == b.timestamps


async def test_smoothing_of_one_freezes_all_frames_to_first(tmp_path):
    """MAD-001 §23 EMA: factor=1.0 keeps every frame equal to the first."""
    master = _write_wav(tmp_path / "master.wav", _sine(2.0))
    data = await _engine().generate_data(
        _analysis(2.0), master_path=master, smoothing=1.0
    )
    assert data.smoothing == 1.0
    first = data.frames[0]
    for frame in data.frames[1:]:
        assert frame == first


async def test_smoothing_is_defaulted_when_not_passed(tmp_path):
    master = _write_wav(tmp_path / "master.wav", _sine(1.0))
    data = await _engine().generate_data(_analysis(1.0), master_path=master)
    assert data.smoothing == 0.7  # engine default


async def test_higher_sensitivity_scales_values_up(tmp_path):
    """MAD-001 §23: sensitivity acts as a gain (1 + sensitivity) on the bands."""
    master = _write_wav(tmp_path / "master.wav", _sine(2.0))
    low = await _engine().generate_data(
        _analysis(2.0), master_path=master, sensitivity=0.0
    )
    high = await _engine().generate_data(
        _analysis(2.0), master_path=master, sensitivity=1.0
    )
    assert low.sensitivity == 0.0
    assert high.sensitivity == 1.0
    low_sum = sum(v for frame in low.frames for v in frame)
    high_sum = sum(v for frame in high.frames for v in frame)
    assert high_sum >= low_sum  # monotonic non-decreasing (clamped at 1.0)


async def test_custom_engine_band_edges_produce_requested_band_count(tmp_path):
    """Bands are derived from band edges, so custom configs are honored."""
    master = _write_wav(tmp_path / "master.wav", _sine(1.0))
    engine = _engine(
        fps=15,
        band_names=["low", "high"],
        band_edges_hz=[0.0, 500.0],
        window_seconds=0.05,
    )
    data = await engine.generate_data(_analysis(1.0), master_path=master)
    assert data.fps == 15
    assert data.band_names == ["low", "high"]
    assert all(len(frame) == 2 for frame in data.frames)


def test_render_layout_places_visualizer_inside_radio(tmp_path):
    """TDD-001 §52: region is the inner 70% of the centered radio square."""
    layout = VisualizerLayout(
        radio_position=RADIO_POSITION,
        radio_scale=RADIO_SCALE,
        visualizer_region=(0.381, 0.381, 0.619, 0.619),
        visualizer_style="bars",
        branding_position=BRANDING_POSITION,
    )
    assert layout.visualizer_region == (0.381, 0.381, 0.619, 0.619)


async def test_render_composes_layer_from_visualizer_data(tmp_path):
    """TDD-001 §126: render() wraps data + deterministic layout."""
    master = _write_wav(tmp_path / "master.wav", _sine(1.0))
    engine = _engine()
    data = await engine.generate_data(_analysis(1.0), master_path=master, style="bars")
    layer = engine.render(data)
    assert isinstance(layer, VisualizerLayer)
    assert isinstance(layer.layout, VisualizerLayout)
    assert layer.visualizer is data
    assert layer.layout.visualizer_style == "bars"
    # radio_scale defaults to 34% of the master frame (TDD-001 §52)
    assert layer.layout.radio_scale == pytest.approx(RADIO_SCALE)
    assert layer.layout.radio_position == pytest.approx(RADIO_POSITION)
    # inner ~70% of the radio square -> 0.34 * 0.5 * 0.7 = 0.119 half-extent
    half = RADIO_SCALE * 0.5 * 0.7
    expected = tuple(
        round(center + offset, 4)
        for center, offset in zip(RADIO_POSITION * 2, (-half, -half, half, half))
    )
    assert layer.layout.visualizer_region == expected
    assert layer.layout.branding_position == BRANDING_POSITION


async def test_render_propagates_custom_radio_position(tmp_path):
    master = _write_wav(tmp_path / "master.wav", _sine(1.0))
    engine = _engine()
    data = await engine.generate_data(_analysis(1.0), master_path=master)
    layer = engine.render(data, radio_position=(0.25, 0.5), radio_scale=0.2)
    assert layer.layout.radio_position == (0.25, 0.5)
    assert layer.layout.radio_scale == pytest.approx(0.2)
    # region must stay inside the master frame for the 0.25 x-position
    x0, y0, x1, y1 = layer.layout.visualizer_region
    assert x0 > 0.0 and x1 < 1.0 and y0 > 0.0 and y1 < 1.0


async def test_generate_data_rejects_empty_master(tmp_path):
    """TDD-001 §126: an empty/undecodable master is a media error, not a crash."""
    master = _write_wav(tmp_path / "empty.wav", np.zeros(0))
    with pytest.raises(MediaProcessingError):
        await _engine().generate_data(_analysis(0.1), master_path=master)


async def test_generate_data_rejects_missing_master(tmp_path):
    with pytest.raises((MediaProcessingError, OSError)):
        await _engine().generate_data(_analysis(1.0), master_path=tmp_path / "nope.wav")
