"""Phase 19: production HTTP API (MASTER §29; MAD-001 §45; TDD-001 §68-72).

Exercises the seven required endpoints over the FastAPI ``TestClient`` against
an isolated temp database. The Temporal workflow runner is replaced by a
recording fake so no Temporal server is needed; every test asserts both the HTTP
contract and the persisted state/recorded runner calls.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.database import make_production_repository, make_workflow_repository, session_scope
from api.domain.enums import ProductionStatus
from api.main import create_app
from api.routes.schemas import (
    ArtifactsResponse,
    CreateProductionResponse,
    ProductionDetail,
    ProductionSummary,
    ProgressResponse,
)
from api.storage.artifacts import ArtifactKind


class FakeRunner:
    """Recording :class:`ProductionRunner` used in place of Temporal."""

    def __init__(self) -> None:
        self.starts: list[tuple[str, object, int]] = []
        self.cancelled: list[str] = []
        self.start_error: Exception | None = None
        self.cancel_error: Exception | None = None

    async def start(self, production_id: str, request: object, *, attempt: int = 1) -> str:
        if self.start_error is not None:
            raise self.start_error
        workflow_id = f"production-{production_id}-a{attempt}"
        self.starts.append((production_id, request, attempt))
        return workflow_id

    async def cancel(self, workflow_id: str) -> None:
        if self.cancel_error is not None:
            raise self.cancel_error
        self.cancelled.append(workflow_id)


@pytest.fixture
def fake_runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def client(settings, fake_runner):
    """A running app with the recording runner injected (lifespan on)."""
    app = create_app(settings, production_runner=fake_runner)
    with TestClient(app) as test_client:
        yield test_client


# --- helpers ----------------------------------------------------------------

def _get_production(client, production_id):
    with session_scope(client.app.state.session_factory) as session:
        return make_production_repository(session).get(production_id)


def _workflow_runs(client, production_id):
    with session_scope(client.app.state.session_factory) as session:
        return make_workflow_repository(session).list_for_production(production_id)


def _set_status(client, production_id, status: ProductionStatus) -> None:
    with session_scope(client.app.state.session_factory) as session:
        repo = make_production_repository(session)
        production = repo.get(production_id)
        production.status = status
        repo.update(production)


def _create(client, **overrides) -> dict:
    payload = {"mode": "genre", "genre": "lofi", "branding_text": "MY CHANNEL"}
    payload.update(overrides)
    response = client.post("/api/productions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# --- POST /api/productions (TDD-001 §69) ------------------------------------

def test_create_genre_production(client):
    body = _create(client)
    assert isinstance(body, dict)
    created = CreateProductionResponse(**body)
    assert created.status == "created"

    production = _get_production(client, created.id)
    assert production is not None
    assert production.mode.value == "genre"
    assert production.genre == "lofi"
    assert production.branding_text == "MY CHANNEL"
    assert production.status is ProductionStatus.CREATED

    # A config snapshot is persisted for the pipeline (MAD-001 §92-94).
    with session_scope(client.app.state.session_factory) as session:
        config = make_production_repository(session).get_config(created.id)
    assert config is not None
    assert config.genre == "lofi"


def test_create_trending_production_without_genre(client):
    body = _create(client, mode="trending", genre=None)
    created = CreateProductionResponse(**body)
    production = _get_production(client, created.id)
    assert production.mode.value == "trending"
    assert production.genre is None


def test_create_genre_mode_requires_genre(client):
    response = client.post("/api/productions", json={"mode": "genre", "branding_text": "X"})
    assert response.status_code == 422


def test_create_rejects_overlong_branding(client):
    response = client.post(
        "/api/productions",
        json={"mode": "genre", "genre": "lofi", "branding_text": "X" * 81},
    )
    assert response.status_code == 422


def test_create_trims_whitespace(client):
    body = _create(client, genre="  Lo-Fi  ", branding_text="  CH  ")
    production = _get_production(client, body["id"])
    assert production.genre == "lo-fi"
    assert production.branding_text == "CH"


def test_create_starts_workflow_and_records_run(client, fake_runner):
    body = _create(client)
    assert len(fake_runner.starts) == 1
    production_id, request, attempt = fake_runner.starts[0]
    assert production_id == body["id"]
    assert attempt == 1
    assert request.production_id == body["id"]
    assert request.mode.value == "genre"

    runs = _workflow_runs(client, body["id"])
    assert len(runs) == 1
    assert runs[0].status == "running"
    assert runs[0].attempts == 1
    assert runs[0].id == f"production-{body['id']}-a1"


def test_create_workflow_start_failure_returns_502(client, fake_runner):
    fake_runner.start_error = RuntimeError("temporal down")
    response = client.post(
        "/api/productions", json={"mode": "genre", "genre": "lofi"}
    )
    assert response.status_code == 502
    assert "failed to start workflow" in response.json()["detail"]


# --- GET /api/productions ---------------------------------------------------

def test_list_productions_empty(client):
    response = client.get("/api/productions")
    assert response.status_code == 200
    assert response.json() == []


def test_list_productions_newest_first(client):
    first = _create(client, genre="lofi")
    second = _create(client, genre="chillhop")
    response = client.get("/api/productions")
    assert response.status_code == 200
    items = [ProductionSummary(**item) for item in response.json()]
    assert [item.id for item in items] == [second["id"], first["id"]]
    assert items[0].genre == "chillhop"


# --- GET /api/productions/{id} ----------------------------------------------

def test_get_production_detail(client):
    body = _create(client)
    response = client.get(f"/api/productions/{body['id']}")
    assert response.status_code == 200
    detail = ProductionDetail(**response.json())
    assert detail.id == body["id"]
    assert detail.status == "created"
    assert detail.attempt == 1
    assert detail.workflow_id == f"production-{body['id']}-a1"


def test_get_production_404(client):
    response = client.get("/api/productions/prod_00000000000000000000000000")
    assert response.status_code == 404


def test_get_production_invalid_id_422(client):
    response = client.get("/api/productions/not-an-id")
    assert response.status_code == 422


# --- POST /api/productions/{id}/retry ---------------------------------------

def test_retry_failed_production_starts_new_attempt(client, fake_runner):
    body = _create(client)
    _set_status(client, body["id"], ProductionStatus.FAILED)

    response = client.post(f"/api/productions/{body['id']}/retry")
    assert response.status_code == 200
    detail = ProductionDetail(**response.json())
    assert detail.status == "created"
    assert detail.attempt == 2

    assert len(fake_runner.starts) == 2
    _, _, attempt = fake_runner.starts[1]
    assert attempt == 2
    runs = _workflow_runs(client, body["id"])
    assert len(runs) == 2
    assert max(run.attempts for run in runs) == 2


def test_retry_non_failed_production_conflict(client):
    body = _create(client)  # CREATED
    response = client.post(f"/api/productions/{body['id']}/retry")
    assert response.status_code == 409


def test_retry_missing_production_404(client):
    response = client.post("/api/productions/prod_00000000000000000000000000/retry")
    assert response.status_code == 404


# --- POST /api/productions/{id}/cancel --------------------------------------

def test_cancel_running_production(client, fake_runner):
    body = _create(client)
    response = client.post(f"/api/productions/{body['id']}/cancel")
    assert response.status_code == 200
    detail = ProductionDetail(**response.json())
    assert detail.status == "cancelled"

    production = _get_production(client, body["id"])
    assert production.status is ProductionStatus.CANCELLED
    # The running workflow (recorded at create) was cancelled.
    assert fake_runner.cancelled == [f"production-{body['id']}-a1"]


def test_cancel_completed_production_conflict(client):
    body = _create(client)
    _set_status(client, body["id"], ProductionStatus.COMPLETED)
    response = client.post(f"/api/productions/{body['id']}/cancel")
    assert response.status_code == 409


def test_cancel_failed_production_conflict(client):
    body = _create(client)
    _set_status(client, body["id"], ProductionStatus.FAILED)
    response = client.post(f"/api/productions/{body['id']}/cancel")
    assert response.status_code == 409


# --- GET /api/productions/{id}/progress (TDD-001 §71) ------------------------

def test_progress_created(client):
    body = _create(client)
    response = client.get(f"/api/productions/{body['id']}/progress")
    assert response.status_code == 200
    progress = ProgressResponse(**response.json())
    assert progress.status == "created"
    assert progress.progress == 0.0
    assert progress.stage == "Created"


def test_progress_mid_stage(client):
    body = _create(client)
    _set_status(client, body["id"], ProductionStatus.RENDERING_MASTER)
    response = client.get(f"/api/productions/{body['id']}/progress")
    progress = ProgressResponse(**response.json())
    assert progress.status == "rendering_master"
    assert progress.stage == "Rendering Master"
    assert progress.progress == pytest.approx(8 / 15, abs=1e-2)


def test_progress_completed_is_1(client):
    body = _create(client)
    _set_status(client, body["id"], ProductionStatus.COMPLETED)
    progress = ProgressResponse(**client.get(f"/api/productions/{body['id']}/progress").json())
    assert progress.progress == 1.0
    assert progress.stage == "Completed"


def test_progress_failed_is_0(client):
    body = _create(client)
    _set_status(client, body["id"], ProductionStatus.FAILED)
    progress = ProgressResponse(**client.get(f"/api/productions/{body['id']}/progress").json())
    assert progress.progress == 0.0


# --- GET /api/productions/{id}/artifacts (TDD-001 §72) -----------------------

def test_artifacts_listing_reflects_present_files(client):
    body = _create(client)
    response = client.get(f"/api/productions/{body['id']}/artifacts")
    assert response.status_code == 200
    listing = ArtifactsResponse(**response.json())
    assert listing.production_id == body["id"]
    assert len(listing.artifacts) == len(list(ArtifactKind))
    assert all(descriptor.exists is False for descriptor in listing.artifacts)
    assert all(descriptor.url.startswith(f"/api/productions/{body['id']}/artifacts/") for descriptor in listing.artifacts)

    # Produce one artifact; its descriptor flips to exists with a size.
    client.app.state.artifact_service.write(
        body["id"], ArtifactKind.MASTER_VIDEO, b"\x00\x00\x00\x1cftypmp42"
    )
    listing = ArtifactsResponse(**client.get(f"/api/productions/{body['id']}/artifacts").json())
    by_kind = {descriptor.kind: descriptor for descriptor in listing.artifacts}
    assert by_kind["master-16x9.mp4"].exists is True
    assert by_kind["master-16x9.mp4"].size_bytes == 12
    assert by_kind["master-16x9.mp4"].mime_type == "video/mp4"


def test_artifact_download_serves_bytes(client):
    body = _create(client)
    client.app.state.artifact_service.write(
        body["id"], ArtifactKind.AUDIO_MASTER, b"\x52\x49\x46\x46" + b"\x00" * 8
    )
    response = client.get(f"/api/productions/{body['id']}/artifacts/audio-master.wav")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"\x52\x49\x46\x46" + b"\x00" * 8


def test_artifact_download_unproduced_404(client):
    body = _create(client)
    response = client.get(f"/api/productions/{body['id']}/artifacts/master-16x9.mp4")
    assert response.status_code == 404


def test_artifact_download_unknown_kind_404(client):
    body = _create(client)
    response = client.get(f"/api/productions/{body['id']}/artifacts/not-a-real-kind")
    assert response.status_code == 404
