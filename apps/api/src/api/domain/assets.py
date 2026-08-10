"""Asset entity (MAD-001 §65, TDD-001 §16-17).

Every artifact a production generates or consumes (audio, visuals, metadata,
reports) is an :class:`Asset` tracked against its production. The lifecycle
mimics MAD-001 §65: REQUESTED -> GENERATING -> DOWNLOADING -> VALIDATING ->
READY, with any stage able to fail. The ``metadata`` bag carries extra
provider/renderer details without tightening the schema.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, field_validator

from api.core.clock import utc_now
from api.core.errors import InvalidStateTransitionError
from api.core.ids import ASSET_ID_PATTERN, PRODUCTION_ID_PATTERN, new_asset_id
from api.domain.enums import AssetStatus, AssetType

_ASSET_FLOW: list[AssetStatus] = [
    AssetStatus.REQUESTED,
    AssetStatus.GENERATING,
    AssetStatus.DOWNLOADING,
    AssetStatus.VALIDATING,
    AssetStatus.READY,
]

# Some providers skip the explicit download step (they write the file directly).
_SKIP_DOWNLOAD: dict[AssetStatus, set[AssetStatus]] = {
    AssetStatus.GENERATING: {AssetStatus.DOWNLOADING, AssetStatus.VALIDATING},
}

# Retry from a failed state re-requests generation (idempotent, MAD-001 §3.5).
_RETRY: set[AssetStatus] = {AssetStatus.REQUESTED}

_ASSET_TRANSITIONS: dict[AssetStatus, frozenset[AssetStatus]] = {}


def _build_asset_transitions() -> dict[AssetStatus, frozenset[AssetStatus]]:
    transitions: dict[AssetStatus, set[AssetStatus]] = {s: set() for s in AssetStatus}
    for previous, next_status in zip(_ASSET_FLOW, _ASSET_FLOW[1:]):
        transitions[previous].add(next_status)
        transitions[previous].update(_SKIP_DOWNLOAD.get(previous, set()))
    for status in AssetStatus:
        if status not in (AssetStatus.READY, AssetStatus.FAILED):
            transitions[status].add(AssetStatus.FAILED)
    transitions[AssetStatus.FAILED].update(_RETRY)
    return {s: frozenset(targets) for s, targets in transitions.items()}


_ASSET_TRANSITIONS = _build_asset_transitions()


class Asset(BaseModel):
    """An artifact produced for or consumed by a production (TDD-001 §16)."""

    id: str = Field(default_factory=new_asset_id)
    production_id: str
    type: AssetType
    path: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = None
    provider: str | None = None
    status: AssetStatus = AssetStatus.REQUESTED
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if ASSET_ID_PATTERN.match(value) is None:
            raise ValueError("asset id must match asset_<ULID>")
        return value

    @field_validator("production_id")
    @classmethod
    def _validate_production_id(cls, value: str) -> str:
        if PRODUCTION_ID_PATTERN.match(value) is None:
            raise ValueError("production_id must match prod_<ULID>")
        return value

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("path must not be empty")
        return value

    @field_validator("mime_type")
    @classmethod
    def _validate_mime_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if "/" not in value:
            raise ValueError(f"invalid mime_type {value!r}")
        return value

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("sha256 must be a 64-char lowercase hex digest")
        return value

    # --- lifecycle --------------------------------------------------------

    def can_transition_to(self, target: AssetStatus) -> bool:
        return target in _ASSET_TRANSITIONS[self.status]

    def transition_to(self, target: AssetStatus) -> Self:
        if not self.can_transition_to(target):
            raise InvalidStateTransitionError(self.status.value, target.value)
        self.status = target
        return self
