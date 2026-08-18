"""Tests for creative-direction models (MAD-001 §16-20; TDD-001 §12-15)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.domain.creative import CreativeConcept, MusicStrategy, TrendResult, VisualStrategy


# --- CreativeConcept ----------------------------------------------------------

def test_valid_concept():
    concept = CreativeConcept(
        genre="Lo-fi",
        mood="mellow",
        theme="late-night study",
        music_direction="warm keys, dusty drums",
        visual_direction="warm window light, vinyl close-ups",
    )
    assert concept.genre == "lo-fi"


def test_concept_requires_music_direction():
    with pytest.raises(ValidationError):
        CreativeConcept(
            genre="lofi",
            mood="mellow",
            theme="late-night study",
            visual_direction="warm",
        )


# --- MusicStrategy -------------------------------------------------------------

def test_valid_music_strategy():
    strategy = MusicStrategy(
        genre="lofi",
        mood="mellow",
        bpm_range=[70, 85],
        key="A minor",
        structure="intro-verse-chorus-outro",
    )
    assert strategy.vocal_policy == "none"
    assert strategy.duration_target_minutes == 60


def test_vocal_policy_must_be_none():
    # PRD-001 §15: instrumentals only — anything with vocals is rejected.
    with pytest.raises(ValidationError):
        MusicStrategy(
            genre="lofi",
            mood="mellow",
            key="A minor",
            structure="intro-verse-chorus-outro",
            vocal_policy="vocals",
        )


def test_bpm_range_requires_two_values():
    with pytest.raises(ValidationError):
        MusicStrategy(
            genre="lofi",
            mood="mellow",
            bpm_range=[80],
            key="A minor",
            structure="intro",
        )


def test_bpm_range_requires_low_le_high():
    with pytest.raises(ValidationError):
        MusicStrategy(
            genre="lofi",
            mood="mellow",
            bpm_range=[100, 80],
            key="A minor",
            structure="intro",
        )


def test_bpm_range_positive():
    with pytest.raises(ValidationError):
        MusicStrategy(
            genre="lofi",
            mood="mellow",
            bpm_range=[0, 80],
            key="A minor",
            structure="intro",
        )


# --- VisualStrategy -------------------------------------------------------------

def test_valid_visual_strategy():
    strategy = VisualStrategy(
        theme="late-night drive",
        environment="city at night",
        lighting="neon glow",
        style="retro-futurist",
        color_direction="teal and magenta",
        radio_style="vinyl player",
        composition="centered radio, floating bars",
    )
    assert strategy.visualizer_style == "bars"
    assert strategy.palette == []


def test_visual_strategy_requires_theme():
    with pytest.raises(ValidationError):
        VisualStrategy(
            environment="city at night",
            lighting="neon glow",
            style="retro-futurist",
            color_direction="teal",
            radio_style="vinyl",
            composition="centered",
        )


# --- TrendResult ----------------------------------------------------------------

def test_valid_trend_result():
    result = TrendResult(
        source="spotify",
        topic="lo-fi beats 2026",
        genre="Lo-Fi",
        score=89.4,
        confidence=0.8,
        growth=0.6,
        volume=0.5,
        cross_platform=0.7,
        content_fit=0.9,
        reasoning="sustained growth across platforms",
    )
    assert result.genre == "lo-fi"
    assert result.evidence == []


def test_trend_score_upper_bound():
    with pytest.raises(ValidationError):
        TrendResult(source="spotify", topic="x", score=101)


def test_trend_confidence_bounds():
    with pytest.raises(ValidationError):
        TrendResult(source="spotify", topic="x", confidence=1.5)
    with pytest.raises(ValidationError):
        TrendResult(source="spotify", topic="x", confidence=-0.1)


def test_trend_component_signals_bounded():
    with pytest.raises(ValidationError):
        TrendResult(source="spotify", topic="x", volume=2.0)
