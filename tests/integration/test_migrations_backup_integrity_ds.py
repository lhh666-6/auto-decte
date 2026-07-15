from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.infrastructure.backup.integrity_ds import IntegrityChecker
from app.infrastructure.backup.service_ds import BackupService
from app.infrastructure.database.migrations import upgrade_database
from app.services.container import build_services
from config.settings import Settings


def test_alembic_upgrade_creates_task_and_review_lease_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "demo.db"

    upgrade_database(database_path)

    tables = set(inspect(create_engine(f"sqlite:///{database_path}")).get_table_names())
    assert {"tasks", "task_events", "review_leases"} <= tables


def test_alembic_upgrade_creates_template_version_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "template-schema.db"

    upgrade_database(database_path)

    tables = set(inspect(create_engine(f"sqlite:///{database_path}")).get_table_names())
    assert {"template_versions", "template_fields", "template_artifacts"} <= tables


def test_alembic_upgrade_creates_review_drafts_and_form_priority(tmp_path: Path) -> None:
    database_path = tmp_path / "review-schema.db"

    upgrade_database(database_path)

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    assert "review_drafts" in inspector.get_table_names()
    assert "priority" in {column["name"] for column in inspector.get_columns("forms")}


def test_auto_created_legacy_database_gains_priority_without_losing_forms(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "demo.db"
    database_path.parent.mkdir(parents=True)
    engine = create_engine(f"sqlite:///{database_path}")
    created_at = datetime(2026, 7, 15, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE forms ("
                "form_id VARCHAR PRIMARY KEY, template_id VARCHAR NOT NULL, "
                "template_version VARCHAR NOT NULL, coordinate_version VARCHAR NOT NULL, "
                "review_status VARCHAR NOT NULL, export_status VARCHAR NOT NULL, "
                "current_record_version INTEGER NOT NULL, created_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO forms VALUES "
                "('FORM-LEGACY', 'T1', '1', '1', 'NEEDS_REVIEW', "
                "'NOT_EXPORTED', 0, :created_at)"
            ),
            {"created_at": created_at},
        )
    engine.dispose()

    services = build_services(Settings(data_root=tmp_path))

    form = services.repository.get_form("FORM-LEGACY")
    assert form is not None
    assert form.priority == 0
    assert "review_drafts" in inspect(services.engine).get_table_names()


def test_production_mode_requires_current_alembic_revision(tmp_path: Path) -> None:
    database_path = tmp_path / "database" / "demo.db"
    upgrade_database(database_path)

    settings = Settings(data_root=tmp_path, environment="production", auto_create_schema=False)
    assert settings.environment == "production"
    assert settings.auto_create_schema is False
    services = build_services(settings)

    assert services.repository.list_export_batches() == []


def test_backup_restores_to_staging_and_detects_missing_evidence(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path / "source"))
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    services.imports.import_image(image, "FORM-1", "T1", "1", "operator-a")
    backup = BackupService(
        services.engine,
        services.settings.evidence_root,
        services.settings.exports_root,
        backup_root=tmp_path / "backups",
    )

    manifest = backup.create("operator-a")
    plan = backup.restore_to(manifest, tmp_path / "restored")

    restored_engine = create_engine(f"sqlite:///{plan.database_path}")
    restored_report = IntegrityChecker(
        restored_engine,
        plan.evidence_root,
        plan.exports_root,
    ).run()
    assert restored_report.exit_code == 0

    next(services.settings.evidence_root.rglob("*.*")).unlink()
    source_report = IntegrityChecker(
        services.engine,
        services.settings.evidence_root,
        services.settings.exports_root,
    ).run()
    assert source_report.exit_code != 0


def test_integrity_detects_invalid_version_pointer_and_expired_lease(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    services.imports.import_image(image, "FORM-1", "T1", "1", "operator-a")
    now = datetime.now(UTC)
    with services.engine.begin() as connection:
        connection.execute(
            text("UPDATE forms SET current_record_version = 3 WHERE form_id = 'FORM-1'")
        )
        connection.execute(
            text(
                "INSERT INTO review_leases "
                "(form_id, owner_id, lease_token, acquired_at, expires_at, heartbeat_at) "
                "VALUES (:form_id, :owner_id, :lease_token, :acquired_at, "
                ":expires_at, :heartbeat_at)"
            ),
            {
                "form_id": "FORM-1",
                "owner_id": "reviewer-a",
                "lease_token": "expired-token",
                "acquired_at": now - timedelta(minutes=10),
                "expires_at": now - timedelta(minutes=5),
                "heartbeat_at": now - timedelta(minutes=10),
            },
        )

    report = IntegrityChecker(
        services.engine,
        services.settings.evidence_root,
        services.settings.exports_root,
    ).run()

    assert {issue.code for issue in report.issues} >= {
        "INVALID_VERSION_POINTER",
        "EXPIRED_REVIEW_LEASE",
    }
