"""Audio analysis and visualizer data (MAD-001 §23, TDD-001 §45-46).

``AudioAnalysis`` captures FFprobe/FFT output used for beat-matching and short
selection; ``VisualizerData`` holds the normalized per-frame frequency bands
that drive the deterministic visualizer render (MAD-001 §23: 5 band groups,
normalized 0-1 values, frame-aligned timestamps).
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

_DEFAULT_BAND_NAMES = ["bass", "low_mid", "mid", "high_mid", "high"]


class AudioSection(BaseModel):
    """A labelled span within the track."""

    start_seconds: float = Field(ge=0.0)
    end_seconds: float = Field(ge=0.0)
    label: str = ""

    @model_validator(mode="after")
    def _ordered(self) -> "AudioSection":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must not be before start_seconds")
        return self


class AudioAnalysis(BaseModel):
    """Analysis of the source/master audio (TDD-001 §45)."""

    duration_seconds: float = Field(gt=0.0)
    bpm: float | None = Field(default=None, gt=0.0, le=400.0)
    loudness_db: float | None = Field(default=None)
    energy_curve: list[float] = Field(default_factory=list)
    spectral_curve: list[float] = Field(default_factory=list)
    beats: list[float] = Field(default_factory=list)
    sections: list[AudioSection] = Field(default_factory=list)
    timestamps: list[float] = Field(default_factory=list)


class VisualizerData(BaseModel):
    """Normalized per-frame band data for the visualizer (MAD-001 §23)."""

    style: str = Field(default="bars", max_length=40)
    position: str = Field(default="radio-center", max_length=40)
    sensitivity: float = Field(default=0.8, ge=0.0, le=1.0)
    smoothing: float = Field(default=0.7, ge=0.0, le=1.0)
    fps: int = Field(default=30, ge=1, le=120)
    band_names: list[str] = Field(default_factory=lambda: list(_DEFAULT_BAND_NAMES))
    frames: list[list[float]] = Field(default_factory=list)
    timestamps: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self) -> "VisualizerData":
        if self.timestamps and len(self.frames) != len(self.timestamps):
            raise ValueError("frames and timestamps must have the same length")
        expected = len(self.band_names)
        for index, frame in enumerate(self.frames):
            if len(frame) != expected:
                raise ValueError(
                    f"frame {index} has {len(frame)} bands, expected {expected}"
                )
            for value in frame:
                if not 0.0 <= value <= 1.0:
                    raise ValueError(
                        f"frame {index} contains non-normalized value {value!r}"
                    )
        return self
