"""Phase 07: audio analysis (MAD-001 §19, §23; TDD-001 §45-46).

Unit tests exercise the pure NumPy DSP on synthetic signals (comb onsets, sines,
silence, staged energy) without any subprocess. Integration tests decode real
WAV fixtures through FFmpeg and are skipped when FFmpeg is unavailable. Fixtures
are generated deterministically in-process via the Phase05 mock codec helpers.
"""
from __future__ import annotations

import math
import shutil

import numpy as np
import pytest

from api.core.errors import MediaProcessingError
from api.domain.audio import AudioAnalysis
from api.media.audio import (
    AudioAnalysisEngine,
    bpm_from_beats,
    detect_beats,
    detect_sections,
    estimate_bpm,
    frame_times,
    onset_flux,
    rms_loudness_db,
    spectral_centroids,
    split_frames,
    windowed_rms,
)

FFMPEG_PRESENT = shutil.which("ffmpeg") is not None

SAMPLE_RATE = 22050
FRAME_SIZE = 2048
HOP = 512
FRAME_SEC = HOP / SAMPLE_RATE  # ~0.0232 s


# --- Fixture helpers (deterministic synthetic audio) --------------------------

def _sine_samples(seconds: float, amplitude: float, freq: float = 440.0) -> list[int]:
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    wave = amplitude * np.sin(2 * np.pi * freq * t)
    return (wave * 32767).astype(np.int16).tolist()


def _segment_samples(segments: list[tuple[float, float, float]]) -> list[int]:
    """Concatenate (seconds, amplitude, freq) segments into int16 samples."""
    return [s for seconds, amplitude, freq in segments for s in _sine_samples(seconds, amplitude, freq)]


def _click_samples(duration: float, bpm: float, click_len: int = 441) -> list[int]:
    """A click every beat (60/bpm s): short 440 Hz burst, silence between."""
    n = int(duration * SAMPLE_RATE)
    samples = [0] * n
    burst = (0.9 * np.sin(2 * np.pi * 440.0 * np.arange(click_len) / SAMPLE_RATE) * 32767).astype(np.int16)
    step = int(60.0 / bpm * SAMPLE_RATE)
    pos = 0
    while pos < n:
        for j in range(min(click_len, n - pos)):
            samples[pos + j] = int(burst[j])
        pos += step
    return samples


def _write_wav(tmp_path, name: str, samples: list[int]) -> str:
    from api.providers.mock import _encode_wav

    path = tmp_path / name
    path.write_bytes(_encode_wav(samples, sample_rate=SAMPLE_RATE, channels=1, bits=16))
    return str(path)


# --- Pure DSP: frames, energy, spectral centroid (TDD-001 §45) ----------------

def test_split_frames_returns_overlapping_frames():
    samples = np.ones(FRAME_SIZE + 3 * HOP, dtype=np.float32)
    frames = split_frames(samples, FRAME_SIZE, HOP)
    assert frames.shape == (4, FRAME_SIZE)
    assert np.all(frames == 1.0)


def test_split_frames_pads_short_signal_to_one_frame():
    samples = np.arange(1000, dtype=np.float32)  # shorter than frame_size
    frames = split_frames(samples, FRAME_SIZE, HOP)
    assert frames.shape == (1, FRAME_SIZE)
    assert np.array_equal(frames[0, :1000], samples)
    assert np.all(frames[0, 1000:] == 0.0)  # tail zero-padded


def test_frame_times_are_centred():
    times = frame_times(4, HOP, FRAME_SIZE, SAMPLE_RATE)
    assert times[0] == pytest.approx((FRAME_SIZE / 2.0) / SAMPLE_RATE)
    assert (times[1] - times[0]) == pytest.approx(FRAME_SEC)


def test_windowed_rms_sine_is_amplitude_over_root_two():
    samples = np.tile(_sine_samples(0.1, 0.5), 8).astype(np.float32) / 32767.0
    frames = split_frames(samples, FRAME_SIZE, HOP)
    rms = windowed_rms(frames)
    assert rms.shape == (frames.shape[0],)
    assert np.allclose(rms, 0.5 / math.sqrt(2.0), atol=0.01)


def test_windowed_rms_silence_is_zero():
    frames = np.zeros((10, FRAME_SIZE), dtype=np.float32)
    assert np.all(windowed_rms(frames) == 0.0)


def test_spectral_centroid_separates_pitch():
    low = split_frames(np.tile(_sine_samples(0.1, 0.5, 440.0), 8).astype(np.float32) / 32767.0, FRAME_SIZE, HOP)
    high = split_frames(np.tile(_sine_samples(0.1, 0.5, 1000.0), 8).astype(np.float32) / 32767.0, FRAME_SIZE, HOP)
    centroid_low = spectral_centroids(low, SAMPLE_RATE).mean()
    centroid_high = spectral_centroids(high, SAMPLE_RATE).mean()
    assert 0.0 < centroid_low < 0.06
    assert 0.07 < centroid_high < 1.0
    assert centroid_low < centroid_high


# --- Pure DSP: loudness ------------------------------------------------------

def test_rms_loudness_db_silence_floor():
    assert rms_loudness_db(np.zeros(8192, dtype=np.float32)) == -90.0


def test_rms_loudness_db_sine():
    samples = np.asarray(_sine_samples(1.0, 0.5), dtype=np.float32) / 32767.0
    expected = 20.0 * math.log10(0.5 / math.sqrt(2.0))
    assert rms_loudness_db(samples) == pytest.approx(expected, abs=0.1)


# --- Pure DSP: beats and BPM --------------------------------------------------

def _comb_onset(n_frames: int, period: float = 21.5) -> np.ndarray:
    onset = np.zeros(n_frames, dtype=np.float64)
    positions = np.arange(10.0, n_frames, period).round().astype(int)
    onset[positions] = 1.0
    return onset


def test_detect_beats_counts_periodic_spikes():
    onset = _comb_onset(200)
    times = np.arange(onset.size) * FRAME_SEC
    beats = detect_beats(onset, times)
    assert len(beats) == int(np.count_nonzero(onset))


def test_detect_beats_times_follow_spikes():
    onset = _comb_onset(200)
    times = np.arange(onset.size) * FRAME_SEC
    beats = detect_beats(onset, times)
    spikes = np.flatnonzero(onset).astype(float)
    assert max(abs(b / FRAME_SEC - s) for b, s in zip(beats, spikes)) < 1.5


def test_detect_beats_empty_onset():
    assert detect_beats(np.zeros(5), np.arange(5) * FRAME_SEC) == []


def test_estimate_bpm_periodic_comb():
    onset = _comb_onset(600)
    times = np.arange(onset.size) * FRAME_SEC
    bpm = estimate_bpm(onset, times)
    assert bpm is not None
    assert 114.0 <= bpm <= 126.0  # 120 BPM target


def test_estimate_bpm_flat_onset_returns_none():
    assert estimate_bpm(np.zeros(100), np.arange(100) * FRAME_SEC) is None


def test_bpm_from_beats_regular_grid():
    beats = [i * 0.5 for i in range(20)]
    assert bpm_from_beats(beats) == pytest.approx(120.0)


def test_bpm_from_beats_tolerates_missed_beats():
    beats = [0.0, 0.5, 1.0, 1.55, 2.0, 2.5, 3.05]  # one slightly late hit
    assert 118.0 <= bpm_from_beats(beats) <= 122.0


def test_bpm_from_beats_too_few_returns_none():
    assert bpm_from_beats([0.0, 0.5, 0.9]) is None


def test_bpm_from_beats_out_of_range_returns_none():
    assert bpm_from_beats([i * 0.1 for i in range(20)]) is None  # 600 BPM


# --- Pure DSP: sections -------------------------------------------------------

def _energy_runs(*lengths, low=0.1, high=0.9):
    parts = []
    for i, length in enumerate(lengths):
        parts.append(np.full(length, high if i % 2 else low, dtype=np.float64))
    return np.concatenate(parts)


def test_detect_sections_splits_quiet_loud_quiet():
    energy = _energy_runs(100, 100, 100)
    times = np.arange(energy.size) * FRAME_SEC
    sections = detect_sections(energy, times)
    assert [s.label for s in sections] == ["quiet", "loud", "quiet"]
    assert sections[1].start_seconds == pytest.approx(100 * FRAME_SEC, abs=0.3)
    assert sections[2].start_seconds == pytest.approx(200 * FRAME_SEC, abs=0.3)
    for a, b in zip(sections, sections[1:]):
        assert b.start_seconds == pytest.approx(a.end_seconds)


def test_detect_sections_constant_energy_is_single_section():
    sections = detect_sections(np.full(200, 0.5), np.arange(200) * FRAME_SEC)
    assert len(sections) == 1
    assert sections[0].label in ("loud", "quiet")


def test_detect_sections_empty():
    assert detect_sections(np.array([]), np.array([])) == []


# --- Engine wiring (injectable runner, no subprocess) -------------------------

class FakeRunner:
    def __init__(self, stdout: bytes):
        self.calls: list[list[str]] = []
        self.stdout = stdout

    async def __call__(self, cmd, *, timeout=None):
        self.calls.append(cmd)
        return self.stdout, b""


def _pcm_f32(seconds: float, amplitude: float, freq: float = 440.0) -> bytes:
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32).tobytes()


async def test_engine_decodes_via_ffmpeg_and_builds_analysis(tmp_path):
    runner = FakeRunner(_pcm_f32(3.0, 0.5))
    engine = AudioAnalysisEngine(ffmpeg_bin="ffmpeg-test", runner=runner, sample_rate=SAMPLE_RATE)
    path = tmp_path / "in.wav"
    path.write_bytes(b"x")

    result = await engine.analyze(str(path))

    cmd = runner.calls[0]
    assert cmd[0] == "ffmpeg-test"
    assert cmd[cmd.index("-f") + 1] == "f32le"
    assert cmd[cmd.index("-ar") + 1] == str(SAMPLE_RATE)
    assert "-ac" in cmd and cmd[cmd.index("-ac") + 1] == "1"

    assert isinstance(result, AudioAnalysis)
    assert result.duration_seconds == pytest.approx(3.0, abs=0.01)
    assert result.loudness_db is not None
    assert result.energy_curve and result.spectral_curve and result.timestamps
    assert len(result.energy_curve) == len(result.spectral_curve) == len(result.timestamps)


# --- Real FFmpeg integration (skipped when FFmpeg is absent) ------------------

@pytest.fixture
def engine() -> AudioAnalysisEngine:
    return AudioAnalysisEngine(sample_rate=SAMPLE_RATE)


@pytest.mark.skipif(not FFMPEG_PRESENT, reason="FFmpeg not on PATH")
async def test_integration_analyze_sine_wav(tmp_path, engine):
    path = _write_wav(tmp_path, "sine.wav", _sine_samples(5.0, 0.5))
    result = await engine.analyze(path)
    assert result.duration_seconds == pytest.approx(5.0, abs=0.05)
    assert result.loudness_db is not None
    assert -11.0 < result.loudness_db < -7.0  # 0.5 sine ≈ -9 dB
    assert result.energy_curve and result.spectral_curve and result.timestamps
    assert len(result.energy_curve) == len(result.timestamps)
    assert 0.0 <= max(result.spectral_curve) <= 1.0


@pytest.mark.skipif(not FFMPEG_PRESENT, reason="FFmpeg not on PATH")
async def test_integration_analyze_click_track_bpm(tmp_path, engine):
    path = _write_wav(tmp_path, "clicks.wav", _click_samples(15.0, bpm=120.0))
    result = await engine.analyze(path)
    assert result.duration_seconds == pytest.approx(15.0, abs=0.05)
    assert result.bpm is not None
    assert 114.0 <= result.bpm <= 126.0  # 120 BPM click track
    assert len(result.beats) >= 25  # 30 clicks, first/last edge tolerated
    assert all(b >= 0.0 for b in result.beats)


@pytest.mark.skipif(not FFMPEG_PRESENT, reason="FFmpeg not on PATH")
async def test_integration_analyze_loud_quiet_loud_sections(tmp_path, engine):
    segments = [(4.0, 0.8, 440.0), (4.0, 0.05, 440.0), (4.0, 0.8, 440.0)]
    path = _write_wav(tmp_path, "staged.wav", _segment_samples(segments))
    result = await engine.analyze(path)
    assert [s.label for s in result.sections] == ["loud", "quiet", "loud"]
    assert result.sections[1].start_seconds == pytest.approx(4.0, abs=0.5)
    assert result.sections[2].start_seconds == pytest.approx(8.0, abs=0.5)


@pytest.mark.skipif(not FFMPEG_PRESENT, reason="FFmpeg not on PATH")
async def test_integration_analyze_silence(tmp_path, engine):
    path = _write_wav(tmp_path, "silence.wav", [0] * int(3.0 * SAMPLE_RATE))
    result = await engine.analyze(path)
    assert result.loudness_db == -90.0
    assert result.bpm is None
    assert result.beats == []
    assert [s.label for s in result.sections] == ["quiet"]
    assert result.sections[0].start_seconds == pytest.approx(0.0, abs=0.05)


@pytest.mark.skipif(not FFMPEG_PRESENT, reason="FFmpeg not on PATH")
async def test_integration_analyze_too_short_raises(tmp_path, engine):
    path = _write_wav(tmp_path, "short.wav", [0] * 1000)  # < frame_size
    with pytest.raises(MediaProcessingError):
        await engine.analyze(path)
