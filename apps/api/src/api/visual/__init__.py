"""Visual pipeline support (MASTER §23; MAD-001 §20-22; TDD-001 §47-48).

Prompt construction, deterministic image validation and the reusable radio
asset registry that back the Phase 13 visual pipeline stages (visual strategy,
background generation, radio resolution).
"""
from api.visual.prompts import VisualPromptBuilder
from api.visual.registry import RadioAsset, RadioAssetRegistry
from api.visual.validate import (
    ImageValidationResult,
    ImageValidator,
    aspect_ratio_label,
    png_dimensions,
)

__all__ = [
    "ImageValidationResult",
    "ImageValidator",
    "RadioAsset",
    "RadioAssetRegistry",
    "VisualPromptBuilder",
    "aspect_ratio_label",
    "png_dimensions",
]
