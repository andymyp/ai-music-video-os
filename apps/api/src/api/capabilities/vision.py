"""Vision capability contract (TDD-001 §33).

Vision providers analyze an image and return structured findings. Used where
visual AI analysis is required (e.g. QC on generated visuals/branding).
"""
from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator


class VisionRequest(BaseModel):
    """A request to analyze a single image."""

    image: bytes
    question: str
    detail: Literal["low", "high"] = "high"
    model: str | None = None

    @field_validator("image")
    @classmethod
    def _image(cls, value: bytes) -> bytes:
        if not value:
            raise ValueError("image must not be empty")
        return value

    @field_validator("question")
    @classmethod
    def _question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be empty")
        return value


class VisionResult(BaseModel):
    """Structured output of a vision analysis.

    ``findings`` holds schema-validated observations; ``summary`` is a short
    human/machine-readable conclusion. Consumers validate against their own
    schema per MAD-001 §67.
    """

    summary: str
    findings: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None


@runtime_checkable
class VisionProvider(Protocol):
    """A provider that analyzes images."""

    async def analyze(
        self,
        request: VisionRequest,
    ) -> VisionResult:
        """Answer *request.question* about *request.image*."""
        ...
