"""Radio asset registry (MAD-001 §22; TDD-001 §48; PRD-001 FR-017).

Radios are reusable assets: a style maps to one deterministic PNG that is
generated once under the shared assets root and reused across productions.
:meth:`RadioAssetRegistry.resolve` implements the MAD-001 §22 selection flow —
look up the style's asset file; if it exists reuse it, otherwise generate it
through the image capability and cache it. This reduces generation cost and
keeps visual identity consistent across a style (MAD-001 §22).
"""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from api.capabilities import ImageGenerationRequest, ImageProvider
from api.core.errors import WorkflowError
from api.storage.storage import StorageService
from api.visual.prompts import VisualPromptBuilder


class RadioAsset(BaseModel):
    """A resolved radio asset (generated or reused from the registry)."""

    style: str
    path: Path
    reused: bool = False
    data: bytes = Field(default_factory=bytes)


class RadioAssetRegistry:
    """Shared, style-keyed radio asset store (MAD-001 §22)."""

    RADIO_SUBDIR = "radios"

    def __init__(
        self,
        storage: StorageService,
        provider: ImageProvider,
        *,
        prompt_builder: VisualPromptBuilder | None = None,
        size: int = 1024,
    ) -> None:
        self._storage = storage
        self._provider = provider
        self._prompt_builder = prompt_builder or VisualPromptBuilder()
        self._size = size

    @staticmethod
    def slug(style: str) -> str:
        """Deterministic filesystem-safe slug for a radio style."""
        cleaned = re.sub(r"[^a-z0-9]+", "-", style.lower()).strip("-")
        return cleaned or "radio"

    def _rel_path(self, style: str) -> str:
        return f"{self.RADIO_SUBDIR}/{self.slug(style)}-radio.png"

    def path_for(self, style: str) -> Path:
        """Absolute path where the style's asset lives (or would be written)."""
        return self._storage.root / self._rel_path(style)

    async def resolve(self, style: str) -> RadioAsset:
        """Return the style's radio asset, generating it on first use.

        Same style across productions resolves to the same bytes and the same
        file, so ``reused=True`` identifies the cache-hit path (TDD-001 §48).
        """
        rel = self._rel_path(style)
        if self._storage.exists(rel):
            path = self._storage.root / rel
            return RadioAsset(style=style, path=path, reused=True, data=path.read_bytes())
        image = await self._provider.generate(
            ImageGenerationRequest(
                prompt=self._prompt_builder.radio_prompt(style),
                aspect_ratio="1:1",
                width=self._size,
                height=self._size,
                style_hints=["radio", "visualizer", style],
            )
        )
        if not image.image_bytes:
            raise WorkflowError(f"image provider returned no radio asset for style {style!r}")
        self._storage.write(rel, image.image_bytes)
        return RadioAsset(
            style=style,
            path=self._storage.root / rel,
            reused=False,
            data=image.image_bytes,
        )
