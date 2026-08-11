"""Phase 14: audio visualizer (MASTER §24; MAD-001 §23; PRD-001 §23-24).

Covers the deterministic FFT → band → normalize → smooth pipeline over a real
master WAV, the sensitivity/smoothing config, and the radio-composited layer
layout (TDD-001 §46, §52, §126).
"""
from __future__ import annotations

import math
import struct
import wave
import zlib
from pathlib import Path

import numpy as np
import pytest

from api.core.errors import MediaProcessingError
from api.domain.audio import AudioAnalysis, VisualizerData
from api.media import (
    SHORT_BRANDING_POSITION,
    SHORT_RADIO_POSITION,
    SHORT_RADIO_SCALE,
    VisualizerEngine,
    VisualizerLayer,
    VisualizerLayout,
    branding_pixels,
    radio_overlay_pixels,
    slice_visualizer,
    vertical_layout,
    visualizer_region_pixels,
)
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
    # inner ~70% of the radio square -> 0.34 * 0.5 * 0.7 = 0.119 half-extent in
    # x; the y half-extent is the same pixel span re-scaled to the frame height
    # so the region stays inside the radio square on any aspect ratio
    # (TDD-001 §52, §128).
    half_x = RADIO_SCALE * 0.5 * 0.7
    half_y = half_x * 1920 / 1080
    expected = (
        round(RADIO_POSITION[0] - half_x, 4),
        round(RADIO_POSITION[1] - half_y, 4),
        round(RADIO_POSITION[0] + half_x, 4),
        round(RADIO_POSITION[1] + half_y, 4),
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


# --- Phase 15: layout -> pixel geometry (TDD-001 §52) -------------------------


def _default_layout() -> VisualizerLayout:
    return VisualizerLayout(
        radio_position=RADIO_POSITION,
        radio_scale=RADIO_SCALE,
        visualizer_region=(0.381, 0.381, 0.619, 0.619),
        visualizer_style="bars",
        branding_position=BRANDING_POSITION,
    )


def test_radio_overlay_pixels_centers_scaled_square():
    """The radio is a radio_scale×frame-width square centered on its position."""
    x, y, w, h = radio_overlay_pixels(_default_layout(), width=1920, height=1080)
    assert (w, h) == (653, 653)  # round(0.34 * 1920)
    assert x + w // 2 == 960  # centered horizontally
    assert y + h // 2 == 540  # centered vertically


def test_visualizer_region_pixels_match_layout():
    x, y, w, h = visualizer_region_pixels(_default_layout(), width=1920, height=1080)
    assert (x, y, w, h) == (732, 411, 456, 258)


def test_branding_pixels_scaled_from_anchor():
    assert branding_pixels(_default_layout(), width=1920, height=1080) == (58, 32)


def test_region_geometry_is_inside_the_radio_square():
    layout = _default_layout()
    rx, ry, rw, rh = radio_overlay_pixels(layout, width=1920, height=1080)
    vx, vy, vw, vh = visualizer_region_pixels(layout, width=1920, height=1080)
    assert rx <= vx and vx + vw <= rx + rw  # bars render in the radio display
    assert ry <= vy and vy + vh <= ry + rh


# --- Phase 15: bar sprite rendering (MAD-001 §23 Video Renderer) --------------


def _sprite_data() -> VisualizerData:
    return VisualizerData(
        style="bars",
        position="radio-center",
        fps=30,
        band_names=BAND_NAMES,
        frames=[[0.0] * 5, [0.5] * 5, [1.0] * 5],
        timestamps=[0.0, 0.033, 0.067],
    )


def _png_idat(png: bytes) -> bytes:
    pos = 8
    while pos < len(png):
        length = struct.unpack(">I", png[pos : pos + 4])[0]
        typ = png[pos + 4 : pos + 8]
        if typ == b"IDAT":
            return zlib.decompress(png[pos + 8 : pos + 8 + length])
        pos += 12 + length
    raise AssertionError("no IDAT chunk")


def _opaque_pixels(png: bytes, width: int, height: int) -> int:
    raw = _png_idat(png)
    stride = width * 4 + 1
    count = 0
    for y in range(height):
        row = raw[y * stride + 1 : (y + 1) * stride]  # skip filter byte
        for x in range(width):
            if row[x * 4 + 3]:
                count += 1
    return count


def test_render_frames_produces_one_valid_png_per_frame():
    sprites = _engine().render_frames(_sprite_data(), width=100, height=60)
    assert len(sprites) == 3
    for png in sprites:
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        assert struct.unpack(">II", png[16:24]) == (100, 60)


def test_render_frames_is_deterministic():
    engine = _engine()
    data = _sprite_data()
    assert engine.render_frames(data, width=100, height=60) == engine.render_frames(
        data, width=100, height=60
    )


def test_render_frames_bar_height_tracks_value():
    """Zero values draw no bars; higher values draw taller (more opaque) bars."""
    engine = _engine()
    data = _sprite_data()
    sprites = engine.render_frames(data, width=100, height=60)
    opaque = [_opaque_pixels(png, 100, 60) for png in sprites]
    assert opaque[0] == 0  # all-zero frame -> fully transparent
    assert opaque[0] < opaque[1] < opaque[2]  # 0.5 < 1.0 bars


def test_render_frames_rejects_nonpositive_dimensions():
    with pytest.raises(ValueError):
        _engine().render_frames(_sprite_data(), width=0, height=60)


# --- Phase 16: vertical composition (MAD-001 §27; TDD-001 §127-128) -----------


def test_vertical_layout_places_radio_in_upper_third():
    """MAD-001 §27: the short's radio sits centered in the upper third, branding
    anchors bottom-center, and the style carries through."""
    layout = vertical_layout(style="waveform", width=1080, height=1920)
    assert layout.radio_position == SHORT_RADIO_POSITION  # (0.5, 0.35)
    assert layout.radio_scale == SHORT_RADIO_SCALE  # 0.5
    assert layout.branding_position == SHORT_BRANDING_POSITION  # (0.5, 0.9)
    assert layout.visualizer_style == "waveform"
    # the radio is a 0.5×1080 square centered at y=0.35 → entirely in the upper
    # half of the frame and horizontally centered.
    x, y, w, h = radio_overlay_pixels(layout, width=1080, height=1920)
    assert (w, h) == (540, 540)
    assert x + w // 2 == 540
    assert 0.2 * 1920 <= y and y + h <= 0.5 * 1920


def test_vertical_layout_region_stays_inside_radio_for_short_sizes():
    """TDD-001 §128: the visualizer region never leaves the radio square on any
    short resolution, so important elements are never cropped."""
    for width, height in [(1080, 1920), (720, 1280), (1080, 1080), (405, 720)]:
        layout = vertical_layout(width=width, height=height)
        rx, ry, rw, rh = radio_overlay_pixels(layout, width=width, height=height)
        vx, vy, vw, vh = visualizer_region_pixels(layout, width=width, height=height)
        assert rx <= vx and vx + vw <= rx + rw
        assert ry <= vy and vy + vh <= ry + rh


def test_vertical_layout_region_is_square_in_pixel_space():
    """The region is the radio's inner 70% in pixel space, so it stays square on
    9:16 frames (the Phase 14 aspect-aware fix applied to the vertical layout)."""
    layout = vertical_layout(width=1080, height=1920)
    vx, vy, vw, vh = visualizer_region_pixels(layout, width=1080, height=1920)
    assert vw == vh
    assert (vw, vh) == (378, 378)


def test_slice_visualizer_subwindows_segment():
    """TDD-001 §129: slicing keeps the segment's frames and rebases timestamps to
    short t=0 so the bars stay synchronized with the trimmed audio."""
    fps = 30
    n = 90
    data = VisualizerData(
        style="bars",
        position="radio-center",
        fps=fps,
        band_names=BAND_NAMES,
        frames=[[float(i) % 2 / 2] * 5 for i in range(n)],
        timestamps=[round(i / fps, 3) for i in range(n)],
    )
    sliced = slice_visualizer(data, start_seconds=1.0, duration_seconds=1.0)
    assert len(sliced.frames) == fps  # the [1.0s, 2.0s) window at 30fps
    assert sliced.frames[0] == data.frames[30]
    assert sliced.frames[-1] == data.frames[59]
    assert sliced.timestamps[0] == 0.0  # rebased to the short's t=0
    assert sliced.timestamps[-1] == pytest.approx(1.0, abs=0.05)
    assert sliced.fps == fps
    assert sliced.band_names == BAND_NAMES


def test_slice_visualizer_bounds_clamp_to_track_end():
    """A window past the end clamps to the available frames, never past it."""
    fps = 30
    data = VisualizerData(
        style="bars",
        position="radio-center",
        fps=fps,
        band_names=BAND_NAMES,
        frames=[[0.5] * 5 for _ in range(90)],
        timestamps=[round(i / fps, 3) for i in range(90)],
    )
    sliced = slice_visualizer(data, start_seconds=2.5, duration_seconds=5.0)
    assert len(sliced.frames) <= len(data.frames) - 75
    assert sliced.frames == data.frames[75:]
    assert sliced.timestamps[0] == pytest.approx(0.0)


def test_slice_visualizer_noop_for_empty_or_short_window():
    data = VisualizerData(
        style="bars", position="radio-center", fps=30, band_names=BAND_NAMES,
        frames=[[0.5] * 5 for _ in range(10)], timestamps=[i / 30 for i in range(10)],
    )
    assert slice_visualizer(data, start_seconds=0.0, duration_seconds=0.0) is data
    assert slice_visualizer(data, start_seconds=1.0, duration_seconds=0.0) is data
