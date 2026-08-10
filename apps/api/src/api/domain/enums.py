"""Domain enums (MAD-001 §12-13, §65; PRD-001 §13; TDD-001 §8-11, §16-17).

Every enum is a ``str`` subclass so values serialize to stable, readable
strings (e.g. ``"generating_music"``) in JSON/database persistence.
"""
from __future__ import annotations

from enum import Enum


class ProductionMode(str, Enum):
    """How a production's creative direction is chosen (PRD-001 §4)."""

    GENRE = "genre"            # a fixed genre the user picks
    TRENDING = "trending"      # the system picks the trending genre


class ProductionStatus(str, Enum):
    """Full production state machine (MAD-001 §13, TDD-001 §10).

    Forward flow: CREATED -> PLANNING -> CONCEPT_READY -> GENERATING_MUSIC ->
    MUSIC_READY -> GENERATING_VISUAL -> VISUAL_READY -> ANALYZING_AUDIO ->
    RENDERING_MASTER -> MASTER_READY -> SELECTING_SHORT -> RENDERING_SHORT ->
    SHORT_READY -> GENERATING_METADATA -> QUALITY_CHECK -> COMPLETED.

    Any non-terminal stage may fail (-> FAILED, then retried) or be cancelled.
    """

    CREATED = "created"
    PLANNING = "planning"
    CONCEPT_READY = "concept_ready"
    GENERATING_MUSIC = "generating_music"
    MUSIC_READY = "music_ready"
    GENERATING_VISUAL = "generating_visual"
    VISUAL_READY = "visual_ready"
    ANALYZING_AUDIO = "analyzing_audio"
    RENDERING_MASTER = "rendering_master"
    MASTER_READY = "master_ready"
    SELECTING_SHORT = "selecting_short"
    RENDERING_SHORT = "rendering_short"
    SHORT_READY = "short_ready"
    GENERATING_METADATA = "generating_metadata"
    QUALITY_CHECK = "quality_check"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AssetType(str, Enum):
    """Kinds of artifacts a production produces/consumes (TDD-001 §17)."""

    AUDIO_SOURCE = "audio_source"        # generated/ downloaded source audio
    AUDIO_MASTER = "audio_master"        # post-processed long-form audio
    BACKGROUND = "background"            # generated background image
    RADIO = "radio"                      # the looping radio asset
    VISUALIZER_DATA = "visualizer_data"  # per-frame FFT band JSON
    MASTER_VIDEO = "master_video"        # long-form rendered master
    SHORT_VIDEO = "short_video"          # short-form rendered clip
    METADATA = "metadata"                # metadata.json package
    QC_REPORT = "qc_report"              # quality-control report
    MANIFEST = "manifest"                # production manifest


class AssetStatus(str, Enum):
    """Asset lifecycle (MAD-001 §65): REQUESTED -> GENERATING -> DOWNLOADING ->
    VALIDATING -> READY, any stage may fail (-> FAILED)."""

    REQUESTED = "requested"
    GENERATING = "generating"
    DOWNLOADING = "downloading"
    VALIDATING = "validating"
    READY = "ready"
    FAILED = "failed"
