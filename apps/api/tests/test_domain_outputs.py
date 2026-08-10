"""Tests for final-output models (MAD-001 §26, §30, §82; TDD-001 §131)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.domain.outputs import Metadata, MetadataPackage, QualityDecision, ShortSegment


# --- Metadata -----------------------------------------------------------------

def test_valid_metadata():
    metadata = Metadata(
        title="Lo-fi Radio — 60 Minutes of Chill Beats",
        description="Relaxing instrumental beats for focus.",
        hashtags=["lofi", "music", "focus"],
    )
    assert metadata.hashtags == ["#lofi", "#music", "#focus"]


def test_metadata_normalizes_hash_prefix():
    metadata = Metadata(
        title="t", description="d", hashtags=["#lofi", "beats", "  chill "]
    )
    assert metadata.hashtags == ["#lofi", "#beats", "#chill"]


def test_metadata_requires_title():
    with pytest.raises(ValidationError):
        Metadata(title="   ", description="d", hashtags=["lofi"])


def test_metadata_requires_description():
    with pytest.raises(ValidationError):
        Metadata(title="t", description="", hashtags=["lofi"])


def test_metadata_requires_at_least_one_hashtag():
    with pytest.raises(ValidationError):
        Metadata(title="t", description="d", hashtags=[])


def test_metadata_rejects_invalid_hashtag():
    with pytest.raises(ValidationError):
        Metadata(title="t", description="d", hashtags=["has spaces"])


def test_metadata_package_valid():
    package = MetadataPackage(
        master=Metadata(title="Master", description="desc", hashtags=["lofi"]),
        short=Metadata(title="Short", description="desc", hashtags=["lofi", "shorts"]),
    )
    assert package.master.title == "Master"
    assert package.short.hashtags == ["#lofi", "#shorts"]


def test_metadata_package_requires_both():
    with pytest.raises(ValidationError):
        MetadataPackage(
            master=Metadata(title="Master", description="desc", hashtags=["lofi"])
        )


# --- QualityDecision ------------------------------------------------------------

def test_valid_passing_decision():
    decision = QualityDecision(passed=True, warnings=["slight clipping"], score=0.9)
    assert decision.passed is True


def test_valid_failing_decision():
    decision = QualityDecision(
        passed=False, issues=["frame drops in section 3"], score=0.4
    )
    assert decision.issues == ["frame drops in section 3"]


def test_passed_with_issues_rejected():
    with pytest.raises(ValidationError):
        QualityDecision(passed=True, issues=["blocky artifacts"], score=0.6)


def test_score_bounds():
    with pytest.raises(ValidationError):
        QualityDecision(passed=False, score=1.5)


# --- ShortSegment -----------------------------------------------------------------

def test_valid_short_segment():
    segment = ShortSegment(
        start_seconds=120.0,
        duration_seconds=45.0,
        score=0.85,
        reason="strong hook at 02:00",
    )
    assert segment.duration_seconds == pytest.approx(45.0)


def test_negative_start_rejected():
    with pytest.raises(ValidationError):
        ShortSegment(start_seconds=-1.0, duration_seconds=45.0, reason="r")


def test_zero_duration_rejected():
    with pytest.raises(ValidationError):
        ShortSegment(start_seconds=0.0, duration_seconds=0.0, reason="r")


def test_score_bounds():
    with pytest.raises(ValidationError):
        ShortSegment(start_seconds=0.0, duration_seconds=45.0, score=1.2, reason="r")


def test_reason_required():
    with pytest.raises(ValidationError):
        ShortSegment(start_seconds=0.0, duration_seconds=45.0, reason="   ")
