"""ArtifactService — production artifact layout and naming.

Layout matches TDD-001 §62 / MASTER_EXECUTION.md §13:

    data/productions/<production-id>/
    ├── input/       raw source material (downloads)
    ├── planning/    production-plan.json, strategies, concept, trends
    ├── audio/       source + master audio, analysis
    ├── visual/      background, radio, visualizer data
    ├── render/      master-16x9.mp4, short-9x16.mp4
    ├── metadata/    metadata.json
    ├── qc/          qc-report.json
    └── manifest/    production.json

Artifacts use the deterministic names from TDD-001 §63 so paths are stable and
reproducible. The service delegates file operations to a :class:`StorageService`
bounded to the production's directory.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

from api.core.errors import StorageError
from api.core.ids import PRODUCTION_ID_PATTERN
from api.storage.storage import StorageService

PRODUCTION_SUBDIRS: tuple[str, ...] = (
    "input",
    "planning",
    "audio",
    "visual",
    "render",
    "metadata",
    "qc",
    "manifest",
)


class ArtifactKind(str, Enum):
    """Canonical artifacts with their subdirectory and deterministic filename
    (TDD-001 §63). The enum value is the filename; ``subdir`` is the folder."""

    PRODUCTION = ("planning", "production-plan.json")
    TREND_RESULT = ("planning", "trend-result.json")
    CREATIVE_CONCEPT = ("planning", "concept.json")
    MUSIC_STRATEGY = ("planning", "music-strategy.json")
    VISUAL_STRATEGY = ("planning", "visual-strategy.json")
    SHORT_SEGMENT = ("planning", "short-segment.json")
    AUDIO_SOURCE = ("audio", "source.wav")
    AUDIO_MASTER = ("audio", "audio-master.wav")
    AUDIO_MASTER_REPORT = ("audio", "audio-master-report.json")
    AUDIO_ANALYSIS = ("audio", "audio-analysis.json")
    BACKGROUND = ("visual", "background.png")
    BACKGROUND_PROMPT = ("visual", "background-prompt.json")
    RADIO = ("visual", "radio.png")
    VISUALIZER_DATA = ("visual", "visualizer.json")
    VISUALIZER_LAYER = ("visual", "visualizer-layer.json")
    MASTER_VIDEO = ("render", "master-16x9.mp4")
    SHORT_VIDEO = ("render", "short-9x16.mp4")
    METADATA = ("metadata", "metadata.json")
    QC_REPORT = ("qc", "qc-report.json")
    MANIFEST = ("manifest", "production.json")

    def __new__(cls, subdir: str, filename: str) -> "ArtifactKind":
        obj = str.__new__(cls, filename)
        obj._value_ = filename
        obj.subdir = subdir
        return obj

    def __str__(self) -> str:  # pragma: no cover - explicit for readability
        return self.value


class ArtifactService:
    """Manages a production's artifact directory and named artifact files."""

    def __init__(self, storage: StorageService, productions_root: Path) -> None:
        self._storage = storage
        self._productions_root = Path(productions_root).resolve()

    # --- layout -------------------------------------------------------------

    def production_dir(self, production_id: str) -> Path:
        """Return the production's root directory (no filesystem side effects)."""
        if PRODUCTION_ID_PATTERN.match(production_id) is None:
            raise StorageError(f"invalid production id: {production_id!r}")
        return self._productions_root / production_id

    def ensure_production_dirs(self, production_id: str) -> list[Path]:
        """Create the production directory and its eight subdirectories."""
        root = self.production_dir(production_id)
        created = [root]
        for subdir in PRODUCTION_SUBDIRS:
            path = root / subdir
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
        return created

    def subdir(self, production_id: str, subdir: str) -> Path:
        """Return a production subdirectory (e.g. 'audio'), verifying containment."""
        if subdir not in PRODUCTION_SUBDIRS:
            raise StorageError(f"unknown production subdirectory: {subdir!r}")
        return self.production_dir(production_id) / subdir

    # --- per-production storage --------------------------------------------

    def _storage_for(self, production_id: str) -> StorageService:
        return StorageService(self.production_dir(production_id))

    # --- artifact operations --------------------------------------------------

    def path_for(self, production_id: str, kind: ArtifactKind) -> Path:
        """Return the absolute path for a named artifact (no side effects)."""
        return self._storage_for(production_id)._resolve(Path(kind.subdir) / kind.value)

    def write(self, production_id: str, kind: ArtifactKind, data: bytes) -> Path:
        """Write a binary artifact, creating the production tree as needed."""
        self.ensure_production_dirs(production_id)
        return self._storage_for(production_id).write(Path(kind.subdir) / kind.value, data)

    def write_text(self, production_id: str, kind: ArtifactKind, text: str) -> Path:
        """Write a text artifact (JSON documents)."""
        return self.write(production_id, kind, text.encode("utf-8"))

    def read(self, production_id: str, kind: ArtifactKind) -> bytes:
        return self._storage_for(production_id).read(Path(kind.subdir) / kind.value)

    def read_text(self, production_id: str, kind: ArtifactKind) -> str:
        return self.read(production_id, kind).decode("utf-8")

    def exists(self, production_id: str, kind: ArtifactKind) -> bool:
        return self._storage_for(production_id).exists(Path(kind.subdir) / kind.value)

    def delete(self, production_id: str, kind: ArtifactKind) -> bool:
        return self._storage_for(production_id).delete(Path(kind.subdir) / kind.value)

    def hash(self, production_id: str, kind: ArtifactKind) -> str:
        return self._storage_for(production_id).hash(Path(kind.subdir) / kind.value)

    def size(self, production_id: str, kind: ArtifactKind) -> int:
        return self._storage_for(production_id).size(Path(kind.subdir) / kind.value)

    def metadata(self, production_id: str, kind: ArtifactKind) -> dict[str, object]:
        return self._storage_for(production_id).metadata(Path(kind.subdir) / kind.value)

    def delete_production_dir(self, production_id: str) -> bool:
        """Remove the whole production directory tree, returning True if it existed."""
        root = self.production_dir(production_id)
        if not root.exists():
            return False
        import shutil

        shutil.rmtree(root)
        return True
