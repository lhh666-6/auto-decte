"""SQLite online backup service with manifest tracking."""

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from shutil import copy2
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


@dataclass(frozen=True, slots=True)
class RestorePlan:
    """A verified restore staged outside the active data root."""

    backup_id: str
    restore_root: Path
    database_path: Path
    evidence_root: Path
    exports_root: Path


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
        staging = self._backup_root / f".{backup_id}.staging"
        staging.mkdir(parents=True, exist_ok=False)

        db_dest = staging / "demo.db"
        db_path = self._resolve_db_path()
        raw_conn = sqlite3.connect(str(db_dest))
        source_conn: sqlite3.Connection | None = None
        try:
            source_conn = sqlite3.connect(str(db_path))
            source_conn.backup(raw_conn, pages=64, progress=None)
        finally:
            if source_conn is not None:
                source_conn.close()
            raw_conn.close()

        db_hash = hashlib.sha256(db_dest.read_bytes()).hexdigest()
        evidence_files = self._collect_files(self._evidence_root)
        export_files = self._collect_files(self._exports_root)
        self._copy_files(self._evidence_root, staging / "evidence", evidence_files)
        self._copy_files(self._exports_root, staging / "exports", export_files)

        total_size = db_dest.stat().st_size
        for entry in evidence_files + export_files:
            total_size += int(entry.get("size", "0"))

        manifest = BackupManifest(
            backup_id=backup_id,
            created_at=timestamp.isoformat(),
            created_by=created_by,
            schema_revision="001",
            database_file="demo.db",
            database_sha256=db_hash,
            evidence_files=evidence_files,
            export_files=export_files,
            size_bytes=total_size,
        )
        manifest_path = staging / "manifest.json"
        temporary_manifest = staging / ".manifest.json.tmp"
        temporary_manifest.write_text(
            json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary_manifest.replace(manifest_path)
        staging.replace(destination)
        return manifest

    def restore_to(self, manifest: BackupManifest, restore_root: Path) -> RestorePlan:
        """Verify a backup and restore it into a new directory without switching live data."""
        source = self._backup_root / manifest.backup_id
        self._verify_backup(source, manifest)
        if restore_root.exists():
            raise FileExistsError(f"Restore target already exists: {restore_root}")
        staging = restore_root.parent / f".{restore_root.name}.staging-{uuid4().hex}"
        staging.mkdir(parents=True, exist_ok=False)
        try:
            database_dir = staging / "database"
            database_dir.mkdir()
            copy2(source / manifest.database_file, database_dir / "demo.db")
            self._copy_files(source / "evidence", staging / "evidence", manifest.evidence_files)
            self._copy_files(source / "exports", staging / "exports", manifest.export_files)
            staging.replace(restore_root)
        except Exception:
            if staging.exists():
                import shutil

                shutil.rmtree(staging)
            raise
        return RestorePlan(
            backup_id=manifest.backup_id,
            restore_root=restore_root,
            database_path=restore_root / "database" / "demo.db",
            evidence_root=restore_root / "evidence",
            exports_root=restore_root / "exports",
        )

    def _resolve_db_path(self) -> Path:
        database = self._engine.url.database
        if database is None:
            raise ValueError("BackupService requires a file-backed SQLite database")
        return Path(database)

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
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "size": str(path.stat().st_size),
                    }
                )
        return entries

    @staticmethod
    def _copy_files(source_root: Path, destination: Path, files: list[dict[str, str]]) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        for entry in files:
            source = source_root / entry["path"]
            target = destination / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            copy2(source, target)

    @staticmethod
    def _verify_backup(source: Path, manifest: BackupManifest) -> None:
        database = source / manifest.database_file
        if (
            not database.exists()
            or hashlib.sha256(database.read_bytes()).hexdigest() != manifest.database_sha256
        ):
            raise ValueError("Backup database hash does not match manifest")
        for category, entries in (
            ("evidence", manifest.evidence_files),
            ("exports", manifest.export_files),
        ):
            for entry in entries:
                file_path = source / category / entry["path"]
                if not file_path.exists():
                    raise ValueError(f"Backup file is missing: {category}/{entry['path']}")
                if hashlib.sha256(file_path.read_bytes()).hexdigest() != entry["sha256"]:
                    raise ValueError(f"Backup file hash does not match: {category}/{entry['path']}")
