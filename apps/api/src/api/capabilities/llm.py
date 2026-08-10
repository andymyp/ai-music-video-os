"""LLM capability contract (TDD-001 §32, MAD-001 §67).

Every LLM provider adapter implements :class:`LLMProvider`. Agents request
structured output only — MAD-001 §67 mandates the flow ``LLM → JSON Schema →
Pydantic validation → domain object``, so the interface takes an ``output_schema``
and returns parsed, schema-validated data rather than free text.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator


class StructuredGenerationRequest(BaseModel):
    """A request for schema-validated text generation (MAD-001 §67)."""

    task: str
    prompt: str
    system_prompt: str | None = None
    output_schema: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)

    @field_validator("prompt")
    @classmethod
    def _prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt must not be empty")
        return value


class StructuredResult(BaseModel):
    """Schema-validated structured output from an LLM provider.

    ``data`` holds the validated fields; ``raw`` keeps the provider's original
    text for debugging/repair (MAD-001 §67: invalid responses trigger controlled
    repair/retry, so the raw payload must survive).
    """

    data: dict[str, Any]
    model: str | None = None
    raw: str | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """A provider that returns structured, schema-validated text."""

    async def generate_structured(
        self,
        request: StructuredGenerationRequest,
    ) -> StructuredResult:
        """Generate text conforming to ``request.output_schema``."""
        ...
