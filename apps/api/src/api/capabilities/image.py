"""Image generation capability contract (TDD-001 §31, MAD-001 §78).

Image provider adapters implement :class:`ImageProvider`. Aspect ratio is part
of the contract because the visual pipeline requires 16:9 (master background),
9:16 (short background) and a central radio composition (MAD-001 §78).
"""
from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator

AspectRatio = Literal["16:9", "9:16", "1:1", "4:3", "3:4"]


class ImageGenerationRequest(BaseModel):
    """A request to generate a background/visual image."""

    prompt: str
    aspect_ratio: AspectRatio = "16:9"
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    style_hints: list[str] = Field(default_factory=list)
    model: str | None = None

    @field_validator("prompt")
    @classmethod
    def _prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt must not be empty")
        return value


class GeneratedImage(BaseModel):
    """Image a provider produced, referenced inline or by download URL."""

    url: str | None = None
    image_bytes: bytes | None = None
    format: str = "png"
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    mime_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _has_source(self) -> "GeneratedImage":
        if self.url is None and self.image_bytes is None:
            raise ValueError("GeneratedImage must provide either url or image_bytes")
        return self


@runtime_checkable
class ImageProvider(Protocol):
    """A provider that generates images."""

    async def generate(
        self,
        request: ImageGenerationRequest,
    ) -> GeneratedImage:
        """Generate an image for *request* and return a retrievable result."""
        ...
