"""Back up and optionally remove files referenced by retired recognition evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _evidence_paths(database_path: Path, evidence_root: Path) -> list[Path]:
    with closing(sqlite3.connect(database_path)) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='legacy_archive_evidence_files'"
        ).fetchone()
        if exists is None:
            return []
        uris = connection.execute(
            "SELECT uri FROM legacy_archive_evidence_files ORDER BY uri"
        ).fetchall()
    root = evidence_root.resolve()
    paths: list[Path] = []
    for (uri,) in uris:
        candidate = Path(str(uri))
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        if resolved == root or root not in resolved.parents:
            continue
        if resolved.is_file():
            paths.append(resolved)
    return sorted(set(paths))


def retire(data_root: Path, output_dir: Path, *, apply: bool) -> dict[str, object]:
    data_root = data_root.resolve()
    database_path = data_root / "database" / "demo.db"
    evidence_root = data_root / "evidence"
    if not database_path.is_file():
        raise FileNotFoundError(database_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_path = output_dir / f"legacy-recognition-backup-{stamp}.zip"
    report_path = output_dir / f"legacy-recognition-cleanup-{stamp}.json"
    evidence_paths = _evidence_paths(database_path, evidence_root)

    with tempfile.TemporaryDirectory(prefix="legacy-recognition-") as temporary:
        snapshot = Path(temporary) / "demo.db"
        with (
            closing(sqlite3.connect(database_path)) as source,
            closing(sqlite3.connect(snapshot)) as target,
        ):
            sqlite3.Connection.backup(source, target)
        files = [
            {
                "path": str(path.relative_to(evidence_root.resolve())),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in evidence_paths
        ]
        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "database_sha256": _sha256(snapshot),
            "evidence_files": files,
        }
        with zipfile.ZipFile(
            archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            archive.write(snapshot, "database/demo.db")
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
            for path in evidence_paths:
                archive.write(
                    path,
                    f"evidence/{path.relative_to(evidence_root.resolve()).as_posix()}",
                )
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("backup archive verification failed")

    deleted: list[str] = []
    if apply:
        for path in evidence_paths:
            path.unlink()
            deleted.append(str(path))
    report = {
        "status": "APPLIED" if apply else "DRY_RUN",
        "backup_path": str(archive_path),
        "backup_sha256": _sha256(archive_path),
        "candidate_count": len(evidence_paths),
        "candidate_bytes": sum(path_info["size"] for path_info in files),
        "deleted_files": deleted,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {**report, "report_path": str(report_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="delete only archived legacy evidence after the verified backup is written",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            retire(args.data_root, args.output_dir, apply=args.apply),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
