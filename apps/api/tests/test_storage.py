"""Storage tests.

Phase 00: runtime directory layout (MAD-001 §11).
Phase 03: HashService / StorageService / ArtifactService covering write/read/
exists/delete/hash/size/metadata plus path-containment and the production
artifact layout (MASTER_EXECUTION.md §13, TDD-001 §62-65).
"""
from __future__ import annotations

import json

import pytest

from api.core.errors import StorageError
from api.core.hashing import HashService
from api.core.ids import new_production_id
from api.domain.production import Production
from api.storage.artifacts import PRODUCTION_SUBDIRS, ArtifactKind, ArtifactService
from api.storage.layout import RUNTIME_DIR_NAMES, ensure_runtime_dirs, runtime_dirs
from api.storage.storage import StorageService


# --- Phase 00: runtime directory layout -----------------------------------------

def test_runtime_dirs_created(settings):
    paths = ensure_runtime_dirs(settings)
    assert len(paths) == len(RUNTIME_DIR_NAMES)
    for name, path in runtime_dirs(settings).items():
        assert path.is_dir(), f"{name} was not created"


def test_ensure_runtime_dirs_idempotent(settings):
    first = ensure_runtime_dirs(settings)
    second = ensure_runtime_dirs(settings)
    assert [p.as_posix() for p in first] == [p.as_posix() for p in second]


def test_required_dir_names():
    assert set(RUNTIME_DIR_NAMES) == {
        "database",
        "productions",
        "assets",
        "cache",
        "logs",
        "temp",
    }


# --- HashService ----------------------------------------------------------------

def test_sha256_bytes_known_digest():
    # SHA-256("abc") is a well-known test vector.
    assert HashService().sha256_bytes(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_sha256_file_matches_bytes(tmp_path):
    path = tmp_path / "sample.bin"
    path.write_bytes(b"hello world")
    service = HashService()
    assert service.sha256_file(path) == service.sha256_bytes(b"hello world")


def test_sha256_text_stable():
    assert HashService().sha256_text("lofi") == HashService().sha256_text("lofi")


def test_verify_matches(tmp_path):
    path = tmp_path / "f.bin"
    path.write_bytes(b"data")
    service = HashService()
    assert service.verify(path, service.sha256_file(path)) is True
    assert service.verify(path, "0" * 64) is False


# --- StorageService --------------------------------------------------------------

@pytest.fixture
def storage(tmp_path) -> StorageService:
    return StorageService(tmp_path / "root")


def test_write_read_bytes(storage):
    storage.ensure_root()
    storage.write("audio/master.wav", b"\x00\x01\x02")
    assert storage.read("audio/master.wav") == b"\x00\x01\x02"


def test_write_read_text(storage):
    storage.write_text("metadata.json", '{"k": "v"}')
    assert json.loads(storage.read_text("metadata.json")) == {"k": "v"}


def test_write_creates_parents(storage):
    storage.write("a/b/c/file.bin", b"x")
    assert (storage.root / "a" / "b" / "c" / "file.bin").is_file()


def test_exists(storage):
    assert storage.exists("missing.bin") is False
    storage.write("present.bin", b"x")
    assert storage.exists("present.bin") is True


def test_delete(storage):
    storage.write("temp.bin", b"x")
    assert storage.delete("temp.bin") is True
    assert storage.exists("temp.bin") is False
    assert storage.delete("temp.bin") is False


def test_size_and_hash(storage):
    storage.write("payload.bin", b"abc")
    assert storage.size("payload.bin") == 3
    service = HashService()
    assert storage.hash("payload.bin") == service.sha256_bytes(b"abc")


def test_metadata_fields(storage):
    storage.write("video.mp4", b"\x00" * 8)
    meta = storage.metadata("video.mp4")
    assert meta["size_bytes"] == 8
    assert len(meta["sha256"]) == 64
    assert meta["path"] == "video.mp4"
    assert meta["mime_type"] == "video/mp4"
    assert meta["modified_at"]


def test_read_missing_raises(storage):
    with pytest.raises(StorageError):
        storage.read("nope.bin")


def test_size_missing_raises(storage):
    with pytest.raises(StorageError):
        storage.size("nope.bin")


def test_hash_missing_raises(storage):
    with pytest.raises(StorageError):
        storage.hash("nope.bin")


def test_metadata_missing_raises(storage):
    with pytest.raises(StorageError):
        storage.metadata("nope.bin")


def test_path_traversal_rejected(storage):
    storage.ensure_root()
    with pytest.raises(StorageError):
        storage.write("../escape.bin", b"x")


def test_absolute_path_outside_root_rejected(storage):
    storage.ensure_root()
    with pytest.raises(StorageError):
        storage.read(str(storage.root.parent / "secret.bin"))


# --- ArtifactService ---------------------------------------------------------------

@pytest.fixture
def artifact_service(tmp_path) -> ArtifactService:
    storage = StorageService(tmp_path / "root")
    productions_root = tmp_path / "data" / "productions"
    return ArtifactService(storage, productions_root)


def test_ensure_production_dirs_creates_layout(artifact_service):
    production_id = new_production_id()
    created = artifact_service.ensure_production_dirs(production_id)
    assert len(created) == 1 + len(PRODUCTION_SUBDIRS)
    for subdir in PRODUCTION_SUBDIRS:
        assert (artifact_service.production_dir(production_id) / subdir).is_dir()


def test_invalid_production_id_rejected(artifact_service):
    with pytest.raises(StorageError):
        artifact_service.production_dir("prod_short")


def test_artifact_round_trip(artifact_service):
    production_id = new_production_id()
    artifact_service.write(production_id, ArtifactKind.AUDIO_MASTER, b"\x01\x02")
    assert artifact_service.exists(production_id, ArtifactKind.AUDIO_MASTER)
    assert artifact_service.read(production_id, ArtifactKind.AUDIO_MASTER) == b"\x01\x02"
    assert artifact_service.size(production_id, ArtifactKind.AUDIO_MASTER) == 2
    assert artifact_service.delete(production_id, ArtifactKind.AUDIO_MASTER) is True
    assert artifact_service.exists(production_id, ArtifactKind.AUDIO_MASTER) is False


def test_artifact_text_round_trip(artifact_service):
    production_id = new_production_id()
    document = {"status": "completed"}
    artifact_service.write_text(production_id, ArtifactKind.PRODUCTION, json.dumps(document))
    loaded = json.loads(artifact_service.read_text(production_id, ArtifactKind.PRODUCTION))
    assert loaded == document


def test_artifact_hash_matches(artifact_service):
    production_id = new_production_id()
    artifact_service.write(production_id, ArtifactKind.MANIFEST, b"manifest-body")
    service = HashService()
    assert artifact_service.hash(production_id, ArtifactKind.MANIFEST) == service.sha256_bytes(
        b"manifest-body"
    )


def test_artifact_metadata(artifact_service):
    production_id = new_production_id()
    artifact_service.write(production_id, ArtifactKind.QC_REPORT, b"ok")
    meta = artifact_service.metadata(production_id, ArtifactKind.QC_REPORT)
    assert meta["size_bytes"] == 2
    assert meta["path"] == "qc/qc-report.json"
    assert meta["mime_type"] == "application/json"


def test_deterministic_paths(artifact_service):
    production_id = new_production_id()
    assert artifact_service.path_for(production_id, ArtifactKind.MASTER_VIDEO).name == "master-16x9.mp4"
    assert artifact_service.path_for(production_id, ArtifactKind.SHORT_VIDEO).name == "short-9x16.mp4"
    assert artifact_service.path_for(production_id, ArtifactKind.BACKGROUND).name == "background.png"
    assert artifact_service.path_for(production_id, ArtifactKind.VISUALIZER_DATA).name == "visualizer.json"
    assert artifact_service.path_for(production_id, ArtifactKind.METADATA).name == "metadata.json"
    assert artifact_service.path_for(production_id, ArtifactKind.QC_REPORT).name == "qc-report.json"


def test_delete_production_dir(artifact_service):
    production_id = new_production_id()
    artifact_service.write(production_id, ArtifactKind.METADATA, b"x")
    assert artifact_service.delete_production_dir(production_id) is True
    assert artifact_service.production_dir(production_id).exists() is False


def test_delete_production_dir_missing_returns_false(artifact_service):
    assert artifact_service.delete_production_dir(new_production_id()) is False


def test_artifact_service_integration_with_domain(tmp_path):
    """A production's artifacts live under data/productions/<id>/."""
    production = Production(mode="genre", genre="lofi")
    storage = StorageService(tmp_path / "root")
    artifact_service = ArtifactService(storage, tmp_path / "data" / "productions")

    artifact_service.write_text(
        production.id, ArtifactKind.PRODUCTION, production.model_dump_json()
    )
    loaded = Production.model_validate_json(
        artifact_service.read_text(production.id, ArtifactKind.PRODUCTION)
    )
    assert loaded.id == production.id
    assert loaded.genre == "lofi"
