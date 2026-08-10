"""Deterministic image validation (TDD-001 §47; PRD-001 FR-016).

The background step validates the generated PNG *before* committing it as the
background asset: PNG signature, readability (IHDR parse), aspect ratio and
minimum resolution. Pure stdlib — no FFmpeg needed for the PNG contract. The
identity checks the spec lists (no text/logos/watermark, coherent composition)
are enforced by the prompt contract and a vision provider in later phases; this
validator guards the structural properties that make a frame renderable.
"""
from __future__ import annotations

import math
import struct

from pydantic import BaseModel, Field

from api.media.models import ValidationCheck

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ImageValidationResult(BaseModel):
    """Aggregate image validation outcome; ``valid`` only when every check passes."""

    valid: bool
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    checks: list[ValidationCheck] = Field(default_factory=list)

    @property
    def failures(self) -> list[ValidationCheck]:
        return [check for check in self.checks if not check.passed]


def png_dimensions(data: bytes) -> tuple[int, int]:
    """Return (width, height) from a PNG header, raising ValueError if invalid."""
    if len(data) < 24 or data[:8] != _PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise ValueError("not a valid PNG")
    width, height = struct.unpack(">II", data[16:24])
    if width == 0 or height == 0:
        raise ValueError("PNG has a zero dimension")
    return width, height


def aspect_ratio_label(width: int, height: int) -> str:
    """Simplified W:H ratio label (e.g. 1280x720 -> '16:9')."""
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


class ImageValidator:
    """Checks structural image properties against expectations."""

    def validate(
        self,
        data: bytes,
        *,
        expected_aspect: str = "16:9",
        min_width: int = 1280,
        min_height: int = 720,
    ) -> ImageValidationResult:
        checks: list[ValidationCheck] = []
        try:
            width, height = png_dimensions(data)
        except ValueError as exc:
            return ImageValidationResult(
                valid=False,
                checks=[ValidationCheck(name="readable", passed=False, actual=str(exc))],
            )
        actual_aspect = aspect_ratio_label(width, height)
        checks.append(
            ValidationCheck(name="signature", passed=True, expected="PNG", actual="PNG")
        )
        checks.append(
            ValidationCheck(
                name="aspect_ratio",
                passed=actual_aspect == expected_aspect,
                expected=expected_aspect,
                actual=actual_aspect,
            )
        )
        checks.append(
            ValidationCheck(
                name="resolution_min",
                passed=width >= min_width and height >= min_height,
                expected=f"{min_width}x{min_height}",
                actual=f"{width}x{height}",
            )
        )
        return ImageValidationResult(
            valid=all(check.passed for check in checks),
            width=width,
            height=height,
            checks=checks,
        )
