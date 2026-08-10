"""Domain layer (TDD-001 §7-17, MAD-001 §12-13, §16-20, §23, §26, §30, §65, §82).

Public surface of the domain models so the rest of the backend imports from
``api.domain`` without reaching into submodules.
"""
from __future__ import annotations

from api.domain.assets import Asset
from api.domain.agents import (
    MetadataRequest,
    MusicStrategyRequest,
    OrchestratorDecision,
    OrchestratorRequest,
    QualityControlRequest,
    ShortSelectionRequest,
    TechnicalCheck,
    TrendResearchRequest,
    TrendResearchResult,
    VisualStrategyRequest,
)
from api.domain.audio import AudioAnalysis, AudioSection, VisualizerData
from api.domain.creative import CreativeConcept, MusicStrategy, TrendResult, VisualStrategy
from api.domain.enums import (
    AssetStatus,
    AssetType,
    ProductionMode,
    ProductionStatus,
)
from api.domain.outputs import Metadata, MetadataPackage, QualityDecision, ShortSegment
from api.domain.production import (
    PRODUCTION_TRANSITIONS,
    TERMINAL_STATUSES,
    BrandingConfig,
    Production,
    ProductionConfig,
)

__all__ = [
    # enums
    "ProductionMode",
    "ProductionStatus",
    "AssetType",
    "AssetStatus",
    # production
    "Production",
    "ProductionConfig",
    "BrandingConfig",
    "PRODUCTION_TRANSITIONS",
    "TERMINAL_STATUSES",
    # creative
    "CreativeConcept",
    "MusicStrategy",
    "VisualStrategy",
    "TrendResult",
    # assets & outputs
    "Asset",
    "Metadata",
    "MetadataPackage",
    "QualityDecision",
    "ShortSegment",
    # audio
    "AudioAnalysis",
    "AudioSection",
    "VisualizerData",
    # agents
    "TrendResearchRequest",
    "TrendResearchResult",
    "MusicStrategyRequest",
    "VisualStrategyRequest",
    "ShortSelectionRequest",
    "MetadataRequest",
    "TechnicalCheck",
    "QualityControlRequest",
    "OrchestratorRequest",
    "OrchestratorDecision",
]
