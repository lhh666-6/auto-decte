"""SQLite online backup service with manifest tracking."""

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine


@dataclass
class BackupManifest:
    backup_id: str
    created_at: str
    created_by: str
    schema_revision: str
    database_file: str
    database_sha256: str
    evidence_files: list[dict[str, str]] = field(default_factory=list)
    export_files: list[dict[str, str]] = field(default_factory=list)
    size_bytes: int = 0
    status: str = "completed"


class BackupService:
    """Create SQLite Online Backup to a temporary directory with manifest."""

    def __init__(
        self,
        engine: Engine,
        evidence_root: Path,
        exports_root: Path,
        backup_root: Path | None = None,
    ) -> None:
        self._engine = engine
        self._evidence_root = evidence_root
        self._exports_root = exports_root
        self._backup_root = backup_root or (exports_root.parent / "backups")

    def create(self, created_by: str = "system") -> BackupManifest:
        backup_id = f"BACKUP-{uuid4().hex}"
        timestamp = datetime.now(UTC)
        destination = self._backup_root / backup_id
        destination.mkdir(parents=True, exist_ok=True)

        db_dest = destination / "demo.db"
        db_path = self._resolve_db_path()
        raw_conn = sqlite3.connect(str(db_dest))
        try:
            source_conn = sqlite3.connect(str(db_path))
            source_conn.backup(raw_conn, pages=64, progress=None)
            source_conn.close()
        finally:
            raw_conn.close()

        db_hash = hashlib.sha256(db_dest.read_bytes()).hexdigest()
        evidence_files = self._collect_files(self._evidence_root)
        export_files = self._collect_files(self._exports_root)
        self._copy_files(destination / "evidence", evidence_files)
        self._copy_files(destination / "exports", export_files)

        total_size = db_dest.stat().st_size
        for entry in evidence_files + export_files:
            total_size += int(entry.get("size", "0"))

        manifest = BackupManifest(
            backup_id=backup_id,
            created_at=timestamp.isoformat(),
            created_by=created_by,
            schema_revision="001",
            database_file=str(db_dest),
            database_sha256=db_hash,
            evidence_files=evidence_files,
            export_files=export_files,
            size_bytes=total_size,
        )
        manifest_path = destination / "manifest.json"
        manifest_path.write_text(
            json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return manifest

    def _resolve_db_path(self) -> Path:
        db_url = str(self._engine.url)
        if db_url.startswith("sqlite:///"):
            return Path(db_url[len("sqlite:///"):])
        return Path("data/database/demo.db")

    @staticmethod
    def _collect_files(root: Path) -> list[dict[str, str]]:
        if not root.exists():
            return []
        entries: list[dict[str, str]] = []
        for path in sorted(root.rglob("*")):
            if path.is_file():
                entries.append(
                    {
                        "path": str(path.relative_to(root)),
                        "full_path": str(path),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "size": str(path.stat().st_size),
                    }
                )
        return entries

    @staticmethod
    def _copy_files(destination: Path, files: list[dict[str, str]]) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        for entry in files:
            source = Path(entry["full_path"])
            target = destination / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
