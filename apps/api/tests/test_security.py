"""Phase 23: security (MASTER §36; MAD-001 §47-48; TDD-001 §78-79, §90-93).

Locks in the six security boundaries:

* credential isolation — secrets are env-var *references* only, resolved at
  call time by :func:`api.core.secrets.resolve_credentials`, never stored,
  logged or handed to agents;
* filesystem path validation — every production path is derived from a
  validated production id and confined to the storage root (TDD-001 §91);
* safe FFmpeg execution — structured argument arrays, no shell (TDD-001 §92);
* agent tool restrictions — the runtime exposes only the registered tool set,
  and agent decision files can never reach secrets (TDD-001 §93);
* secret handling — resolution never logs the value;
* API validation — hostile ids are rejected and responses never expose
  arbitrary filesystem paths (TDD-001 §72, §121).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.agents import CapabilityStatusTool, build_agent_runtime
from api.agents.tools import CapabilityQuery
from api.capabilities import (
    Capability,
    InMemoryProviderRegistry,
    ProviderConfig,
)
from api.core import secrets as secrets_module
from api.core.errors import StorageError
from api.core.secrets import get_secret, is_valid_reference, resolve_credentials
from api.main import create_app
from api.media.ffmpeg import _escape_filter, build_render_args
from api.providers import register_mock_providers
from api.storage.artifacts import ArtifactService
from api.storage.storage import StorageService

_FORBIDDEN_SECRET_TOOLS = frozenset({"exec", "shell", "run", "read_file", "write_file", "fs"})
_KNOWN_TOOLS = frozenset(
    {"audio_analyze", "capability_status", "image_generate", "llm_generate", "music_generate", "trend_search"}
)
_SECRET_ACCESS = re.compile(r"\b(?:os\.getenv|os\.environ|getpass|os\.getlogin)\b")


def _code_without_docstrings_and_comments(path: Path) -> str:
    """Return *path*'s source with docstrings and comments stripped, so source
    scans (e.g. no ``shell=``) inspect real call sites, not prose about them."""
    text = path.read_text(encoding="utf-8")
    no_docstrings = re.sub(
        r'"""(?:(?!""").)*"""|\'\'\'(?:(?!\'\'\').)*\'\'\'', "", text, flags=re.DOTALL
    )
    return re.sub(r"#[^\n]*", "", no_docstrings)


# --- Secret resolution (MAD-001 §48, TDD-001 §79) ------------------------------

def test_is_valid_reference_accepts_env_var_names():
    for reference in ("OPENAI_API_KEY", "GEMINI_API_KEY", "SECRETS_MOCK_KEY", "AWS_S3"):
        assert is_valid_reference(reference)


def test_is_valid_reference_rejects_secret_like_values():
    for reference in ("sk-abc123", "api_key", "my api key", "", None, "../etc/passwd", "secret!value", "1ABC"):
        assert not is_valid_reference(reference)


def test_get_secret_resolves_from_environment(monkeypatch):
    monkeypatch.setenv("SECRETS_TEST_KEY", "env-value")
    assert get_secret("SECRETS_TEST_KEY") == "env-value"


def test_get_secret_missing_returns_none(monkeypatch):
    monkeypatch.delenv("SECRETS_TEST_MISSING", raising=False)
    assert get_secret("SECRETS_TEST_MISSING") is None


def test_get_secret_falls_back_to_dotenv(monkeypatch):
    monkeypatch.delenv("SECRETS_TEST_DOTENV", raising=False)
    monkeypatch.setattr(secrets_module, "_load_dotenv_values", lambda: {"SECRETS_TEST_DOTENV": "from-dotenv"})
    assert get_secret("SECRETS_TEST_DOTENV") == "from-dotenv"


def test_get_secret_invalid_reference_raises(monkeypatch):
    monkeypatch.setenv("sk-literal", "should-never-resolve")
    with pytest.raises(Exception, match="invalid secret reference"):
        get_secret("sk-literal")
    with pytest.raises(Exception, match="invalid secret reference"):
        get_secret("../etc/passwd")
    with pytest.raises(Exception, match="invalid secret reference"):
        get_secret("")


def test_secret_resolution_never_logs_value(caplog, monkeypatch):
    monkeypatch.setenv("SECRETS_TEST_LOGGING", "super-duper-secret-value")
    # Some other test may disable this logger via pytest --log-disable; ensure it's enabled.
    secrets_module.logger.disabled = False
    secrets_module.logger.setLevel(logging.DEBUG)
    caplog.set_level(logging.DEBUG)

    assert get_secret("SECRETS_TEST_LOGGING") == "super-duper-secret-value"

    assert "super-duper-secret-value" not in caplog.text
    # the debug line names the reference only, so operators can trace resolution
    assert "SECRETS_TEST_LOGGING" in caplog.text


def test_resolve_credentials_returns_empty_for_no_reference():
    assert resolve_credentials(None) == {}
    assert resolve_credentials("") == {}


def test_resolve_credentials_returns_secret_map(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-resolved")
    assert resolve_credentials("OPENAI_API_KEY") == {"OPENAI_API_KEY": "sk-resolved"}


def test_resolve_credentials_omits_unset_reference(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert resolve_credentials("OPENAI_API_KEY") == {}


# --- Credential isolation (TDD-001 §78, §90) ------------------------------------

def test_provider_config_rejects_literal_secret_reference():
    with pytest.raises(Exception, match="env-var name"):
        ProviderConfig(provider_id="p", capability=Capability.LLM, credentials_reference="sk-abc123")


def test_provider_config_rejects_path_reference():
    with pytest.raises(Exception, match="env-var name"):
        ProviderConfig(provider_id="p", capability=Capability.LLM, credentials_reference="/etc/secrets/key")


def test_provider_config_accepts_env_var_reference():
    config = ProviderConfig(
        provider_id="p", capability=Capability.LLM, credentials_reference="OPENAI_API_KEY"
    )
    assert config.credentials_reference == "OPENAI_API_KEY"


def test_provider_config_holds_indirection_not_value(monkeypatch):
    """The config stores the reference name; the value only exists at call time."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-NEVER-STORE-ME")
    config = ProviderConfig(
        provider_id="p", capability=Capability.LLM, credentials_reference="OPENAI_API_KEY"
    )
    dumped = config.model_dump()
    assert dumped["credentials_reference"] == "OPENAI_API_KEY"
    assert "sk-NEVER-STORE-ME" not in repr(dumped)


async def test_capability_status_tool_never_leaks_credentials(monkeypatch):
    """The agent-facing capability tool exposes provider ids only — never the
    credentials reference or the resolved secret (TDD-001 §90 boundary)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-SUPERSECRET-123")
    registry = InMemoryProviderRegistry()
    registry.register(
        Capability.LLM,
        object(),
        ProviderConfig(
            provider_id="mock",
            capability=Capability.LLM,
            credentials_reference="OPENAI_API_KEY",
        ),
    )

    status = await CapabilityStatusTool(registry).run(CapabilityQuery(capability=Capability.LLM))
    dumped = status.model_dump_json()

    assert status.provider_ids == ["mock"]
    assert "sk-SUPERSECRET-123" not in dumped
    assert "credentials_reference" not in dumped
    assert "OPENAI_API_KEY" not in dumped


# --- Filesystem path validation (TDD-001 §91) -----------------------------------

def test_artifact_service_rejects_hostile_production_ids(tmp_path):
    service = ArtifactService(StorageService(tmp_path / "root"), tmp_path / "productions")
    for hostile in ("prod_../../etc", "../escape", "prod_NOT_A_ULID", "prod_x"):
        with pytest.raises(StorageError):
            service.production_dir(hostile)


def test_storage_rejects_deep_nested_traversal(tmp_path):
    storage = StorageService(tmp_path / "root")
    storage.ensure_root()
    with pytest.raises(StorageError):
        storage.write("a/../../escape.bin", b"x")


def test_storage_rejects_absolute_escape_via_join(tmp_path):
    storage = StorageService(tmp_path / "root")
    storage.ensure_root()
    outside = (tmp_path / "outside.bin").resolve()
    with pytest.raises(StorageError):
        storage.write(str(outside), b"x")


# --- Safe FFmpeg execution (TDD-001 §92) ----------------------------------------

def test_escape_filter_escapes_filter_graph_metacharacters():
    # drawtext values are embedded in a single-quoted token (text='...'); the
    # four filter-graph metacharacters plus '%' are escaped so the value can
    # never break out of the token (TDD-001 §92). No shell is involved, so
    # shell metacharacters like ';'/'$'/'`' are literal inside the quotes.
    for raw, safe in (("\\", "\\\\"), (":", "\\:"), (",", "\\,"), ("'", "\\'"), ("%", "%%")):
        assert _escape_filter(raw) == safe


def test_escape_filter_neutralizes_shell_and_filter_metacharacters():
    hostile = "$(id); `reboot` %'\"\n\t"
    escaped = _escape_filter(hostile)
    assert "%%" in escaped and "\\'" in escaped
    # every single-quote is escaped: embedding in text='...' cannot break out
    assert escaped.count("'") == escaped.count("\\'")


def test_escape_filter_survives_every_control_char():
    for value in ("a;b", "a$(cmd)b", "a`cmd`b", "a,b", "a:b", "a'b", "50%", "\\backslash", "a\nb\t"):
        escaped = _escape_filter(value)
        # deterministic and exception-free; an unescaped quote never survives
        assert escaped.count("'") == escaped.count("\\'")


def test_ffmpeg_source_never_uses_shell():
    path = Path(__file__).resolve().parents[1] / "src/api/media/ffmpeg.py"
    code = _code_without_docstrings_and_comments(path)
    assert "shell=" not in code
    assert "os.system" not in code
    assert "subprocess.run" not in code
    assert "Popen" not in code
    assert "create_subprocess_exec" in code  # the structured, shell-free runner


# --- Agent tool restrictions (TDD-001 §93) ---------------------------------------

def test_agent_runtime_exposes_only_registered_tools():
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    runtime = build_agent_runtime(registry)

    tool_names = set(runtime.tools.names())
    assert tool_names == _KNOWN_TOOLS
    assert tool_names.isdisjoint(_FORBIDDEN_SECRET_TOOLS)
    # the audio tool takes a path but only ever resolves it through the
    # storage-confined engine — no generic filesystem tool exists.


def test_agent_decision_files_cannot_read_secrets_directly():
    infra = {"__init__.py", "base.py", "tools.py", "runtime.py"}
    agent_dir = Path(__file__).resolve().parents[1] / "src/api/agents"
    offenders: list[str] = []
    for path in sorted(agent_dir.glob("*.py")):
        if path.name in infra:
            continue
        text = path.read_text(encoding="utf-8")
        if _SECRET_ACCESS.search(text):
            offenders.append(path.name)
    assert offenders == []


# --- API validation / no path exposure (TDD-001 §72, §121) ------------------------

class _RecordingRunner:
    async def start(self, production_id, request, *, attempt=1):
        return f"production-{production_id}-a{attempt}"

    async def cancel(self, workflow_id):
        return None


@pytest.fixture
def client(settings):
    """A running app (lifespan on) with the recording runner injected."""
    app = create_app(settings, production_runner=_RecordingRunner())
    with TestClient(app) as test_client:
        yield test_client


def test_api_rejects_hostile_production_id(client):
    # a percent-encoded traversal id never matches a route (safe 404 — the id
    # is never resolved against storage)
    response = client.get("/api/productions/prod_..%2F..%2Fetc/artifacts/master-video")
    assert response.status_code == 404
    # a malformed id that reaches route validation is rejected outright (422)
    response = client.get("/api/productions/prod_NOT_A_ULID/artifacts")
    assert response.status_code == 422


def test_api_responses_never_expose_filesystem_paths(client, settings):
    body = client.post("/api/productions", json={"mode": "genre", "genre": "lofi"}).json()
    production_id = body["id"]

    responses = [
        client.get("/api/productions").text,
        client.get(f"/api/productions/{production_id}").text,
    ]
    data_dir = settings.app_data_dir.as_posix()
    windows_dir = data_dir.replace("/", "\\")
    for text in responses:
        assert data_dir not in text
        assert windows_dir not in text
        assert "app.db" not in text
