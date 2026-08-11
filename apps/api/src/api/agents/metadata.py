"""Metadata Agent (MAD-001 §34; PRD-001 §68; TDD-001 §57-58).

Generates platform-ready metadata for the master and the short through the
registered ``llm_generate`` tool (MAD-001 §67 flow) and validates it into the
:class:`MetadataPackage` domain model. The prompt is built from the full
creative brief — CreativeConcept, MusicStrategy, VisualStrategy, Production
Context, Trend Context and the ShortSegment (TDD-001 §57) — so metadata
corresponds to the actual production (TDD-001 §58). Master and short are
optimized separately (long-form vs vertical; PRD-001 §32-33) but stay factually
consistent. Hashtags are derived deterministically from genre/mood/theme rather
than free-generated, which avoids keyword stuffing (PRD-001 §68.6) and keeps
the package structurally valid.
"""
from __future__ import annotations

import re
from typing import Any

from api.agents.tools import ToolRegistry
from api.capabilities import StructuredGenerationRequest
from api.core.errors import AgentError
from api.domain.agents import MetadataRequest
from api.domain.outputs import Metadata, MetadataPackage

_TITLE_DESCRIPTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "maxLength": 120},
        "description": {"type": "string"},
    },
    "required": ["title", "description"],
}

#: Max length of the final hashtag slug (mirrors Metadata._MAX_HASHTAG_LEN).
_MAX_HASHTAG_LEN = 30


class MetadataAgent:
    """Generates validated master + short metadata."""

    name = "metadata"
    version = "metadata_v1"
    description = "Generates platform-ready metadata for master and short."

    def __init__(self, tools: ToolRegistry) -> None:
        self._tools = tools

    async def execute(self, request: MetadataRequest) -> MetadataPackage:
        llm = self._tools.get("llm_generate")
        context = self._creative_context(request)
        base = (
            f"Write YouTube metadata for an instrumental {request.genre!r} music video "
            f"with a {request.mood!r} mood."
            + (f" {context}" if context else "")
            + (f" Branding: {request.branding}." if request.branding else "")
            + (f" Title hint: {request.title_hint}." if request.title_hint else "")
        )
        try:
            master = await self._generate_one(
                llm, "metadata_master",
                base + " Target: long-form master video. The title must be descriptive "
                "and natural, and the description must accurately describe the music "
                "and visual concept.",
            )
            short = await self._generate_one(
                llm, "metadata_short",
                base + self._short_segment_context(request)
                + " Target: vertical short-form clip. Optimize the title/description "
                "for short-form discovery, distinct from the master while remaining "
                "factually consistent with the production.",
            )
        except KeyError as exc:
            raise AgentError(f"LLM metadata output missing field: {exc}") from exc
        hashtags = self._hashtags(request.genre, request.mood, request.theme)
        return MetadataPackage(
            master=Metadata(title=master["title"], description=master["description"], hashtags=hashtags),
            short=Metadata(title=short["title"], description=short["description"], hashtags=hashtags),
        )

    @staticmethod
    def _creative_context(request: MetadataRequest) -> str:
        """Flatten the creative brief into prompt context (TDD-001 §57)."""
        parts: list[str] = []
        if request.theme:
            parts.append(f"Theme: {request.theme}.")
        if request.audience:
            parts.append(f"Target audience: {request.audience}.")
        if request.music_concept:
            parts.append(f"Music concept: {request.music_concept}.")
        if request.visual_concept:
            parts.append(f"Visual concept: {request.visual_concept}.")
        if request.trend_context:
            parts.append(f"Trend context: {request.trend_context}.")
        return " ".join(parts)

    @staticmethod
    def _short_segment_context(request: MetadataRequest) -> str:
        if request.short_segment is None:
            return ""
        segment = request.short_segment
        return (
            f" This short is the {segment.duration_seconds:g}s clip starting at "
            f"{segment.start_seconds:g}s of the master."
        )

    @staticmethod
    async def _generate_one(llm, task: str, prompt: str) -> dict[str, Any]:
        result = await llm.run(
            StructuredGenerationRequest(
                task=task,
                prompt=prompt,
                system_prompt="Return a JSON object with a non-empty title and description.",
                output_schema=_TITLE_DESCRIPTION_SCHEMA,
            )
        )
        try:
            title = str(result.data["title"]).strip()
            description = str(result.data["description"]).strip()
        except (KeyError, TypeError) as exc:
            raise AgentError(f"LLM produced invalid metadata: {result.data!r}") from exc
        if not title or not description:
            raise AgentError(f"LLM produced empty metadata: {result.data!r}")
        return {"title": title, "description": description}

    @classmethod
    def _hashtags(cls, *terms: str) -> list[str]:
        tags: list[str] = []
        for term in terms:
            slug = re.sub(r"[^a-z0-9]+", "", (term or "").lower())
            # Skip slugs that would overflow the domain's 30-char limit — a
            # theme that long is not a usable hashtag anyway.
            if not slug or len(slug) > _MAX_HASHTAG_LEN or slug in tags:
                continue
            tags.append(f"#{slug}")
        if not tags:
            tags.append("#instrumentalmusic")
        return tags
