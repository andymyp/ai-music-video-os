"""Activity services container (TDD-001 §24, §123).

Activities are stateless; every external call — database, provider, storage —
goes through :class:`WorkflowServices`, which owns the session factory, the
provider registry and the agent runtime. The Temporal worker builds one
container at startup and hands it to the ``@activity.defn`` wrappers via
:func:`set_activity_services`; tests construct the same container directly (or
with an isolated in-memory session factory) and exercise the same methods.
"""
from __future__ import annotations

import asyncio
import shutil
from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import sessionmaker

from api.activities.models import AgentStep, AgentStepResult, WorkflowRunRecord
from api.agents.runtime import AgentRuntime, build_agent_runtime
from api.capabilities import Capability, InMemoryProviderRegistry, ProviderRegistry
from api.config.settings import AppSettings, get_settings
from api.core.errors import ConfigurationError, WorkflowError
from api.database import (
    create_session_factory,
    make_production_repository,
    make_workflow_repository,
    session_scope,
)
from api.domain.agents import (
    MetadataRequest,
    MusicStrategyRequest,
    QualityControlRequest,
    ShortSelectionRequest,
    TrendResearchRequest,
    VisualStrategyRequest,
)
from api.domain.enums import ProductionMode, ProductionStatus
from api.domain.production import Production, ProductionConfig, next_status_in_flow
from api.providers import register_mock_providers

#: Minimum free disk space required before generation starts (TDD-001 §25).
MIN_DISK_FREE_BYTES = 100 * 1024 * 1024  # 100 MiB

#: Capabilities every production run needs to be viable (TDD-001 §25).
REQUIRED_CAPABILITIES: tuple[Capability, ...] = (
    Capability.LLM,
    Capability.MUSIC,
    Capability.IMAGE,
    Capability.TREND,
)


def build_provider_registry(settings: AppSettings) -> ProviderRegistry:
    """Build the development/test provider registry (mock mode) from settings."""
    registry: ProviderRegistry = InMemoryProviderRegistry()
    if settings.provider_mode == "mock":
        register_mock_providers(registry)
    return registry


class WorkflowServices:
    """Owning container for all activity side effects."""

    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        session_factory: sessionmaker[Any] | None = None,
        provider_registry: ProviderRegistry | None = None,
        agent_runtime: AgentRuntime | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._session_factory = session_factory or create_session_factory(self.settings)
        if provider_registry is None and agent_runtime is None:
            provider_registry = build_provider_registry(self.settings)
        self.provider_registry = provider_registry
        self.agent_runtime = agent_runtime or (
            build_agent_runtime(provider_registry) if provider_registry is not None else None
        )

    # --- database (each public method opens its own transactional scope) ----

    def get_production(self, production_id: str) -> Production:
        with session_scope(self._session_factory) as session:
            production = make_production_repository(session).get(production_id)
        if production is None:
            raise WorkflowError(f"production {production_id!r} not found")
        return production

    def get_production_config(self, production_id: str) -> ProductionConfig | None:
        with session_scope(self._session_factory) as session:
            config = make_production_repository(session).get_config(production_id)
        return config

    def get_production_status(self, production_id: str) -> ProductionStatus:
        return self.get_production(production_id).status

    def advance_production_status(self, production_id: str) -> ProductionStatus:
        """Transition the production one forward step and persist it."""
        with session_scope(self._session_factory) as session:
            repo = make_production_repository(session)
            production = repo.get(production_id)
            if production is None:
                raise WorkflowError(f"production {production_id!r} not found")
            target = next_status_in_flow(production.status)
            production.transition_to(target)
            repo.update(production)
        return target

    def save_music_strategy(self, production_id: str, strategy) -> None:
        with session_scope(self._session_factory) as session:
            make_production_repository(session).save_music_strategy(production_id, strategy)

    def save_visual_strategy(self, production_id: str, strategy) -> None:
        with session_scope(self._session_factory) as session:
            make_production_repository(session).save_visual_strategy(production_id, strategy)

    def save_trend_result(self, production_id: str, result) -> None:
        with session_scope(self._session_factory) as session:
            make_production_repository(session).save_trend_result(production_id, result)

    def get_workflow_run(self, workflow_id: str):
        with session_scope(self._session_factory) as session:
            return make_workflow_repository(session).get(workflow_id)

    def upsert_workflow_run(self, record: WorkflowRunRecord) -> None:
        from api.core.clock import utc_now
        from api.database import WorkflowRun

        completed_at = utc_now() if record.status == "completed" else None
        with session_scope(self._session_factory) as session:
            repo = make_workflow_repository(session)
            existing = repo.get(record.workflow_id)
            run = WorkflowRun(
                id=record.workflow_id,
                production_id=record.production_id,
                workflow_type=record.workflow_type,
                task_queue=record.task_queue,
                status=record.status,
                completed_at=completed_at,
                attempts=record.attempt,
                error=record.error,
            )
            if existing is None:
                repo.create(run)
            else:
                repo.update(run)

    # --- provider / disk availability (TDD-001 §25) --------------------------

    def provider_availability(self) -> dict[str, bool]:
        if self.provider_registry is None:
            raise ConfigurationError("provider registry is not configured")
        return {
            capability.value: self.provider_registry.available(capability)
            for capability in REQUIRED_CAPABILITIES
        }

    def disk_free_bytes(self) -> int:
        try:
            root = self.settings.app_data_dir
            root.mkdir(parents=True, exist_ok=True)
            usage = shutil.disk_usage(root)
        except OSError:
            return 0
        return usage.free

    # --- agent execution (external provider call) ----------------------------

    async def run_agent_step(self, step: AgentStep) -> AgentStepResult:
        """Run the orchestrator-decided agent with a deterministic request."""
        if self.agent_runtime is None:
            raise ConfigurationError("agent runtime is not configured")
        if step.agent not in self.agent_runtime.agent_names():
            raise WorkflowError(f"unknown agent {step.agent!r}")
        production = await asyncio.to_thread(self.get_production, step.production_id)
        config = await asyncio.to_thread(self.get_production_config, step.production_id)
        request = build_agent_request(step.agent, production, config)
        result = await self.agent_runtime.run(step.agent, request)

        # Persist strategy/trend outputs that later stages consume; media asset
        # persistence is owned by the music/visual pipeline phases.
        if step.agent == "trend_research" and getattr(result, "recommendations", None):
            top = result.recommendations[0]
            await asyncio.to_thread(self.save_trend_result, production.id, top)
        elif step.agent == "music_strategy":
            await asyncio.to_thread(self.save_music_strategy, production.id, result)
        elif step.agent == "visual_strategy":
            await asyncio.to_thread(self.save_visual_strategy, production.id, result)

        return AgentStepResult(
            production_id=production.id,
            agent=step.agent,
            ok=True,
            summary=stage_summary(step.agent, result),
        )


# --- deterministic request derivation -----------------------------------------

def _mood(production: Production) -> str:
    """Deterministic placeholder mood until the creative-direction step lands.

    Phase 10 resolves a real CreativeConcept; until then the mood is derived
    from the genre so mock providers stay deterministic and valid.
    """
    return f"{production.genre or 'instrumental'} atmosphere"


def build_agent_request(agent: str, production: Production, config: ProductionConfig | None):
    """Build the typed agent input for *agent* from persisted production state.

    Deterministic: identical production state yields identical requests, which
    keeps workflow replay stable (TDD-001 §23).
    """
    genre = production.genre or "instrumental"
    mood = _mood(production)
    config = config or ProductionConfig(mode=production.mode, genre=production.genre)

    if agent == "trend_research":
        return TrendResearchRequest(genre_hint=production.genre)
    if agent == "music_strategy":
        return MusicStrategyRequest(
            genre=genre,
            mood=mood,
            duration_target_minutes=config.long_form_duration_minutes,
        )
    if agent == "music_generation":
        return _music_generation_request(genre, mood, config)
    if agent == "visual_strategy":
        return VisualStrategyRequest(genre=genre, mood=mood)
    if agent == "visual_generation":
        return _visual_generation_request(genre, config)
    if agent == "short_selection":
        return ShortSelectionRequest(
            audio_path=str(_audio_path(production.id)),
            target_duration_seconds=float(config.short_form_duration_seconds),
            min_duration_seconds=20.0,
            max_duration_seconds=60.0,
        )
    if agent == "metadata":
        return MetadataRequest(
            genre=genre,
            mood=mood,
            branding=production.branding_text,
        )
    if agent == "quality_control":
        return QualityControlRequest(
            production_id=production.id,
            creative_context=f"{genre} {mood} production",
            technical_checks=[],
            mandatory_checks=[],
        )
    raise WorkflowError(f"no input builder for agent {agent!r}")


def _music_generation_request(genre: str, mood: str, config: ProductionConfig):
    from api.capabilities import MusicGenerationRequest

    return MusicGenerationRequest(
        prompt=f"instrumental {genre} track, {mood}",
        genre=genre,
        duration_seconds=max(config.short_form_duration_seconds, 30),
        style_hints=[mood],
    )


def _visual_generation_request(genre: str, config: ProductionConfig):
    from api.capabilities import ImageGenerationRequest

    return ImageGenerationRequest(
        prompt=f"{genre} ambient background for a music video",
        aspect_ratio="16:9",
        style_hints=["ambient", genre],
    )


def _audio_path(production_id: str) -> str:
    from api.config.settings import get_settings
    from api.core.paths import find_project_root

    return str(
        get_settings().app_data_dir
        / "productions"
        / production_id
        / "assets"
        / "audio"
        / "master.wav"
    )


def stage_summary(agent: str, result: Any) -> str:
    """Short human-readable summary of an agent stage result."""
    if agent == "trend_research":
        return f"selected genre {getattr(result, 'selected_genre', '?')!r}"
    if agent == "music_strategy":
        return f"genre {getattr(result, 'genre', '?')} / bpm {getattr(result, 'bpm_range', '?')}"
    if agent == "visual_strategy":
        return f"theme {getattr(result, 'theme', '?')!r}"
    return getattr(result, "reasoning", "") or getattr(result, "summary", "") or "ok"
