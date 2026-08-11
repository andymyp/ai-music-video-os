"""Production HTTP API (MASTER §29; MAD-001 §45; TDD-001 §68-72).

The seven required endpoints:

    POST /api/productions
    GET  /api/productions
    GET  /api/productions/{id}
    POST /api/productions/{id}/retry
    POST /api/productions/{id}/cancel
    GET  /api/productions/{id}/progress
    GET  /api/productions/{id}/artifacts

plus a safe per-artifact download route so the frontend can actually fetch the
generated files (MASTER §33; TDD-001 §72: never expose arbitrary filesystem
paths). Every route validates/persists through the injected session factory and
hands long-running execution to the injected :class:`ProductionRunner` — the
API never performs pipeline work itself (MAD-001 §45).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from api.config.settings import AppSettings
from api.core.errors import AppError
from api.core.ids import PRODUCTION_ID_PATTERN
from api.database import (
    WorkflowRun,
    make_production_repository,
    make_workflow_repository,
    session_scope,
)
from api.domain.enums import ProductionStatus
from api.domain.production import (
    TERMINAL_STATUSES,
    _PRODUCTION_FLOW,
    BrandingConfig,
    Production,
    ProductionConfig,
)
from api.routes.deps import get_artifact_service, get_runner, get_session_factory, get_settings
from api.routes.runner import ProductionRunner
from api.routes.schemas import (
    ArtifactDescriptor,
    ArtifactsResponse,
    CreateProductionRequest,
    CreateProductionResponse,
    ProductionDetail,
    ProductionSummary,
    ProgressResponse,
)
from api.storage.artifacts import ArtifactKind, ArtifactService
from api.workflows.production import ProductionWorkflowInput

router = APIRouter(prefix="/api/productions", tags=["productions"])

#: HTTP media type by artifact filename extension (only used for downloads).
_MIME_BY_SUFFIX = {
    ".mp4": "video/mp4",
    ".wav": "audio/wav",
    ".png": "image/png",
    ".json": "application/json",
}


# --- helpers ----------------------------------------------------------------

def _validate_id(production_id: str) -> None:
    if PRODUCTION_ID_PATTERN.match(production_id) is None:
        raise HTTPException(
            status_code=422,
            detail=f"invalid production id {production_id!r}",
        )


def _get_production(session_factory, production_id: str) -> Production:
    with session_scope(session_factory) as session:
        production = make_production_repository(session).get(production_id)
    if production is None:
        raise HTTPException(
            status_code=404,
            detail=f"production {production_id!r} not found",
        )
    return production


def _load_config(session_factory, production_id: str) -> ProductionConfig | None:
    with session_scope(session_factory) as session:
        return make_production_repository(session).get_config(production_id)


def _workflow_runs(session_factory, production_id: str) -> list[WorkflowRun]:
    with session_scope(session_factory) as session:
        return make_workflow_repository(session).list_for_production(production_id)


def _run_state(session_factory, production_id: str) -> tuple[int, str | None]:
    """Return (max attempt, latest running workflow id) for a production."""
    runs = _workflow_runs(session_factory, production_id)
    if not runs:
        return 1, None
    attempt = max(run.attempts for run in runs)
    running = [run.id for run in reversed(runs) if run.status == "running"]
    return attempt, running[0] if running else None


def _to_summary(production: Production) -> ProductionSummary:
    return ProductionSummary(
        id=production.id,
        mode=production.mode.value,
        genre=production.genre,
        branding_text=production.branding_text,
        status=production.status.value,
        target_duration_minutes=production.target_duration_minutes,
        created_at=production.created_at,
        updated_at=production.updated_at,
        completed_at=production.completed_at,
    )


def _to_detail(session_factory, production: Production) -> ProductionDetail:
    attempt, workflow_id = _run_state(session_factory, production.id)
    return ProductionDetail(
        **_to_summary(production).model_dump(),
        attempt=attempt,
        workflow_id=workflow_id,
    )


def _progress(status: ProductionStatus) -> float:
    """Linear progress through the canonical status flow (MAD-001 §13).

    CREATED -> 0.0, COMPLETED -> 1.0; FAILED/CANCELLED report 0.0 because they
    are dead ends, not forward progress (TDD-001 §71).
    """
    if status in (ProductionStatus.FAILED, ProductionStatus.CANCELLED):
        return 0.0
    try:
        index = _PRODUCTION_FLOW.index(status)
    except ValueError:
        return 0.0
    return round(index / (len(_PRODUCTION_FLOW) - 1), 2)


def _stage_label(status: ProductionStatus) -> str:
    """Human-readable stage name: ``rendering_master`` -> ``Rendering Master``."""
    return " ".join(part.capitalize() for part in status.value.split("_"))


def _mime_for(kind: ArtifactKind) -> str:
    return _MIME_BY_SUFFIX.get(Path(kind.value).suffix.lower(), "application/octet-stream")


async def _start_workflow(
    session_factory,
    runner: ProductionRunner,
    production: Production,
    config: ProductionConfig,
    *,
    attempt: int,
) -> str:
    """Persist the production, start the workflow, and record the run.

    The workflow's own ``record_workflow_run`` activity later upserts this row,
    so the API recording it first gives cancel/progress endpoints a handle even
    before the worker picks the task up.
    """
    request = ProductionWorkflowInput(
        production_id=production.id,
        mode=production.mode,
        genre=production.genre,
        branding_text=production.branding_text,
        provider_mode=config.provider_profile,
        target_duration_minutes=production.target_duration_minutes,
    )
    try:
        workflow_id = await runner.start(production.id, request, attempt=attempt)
    except AppError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - Temporal connection failures surface as 502
        raise HTTPException(status_code=502, detail=f"failed to start workflow: {exc}") from exc
    with session_scope(session_factory) as session:
        make_workflow_repository(session).create(
            WorkflowRun(
                id=workflow_id,
                production_id=production.id,
                workflow_type="ProductionWorkflow",
                task_queue="production",
                status="running",
                attempts=attempt,
            )
        )
    return workflow_id


# --- routes ----------------------------------------------------------------

@router.post("", response_model=CreateProductionResponse, status_code=201)
async def create_production(
    payload: CreateProductionRequest,
    session_factory=Depends(get_session_factory),
    runner: ProductionRunner = Depends(get_runner),
    settings: AppSettings = Depends(get_settings),
) -> CreateProductionResponse:
    """Validate, persist, then start the workflow (TDD-001 §69; MAD-001 §45)."""
    production = Production(
        mode=payload.mode,
        genre=payload.genre,
        branding_text=payload.branding_text,
    )
    config = ProductionConfig(
        mode=payload.mode,
        genre=payload.genre,
        branding=BrandingConfig(text=payload.branding_text or ""),
        provider_profile=settings.provider_mode,
    )
    with session_scope(session_factory) as session:
        repo = make_production_repository(session)
        repo.create(production)
        repo.save_config(production.id, config)
    await _start_workflow(session_factory, runner, production, config, attempt=1)
    return CreateProductionResponse(id=production.id, status=production.status.value)


@router.get("", response_model=list[ProductionSummary])
async def list_productions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session_factory=Depends(get_session_factory),
) -> list[ProductionSummary]:
    """List productions, newest first."""
    with session_scope(session_factory) as session:
        productions = make_production_repository(session).list(limit=limit, offset=offset)
    return [_to_summary(production) for production in productions]


@router.get("/{production_id}", response_model=ProductionDetail)
async def get_production(
    production_id: str,
    session_factory=Depends(get_session_factory),
) -> ProductionDetail:
    _validate_id(production_id)
    return _to_detail(session_factory, _get_production(session_factory, production_id))


@router.post("/{production_id}/retry", response_model=ProductionDetail)
async def retry_production(
    production_id: str,
    session_factory=Depends(get_session_factory),
    runner: ProductionRunner = Depends(get_runner),
) -> ProductionDetail:
    """Restart a FAILED production as a new workflow attempt.

    The production returns to CREATED and the workflow is started again with an
    incremented attempt id (MAD-001 §13: FAILED may retry into any non-terminal
    stage; the state machine owns the transition).
    """
    _validate_id(production_id)
    production = _get_production(session_factory, production_id)
    if production.status is not ProductionStatus.FAILED:
        raise HTTPException(
            status_code=409,
            detail=f"production {production_id!r} is not in 'failed' status",
        )
    attempt = max((run.attempts for run in _workflow_runs(session_factory, production_id)), default=0) + 1
    with session_scope(session_factory) as session:
        repo = make_production_repository(session)
        current = repo.get(production_id)
        current.transition_to(ProductionStatus.CREATED)
        repo.update(current)
        production = current
    config = _load_config(session_factory, production_id) or ProductionConfig(
        mode=production.mode, genre=production.genre
    )
    await _start_workflow(session_factory, runner, production, config, attempt=attempt)
    return _to_detail(session_factory, production)


@router.post("/{production_id}/cancel", response_model=ProductionDetail)
async def cancel_production(
    production_id: str,
    session_factory=Depends(get_session_factory),
    runner: ProductionRunner = Depends(get_runner),
) -> ProductionDetail:
    """Cancel a running production: transition to CANCELLED and stop the workflow."""
    _validate_id(production_id)
    production = _get_production(session_factory, production_id)
    if production.status in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"production {production_id!r} is already {production.status.value!r}",
        )
    if production.status is ProductionStatus.FAILED:
        raise HTTPException(
            status_code=409,
            detail=f"production {production_id!r} is 'failed'; use retry instead",
        )
    with session_scope(session_factory) as session:
        repo = make_production_repository(session)
        current = repo.get(production_id)
        current.transition_to(ProductionStatus.CANCELLED)
        repo.update(current)
        production = current
    running = _run_state(session_factory, production_id)[1]
    if running:
        await runner.cancel(running)
    return _to_detail(session_factory, production)


@router.get("/{production_id}/progress", response_model=ProgressResponse)
async def get_progress(
    production_id: str,
    session_factory=Depends(get_session_factory),
) -> ProgressResponse:
    _validate_id(production_id)
    production = _get_production(session_factory, production_id)
    attempt, _ = _run_state(session_factory, production_id)
    return ProgressResponse(
        production_id=production.id,
        status=production.status.value,
        progress=_progress(production.status),
        stage=_stage_label(production.status),
        attempt=attempt,
    )


@router.get("/{production_id}/artifacts", response_model=ArtifactsResponse)
async def list_artifacts(
    production_id: str,
    session_factory=Depends(get_session_factory),
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactsResponse:
    """List the canonical artifacts with safe download urls (TDD-001 §72)."""
    _validate_id(production_id)
    _get_production(session_factory, production_id)
    descriptors: list[ArtifactDescriptor] = []
    for kind in ArtifactKind:
        exists = artifact_service.exists(production_id, kind)
        descriptors.append(
            ArtifactDescriptor(
                kind=kind.value,
                url=f"/api/productions/{production_id}/artifacts/{kind.value}",
                exists=exists,
                size_bytes=artifact_service.size(production_id, kind) if exists else None,
                mime_type=_mime_for(kind),
            )
        )
    return ArtifactsResponse(production_id=production_id, artifacts=descriptors)


@router.get("/{production_id}/artifacts/{kind}")
async def download_artifact(
    production_id: str,
    kind: str,
    session_factory=Depends(get_session_factory),
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> FileResponse:
    """Serve one artifact by kind (MASTER §33; MAD-001 §45 asset access)."""
    _validate_id(production_id)
    _get_production(session_factory, production_id)
    try:
        artifact_kind = ArtifactKind(kind)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"unknown artifact kind {kind!r}")
    path = artifact_service.path_for(production_id, artifact_kind)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"artifact {kind!r} has not been produced yet",
        )
    return FileResponse(path, media_type=_mime_for(artifact_kind), filename=kind)
