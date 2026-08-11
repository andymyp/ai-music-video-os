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
from api.domain.production import ProductionConfig


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


class VisualizerInput(BaseModel):
    """Per-frame visualizer sprites composited over the render (MAD-001 §23).

    ``frames_dir`` holds one ``%05d.png`` bar sprite per visualizer frame,
    rendered at ``fps``; FFmpeg reads them as a time-aligned video stream
    positioned/scaled to ``region_*`` (TDD-001 §52). ``duration_seconds`` bounds
    the overlay with ``enable=between(t,0,D)`` so sprites never leak past the
    audio.
    """

    frames_dir: Path
    fps: int = Field(default=30, gt=0)
    region_x: int = Field(default=0, ge=0)
    region_y: int = Field(default=0, ge=0)
    region_width: int = Field(default=0, gt=0)
    region_height: int = Field(default=0, gt=0)
    duration_seconds: float | None = Field(default=None, gt=0)


class RenderRequest(BaseModel):
    """Inputs for one deterministic render (MAD-001 §24, §27).

    ``background`` and ``audio`` are required; ``overlays`` (radio), a
    ``visualizer`` sprite stream, and ``branding_text`` are composited on top
    (TDD-001 §49-53). For short renders, ``segment`` trims the audio to the
    selected clip (TDD-001 §129).
    """

    background: Path
    audio: Path
    overlays: list[OverlaySpec] = Field(default_factory=list)
    visualizer: VisualizerInput | None = None
    branding_text: str | None = None
    branding_font: Path | None = None
    branding_x: int = 0
    branding_y: int = 0
    branding_size: int = Field(default=48, gt=0)
    branding_opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    branding_align: str = "left"
    output_path: Path
    segment: ShortSegment | None = None

    @field_validator("branding_align")
    @classmethod
    def _align(cls, value: str) -> str:
        if value not in ("left", "center"):
            raise ValueError("branding_align must be 'left' or 'center'")
        return value


def master_render_profile(
    config: ProductionConfig | None,
    base: RenderProfile = MASTER_PROFILE,
) -> RenderProfile:
    """Render profile honoring a production's configured master size/FPS.

    The encoding defaults (codec, crf, pixel format) stay externalized through
    ``base`` (MAD-001 §56); only the resolution/FPS the user configured on the
    production are applied (PRD-001 §27 long-form configurability).
    """
    if config is None:
        return base
    return base.model_copy(
        update={
            "name": base.name,
            "width": config.master_width,
            "height": config.master_height,
            "fps": config.fps,
        }
    )


def short_render_profile(
    config: ProductionConfig | None,
    base: RenderProfile = SHORT_PROFILE,
) -> RenderProfile:
    """Render profile honoring a production's configured short size/FPS.

    Mirrors :func:`master_render_profile` for the vertical output
    (TDD-001 §127 ``ShortRenderProfile``).
    """
    if config is None:
        return base
    return base.model_copy(
        update={
            "name": base.name,
            "width": config.short_width,
            "height": config.short_height,
            "fps": config.fps,
        }
    )


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
