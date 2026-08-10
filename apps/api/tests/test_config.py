"""Configuration tests (MASTER_EXECUTION Phase 00 / MAD-001 §92-94)."""

from __future__ import annotations

import pytest

from api.config.profiles import ENVIRONMENT_PROFILES, PROVIDER_MODES
from api.config.settings import AppSettings, get_settings


def test_default_settings_valid():
    settings = get_settings()
    assert settings.app_env in ENVIRONMENT_PROFILES
    assert settings.provider_mode in PROVIDER_MODES
    assert settings.temporal_address == "localhost:7233"
    assert settings.max_concurrent_productions == 1


def test_environment_profiles():
    assert set(ENVIRONMENT_PROFILES) == {"development", "test", "mock", "production"}


def test_provider_modes():
    assert set(PROVIDER_MODES) == {"mock", "free", "balanced", "quality", "custom"}


def test_invalid_environment_rejected():
    with pytest.raises(ValueError):
        AppSettings(app_env="not-a-profile", app_data_dir=".")


def test_invalid_provider_mode_rejected():
    with pytest.raises(ValueError):
        AppSettings(provider_mode="not-a-mode", app_data_dir=".")


def test_default_database_url_under_data_dir(tmp_path):
    settings = AppSettings(app_data_dir=tmp_path, app_env="test")
    url = settings.resolved_database_url()
    assert url.startswith("sqlite:///")
    assert "database/app.db" in url


def test_explicit_database_url_wins(tmp_path):
    explicit = f"sqlite:///{(tmp_path / 'custom.db').as_posix()}"
    settings = AppSettings(app_data_dir=tmp_path, app_env="test", database_url=explicit)
    assert settings.resolved_database_url() == explicit


def test_temp_dir_defaults_under_data_dir(tmp_path):
    settings = AppSettings(app_data_dir=tmp_path, app_env="test")
    assert settings.resolved_temp_dir() == tmp_path / "temp"


def test_cors_origins_json_list(tmp_path):
    settings = AppSettings(
        app_data_dir=tmp_path,
        app_env="test",
        cors_origins='["http://a.test", "http://b.test"]',
    )
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_cors_origins_comma_separated(tmp_path):
    settings = AppSettings(
        app_data_dir=tmp_path,
        app_env="test",
        cors_origins="http://a.test,http://b.test",
    )
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_render_defaults():
    settings = AppSettings(app_env="test", app_data_dir=".")
    assert settings.master_video_width == 1920
    assert settings.master_video_height == 1080
    assert settings.master_video_fps == 30
    assert settings.short_video_width == 1080
    assert settings.short_video_height == 1920
    assert settings.short_video_duration_seconds == 45
