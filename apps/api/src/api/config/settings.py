"""Application settings.

Config precedence (MAD-001 §93): defaults < .env < environment variables < overrides.

Only foundation-level configuration is defined here. Domain/provider/rendering
configuration is added by later phases without changing the loading mechanism.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from api.config.profiles import ENVIRONMENT_PROFILES, PROVIDER_MODES
from api.core.paths import find_project_root


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application identity -------------------------------------------------
    app_name: str = "ai-music-video-os"
    app_version: str = "0.1.0"

    # --- Environment / mode --------------------------------------------------
    app_env: str = "development"
    provider_mode: str = "mock"
    log_level: str = "INFO"

    # --- Local storage ---------------------------------------------------------
    app_data_dir: Path = Field(default_factory=lambda: find_project_root() / "data")
    temp_dir: Path | None = None
    database_url: str | None = None

    # --- Default providers (Phase 00: mock) ------------------------------------
    default_llm_provider: str = "mock"
    default_music_provider: str = "mock"
    default_image_provider: str = "mock"
    default_trend_provider: str = "mock"

    # --- Resource limits (MAD-001 §43, §71) -----------------------------------
    max_concurrent_productions: int = 1
    max_render_workers: int = 1

    # --- Rendering defaults (MAD-001 §94) -------------------------------------
    master_video_width: int = 1920
    master_video_height: int = 1080
    master_video_fps: int = 30
    short_video_width: int = 1080
    short_video_height: int = 1920
    short_video_duration_seconds: int = 45

    # --- Temporal (MAD-001 §9) -------------------------------------------------
    temporal_address: str = "localhost:7233"
    temporal_task_queue: str = "production"

    # --- API server -------------------------------------------------------------
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    auto_reload: bool = False

    # --- HTTP -------------------------------------------------------------------
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("app_env")
    @classmethod
    def _validate_app_env(cls, value: str) -> str:
        if value not in ENVIRONMENT_PROFILES:
            raise ValueError(f"app_env must be one of {ENVIRONMENT_PROFILES}")
        return value

    @field_validator("provider_mode")
    @classmethod
    def _validate_provider_mode(cls, value: str) -> str:
        if value not in PROVIDER_MODES:
            raise ValueError(f"provider_mode must be one of {PROVIDER_MODES}")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    # --- Resolved values --------------------------------------------------------

    def resolved_temp_dir(self) -> Path:
        return self.temp_dir or (self.app_data_dir / "temp")

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        default_db = (self.app_data_dir / "database" / "app.db").as_posix()
        return f"sqlite:///{default_db}"


@lru_cache
def get_settings() -> AppSettings:
    """Return the process-wide settings instance."""
    return AppSettings()
