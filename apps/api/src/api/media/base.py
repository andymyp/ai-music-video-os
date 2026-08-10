"""MediaEngine — deterministic media-processing abstraction (TDD-001 §124).

AI never performs technical media operations (TDD-001 §2.4); every render,
probe, validation and extraction goes through this interface. Implementations
(such as :class:`~api.media.ffmpeg.FFmpegMediaEngine`) must be deterministic and
must never be bypassed by the workflow layers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from api.media.models import (
    MASTER_PROFILE,
    SHORT_PROFILE,
    MediaExpectations,
    MediaProbe,
    MediaValidationResult,
    RenderProfile,
    RenderRequest,
)


@runtime_checkable
class MediaEngine(Protocol):
    """Deterministic media-processing abstraction (TDD-001 §124, MASTER §16)."""

    async def render_master(
        self,
        request: RenderRequest,
        profile: RenderProfile = MASTER_PROFILE,
    ) -> Path:
        """Render the 16:9 master video (MAD-001 §24) to ``request.output_path``."""

    async def render_short(
        self,
        request: RenderRequest,
        profile: RenderProfile = SHORT_PROFILE,
    ) -> Path:
        """Render the vertical 9:16 short (MAD-001 §25) to ``request.output_path``."""

    async def analyze_audio(self, path: Path) -> MediaProbe:
        """Return the structural probe (duration, sample rate, channels, codecs)."""

    async def validate_media(
        self,
        path: Path,
        *,
        expectations: MediaExpectations | None = None,
    ) -> MediaValidationResult:
        """Validate *path* against *expectations* (PRD-001 §18)."""

    async def extract_audio(self, source: Path, output_path: Path) -> Path:
        """Extract the audio track of *source* to *output_path* (e.g. a WAV)."""

    async def extract_segment(
        self,
        source: Path,
        output_path: Path,
        start: float,
        duration: float | None = None,
    ) -> Path:
        """Extract a clip starting at *start* (TDD-001 §129)."""
