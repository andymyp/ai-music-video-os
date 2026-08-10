"""Agent contract and schema helper (TDD-001 §39, MAD-001 §33-34, §67).

Every agent is a :class:`Agent` with a typed input and typed output
(``async def execute(input) -> output``), a stable ``name`` and a ``version``
for the agent-versioning convention (MAD-001 §66: ``music_strategy_v1`` etc.).
Agents receive only a :class:`~api.agents.tools.ToolRegistry` and must route
every side effect through a registered tool (TDD-001 §93) — no filesystem,
shell, database or secret access.
"""
from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT", covariant=True)


@runtime_checkable
class Agent(Protocol[InputT, OutputT]):
    """Structural agent contract (TDD-001 §39)."""

    name: str
    version: str
    description: str

    async def execute(self, input: InputT) -> OutputT:
        """Run the agent on *input* and return the typed output."""
        ...


def generation_schema(
    model: type[BaseModel],
    **property_overrides: dict[str, Any],
) -> dict[str, Any]:
    """JSON Schema for structured generation (MAD-001 §67) from a Pydantic model.

    Fields defined with ``default_factory`` (e.g. ``bpm_range=[70, 85]``) are
    emitted as ``default``s, which the mock provider honours, so schema-shaped
    LLM output validates back into the model. ``property_overrides`` patch
    individual properties when the model needs extra constraints.
    """
    schema = model.model_json_schema()
    schema.pop("title", None)
    props = schema.setdefault("properties", {})
    for name, info in model.model_fields.items():
        if name not in props or "default" in props[name]:
            continue
        if info.default_factory is not None:
            try:
                props[name]["default"] = info.default_factory()
            except Exception:
                continue
    for name, patch in property_overrides.items():
        merged = dict(props.get(name, {}))
        merged.update(patch)
        props[name] = merged
    return schema
