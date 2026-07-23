"""Verified backup must precede legacy evidence deletion."""

import sqlite3
import zipfile
from pathlib import Path

from scripts.retire_legacy_recognition import retire


def test_cleanup_backs_up_exact_archived_evidence_before_deletion(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    database_path = data_root / "database" / "demo.db"
    evidence_root = data_root / "evidence"
    database_path.parent.mkdir(parents=True)
    evidence_root.mkdir(parents=True)
    retired = evidence_root / "legacy.jpg"
    retained = evidence_root / "mobile-current.jpg"
    retired.write_bytes(b"legacy")
    retained.write_bytes(b"mobile")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE legacy_archive_evidence_files "
            "(file_id TEXT PRIMARY KEY, uri TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO legacy_archive_evidence_files VALUES (?, ?)",
            ("legacy-1", str(retired)),
        )

    result = retire(data_root, tmp_path / "backups", apply=True)

    assert result["status"] == "APPLIED"
    assert not retired.exists()
    assert retained.exists()
    with zipfile.ZipFile(str(result["backup_path"])) as archive:
        assert archive.testzip() is None
        assert "database/demo.db" in archive.namelist()
        assert "evidence/legacy.jpg" in archive.namelist()
