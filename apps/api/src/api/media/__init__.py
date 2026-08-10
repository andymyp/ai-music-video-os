"""Deterministic media-processing abstraction (MAD-001 §24-27, §56; TDD-001 §124-125).

The workflow layers interact with media only through :class:`MediaEngine`; the
default implementation is the FFmpeg-backed :class:`FFmpegMediaEngine` with
structured, shell-free argument arrays (TDD-001 §92).
"""
from __future__ import annotations

from api.media.audio import AudioAnalysisEngine
from api.media.base import MediaEngine
from api.media.ffmpeg import (
    FFmpegMediaEngine,
    _run_process,
    build_render_args,
    probe_to_model,
    run_validation_checks,
)
from api.media.mastering import AudioMasteringEngine, AudioMasterReport
from api.media.models import (
    MASTER_PROFILE,
    SHORT_PROFILE,
    MediaExpectations,
    MediaProbe,
    MediaValidationResult,
    OverlaySpec,
    RenderProfile,
    RenderRequest,
    ValidationCheck,
)

__all__ = [
    "MediaEngine",
    "FFmpegMediaEngine",
    "AudioAnalysisEngine",
    "AudioMasteringEngine",
    "AudioMasterReport",
    "build_render_args",
    "probe_to_model",
    "run_validation_checks",
    "_run_process",
    "RenderProfile",
    "MASTER_PROFILE",
    "SHORT_PROFILE",
    "RenderRequest",
    "OverlaySpec",
    "MediaProbe",
    "MediaExpectations",
    "MediaValidationResult",
    "ValidationCheck",
]
