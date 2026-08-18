"""Tests for the Asset entity (MAD-001 §65; TDD-001 §16-17)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.core.errors import InvalidStateTransitionError
from api.core.ids import new_production_id
from api.domain.assets import Asset
from api.domain.enums import AssetStatus, AssetType


def test_valid_asset():
    asset = Asset(
        production_id=new_production_id(),
        type=AssetType.MASTER_VIDEO,
    )
    assert asset.id.startswith("asset_")
    assert asset.status is AssetStatus.REQUESTED
    assert asset.path is None


def test_asset_with_file_fields():
    asset = Asset(
        production_id=new_production_id(),
        type=AssetType.AUDIO_MASTER,
        path="data/assets/audio/master.wav",
        mime_type="audio/wav",
        size_bytes=2048,
        sha256="ab" * 32,
        provider="mock",
        status=AssetStatus.READY,
    )
    assert asset.sha256 == "ab" * 32
    assert asset.metadata == {}


def test_invalid_asset_id():
    with pytest.raises(ValidationError):
        Asset(id="asset_short", production_id=new_production_id(), type=AssetType.RADIO)


def test_invalid_production_id():
    with pytest.raises(ValidationError):
        Asset(production_id="prod_bad", type=AssetType.RADIO)


def test_invalid_sha256():
    with pytest.raises(ValidationError):
        Asset(
            production_id=new_production_id(),
            type=AssetType.RADIO,
            sha256="not-a-hash",
        )


def test_invalid_mime_type():
    with pytest.raises(ValidationError):
        Asset(
            production_id=new_production_id(),
            type=AssetType.RADIO,
            mime_type="audio",
        )


def test_negative_size_rejected():
    with pytest.raises(ValidationError):
        Asset(
            production_id=new_production_id(),
            type=AssetType.RADIO,
            size_bytes=-1,
        )


# --- lifecycle ----------------------------------------------------------------

def test_asset_happy_path():
    asset = Asset(production_id=new_production_id(), type=AssetType.AUDIO_SOURCE)
    asset.transition_to(AssetStatus.GENERATING)
    asset.transition_to(AssetStatus.DOWNLOADING)
    asset.transition_to(AssetStatus.VALIDATING)
    asset.transition_to(AssetStatus.READY)
    assert asset.status is AssetStatus.READY


def test_asset_skip_download():
    asset = Asset(production_id=new_production_id(), type=AssetType.RADIO)
    asset.transition_to(AssetStatus.GENERATING)
    assert asset.can_transition_to(AssetStatus.VALIDATING)
    asset.transition_to(AssetStatus.VALIDATING)
    assert asset.status is AssetStatus.VALIDATING


def test_asset_any_active_stage_may_fail():
    for status in (AssetStatus.REQUESTED, AssetStatus.GENERATING,
                   AssetStatus.DOWNLOADING, AssetStatus.VALIDATING):
        asset = Asset(production_id=new_production_id(), type=AssetType.RADIO)
        asset.status = status
        asset.transition_to(AssetStatus.FAILED)
        assert asset.status is AssetStatus.FAILED


def test_asset_retry_from_failed():
    asset = Asset(production_id=new_production_id(), type=AssetType.RADIO)
    asset.transition_to(AssetStatus.FAILED)
    asset.transition_to(AssetStatus.REQUESTED)
    assert asset.status is AssetStatus.REQUESTED


def test_ready_is_terminal():
    asset = Asset(production_id=new_production_id(), type=AssetType.RADIO)
    asset.status = AssetStatus.READY
    with pytest.raises(InvalidStateTransitionError):
        asset.transition_to(AssetStatus.FAILED)


def test_invalid_asset_transition():
    asset = Asset(production_id=new_production_id(), type=AssetType.RADIO)
    with pytest.raises(InvalidStateTransitionError):
        asset.transition_to(AssetStatus.READY)  # cannot jump REQUESTED -> READY
