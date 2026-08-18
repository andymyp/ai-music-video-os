"""Tests for audio analysis + visualizer data (MAD-001 §23; TDD-001 §45-46)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.domain.audio import AudioAnalysis, AudioSection, VisualizerData


# --- AudioAnalysis --------------------------------------------------------------

def test_valid_analysis():
    analysis = AudioAnalysis(
        duration_seconds=3600.0,
        bpm=78.5,
        loudness_db=-14.0,
        energy_curve=[0.5, 0.6],
        beats=[0.0, 0.5],
        sections=[AudioSection(start_seconds=0.0, end_seconds=120.0, label="intro")],
        timestamps=[0.0, 1.0],
    )
    assert analysis.duration_seconds == pytest.approx(3600.0)
    assert analysis.sections[0].label == "intro"


def test_zero_duration_rejected():
    with pytest.raises(ValidationError):
        AudioAnalysis(duration_seconds=0.0)


def test_section_end_before_start_rejected():
    with pytest.raises(ValidationError):
        AudioSection(start_seconds=120.0, end_seconds=0.0, label="oops")


def test_invalid_bpm_rejected():
    with pytest.raises(ValidationError):
        AudioAnalysis(duration_seconds=60.0, bpm=500.0)


# --- VisualizerData --------------------------------------------------------------

def test_valid_visualizer_data():
    data = VisualizerData(
        frames=[[0.1, 0.2, 0.3, 0.4, 0.5], [0.5, 0.4, 0.3, 0.2, 0.1]],
        timestamps=[0.0, 1.0],
    )
    assert data.style == "bars"
    assert data.band_names == ["bass", "low_mid", "mid", "high_mid", "high"]
    assert len(data.frames) == len(data.timestamps)


def test_frame_timestamp_mismatch_rejected():
    with pytest.raises(ValidationError):
        VisualizerData(frames=[[0.1] * 5], timestamps=[0.0, 1.0])


def test_frame_band_count_mismatch_rejected():
    with pytest.raises(ValidationError):
        VisualizerData(frames=[[0.1, 0.2]])


def test_frame_values_must_be_normalized():
    with pytest.raises(ValidationError):
        VisualizerData(frames=[[0.1, 0.2, 0.3, 0.4, 1.5]])


def test_sensitivity_bounds():
    with pytest.raises(ValidationError):
        VisualizerData(sensitivity=1.5)
