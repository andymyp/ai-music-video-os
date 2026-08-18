"""Tests for Production, ProductionConfig and the state machine
(MAD-001 §12-13, §28; TDD-001 §8-11).

Covers the Phase01 required tests: valid/invalid production, genre mode,
trending mode, branding, status transitions and configuration validation.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.domain.enums import ProductionMode, ProductionStatus
from api.domain.production import (
    PRODUCTION_TRANSITIONS,
    TERMINAL_STATUSES,
    BrandingConfig,
    Production,
    ProductionConfig,
)
from api.core.errors import InvalidStateTransitionError


# --- valid / invalid productions ------------------------------------------

def test_valid_genre_production():
    production = Production(mode=ProductionMode.GENRE, genre="Lo-fi")
    assert production.mode is ProductionMode.GENRE
    assert production.genre == "lo-fi"  # normalized to a slug
    assert production.status is ProductionStatus.CREATED
    assert production.id.startswith("prod_")
    assert production.created_at is not None
    assert production.updated_at is not None
    assert production.completed_at is None


def test_valid_trending_production():
    production = Production(mode=ProductionMode.TRENDING)
    assert production.mode is ProductionMode.TRENDING
    assert production.genre is None


def test_invalid_production_genre_mode_without_genre():
    with pytest.raises(ValidationError):
        Production(mode=ProductionMode.GENRE)


def test_invalid_production_id():
    with pytest.raises(ValidationError):
        Production(id="prod_short", mode=ProductionMode.TRENDING)


def test_invalid_production_mode():
    with pytest.raises(ValidationError):
        Production(mode="not-a-mode", genre="lofi")


def test_invalid_target_duration():
    with pytest.raises(ValidationError):
        Production(mode=ProductionMode.TRENDING, target_duration_minutes=0)
    with pytest.raises(ValidationError):
        Production(mode=ProductionMode.TRENDING, target_duration_minutes=601)


def test_blank_genre_rejected():
    with pytest.raises(ValidationError):
        Production(mode=ProductionMode.GENRE, genre="   ")


# --- genre vs trending mode ------------------------------------------------

def test_genre_mode_persists_genre():
    production = Production(mode="genre", genre="synthwave")
    assert production.mode is ProductionMode.GENRE
    assert production.genre == "synthwave"


def test_trending_mode_allows_explicit_genre():
    # Trending chooses the genre, but an explicit override is tolerated.
    production = Production(mode="trending", genre="jazz")
    assert production.mode is ProductionMode.TRENDING
    assert production.genre == "jazz"


# --- branding ---------------------------------------------------------------

def test_branding_text_optional():
    production = Production(mode=ProductionMode.TRENDING)
    assert production.branding_text is None


def test_blank_branding_text_becomes_none():
    production = Production(mode=ProductionMode.TRENDING, branding_text="   ")
    assert production.branding_text is None


def test_branding_text_is_stripped():
    production = Production(mode=ProductionMode.TRENDING, branding_text="  MY CHANNEL ")
    assert production.branding_text == "MY CHANNEL"


def test_branding_config_defaults():
    branding = BrandingConfig()
    assert branding.text == ""
    assert branding.position == "bottom-right"
    assert branding.opacity == pytest.approx(0.65)
    assert branding.font_size == 28


def test_branding_config_invalid_opacity():
    with pytest.raises(ValidationError):
        BrandingConfig(opacity=1.5)


def test_branding_config_invalid_position():
    with pytest.raises(ValidationError):
        BrandingConfig(position="floating")


def test_branding_config_invalid_font_size():
    with pytest.raises(ValidationError):
        BrandingConfig(font_size=2)


# --- status transitions ------------------------------------------------------

FULL_FLOW = [
    ProductionStatus.CREATED,
    ProductionStatus.PLANNING,
    ProductionStatus.CONCEPT_READY,
    ProductionStatus.GENERATING_MUSIC,
    ProductionStatus.MUSIC_READY,
    ProductionStatus.GENERATING_VISUAL,
    ProductionStatus.VISUAL_READY,
    ProductionStatus.ANALYZING_AUDIO,
    ProductionStatus.RENDERING_MASTER,
    ProductionStatus.MASTER_READY,
    ProductionStatus.SELECTING_SHORT,
    ProductionStatus.RENDERING_SHORT,
    ProductionStatus.SHORT_READY,
    ProductionStatus.GENERATING_METADATA,
    ProductionStatus.QUALITY_CHECK,
    ProductionStatus.COMPLETED,
]


def test_happy_path_transitions():
    production = Production(mode=ProductionMode.TRENDING)
    for status in FULL_FLOW[1:]:
        production.transition_to(status)
        assert production.status is status
    assert production.completed_at is not None


def test_skipped_transition_rejected():
    production = Production(mode=ProductionMode.TRENDING)
    with pytest.raises(InvalidStateTransitionError):
        production.transition_to(ProductionStatus.COMPLETED)


def test_backwards_transition_rejected():
    production = Production(mode=ProductionMode.TRENDING)
    production.transition_to(ProductionStatus.PLANNING)
    with pytest.raises(InvalidStateTransitionError):
        production.transition_to(ProductionStatus.CREATED)


def test_failed_allowed_from_any_active_stage():
    for status in ProductionStatus:
        if status in TERMINAL_STATUSES:
            continue
        production = Production(mode=ProductionMode.TRENDING)
        production.status = status
        assert production.can_transition_to(ProductionStatus.FAILED)
        production.transition_to(ProductionStatus.FAILED)
        assert production.status is ProductionStatus.FAILED


def test_cancelled_allowed_from_any_active_stage():
    for status in ProductionStatus:
        if status in TERMINAL_STATUSES:
            continue
        production = Production(mode=ProductionMode.TRENDING)
        production.status = status
        assert production.can_transition_to(ProductionStatus.CANCELLED)


def test_terminal_statuses_are_terminal():
    for terminal in TERMINAL_STATUSES:
        for target in ProductionStatus:
            if target is terminal:
                continue
            production = Production(mode=ProductionMode.TRENDING)
            production.status = terminal
            with pytest.raises(InvalidStateTransitionError):
                production.transition_to(target)


def test_retry_from_failed_to_active_stage():
    production = Production(mode=ProductionMode.TRENDING)
    for status in FULL_FLOW[1:]:
        production.transition_to(status)
        if status is ProductionStatus.RENDERING_MASTER:
            break
    assert production.status is ProductionStatus.RENDERING_MASTER
    production.transition_to(ProductionStatus.FAILED)
    production.transition_to(ProductionStatus.RENDERING_MASTER)
    assert production.status is ProductionStatus.RENDERING_MASTER


def test_idempotent_retry_within_stage():
    production = Production(mode=ProductionMode.TRENDING)
    production.transition_to(ProductionStatus.PLANNING)
    production.transition_to(ProductionStatus.PLANNING)  # no-op retry
    assert production.status is ProductionStatus.PLANNING


def test_cannot_transition_to_failed_when_completed():
    production = Production(mode=ProductionMode.TRENDING)
    production.status = ProductionStatus.COMPLETED
    assert not production.can_transition_to(ProductionStatus.FAILED)


def test_transition_marks_completed_at():
    production = Production(mode=ProductionMode.TRENDING)
    for status in FULL_FLOW[1:]:
        production.transition_to(status)
    assert production.completed_at is not None
    assert production.completed_at >= production.created_at


def test_transition_map_has_no_missing_entries():
    assert set(PRODUCTION_TRANSITIONS) == set(ProductionStatus)
    for status, targets in PRODUCTION_TRANSITIONS.items():
        assert status not in targets or status not in TERMINAL_STATUSES


# --- configuration validation ------------------------------------------------

def test_config_valid_genre_mode():
    config = ProductionConfig(mode=ProductionMode.GENRE, genre="ambient")
    assert config.mode is ProductionMode.GENRE
    assert config.genre == "ambient"
    assert config.branding.text == ""


def test_config_valid_trending_mode():
    config = ProductionConfig(mode=ProductionMode.TRENDING)
    assert config.genre is None
    assert config.master_width == 1920
    assert config.short_height == 1920
    assert config.fps == 30


def test_config_genre_required_in_genre_mode():
    with pytest.raises(ValidationError):
        ProductionConfig(mode=ProductionMode.GENRE)


def test_config_invalid_provider_profile():
    with pytest.raises(ValidationError):
        ProductionConfig(mode=ProductionMode.TRENDING, provider_profile="ultra")


def test_config_invalid_resolution():
    with pytest.raises(ValidationError):
        ProductionConfig(mode=ProductionMode.TRENDING, master_width=64)


def test_config_invalid_short_duration():
    with pytest.raises(ValidationError):
        ProductionConfig(mode=ProductionMode.TRENDING, short_form_duration_seconds=2)
