"""Tests for entity identifiers (MAD-001 §61, TDD-001 §138-139)."""
from __future__ import annotations

import pytest

from api.core.ids import (
    ASSET_ID_PATTERN,
    PRODUCTION_ID_PATTERN,
    encode_ulid,
    new_asset_id,
    new_production_id,
    new_ulid,
)


def test_production_id_matches_format():
    production_id = new_production_id()
    assert production_id.startswith("prod_")
    assert PRODUCTION_ID_PATTERN.match(production_id)


def test_asset_id_matches_format():
    asset_id = new_asset_id()
    assert asset_id.startswith("asset_")
    assert ASSET_ID_PATTERN.match(asset_id)


def test_ulids_are_unique_and_26_chars():
    ulids = {new_ulid() for _ in range(1000)}
    assert len(ulids) == 1000
    assert all(len(ulid) == 26 for ulid in ulids)


def test_ulid_is_time_ordered():
    earlier = encode_ulid(1_000_000, 0)
    later = encode_ulid(2_000_000, 0)
    assert earlier < later


def test_encode_ulid_known_value():
    # 0x000000000000 (ts=0) with 0 randomness -> 26 zeros in Crockford Base32.
    assert encode_ulid(0, 0) == "0" * 26


@pytest.mark.parametrize("pattern,value", [
    (PRODUCTION_ID_PATTERN, "prod_" + "0" * 26),
    (ASSET_ID_PATTERN, "asset_" + "A" * 26),
])
def test_patterns_accept_valid_ids(pattern, value):
    assert pattern.match(value)


@pytest.mark.parametrize("pattern,value", [
    (PRODUCTION_ID_PATTERN, "prod_short"),
    (PRODUCTION_ID_PATTERN, "asset_" + "0" * 26),  # wrong prefix
    (PRODUCTION_ID_PATTERN, "prod_" + "0" * 25),
    (ASSET_ID_PATTERN, "asset_short"),
    (ASSET_ID_PATTERN, "prod_" + "0" * 26),  # wrong prefix
])
def test_patterns_reject_invalid_ids(pattern, value):
    assert pattern.match(value) is None
