"""Deterministic visual prompt construction (MAD-001 §20-21; PRD-001 FR-015/016).

The visual pipeline derives its image prompts from the persisted
:class:`VisualStrategy` rather than from a generic genre template, so the
background matches the creative direction (theme, environment, lighting, style,
palette, color direction) and reserves central space for the radio (MAD-001
§20: "the visual strategy must reserve a suitable central area for the radio").

``prompt_hash`` provides the idempotency key used by ``generate_background``
(MAD-001 §3.5): if a valid background artifact produced by the same strategy
already exists, it is reused instead of regenerated.
"""
from __future__ import annotations

import hashlib
import json

from api.domain.creative import VisualStrategy


class VisualPromptBuilder:
    """Builds image prompts and idempotency hashes from a visual strategy."""

    def background_prompt(self, strategy: VisualStrategy, genre: str, mood: str) -> str:
        """16:9 background prompt carrying the strategy's creative fields."""
        palette = ", ".join(strategy.palette) if strategy.palette else "muted warm tones"
        return (
            f"{strategy.theme} {strategy.environment} scene, {strategy.lighting} lighting, "
            f"{strategy.style} style, {strategy.color_direction} color direction, "
            f"palette {palette}, 16:9 composition, no text, no logos, no watermark, "
            f"consistent lighting, central space reserved for a radio visualizer. "
            f"{genre} instrumental music video, {mood} mood."
        )

    def generic_background_prompt(self, genre: str, mood: str) -> str:
        """Fallback prompt when no strategy is persisted (deterministic stage)."""
        return (
            f"{genre} ambient background for an instrumental music video, {mood} mood, "
            f"16:9 composition, no text, no logos, central space reserved for a radio"
        )

    def radio_prompt(self, radio_style: str) -> str:
        """1:1 radio prompt keyed only by style (keeps the asset reusable).

        The prompt deliberately omits genre/mood: a style must map to the same
        asset across productions (MAD-001 §22 asset registry).
        """
        return (
            f"{radio_style} radio hosting a beat-reactive visualizer, "
            f"1:1 composition, no text, no logos"
        )

    def prompt_hash(self, strategy: VisualStrategy, *, salt: str = "background") -> str:
        """Deterministic SHA-256 idempotency key for a strategy (MAD-001 §3.5)."""
        payload = json.dumps(
            {
                "salt": salt,
                "theme": strategy.theme,
                "environment": strategy.environment,
                "lighting": strategy.lighting,
                "style": strategy.style,
                "color_direction": strategy.color_direction,
                "composition": strategy.composition,
                "visualizer_style": strategy.visualizer_style,
                "radio_style": strategy.radio_style,
                "palette": list(strategy.palette),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def hash_text(self, text: str) -> str:
        """SHA-256 of a prompt string (fallback idempotency key)."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
