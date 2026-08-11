"""FastAPI dependencies for the API routes (MASTER §29, MAD-001 §45).

Shared services (session factory, workflow runner, artifact service, settings)
are built once in the app lifespan and exposed on ``app.state``; routes resolve
them through these dependencies instead of constructing their own. This keeps
the routes thin and makes every service injectable in tests.
"""
from __future__ import annotations

from typing import Any

from fastapi import Request

from api.routes.runner import ProductionRunner
from api.storage.artifacts import ArtifactService


def get_session_factory(request: Request) -> Any:
    """Return the app's SQLAlchemy session factory (bound in the lifespan)."""
    return request.app.state.session_factory


def get_runner(request: Request) -> ProductionRunner:
    """Return the injected production workflow runner."""
    return request.app.state.production_runner


def get_artifact_service(request: Request) -> ArtifactService:
    """Return the app's artifact service (bounded to the productions root)."""
    return request.app.state.artifact_service


def get_settings(request: Request):
    """Return the app's settings instance."""
    return request.app.state.settings
