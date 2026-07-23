"""The head migration preserves legacy rows in read-only archive tables."""

from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.infrastructure.database.migrations import HEAD_REVISION, upgrade_database
from app.services.container import build_services
from config.settings import Settings


def test_head_archives_legacy_tables_and_records_counts(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    database_path = data_root / "database" / "demo.db"
    upgrade_database(database_path)
    engine = create_engine(f"sqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    assert "recognition_attempts" not in tables
    assert "tasks" not in tables
    assert "export_batches" not in tables
    assert {
        "legacy_archive_recognition_attempts",
        "legacy_archive_evidence_files",
        "legacy_archive_tasks",
        "legacy_archive_export_batches",
        "legacy_retirement_manifest",
    } <= tables
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            HEAD_REVISION
        )
        counts = connection.execute(
            text(
                "SELECT table_name, row_count FROM legacy_retirement_manifest "
                "ORDER BY table_name"
            )
        ).all()
    assert len(counts) == 8
    assert all(row_count == 0 for _, row_count in counts)
    services = build_services(
        Settings(data_root=data_root, auto_create_schema=False)
    )
    services.engine.dispose()
