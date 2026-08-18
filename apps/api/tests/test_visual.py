"""Phase 13: visual pipeline support (MASTER §23; MAD-001 §20-22; TDD-001 §47-48).

Covers the deterministic visual building blocks: strategy-driven prompt
construction + idempotency hash, structural PNG validation, and the reusable
radio asset registry (generate once per style, reuse afterwards).
"""
from __future__ import annotations

import pytest

from api.capabilities import ImageGenerationRequest
from api.domain.creative import VisualStrategy
from api.providers.mock import MockImageProvider
from api.storage.storage import StorageService
from api.visual import (
    ImageValidator,
    RadioAssetRegistry,
    VisualPromptBuilder,
    aspect_ratio_label,
    png_dimensions,
)


def _strategy(**overrides) -> VisualStrategy:
    base = dict(
        theme="rainy late-night bedroom",
        environment="cozy bedroom",
        lighting="warm lamp + blue night",
        style="cinematic illustration",
        color_direction="teal and amber",
        radio_style="vintage",
        composition="centered radio, reserved central area",
        visualizer_style="bars",
        era="modern",
        palette=["teal", "amber", "slate"],
    )
    base.update(overrides)
    return VisualStrategy(**base)


# --- PNG header helpers --------------------------------------------------------

def test_aspect_ratio_label():
    assert aspect_ratio_label(1280, 720) == "16:9"
    assert aspect_ratio_label(720, 1280) == "9:16"
    assert aspect_ratio_label(1024, 1024) == "1:1"


async def test_png_dimensions_reads_mock_provider_output():
    image = await MockImageProvider().generate(
        ImageGenerationRequest(prompt="bg", aspect_ratio="16:9")
    )
    assert image.image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert png_dimensions(image.image_bytes) == (1280, 720)


# --- VisualPromptBuilder (PRD-001 FR-015/016) ---------------------------------

def test_background_prompt_carries_strategy_fields():
    prompt = VisualPromptBuilder().background_prompt(_strategy(), "lofi", "calm")
    assert "rainy late-night bedroom" in prompt
    assert "cozy bedroom" in prompt
    assert "warm lamp + blue night" in prompt
    assert "cinematic illustration" in prompt
    assert "teal" in prompt
    assert "no text" in prompt
    assert "no logos" in prompt
    assert "central space reserved for a radio" in prompt
    assert "lofi" in prompt


def test_radio_prompt_is_style_keyed_only():
    prompt = VisualPromptBuilder().radio_prompt("cyberpunk")
    assert "cyberpunk" in prompt
    assert "1:1" in prompt


def test_prompt_hash_is_deterministic_and_sensitive():
    builder = VisualPromptBuilder()
    first = builder.prompt_hash(_strategy())
    assert first == builder.prompt_hash(_strategy())
    assert first != builder.prompt_hash(_strategy(theme="sunny beach"))
    assert first != builder.prompt_hash(_strategy(), salt="radio")


# --- ImageValidator (TDD-001 §47, PRD-001 FR-016) -----------------------------

async def test_image_validator_accepts_16x9_background():
    image = await MockImageProvider().generate(
        ImageGenerationRequest(prompt="bg", aspect_ratio="16:9")
    )
    result = ImageValidator().validate(
        image.image_bytes, expected_aspect="16:9", min_width=1280, min_height=720
    )
    assert result.valid
    assert result.width == 1280
    assert result.height == 720


async def test_image_validator_rejects_wrong_aspect():
    image = await MockImageProvider().generate(
        ImageGenerationRequest(prompt="portrait", aspect_ratio="9:16")
    )
    result = ImageValidator().validate(image.image_bytes, expected_aspect="16:9")
    assert not result.valid
    assert any(c.name == "aspect_ratio" and not c.passed for c in result.checks)


async def test_image_validator_rejects_low_resolution():
    image = await MockImageProvider().generate(
        ImageGenerationRequest(prompt="tiny", width=640, height=360)
    )
    result = ImageValidator().validate(
        image.image_bytes, expected_aspect="16:9", min_width=1280, min_height=720
    )
    assert not result.valid
    assert any(c.name == "resolution_min" and not c.passed for c in result.checks)


def test_image_validator_rejects_non_png():
    result = ImageValidator().validate(b"not a png at all")
    assert not result.valid
    assert any(c.name == "readable" and not c.passed for c in result.checks)


# --- RadioAssetRegistry (MAD-001 §22, TDD-001 §48, PRD-001 FR-017) ------------

async def test_radio_registry_generates_then_reuses(tmp_path):
    registry = RadioAssetRegistry(StorageService(tmp_path / "assets"), MockImageProvider())
    first = await registry.resolve("vintage")
    second = await registry.resolve("vintage")
    assert not first.reused
    assert second.reused
    assert first.data == second.data
    assert first.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert first.path == second.path
    assert "vintage" in first.path.name


async def test_radio_registry_distinguishes_styles(tmp_path):
    registry = RadioAssetRegistry(StorageService(tmp_path / "assets"), MockImageProvider())
    vintage = await registry.resolve("vintage")
    cyberpunk = await registry.resolve("cyberpunk")
    assert vintage.data != cyberpunk.data
    assert vintage.path != cyberpunk.path


def test_radio_slug_normalizes_style():
    assert RadioAssetRegistry.slug("Vintage  Radio!") == "vintage-radio"
    assert RadioAssetRegistry.slug("") == "radio"
    assert RadioAssetRegistry.slug("wooden radio") == "wooden-radio"