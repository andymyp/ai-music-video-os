"""FastAPI application entry point.

Phase 00 provides the health surface and bootstraps the runtime directories
and database connection. Production/asset/config routes arrive in Phase 19 (API).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config.settings import AppSettings, get_settings
from api.core.logging import configure_logging
from api.database.engine import connect_database, verify_database
from api.storage.layout import ensure_runtime_dirs


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Application factory. ``settings`` is injectable for tests."""
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> None:
        ensure_runtime_dirs(settings)
        app.state.db_engine = connect_database(settings)
        yield
        app.state.db_engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root() -> dict[str, object]:
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/health",
        }

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
            "provider_mode": settings.provider_mode,
        }

    @app.get("/api/health/ready")
    async def ready() -> dict[str, object]:
        db_ok = False
        try:
            engine = getattr(app.state, "db_engine", None)
            if engine is not None:
                verify_database(engine)
                db_ok = True
        except Exception:  # noqa: BLE001 - health endpoint must not raise
            db_ok = False
        return {"status": "ok" if db_ok else "error", "database": db_ok}

    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.auto_reload,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
