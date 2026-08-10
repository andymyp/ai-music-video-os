"""Repository interfaces + SQLite implementations (TDD-001 §123).

Persistence is exposed through four interfaces — :class:`ProductionRepository`,
:class:`AssetRepository`, :class:`WorkflowRepository`,
:class:`ProviderRunRepository` — with concrete SQLite implementations. Each
repository is bound to a ``Session`` and never commits itself: the transaction
boundary is :func:`api.database.session.session_scope`. Methods convert between
the Phase01 domain objects and the ORM rows; ``workflow_runs`` / ``provider_runs``
map to the small value objects below since those domains arrive in later phases.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.clock import utc_naive, utc_now
from api.core.ids import new_ulid
from api.database.base import utc_aware
from api.database.models import (
    AssetRow,
    CreativeConceptRow,
    MusicStrategyRow,
    ProductionConfigRow,
    ProductionRow,
    ProviderRunRow,
    TrendResultRow,
    VisualStrategyRow,
    WorkflowRunRow,
)
from api.domain.assets import Asset
from api.domain.creative import CreativeConcept, MusicStrategy, TrendResult, VisualStrategy
from api.domain.production import Production, ProductionConfig


@dataclass
class WorkflowRun:
    """Value object for a workflow_runs row (full domain arrives in Phase 09)."""

    id: str
    production_id: str
    workflow_type: str
    task_queue: str
    status: str
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    attempts: int = 1
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_row(cls, row: WorkflowRunRow) -> "WorkflowRun":
        return cls(
            id=row.id,
            production_id=row.production_id,
            workflow_type=row.workflow_type,
            task_queue=row.task_queue,
            status=row.status,
            started_at=utc_aware(row.started_at) or utc_now(),
            completed_at=utc_aware(row.completed_at),
            attempts=row.attempts,
            error=row.error,
            created_at=utc_aware(row.created_at),
            updated_at=utc_aware(row.updated_at),
        )

    def apply_to(self, row: WorkflowRunRow) -> None:
        row.workflow_type = self.workflow_type
        row.task_queue = self.task_queue
        row.status = self.status
        row.started_at = utc_naive(self.started_at)
        row.completed_at = utc_naive(self.completed_at) if self.completed_at else None
        row.attempts = self.attempts
        row.error = self.error
        row.updated_at = utc_now()


@dataclass
class ProviderRun:
    """Value object for a provider_runs row (full domain arrives in Phase 04)."""

    id: str
    production_id: str
    capability: str
    provider: str
    status: str
    started_at: datetime = field(default_factory=utc_now)
    model: str | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: ProviderRunRow) -> "ProviderRun":
        return cls(
            id=row.id,
            production_id=row.production_id,
            capability=row.capability,
            provider=row.provider,
            model=row.model,
            status=row.status,
            started_at=utc_aware(row.started_at) or utc_now(),
            completed_at=utc_aware(row.completed_at),
            error_code=row.error_code,
            metadata=row.metadata_json,
            created_at=utc_aware(row.created_at),
        )

    def apply_to(self, row: ProviderRunRow) -> None:
        row.capability = self.capability
        row.provider = self.provider
        row.model = self.model
        row.status = self.status
        row.started_at = utc_naive(self.started_at)
        row.completed_at = utc_naive(self.completed_at) if self.completed_at else None
        row.error_code = self.error_code
        row.metadata_json = self.metadata


class ProductionRepository(ABC):
    """Repository for the Production aggregate and its one-to-one children."""

    @abstractmethod
    def create(self, production: Production) -> Production:
        """Persist a new production."""

    @abstractmethod
    def get(self, production_id: str) -> Production | None:
        """Return a production by id, or None."""

    @abstractmethod
    def list(self, *, limit: int = 50, offset: int = 0) -> list[Production]:
        """Return productions ordered by creation time (newest first)."""

    @abstractmethod
    def update(self, production: Production) -> Production:
        """Persist changes to an existing production (upsert if absent)."""

    @abstractmethod
    def delete(self, production_id: str) -> bool:
        """Delete a production and cascade its children. Returns whether a row was removed."""

    # --- one-to-one children (relationships) ------------------------------

    @abstractmethod
    def save_config(self, production_id: str, config: ProductionConfig) -> ProductionConfig:
        """Insert or update the production's configuration snapshot."""

    @abstractmethod
    def get_config(self, production_id: str) -> ProductionConfig | None:
        """Return the production's configuration snapshot, or None."""

    @abstractmethod
    def save_concept(self, production_id: str, concept: CreativeConcept) -> CreativeConcept:
        """Insert or update the production's creative concept."""

    @abstractmethod
    def get_concept(self, production_id: str) -> CreativeConcept | None:
        """Return the production's creative concept, or None."""

    @abstractmethod
    def save_music_strategy(self, production_id: str, strategy: MusicStrategy) -> MusicStrategy:
        """Insert or update the production's music strategy."""

    @abstractmethod
    def get_music_strategy(self, production_id: str) -> MusicStrategy | None:
        """Return the production's music strategy, or None."""

    @abstractmethod
    def save_visual_strategy(self, production_id: str, strategy: VisualStrategy) -> VisualStrategy:
        """Insert or update the production's visual strategy."""

    @abstractmethod
    def get_visual_strategy(self, production_id: str) -> VisualStrategy | None:
        """Return the production's visual strategy, or None."""

    @abstractmethod
    def save_trend_result(self, production_id: str, result: TrendResult) -> TrendResult:
        """Insert or update the production's trend result."""

    @abstractmethod
    def get_trend_result(self, production_id: str) -> TrendResult | None:
        """Return the production's trend result, or None."""


class AssetRepository(ABC):
    """Repository for assets (TDD-001 §16-17)."""

    @abstractmethod
    def create(self, asset: Asset) -> Asset: ...

    @abstractmethod
    def get(self, asset_id: str) -> Asset | None: ...

    @abstractmethod
    def list_for_production(self, production_id: str) -> list[Asset]: ...

    @abstractmethod
    def update(self, asset: Asset) -> Asset: ...

    @abstractmethod
    def delete(self, asset_id: str) -> bool: ...


class WorkflowRepository(ABC):
    """Repository for workflow runs (TDD-001 §18)."""

    @abstractmethod
    def create(self, run: WorkflowRun) -> WorkflowRun: ...

    @abstractmethod
    def get(self, run_id: str) -> WorkflowRun | None: ...

    @abstractmethod
    def list_for_production(self, production_id: str) -> list[WorkflowRun]: ...

    @abstractmethod
    def update(self, run: WorkflowRun) -> WorkflowRun: ...


class ProviderRunRepository(ABC):
    """Repository for provider runs (TDD-001 §21)."""

    @abstractmethod
    def create(self, run: ProviderRun) -> ProviderRun: ...

    @abstractmethod
    def get(self, run_id: str) -> ProviderRun | None: ...

    @abstractmethod
    def list_for_production(self, production_id: str) -> list[ProviderRun]: ...

    @abstractmethod
    def update(self, run: ProviderRun) -> ProviderRun: ...


class SQLiteProductionRepository(ProductionRepository):
    """SQLAlchemy implementation of :class:`ProductionRepository`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, production: Production) -> Production:
        self._session.add(ProductionRow.from_domain(production))
        self._session.flush()
        return production

    def get(self, production_id: str) -> Production | None:
        row = self._session.get(ProductionRow, production_id)
        return row.to_domain() if row else None

    def list(self, *, limit: int = 50, offset: int = 0) -> list[Production]:
        rows = self._session.scalars(
            select(ProductionRow).order_by(ProductionRow.created_at.desc(), ProductionRow.id).limit(limit).offset(offset)
        )
        return [row.to_domain() for row in rows]

    def update(self, production: Production) -> Production:
        row = self._session.get(ProductionRow, production.id)
        if row is None:
            row = ProductionRow.from_domain(production)
            self._session.add(row)
        else:
            row.update_from_domain(production)
        self._session.flush()
        return production

    def delete(self, production_id: str) -> bool:
        row = self._session.get(ProductionRow, production_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True

    # --- one-to-one children ----------------------------------------------

    def save_config(self, production_id: str, config: ProductionConfig) -> ProductionConfig:
        row = self._session.scalar(
            select(ProductionConfigRow).where(ProductionConfigRow.production_id == production_id)
        )
        if row is None:
            row = ProductionConfigRow.from_domain(production_id, config)
            self._session.add(row)
        else:
            row.update_from_domain(config)
        self._session.flush()
        return row.to_domain()

    def get_config(self, production_id: str) -> ProductionConfig | None:
        row = self._session.scalar(
            select(ProductionConfigRow).where(ProductionConfigRow.production_id == production_id)
        )
        return row.to_domain() if row else None

    def save_concept(self, production_id: str, concept: CreativeConcept) -> CreativeConcept:
        row = self._session.scalar(
            select(CreativeConceptRow).where(CreativeConceptRow.production_id == production_id)
        )
        if row is None:
            row = CreativeConceptRow.from_domain(production_id, concept)
            self._session.add(row)
        else:
            row.update_from_domain(concept)
        self._session.flush()
        return row.to_domain()

    def get_concept(self, production_id: str) -> CreativeConcept | None:
        row = self._session.scalar(
            select(CreativeConceptRow).where(CreativeConceptRow.production_id == production_id)
        )
        return row.to_domain() if row else None

    def save_music_strategy(self, production_id: str, strategy: MusicStrategy) -> MusicStrategy:
        row = self._session.scalar(
            select(MusicStrategyRow).where(MusicStrategyRow.production_id == production_id)
        )
        if row is None:
            row = MusicStrategyRow.from_domain(production_id, strategy)
            self._session.add(row)
        else:
            row.update_from_domain(strategy)
        self._session.flush()
        return row.to_domain()

    def get_music_strategy(self, production_id: str) -> MusicStrategy | None:
        row = self._session.scalar(
            select(MusicStrategyRow).where(MusicStrategyRow.production_id == production_id)
        )
        return row.to_domain() if row else None

    def save_visual_strategy(self, production_id: str, strategy: VisualStrategy) -> VisualStrategy:
        row = self._session.scalar(
            select(VisualStrategyRow).where(VisualStrategyRow.production_id == production_id)
        )
        if row is None:
            row = VisualStrategyRow.from_domain(production_id, strategy)
            self._session.add(row)
        else:
            row.update_from_domain(strategy)
        self._session.flush()
        return row.to_domain()

    def get_visual_strategy(self, production_id: str) -> VisualStrategy | None:
        row = self._session.scalar(
            select(VisualStrategyRow).where(VisualStrategyRow.production_id == production_id)
        )
        return row.to_domain() if row else None

    def save_trend_result(self, production_id: str, result: TrendResult) -> TrendResult:
        row = self._session.scalar(
            select(TrendResultRow).where(TrendResultRow.production_id == production_id)
        )
        if row is None:
            row = TrendResultRow.from_domain(production_id, result)
            self._session.add(row)
        else:
            row.update_from_domain(result)
        self._session.flush()
        return row.to_domain()

    def get_trend_result(self, production_id: str) -> TrendResult | None:
        row = self._session.scalar(
            select(TrendResultRow).where(TrendResultRow.production_id == production_id)
        )
        return row.to_domain() if row else None


class SQLiteAssetRepository(AssetRepository):
    """SQLAlchemy implementation of :class:`AssetRepository`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, asset: Asset) -> Asset:
        self._session.add(AssetRow.from_domain(asset))
        self._session.flush()
        return asset

    def get(self, asset_id: str) -> Asset | None:
        row = self._session.get(AssetRow, asset_id)
        return row.to_domain() if row else None

    def list_for_production(self, production_id: str) -> list[Asset]:
        rows = self._session.scalars(
            select(AssetRow)
            .where(AssetRow.production_id == production_id)
            .order_by(AssetRow.created_at, AssetRow.id)
        )
        return [row.to_domain() for row in rows]

    def update(self, asset: Asset) -> Asset:
        row = self._session.get(AssetRow, asset.id)
        if row is None:
            row = AssetRow.from_domain(asset)
            self._session.add(row)
        else:
            row.update_from_domain(asset)
        self._session.flush()
        return asset

    def delete(self, asset_id: str) -> bool:
        row = self._session.get(AssetRow, asset_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True


class SQLiteWorkflowRepository(WorkflowRepository):
    """SQLAlchemy implementation of :class:`WorkflowRepository`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, run: WorkflowRun) -> WorkflowRun:
        row = WorkflowRunRow(
            id=run.id,
            production_id=run.production_id,
            workflow_type=run.workflow_type,
            task_queue=run.task_queue,
            status=run.status,
            started_at=utc_naive(run.started_at),
            completed_at=utc_naive(run.completed_at) if run.completed_at else None,
            attempts=run.attempts,
            error=run.error,
        )
        self._session.add(row)
        self._session.flush()
        return WorkflowRun.from_row(row)

    def get(self, run_id: str) -> WorkflowRun | None:
        row = self._session.get(WorkflowRunRow, run_id)
        return WorkflowRun.from_row(row) if row else None

    def list_for_production(self, production_id: str) -> list[WorkflowRun]:
        rows = self._session.scalars(
            select(WorkflowRunRow)
            .where(WorkflowRunRow.production_id == production_id)
            .order_by(WorkflowRunRow.created_at, WorkflowRunRow.id)
        )
        return [WorkflowRun.from_row(row) for row in rows]

    def update(self, run: WorkflowRun) -> WorkflowRun:
        row = self._session.get(WorkflowRunRow, run.id)
        if row is None:
            raise KeyError(f"workflow run {run.id!r} does not exist")
        run.apply_to(row)
        self._session.flush()
        return WorkflowRun.from_row(row)


class SQLiteProviderRunRepository(ProviderRunRepository):
    """SQLAlchemy implementation of :class:`ProviderRunRepository`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, run: ProviderRun) -> ProviderRun:
        row = ProviderRunRow(
            id=run.id or f"pr_{new_ulid()}",
            production_id=run.production_id,
            capability=run.capability,
            provider=run.provider,
            model=run.model,
            status=run.status,
            started_at=utc_naive(run.started_at),
            completed_at=utc_naive(run.completed_at) if run.completed_at else None,
            error_code=run.error_code,
            metadata_json=run.metadata,
        )
        self._session.add(row)
        self._session.flush()
        return ProviderRun.from_row(row)

    def get(self, run_id: str) -> ProviderRun | None:
        row = self._session.get(ProviderRunRow, run_id)
        return ProviderRun.from_row(row) if row else None

    def list_for_production(self, production_id: str) -> list[ProviderRun]:
        rows = self._session.scalars(
            select(ProviderRunRow)
            .where(ProviderRunRow.production_id == production_id)
            .order_by(ProviderRunRow.created_at, ProviderRunRow.id)
        )
        return [ProviderRun.from_row(row) for row in rows]

    def update(self, run: ProviderRun) -> ProviderRun:
        row = self._session.get(ProviderRunRow, run.id)
        if row is None:
            raise KeyError(f"provider run {run.id!r} does not exist")
        run.apply_to(row)
        self._session.flush()
        return ProviderRun.from_row(row)


def make_production_repository(session: Session) -> ProductionRepository:
    """Concrete factory returning a SQLite production repository (TDD-001 §123)."""
    return SQLiteProductionRepository(session)


def make_asset_repository(session: Session) -> AssetRepository:
    return SQLiteAssetRepository(session)


def make_workflow_repository(session: Session) -> WorkflowRepository:
    return SQLiteWorkflowRepository(session)


def make_provider_run_repository(session: Session) -> ProviderRunRepository:
    return SQLiteProviderRunRepository(session)
