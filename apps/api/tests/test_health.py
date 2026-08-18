"""Health endpoint tests (Phase 00 validation: backend starts)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import create_app


def test_root(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/")
        assert response.status_code == 200
        body = response.json()
        assert body["app"] == settings.app_name


def test_health(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["version"] == settings.app_version
        assert body["env"] == settings.app_env


def test_readiness_database_ok(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] is True
