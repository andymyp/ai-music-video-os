"""Production aggregate and configuration (MAD-001 §12-13, §28; TDD-001 §8-11).

The :class:`Production` is the root aggregate of the system (TDD-001 §8). It
carries the identity, mode, genre, branding and lifecycle state, and enforces
the state machine defined in MAD-001 §13 through :meth:`Production.transition_to`.
:class:`ProductionConfig` snapshots the runtime parameters (resolutions, fps,
durations, branding, provider profile) that later phases pass to providers and
renderers (MAD-001 §92-94 config precedence).
"""
from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from api.config.profiles import PROVIDER_MODES
from api.core.clock import utc_now
from api.core.errors import InvalidStateTransitionError
from api.core.ids import PRODUCTION_ID_PATTERN, new_production_id
from api.domain.enums import ProductionMode, ProductionStatus

# Positions available for on-video branding (MAD-001 §28).
BRANDING_POSITIONS: frozenset[str] = frozenset(
    {"top-left", "top-center", "top-right", "center",
     "bottom-left", "bottom-center", "bottom-right"}
)

TERMINAL_STATUSES: frozenset[ProductionStatus] = frozenset(
    {ProductionStatus.COMPLETED, ProductionStatus.CANCELLED}
)

# Forward progression defined by the state machine (MAD-001 §13).
_PRODUCTION_FLOW: list[ProductionStatus] = [
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


def _build_transition_map() -> dict[ProductionStatus, frozenset[ProductionStatus]]:
    """Derive the allowed-transition graph.

    Rules (MAD-001 §13, §43):
      * forward flow proceeds one adjacent step at a time (no skipping);
      * any non-terminal stage may fail (-> FAILED) or be cancelled (-> CANCELLED);
      * a stage may transition to itself (idempotent retry within the stage);
      * a FAILED production may retry into any non-terminal stage;
      * COMPLETED and CANCELLED are terminal (no outgoing edges).
    """
    transitions: dict[ProductionStatus, set[ProductionStatus]] = {
        status: set() for status in ProductionStatus
    }
    for previous, next_status in zip(_PRODUCTION_FLOW, _PRODUCTION_FLOW[1:]):
        transitions[previous].add(next_status)

    for status in ProductionStatus:
        if status in TERMINAL_STATUSES:
            continue
        transitions[status].add(ProductionStatus.FAILED)
        transitions[status].add(ProductionStatus.CANCELLED)
        transitions[status].add(status)  # idempotent retry in-place

    retryable = [
        status
        for status in ProductionStatus
        if status not in TERMINAL_STATUSES and status is not ProductionStatus.FAILED
    ]
    for status in retryable:
        transitions[ProductionStatus.FAILED].add(status)

    return {status: frozenset(targets) for status, targets in transitions.items()}


PRODUCTION_TRANSITIONS: dict[ProductionStatus, frozenset[ProductionStatus]] = (
    _build_transition_map()
)


class BrandingConfig(BaseModel):
    """On-video branding overlay settings (MAD-001 §28)."""

    text: str = Field(default="", max_length=80)
    position: str = "bottom-right"
    opacity: float = Field(default=0.65)
    font_size: int = Field(default=28)

    @field_validator("position")
    @classmethod
    def _validate_position(cls, value: str) -> str:
        if value not in BRANDING_POSITIONS:
            raise ValueError(
                f"position must be one of {sorted(BRANDING_POSITIONS)}, got {value!r}"
            )
        return value

    @field_validator("opacity")
    @classmethod
    def _validate_opacity(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("opacity must be between 0 and 1")
        return value

    @field_validator("font_size")
    @classmethod
    def _validate_font_size(cls, value: int) -> int:
        if not 8 <= value <= 200:
            raise ValueError("font_size must be between 8 and 200")
        return value


class Production(BaseModel):
    """Root aggregate: identity, mode, genre, branding, lifecycle (TDD-001 §8)."""

    id: str = Field(default_factory=new_production_id)
    mode: ProductionMode
    genre: str | None = None
    branding_text: str | None = None
    status: ProductionStatus = ProductionStatus.CREATED
    target_duration_minutes: int = Field(default=60, ge=1, le=600)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    version: int = Field(default=1, ge=1)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if PRODUCTION_ID_PATTERN.match(value) is None:
            raise ValueError("production id must match prod_<ULID>")
        return value

    @field_validator("genre")
    @classmethod
    def _normalize_genre(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if not value:
            raise ValueError("genre must not be empty")
        return value

    @field_validator("branding_text")
    @classmethod
    def _normalize_branding(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def _genre_required_for_genre_mode(self) -> Self:
        if self.mode is ProductionMode.GENRE and not self.genre:
            raise ValueError("genre is required when mode is 'genre'")
        return self

    # --- lifecycle --------------------------------------------------------

    def can_transition_to(self, target: ProductionStatus) -> bool:
        """Return True if ``target`` is reachable from the current status."""
        return target in PRODUCTION_TRANSITIONS[self.status]

    def transition_to(self, target: ProductionStatus) -> Self:
        """Move the production to ``target``, enforcing the state machine.

        Raises :class:`InvalidStateTransitionError` for forbidden transitions.
        Setting ``completed_at`` is owned by the domain so callers cannot
        record a stale completion timestamp.
        """
        if not self.can_transition_to(target):
            raise InvalidStateTransitionError(self.status.value, target.value)
        self.status = target
        self.updated_at = utc_now()
        if target is ProductionStatus.COMPLETED:
            self.completed_at = self.updated_at
        return self


class ProductionConfig(BaseModel):
    """Snapshot of runtime parameters for a production (TDD-001 §11).

    Long-form renders at master resolution; short-form clips at vertical
    resolution (PRD-001 §27-28). Defaults mirror the environment defaults in
    ``api.config.settings``; later phases layer config precedence on top
    (MAD-001 §92-94).
    """

    mode: ProductionMode
    genre: str | None = None
    branding: BrandingConfig = Field(default_factory=BrandingConfig)
    long_form_duration_minutes: int = Field(default=60, ge=1, le=600)
    short_form_duration_seconds: int = Field(default=45, ge=5, le=300)
    master_width: int = Field(default=1920, ge=320, le=7680)
    master_height: int = Field(default=1080, ge=240, le=4320)
    fps: int = Field(default=30, ge=1, le=120)
    short_width: int = Field(default=1080, ge=240, le=7680)
    short_height: int = Field(default=1920, ge=240, le=4320)
    visualizer_style: str = Field(default="bars", max_length=40)
    provider_profile: str = Field(default="mock")

    @field_validator("genre")
    @classmethod
    def _normalize_genre(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if not value:
            raise ValueError("genre must not be empty")
        return value

    @field_validator("provider_profile")
    @classmethod
    def _validate_provider_profile(cls, value: str) -> str:
        if value not in PROVIDER_MODES:
            raise ValueError(
                f"provider_profile must be one of {sorted(PROVIDER_MODES)}, got {value!r}"
            )
        return value

    @model_validator(mode="after")
    def _genre_required_for_genre_mode(self) -> Self:
        if self.mode is ProductionMode.GENRE and not self.genre:
            raise ValueError("genre is required when mode is 'genre'")
        return self

    def to_row_values(self) -> dict[str, object]:
        """Flat values for DB row mapping (nested branding flattened)."""
        return {
            "mode": self.mode.value,
            "genre": self.genre,
            "branding_text": self.branding.text,
            "branding_position": self.branding.position,
            "branding_opacity": self.branding.opacity,
            "branding_font_size": self.branding.font_size,
            "long_form_duration_minutes": self.long_form_duration_minutes,
            "short_form_duration_seconds": self.short_form_duration_seconds,
            "master_width": self.master_width,
            "master_height": self.master_height,
            "fps": self.fps,
            "short_width": self.short_width,
            "short_height": self.short_height,
            "visualizer_style": self.visualizer_style,
            "provider_profile": self.provider_profile,
        }
