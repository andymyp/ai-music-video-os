"""SQLAlchemy ORM models (TDD-001 §18-21, MASTER_EXECUTION.md §12).

Twelve tables persisting application metadata; binary media stays on the
filesystem (MAD-001 §53, ADR-006). Enum values are stored as plain strings;
repositories convert between rows and the Phase01 domain objects.

Row models that map to a domain object expose ``to_domain`` (row -> domain)
and ``from_domain``/``update_from_domain`` (domain -> row) so the mapping stays
colocated with the schema. ``workflow_runs`` and ``provider_runs`` have no
domain counterpart yet (added in later phases) and are handled as rows.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.clock import utc_now
from api.core.ids import new_ulid
from api.database.base import Base, utc_aware, utc_naive
from api.domain.assets import Asset
from api.domain.creative import CreativeConcept, MusicStrategy, TrendResult, VisualStrategy
from api.domain.enums import AssetStatus, AssetType, ProductionMode, ProductionStatus
from api.domain.outputs import Metadata, QualityDecision
from api.domain.production import BrandingConfig, Production, ProductionConfig

_RUN_STATUS_LEN = 32


class ProductionRow(Base):
    """productions (TDD-001 §19)."""

    __tablename__ = "productions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    mode: Mapped[str] = mapped_column(String(16))
    genre: Mapped[str | None] = mapped_column(String(64))
    branding_text: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), index=True)
    target_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    config: Mapped["ProductionConfigRow | None"] = relationship(
        back_populates="production", uselist=False, cascade="all, delete-orphan"
    )
    concept: Mapped["CreativeConceptRow | None"] = relationship(
        back_populates="production", uselist=False, cascade="all, delete-orphan"
    )
    music_strategy: Mapped["MusicStrategyRow | None"] = relationship(
        back_populates="production", uselist=False, cascade="all, delete-orphan"
    )
    visual_strategy: Mapped["VisualStrategyRow | None"] = relationship(
        back_populates="production", uselist=False, cascade="all, delete-orphan"
    )
    trend_result: Mapped["TrendResultRow | None"] = relationship(
        back_populates="production", uselist=False, cascade="all, delete-orphan"
    )
    assets: Mapped[list["AssetRow"]] = relationship(
        back_populates="production", cascade="all, delete-orphan"
    )
    workflow_runs: Mapped[list["WorkflowRunRow"]] = relationship(
        back_populates="production", cascade="all, delete-orphan"
    )
    provider_runs: Mapped[list["ProviderRunRow"]] = relationship(
        back_populates="production", cascade="all, delete-orphan"
    )
    metadata_rows: Mapped[list["MetadataRow"]] = relationship(
        back_populates="production", cascade="all, delete-orphan"
    )
    qc_reports: Mapped[list["QcReportRow"]] = relationship(
        back_populates="production", cascade="all, delete-orphan"
    )
    events: Mapped[list["EventRow"]] = relationship(
        back_populates="production", cascade="all, delete-orphan"
    )

    # --- domain mapping ----------------------------------------------------

    def to_domain(self) -> Production:
        return Production(
            id=self.id,
            mode=ProductionMode(self.mode),
            genre=self.genre,
            branding_text=self.branding_text,
            status=ProductionStatus(self.status),
            target_duration_minutes=self.target_duration_minutes,
            created_at=utc_aware(self.created_at) or utc_now(),
            updated_at=utc_aware(self.updated_at) or utc_now(),
            completed_at=utc_aware(self.completed_at),
            version=self.version,
        )

    @classmethod
    def from_domain(cls, production: Production) -> "ProductionRow":
        return cls(
            id=production.id,
            mode=production.mode.value,
            genre=production.genre,
            branding_text=production.branding_text,
            status=production.status.value,
            target_duration_minutes=production.target_duration_minutes,
            created_at=utc_naive(production.created_at),
            updated_at=utc_naive(production.updated_at),
            completed_at=utc_naive(production.completed_at) if production.completed_at else None,
            version=production.version,
        )

    def update_from_domain(self, production: Production) -> None:
        self.mode = production.mode.value
        self.genre = production.genre
        self.branding_text = production.branding_text
        self.status = production.status.value
        self.target_duration_minutes = production.target_duration_minutes
        self.updated_at = utc_naive(production.updated_at)
        self.completed_at = utc_naive(production.completed_at) if production.completed_at else None
        self.version = production.version


class ProductionConfigRow(Base):
    """production_configs — one snapshot per production (TDD-001 §11)."""

    __tablename__ = "production_configs"
    __table_args__ = (UniqueConstraint("production_id", name="uq_production_configs_production_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    production_id: Mapped[str] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(16))
    genre: Mapped[str | None] = mapped_column(String(64))
    branding_text: Mapped[str] = mapped_column(String(80), default="")
    branding_position: Mapped[str] = mapped_column(String(32), default="bottom-right")
    branding_opacity: Mapped[float] = mapped_column(Float, default=0.65)
    branding_font_size: Mapped[int] = mapped_column(Integer, default=28)
    long_form_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    short_form_duration_seconds: Mapped[int] = mapped_column(Integer, default=45)
    master_width: Mapped[int] = mapped_column(Integer, default=1920)
    master_height: Mapped[int] = mapped_column(Integer, default=1080)
    fps: Mapped[int] = mapped_column(Integer, default=30)
    short_width: Mapped[int] = mapped_column(Integer, default=1080)
    short_height: Mapped[int] = mapped_column(Integer, default=1920)
    visualizer_style: Mapped[str] = mapped_column(String(40), default="bars")
    provider_profile: Mapped[str] = mapped_column(String(16), default="mock")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    production: Mapped[ProductionRow] = relationship(back_populates="config")

    # --- domain mapping ----------------------------------------------------

    def to_domain(self) -> ProductionConfig:
        return ProductionConfig(
            mode=ProductionMode(self.mode),
            genre=self.genre,
            branding=BrandingConfig(
                text=self.branding_text,
                position=self.branding_position,
                opacity=self.branding_opacity,
                font_size=self.branding_font_size,
            ),
            long_form_duration_minutes=self.long_form_duration_minutes,
            short_form_duration_seconds=self.short_form_duration_seconds,
            master_width=self.master_width,
            master_height=self.master_height,
            fps=self.fps,
            short_width=self.short_width,
            short_height=self.short_height,
            visualizer_style=self.visualizer_style,
            provider_profile=self.provider_profile,
        )

    @classmethod
    def from_domain(cls, production_id: str, config: ProductionConfig) -> "ProductionConfigRow":
        return cls(id=f"cfg_{new_ulid()}", production_id=production_id, **config.to_row_values())

    def update_from_domain(self, config: ProductionConfig) -> None:
        for key, value in config.to_row_values().items():
            setattr(self, key, value)


class CreativeConceptRow(Base):
    """creative_concepts — one concept per production (TDD-001 §12)."""

    __tablename__ = "creative_concepts"
    __table_args__ = (UniqueConstraint("production_id", name="uq_creative_concepts_production_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    production_id: Mapped[str] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    genre: Mapped[str] = mapped_column(String(64))
    mood: Mapped[str] = mapped_column(String(120))
    theme: Mapped[str] = mapped_column(String(120))
    audience: Mapped[str | None] = mapped_column(String(120), nullable=True)
    music_direction: Mapped[str] = mapped_column(Text)
    visual_direction: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    production: Mapped[ProductionRow] = relationship(back_populates="concept")

    def to_domain(self) -> CreativeConcept:
        return CreativeConcept(
            genre=self.genre,
            mood=self.mood,
            theme=self.theme,
            audience=self.audience,
            music_direction=self.music_direction,
            visual_direction=self.visual_direction,
        )

    @classmethod
    def from_domain(cls, production_id: str, concept: CreativeConcept) -> "CreativeConceptRow":
        return cls(id=f"con_{new_ulid()}", production_id=production_id, **concept.to_row_values())

    def update_from_domain(self, concept: CreativeConcept) -> None:
        for key, value in concept.to_row_values().items():
            setattr(self, key, value)


class MusicStrategyRow(Base):
    """music_strategies — one strategy per production (MAD-001 §17, TDD-001 §13)."""

    __tablename__ = "music_strategies"
    __table_args__ = (UniqueConstraint("production_id", name="uq_music_strategies_production_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    production_id: Mapped[str] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    genre: Mapped[str] = mapped_column(String(64))
    mood: Mapped[str] = mapped_column(String(120))
    bpm_min: Mapped[int] = mapped_column(Integer)
    bpm_max: Mapped[int] = mapped_column(Integer)
    key: Mapped[str] = mapped_column(String(32))
    structure: Mapped[str] = mapped_column(String(120))
    instruments: Mapped[list[str]] = mapped_column(JSON, default=list)
    duration_target_minutes: Mapped[int] = mapped_column(Integer, default=60)
    vocal_policy: Mapped[str] = mapped_column(String(16), default="none")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    production: Mapped[ProductionRow] = relationship(back_populates="music_strategy")

    def to_domain(self) -> MusicStrategy:
        return MusicStrategy(
            genre=self.genre,
            mood=self.mood,
            bpm_range=[self.bpm_min, self.bpm_max],
            key=self.key,
            structure=self.structure,
            instruments=self.instruments,
            duration_target_minutes=self.duration_target_minutes,
            vocal_policy=self.vocal_policy,
        )

    @classmethod
    def from_domain(cls, production_id: str, strategy: MusicStrategy) -> "MusicStrategyRow":
        return cls(id=f"mus_{new_ulid()}", production_id=production_id, **strategy.to_row_values())

    def update_from_domain(self, strategy: MusicStrategy) -> None:
        for key, value in strategy.to_row_values().items():
            setattr(self, key, value)


class VisualStrategyRow(Base):
    """visual_strategies — one strategy per production (MAD-001 §20, TDD-001 §14)."""

    __tablename__ = "visual_strategies"
    __table_args__ = (UniqueConstraint("production_id", name="uq_visual_strategies_production_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    production_id: Mapped[str] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    theme: Mapped[str] = mapped_column(String(120))
    environment: Mapped[str] = mapped_column(String(120))
    lighting: Mapped[str] = mapped_column(String(120))
    style: Mapped[str] = mapped_column(String(120))
    color_direction: Mapped[str] = mapped_column(String(120))
    radio_style: Mapped[str] = mapped_column(String(120))
    composition: Mapped[str] = mapped_column(Text)
    visualizer_style: Mapped[str] = mapped_column(String(40), default="bars")
    era: Mapped[str] = mapped_column(String(40), default="modern")
    palette: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    production: Mapped[ProductionRow] = relationship(back_populates="visual_strategy")

    def to_domain(self) -> VisualStrategy:
        return VisualStrategy(
            theme=self.theme,
            environment=self.environment,
            lighting=self.lighting,
            style=self.style,
            color_direction=self.color_direction,
            radio_style=self.radio_style,
            composition=self.composition,
            visualizer_style=self.visualizer_style,
            era=self.era,
            palette=self.palette,
        )

    @classmethod
    def from_domain(cls, production_id: str, strategy: VisualStrategy) -> "VisualStrategyRow":
        return cls(id=f"vis_{new_ulid()}", production_id=production_id, **strategy.to_row_values())

    def update_from_domain(self, strategy: VisualStrategy) -> None:
        for key, value in strategy.to_row_values().items():
            setattr(self, key, value)


class TrendResultRow(Base):
    """trend_results — one scored trend signal per production (MAD-001 §16, TDD-001 §15)."""

    __tablename__ = "trend_results"
    __table_args__ = (UniqueConstraint("production_id", name="uq_trend_results_production_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    production_id: Mapped[str] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(64))
    topic: Mapped[str] = mapped_column(String(120))
    genre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    recency: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    growth: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    cross_platform: Mapped[float | None] = mapped_column(Float, nullable=True)
    content_fit: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    production: Mapped[ProductionRow] = relationship(back_populates="trend_result")

    def to_domain(self) -> TrendResult:
        return TrendResult(
            source=self.source,
            topic=self.topic,
            genre=self.genre,
            score=self.score,
            confidence=self.confidence,
            recency=utc_aware(self.recency) or utc_now(),
            evidence=self.evidence,
            growth=self.growth,
            volume=self.volume,
            cross_platform=self.cross_platform,
            content_fit=self.content_fit,
            reasoning=self.reasoning,
        )

    @classmethod
    def from_domain(cls, production_id: str, result: TrendResult) -> "TrendResultRow":
        return cls(id=f"tre_{new_ulid()}", production_id=production_id, **result.to_row_values())

    def update_from_domain(self, result: TrendResult) -> None:
        for key, value in result.to_row_values().items():
            setattr(self, key, value)


class AssetRow(Base):
    """assets (TDD-001 §20). Paths point at the filesystem; SQLite only stores
    metadata (MAD-001 §53)."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    production_id: Mapped[str] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(32), index=True)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    production: Mapped[ProductionRow] = relationship(back_populates="assets")

    def to_domain(self) -> Asset:
        return Asset(
            id=self.id,
            production_id=self.production_id,
            type=AssetType(self.type),
            path=self.path,
            mime_type=self.mime_type,
            size_bytes=self.size_bytes,
            sha256=self.sha256,
            provider=self.provider,
            status=AssetStatus(self.status),
            created_at=utc_aware(self.created_at) or utc_now(),
            metadata=self.metadata_json,
        )

    @classmethod
    def from_domain(cls, asset: Asset) -> "AssetRow":
        return cls(
            id=asset.id,
            production_id=asset.production_id,
            type=asset.type.value,
            path=asset.path,
            mime_type=asset.mime_type,
            size_bytes=asset.size_bytes,
            sha256=asset.sha256,
            provider=asset.provider,
            status=asset.status.value,
            created_at=utc_naive(asset.created_at),
            metadata_json=asset.metadata,
        )

    def update_from_domain(self, asset: Asset) -> None:
        self.type = asset.type.value
        self.path = asset.path
        self.mime_type = asset.mime_type
        self.size_bytes = asset.size_bytes
        self.sha256 = asset.sha256
        self.provider = asset.provider
        self.status = asset.status.value
        self.metadata_json = asset.metadata


class WorkflowRunRow(Base):
    """workflow_runs — one row per Temporal workflow execution (TDD-001 §18)."""

    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # Temporal workflow id
    production_id: Mapped[str] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    workflow_type: Mapped[str] = mapped_column(String(64))
    task_queue: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(_RUN_STATUS_LEN), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    production: Mapped[ProductionRow] = relationship(back_populates="workflow_runs")


class ProviderRunRow(Base):
    """provider_runs — traces provider usage per capability (TDD-001 §21)."""

    __tablename__ = "provider_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    production_id: Mapped[str] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    capability: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(_RUN_STATUS_LEN), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    production: Mapped[ProductionRow] = relationship(back_populates="provider_runs")


class MetadataRow(Base):
    """metadata — one row per deliverable (master/short) (MAD-001 §82)."""

    __tablename__ = "metadata"
    __table_args__ = (UniqueConstraint("production_id", "kind", name="uq_metadata_production_kind"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    production_id: Mapped[str] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))  # "master" | "short"
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    production: Mapped[ProductionRow] = relationship(back_populates="metadata_rows")

    def to_domain(self) -> Metadata:
        return Metadata(title=self.title, description=self.description, hashtags=self.hashtags)

    @classmethod
    def from_domain(cls, production_id: str, kind: str, metadata: Metadata) -> "MetadataRow":
        return cls(
            id=f"met_{new_ulid()}",
            production_id=production_id,
            kind=kind,
            **metadata.to_row_values(),
        )

    def update_from_domain(self, metadata: Metadata) -> None:
        for key, value in metadata.to_row_values().items():
            setattr(self, key, value)


class QcReportRow(Base):
    """qc_reports — quality-control result per deliverable stage (TDD-001 §131)."""

    __tablename__ = "qc_reports"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    production_id: Mapped[str] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32))  # "master" | "short" | "metadata"
    passed: Mapped[bool] = mapped_column(Boolean)
    issues: Mapped[list[str]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    production: Mapped[ProductionRow] = relationship(back_populates="qc_reports")

    def to_domain(self) -> QualityDecision:
        return QualityDecision(
            passed=self.passed, issues=self.issues, warnings=self.warnings, score=self.score
        )

    @classmethod
    def from_domain(cls, production_id: str, stage: str, decision: QualityDecision) -> "QcReportRow":
        return cls(
            id=f"qc_{new_ulid()}",
            production_id=production_id,
            stage=stage,
            **decision.to_row_values(),
        )

    def update_from_domain(self, decision: QualityDecision) -> None:
        for key, value in decision.to_row_values().items():
            setattr(self, key, value)


class EventRow(Base):
    """events — domain/audit events keyed to a production."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    production_id: Mapped[str] = mapped_column(
        ForeignKey("productions.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    production: Mapped[ProductionRow] = relationship(back_populates="events")
