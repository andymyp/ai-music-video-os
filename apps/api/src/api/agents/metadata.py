"""Metadata Agent (MAD-001 §34; PRD-001 §68).

Generates platform-ready metadata for the master and the short through the
registered ``llm_generate`` tool (MAD-001 §67 flow) and validates it into the
:class:`MetadataPackage` domain model. Hashtags are derived deterministically
from genre/mood rather than free-generated, which avoids keyword stuffing
(PRD-001 §68.6) and keeps the package structurally valid.
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


class MetadataAgent:
    """Generates validated master + short metadata."""

    name = "metadata"
    version = "metadata_v1"
    description = "Generates platform-ready metadata for master and short."

    def __init__(self, tools: ToolRegistry) -> None:
        self._tools = tools

    async def execute(self, request: MetadataRequest) -> MetadataPackage:
        llm = self._tools.get("llm_generate")
        prompt = (
            f"Write YouTube metadata for an instrumental {request.genre!r} music video "
            f"with a {request.mood!r} mood."
            + (f" Branding: {request.branding}." if request.branding else "")
            + (f" Title hint: {request.title_hint}." if request.title_hint else "")
        )
        try:
            master = await self._generate_one(llm, "metadata_master", prompt + " Target: long-form master video.")
            short = await self._generate_one(llm, "metadata_short", prompt + " Target: vertical short clip.")
        except KeyError as exc:
            raise AgentError(f"LLM metadata output missing field: {exc}") from exc
        hashtags = self._hashtags(request.genre, request.mood)
        return MetadataPackage(
            master=Metadata(title=master["title"], description=master["description"], hashtags=hashtags),
            short=Metadata(title=short["title"], description=short["description"], hashtags=hashtags),
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

    @staticmethod
    def _hashtags(*terms: str) -> list[str]:
        tags: list[str] = []
        for term in terms:
            slug = re.sub(r"[^a-z0-9]+", "", (term or "").lower())
            if slug and slug not in tags:
                tags.append(f"#{slug}")
        if not tags:
            tags.append("#instrumentalmusic")
        return tags
