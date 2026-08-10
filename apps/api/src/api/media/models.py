"""Media engine data contracts (MAD-001 §24-27, §56; TDD-001 §50, §124).

Rendering configuration is externalized through :class:`RenderProfile`
(MAD-001 §56: ``youtube_master`` / ``youtube_short`` presets) so encoding
parameters remain configurable (PRD-001 FR-019/FR-020). The request/result
types below are the media engine's contract with the pipeline layers.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from api.domain.outputs import ShortSegment


class RenderProfile(BaseModel):
    """Externalized encoding profile (MAD-001 §56)."""

    name: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: int = Field(default=30, gt=0)
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    video_bitrate: str | None = None
    audio_bitrate: str | None = None
    pixel_format: str = "yuv420p"
    preset: str | None = "medium"
    crf: int | None = Field(default=23, ge=0, le=51)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be empty")
        return value


# Initial rendering profiles (MAD-001 §56 / PRD-001 FR-019, FR-020).
MASTER_PROFILE = RenderProfile(
    name="youtube_master",
    width=1920,
    height=1080,
    fps=30,
    video_codec="libx264",
    audio_codec="aac",
    crf=20,
    preset="medium",
    pixel_format="yuv420p",
)
SHORT_PROFILE = RenderProfile(
    name="youtube_short",
    width=1080,
    height=1920,
    fps=30,
    video_codec="libx264",
    audio_codec="aac",
    crf=20,
    preset="medium",
    pixel_format="yuv420p",
)


class OverlaySpec(BaseModel):
    """An image overlay composited onto the render (e.g. the radio asset)."""

    path: Path
    x: int = 0
    y: int = 0
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)


class RenderRequest(BaseModel):
    """Inputs for one deterministic render (MAD-001 §24, §27).

    ``background`` and ``audio`` are required; ``overlays`` (radio/visualizer)
    and ``branding_text`` are composited on top. For short renders, ``segment``
    trims the audio to the selected clip (TDD-001 §129).
    """

    background: Path
    audio: Path
    overlays: list[OverlaySpec] = Field(default_factory=list)
    branding_text: str | None = None
    branding_font: Path | None = None
    branding_x: int = 0
    branding_y: int = 0
    branding_size: int = Field(default=48, gt=0)
    output_path: Path
    segment: ShortSegment | None = None


class MediaProbe(BaseModel):
    """Structural probe of a media file (ffprobe output normalized)."""

    duration_seconds: float | None = Field(default=None, ge=0)
    sample_rate: int | None = Field(default=None, gt=0)
    channels: int | None = Field(default=None, ge=1)
    audio_codec: str | None = None
    audio_bit_rate: int | None = Field(default=None, ge=0)
    video_codec: str | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    fps: float | None = Field(default=None, gt=0)
    container_format: str | None = None
    has_audio: bool = False
    has_video: bool = False


class MediaExpectations(BaseModel):
    """Pass/fail criteria for :meth:`MediaEngine.validate_media` (PRD-001 §18).

    A ``None`` field is not checked. Duration/resolution tolerances keep the
    deterministic engine robust to codec rounding.
    """

    require_audio: bool = True
    require_video: bool = False
    min_duration: float | None = Field(default=None, ge=0)
    max_duration: float | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    fps: float | None = Field(default=None, gt=0)
    min_sample_rate: int | None = Field(default=None, gt=0)
    min_channels: int | None = Field(default=None, ge=1)
    audio_codec: str | None = None
    video_codec: str | None = None


class ValidationCheck(BaseModel):
    """One named check with its outcome."""

    name: str
    passed: bool
    expected: str | None = None
    actual: str | None = None


class MediaValidationResult(BaseModel):
    """Aggregate validation outcome; ``valid`` is true only when every check passes."""

    valid: bool
    checks: list[ValidationCheck]

    @property
    def failures(self) -> list[ValidationCheck]:
        return [check for check in self.checks if not check.passed]
