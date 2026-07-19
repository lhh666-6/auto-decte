from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.domain.models import stable_json_sha256
from app.infrastructure.backup.integrity_ds import IntegrityChecker
from app.infrastructure.backup.service_ds import BackupService
from app.infrastructure.database.migrations import SchemaRevisionError, upgrade_database
from app.services.container import build_services
from config.settings import Settings


def _upgrade_to_revision(database_path: Path, revision: str) -> None:
    project_root = Path(__file__).resolve().parents[2]
    config = Config(str(project_root / "alembic.ini"))
    config.attributes["database_path"] = database_path.resolve()
    command.upgrade(config, revision)


def _downgrade_to_revision(database_path: Path, revision: str) -> None:
    project_root = Path(__file__).resolve().parents[2]
    config = Config(str(project_root / "alembic.ini"))
    config.attributes["database_path"] = database_path.resolve()
    command.downgrade(config, revision)


def test_alembic_upgrade_creates_task_and_review_lease_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "demo.db"

    upgrade_database(database_path)

    tables = set(inspect(create_engine(f"sqlite:///{database_path}")).get_table_names())
    assert {"tasks", "task_events", "review_leases"} <= tables


def test_alembic_upgrade_creates_template_version_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "template-schema.db"

    upgrade_database(database_path)

    tables = set(inspect(create_engine(f"sqlite:///{database_path}")).get_table_names())
    assert {
        "template_versions",
        "template_fields",
        "template_artifacts",
        "template_metadata",
    } <= tables
    version_columns = {
        column["name"]
        for column in inspect(create_engine(f"sqlite:///{database_path}")).get_columns(
            "template_versions"
        )
    }
    assert {"static_elements", "print_imposition"} <= version_columns


def test_alembic_upgrade_creates_job_profile_versions_without_changing_templates(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "job-profile-schema.db"
    _upgrade_to_revision(database_path, "008")
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO template_versions "
                "(version_id, template_key, version, status, page, parent_version_id, "
                "static_elements, print_imposition) VALUES "
                "('TPL-KEEP', 'CORE_TIMEKEEPING', 1, 'DRAFT', :page, NULL, '[]', NULL)"
            ),
            {
                "page": (
                    '{"size":"A5","orientation":"landscape","width_mm":210,'
                    '"height_mm":148,"canonical_dpi":300,"canonical_width_px":2480,'
                    '"canonical_height_px":1748}'
                )
            },
        )
    engine.dispose()

    upgrade_database(database_path)

    upgraded = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(upgraded)
    assert "job_profile_versions" in inspector.get_table_names()
    unique_columns = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints("job_profile_versions")
    }
    assert ("profile_key", "version") in unique_columns
    assert SqlAlchemyTemplateRepository(upgraded).get_version("TPL-KEEP") is not None
    with upgraded.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert revision == "010"
    upgraded.dispose()


def test_upgrade_010_preserves_forms_and_adds_optional_job_profile_identity(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "form-profile-identity.db"
    _upgrade_to_revision(database_path, "009")
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO forms "
                "(form_id, template_id, template_version, coordinate_version, "
                "review_status, export_status, current_record_version, priority, created_at) "
                "VALUES ('FORM-LEGACY', 'T1', '1', '1', 'IMPORTED', "
                "'NOT_EXPORTED', 0, 0, CURRENT_TIMESTAMP)"
            )
        )
    engine.dispose()

    upgrade_database(database_path)

    upgraded = create_engine(f"sqlite:///{database_path}")
    columns = {column["name"] for column in inspect(upgraded).get_columns("forms")}
    assert {"job_profile_key", "job_profile_version"} <= columns
    restored = SqlAlchemyFormRepository(upgraded).get_form("FORM-LEGACY")
    assert restored is not None
    assert restored.job_profile_key is None
    assert restored.job_profile_version is None


def test_upgrade_007_preserves_legacy_template_and_adds_layout_storage(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "template-layout-007.db"
    _upgrade_to_revision(database_path, "007")
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO template_versions "
                "(version_id, template_key, version, status, page, parent_version_id) "
                "VALUES ('TPL-LEGACY', 'PAYROLL_LEGACY', 1, 'PUBLISHED', "
                ":page, NULL)"
            ),
            {
                "page": (
                    '{"size":"A4","orientation":"portrait","width_mm":210,'
                    '"height_mm":297,"canonical_dpi":300,"canonical_width_px":2480,'
                    '"canonical_height_px":3508}'
                )
            },
        )
        connection.execute(
            text(
                "INSERT INTO template_fields "
                "(field_id, version_id, field_key, position, definition) VALUES "
                "('TPL-LEGACY:worker_name', 'TPL-LEGACY', 'worker_name', 0, :definition)"
            ),
            {
                "definition": (
                    '{"display_name":"姓名","data_type":"text",'
                    '"input_type":"text_box","recognition_engine":"manual",'
                    '"minimum_prefill_confidence":1.0,"rules":{},'
                    '"region":{"x":0.1,"y":0.2,"width":0.3,"height":0.05}}'
                )
            },
        )
    engine.dispose()

    upgrade_database(database_path)

    upgraded = create_engine(f"sqlite:///{database_path}")
    columns = {
        column["name"] for column in inspect(upgraded).get_columns("template_versions")
    }
    assert {"static_elements", "print_imposition"} <= columns
    loaded = SqlAlchemyTemplateRepository(upgraded).get_version("TPL-LEGACY")
    assert loaded is not None
    assert loaded.static_elements == []
    assert loaded.print_imposition is None
    assert loaded.fields[0].paper_entry_mode.value == "HANDWRITTEN_TEXT"
    assert loaded.fields[0].recognition_mode.value == "NONE"
    with upgraded.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert revision == "010"
    upgraded.dispose()


def test_alembic_upgrade_creates_review_drafts_and_form_priority(tmp_path: Path) -> None:
    database_path = tmp_path / "review-schema.db"

    upgrade_database(database_path)

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    assert "review_drafts" in inspector.get_table_names()
    assert "priority" in {column["name"] for column in inspector.get_columns("forms")}


def test_alembic_upgrade_creates_master_data_and_audit_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "master-data-schema.db"

    upgrade_database(database_path)

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    assert {"master_data_records", "master_data_audits"} <= set(
        inspector.get_table_names()
    )
    record_indexes = {item["name"] for item in inspector.get_indexes("master_data_records")}
    assert "ix_master_data_records_catalog_active_name" in record_indexes


def test_evidence_hash_is_unique_only_for_original_images(tmp_path: Path) -> None:
    database_path = tmp_path / "evidence-schema.db"
    upgrade_database(database_path)
    engine = create_engine(f"sqlite:///{database_path}")

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO forms "
                "(form_id, template_id, template_version, coordinate_version, "
                "review_status, export_status, current_record_version, priority, created_at) "
                "VALUES "
                "('FORM-1', 'T1', '1', '1', 'CLASSIFIED', 'NOT_EXPORTED', 0, 0, "
                "CURRENT_TIMESTAMP), "
                "('FORM-2', 'T1', '1', '1', 'CLASSIFIED', 'NOT_EXPORTED', 0, 0, "
                "CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO evidence_files "
                "(file_id, form_id, related_field_id, type, uri, sha256, immutable, created_at) "
                "VALUES "
                "('CROP-1', 'FORM-1', NULL, 'FIELD_CROP', 'crop-1.png', "
                "'same', 1, CURRENT_TIMESTAMP), "
                "('CROP-2', 'FORM-2', NULL, 'FIELD_CROP', 'crop-2.png', "
                "'same', 1, CURRENT_TIMESTAMP)"
            )
        )

    indexes = {item["name"]: item for item in inspect(engine).get_indexes("evidence_files")}
    assert not indexes["ix_evidence_files_sha256"]["unique"]
    assert indexes["ux_evidence_files_original_sha256"]["unique"]


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


def test_interrupted_empty_alembic_ledger_recovers_as_legacy_schema(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "demo.db"
    database_path.parent.mkdir(parents=True)
    engine = create_engine(f"sqlite:///{database_path}")
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
                "INSERT INTO forms VALUES ("
                "'FORM-INTERRUPTED', 'T1', '1', '1', 'NEEDS_REVIEW', "
                "'NOT_EXPORTED', 0, CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
    engine.dispose()

    services = build_services(Settings(data_root=tmp_path))

    assert services.repository.get_form("FORM-INTERRUPTED") is not None
    assert "review_drafts" in inspect(services.engine).get_table_names()


def test_auto_created_database_backfills_template_names(tmp_path: Path) -> None:
    database_path = tmp_path / "database" / "demo.db"
    database_path.parent.mkdir(parents=True)
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE template_versions ("
                "version_id VARCHAR PRIMARY KEY, template_key VARCHAR NOT NULL, "
                "version INTEGER NOT NULL, status VARCHAR NOT NULL, page JSON NOT NULL, "
                "parent_version_id VARCHAR, UNIQUE (template_key, version))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO template_versions VALUES ("
                "'TPL-1', 'PAYROLL_HOURLY', 1, 'PUBLISHED', '{}', NULL)"
            )
        )
    engine.dispose()

    services = build_services(Settings(data_root=tmp_path))

    assert services.template_repository.get_template_metadata("PAYROLL_HOURLY") == (
        "计时考核单",
        "适用于按工时统计的生产岗位",
    )


def test_production_mode_requires_current_alembic_revision(tmp_path: Path) -> None:
    database_path = tmp_path / "database" / "demo.db"
    upgrade_database(database_path)

    settings = Settings(data_root=tmp_path, environment="production", auto_create_schema=False)
    assert settings.environment == "production"
    assert settings.auto_create_schema is False
    services = build_services(settings)

    assert services.repository.list_export_batches() == []


def test_upgrade_006_export_batch_preserves_data_and_adds_snapshot_columns(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "export-batches-006.db"
    _upgrade_to_revision(database_path, "006")
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO export_batches "
                "(export_batch_id, export_type, filters, included_records, file_path, "
                "file_sha256, exported_by, exported_at, supersedes_batch_id) VALUES "
                "('EXPORT-LEGACY', 'OUTPUT', '{\"form_id\":\"FORM-1\"}', "
                "'[[\"FORM-1\",1]]', 'internal/legacy.xlsx', :sha256, 'finance', "
                "'2026-07-15 08:00:00', NULL)"
            ),
            {"sha256": "e" * 64},
        )
    engine.dispose()

    upgrade_database(database_path)

    upgraded = create_engine(f"sqlite:///{database_path}")
    columns = {item["name"] for item in inspect(upgraded).get_columns("export_batches")}
    assert {
        "task_id",
        "template_snapshot",
        "mapping_snapshot",
        "mapping_hash",
        "download_name",
    } <= columns
    batch = SqlAlchemyFormRepository(upgraded).get_export_batch("EXPORT-LEGACY")
    assert batch is not None
    assert batch.filters == {"form_id": "FORM-1"}
    assert batch.included_records == (("FORM-1", 1),)
    assert batch.task_id is None
    assert batch.template_snapshot == {}
    assert batch.mapping_snapshot == ()
    assert len(batch.mapping_hash) == 64
    assert batch.download_name == "export.xlsx"
    with upgraded.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert revision == "010"
    upgraded.dispose()

    _downgrade_to_revision(database_path, "006")

    downgraded = create_engine(f"sqlite:///{database_path}")
    downgraded_columns = {
        item["name"] for item in inspect(downgraded).get_columns("export_batches")
    }
    assert not {
        "task_id",
        "template_snapshot",
        "mapping_snapshot",
        "mapping_hash",
        "download_name",
    } & downgraded_columns
    with downgraded.connect() as connection:
        assert connection.execute(
            text("SELECT file_path FROM export_batches WHERE export_batch_id = 'EXPORT-LEGACY'")
        ).scalar_one() == "internal/legacy.xlsx"


def test_auto_created_legacy_export_batches_gain_snapshot_columns_without_data_loss(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "demo.db"
    database_path.parent.mkdir(parents=True)
    engine = create_engine(f"sqlite:///{database_path}")
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
                "CREATE TABLE export_batches ("
                "export_batch_id VARCHAR PRIMARY KEY, export_type VARCHAR NOT NULL, "
                "filters JSON NOT NULL, included_records JSON NOT NULL, "
                "file_path VARCHAR NOT NULL UNIQUE, file_sha256 VARCHAR(64) NOT NULL, "
                "exported_by VARCHAR NOT NULL, exported_at DATETIME NOT NULL, "
                "supersedes_batch_id VARCHAR)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO export_batches VALUES ("
                "'EXPORT-AUTO-LEGACY', 'OUTPUT', '{}', '[]', "
                "'internal/auto-legacy.xlsx', :sha256, 'finance', "
                "CURRENT_TIMESTAMP, NULL)"
            ),
            {"sha256": "f" * 64},
        )
    engine.dispose()

    services = build_services(Settings(data_root=tmp_path))

    batch = services.repository.get_export_batch("EXPORT-AUTO-LEGACY")
    assert batch is not None
    assert batch.file_path == "internal/auto-legacy.xlsx"
    assert batch.template_snapshot == {}
    assert batch.mapping_snapshot == ()
    assert batch.download_name == "export.xlsx"
    assert len(batch.mapping_hash) == 64
    assert {
        "task_id",
        "template_snapshot",
        "mapping_snapshot",
        "mapping_hash",
        "download_name",
    } <= {
        item["name"]
        for item in inspect(services.engine).get_columns("export_batches")
    }


def test_partial_export_batch_schema_backfills_actual_mapping_hash_idempotently(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "demo.db"
    database_path.parent.mkdir(parents=True)
    mapping_snapshot = [
        {
            "field_key": "employee_id",
            "target": {"worksheet": "employees", "business_column": "employee_code"},
        }
    ]
    engine = create_engine(f"sqlite:///{database_path}")
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
                "CREATE TABLE export_batches ("
                "export_batch_id VARCHAR PRIMARY KEY, export_type VARCHAR NOT NULL, "
                "filters JSON NOT NULL, included_records JSON NOT NULL, "
                "file_path VARCHAR NOT NULL UNIQUE, file_sha256 VARCHAR(64) NOT NULL, "
                "exported_by VARCHAR NOT NULL, exported_at DATETIME NOT NULL, "
                "supersedes_batch_id VARCHAR, mapping_snapshot JSON NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO export_batches "
                "(export_batch_id, export_type, filters, included_records, file_path, "
                "file_sha256, exported_by, exported_at, supersedes_batch_id, "
                "mapping_snapshot) VALUES ("
                "'EXPORT-PARTIAL', 'OUTPUT', '{}', '[]', "
                "'internal/partial.xlsx', :sha256, 'finance', CURRENT_TIMESTAMP, "
                "NULL, :mapping_snapshot)"
            ),
            {
                "sha256": "1" * 64,
                "mapping_snapshot": (
                    '[{"field_key":"employee_id","target":'
                    '{"worksheet":"employees","business_column":"employee_code"}}]'
                ),
            },
        )
    engine.dispose()
    expected_hash = stable_json_sha256(mapping_snapshot)

    services = build_services(Settings(data_root=tmp_path))

    batch = services.repository.get_export_batch("EXPORT-PARTIAL")
    assert batch is not None
    assert batch.mapping_snapshot == tuple(mapping_snapshot)
    assert batch.mapping_hash == expected_hash
    with services.engine.connect() as connection:
        persisted_hash = connection.execute(
            text(
                "SELECT mapping_hash FROM export_batches "
                "WHERE export_batch_id = 'EXPORT-PARTIAL'"
            )
        ).scalar_one()
    assert persisted_hash == expected_hash
    services.engine.dispose()

    rebuilt = build_services(Settings(data_root=tmp_path))

    reloaded = rebuilt.repository.get_export_batch("EXPORT-PARTIAL")
    assert reloaded is not None
    assert reloaded.mapping_hash == expected_hash


def test_partial_schema_replaces_empty_hash_placeholder_only_when_snapshot_nonempty(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "demo.db"
    database_path.parent.mkdir(parents=True)
    nonempty_snapshot = [
        {
            "field_key": "employee_id",
            "target": {"worksheet": "employees"},
        }
    ]
    empty_hash = stable_json_sha256([])
    expected_nonempty_hash = stable_json_sha256(nonempty_snapshot)
    engine = create_engine(f"sqlite:///{database_path}")
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
                "CREATE TABLE export_batches ("
                "export_batch_id VARCHAR PRIMARY KEY, export_type VARCHAR NOT NULL, "
                "filters JSON NOT NULL, included_records JSON NOT NULL, "
                "file_path VARCHAR NOT NULL UNIQUE, file_sha256 VARCHAR(64) NOT NULL, "
                "exported_by VARCHAR NOT NULL, exported_at DATETIME NOT NULL, "
                "supersedes_batch_id VARCHAR, mapping_snapshot JSON NOT NULL, "
                "mapping_hash VARCHAR(64) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO export_batches "
                "(export_batch_id, export_type, filters, included_records, file_path, "
                "file_sha256, exported_by, exported_at, supersedes_batch_id, "
                "mapping_snapshot, mapping_hash) VALUES "
                "('EXPORT-PLACEHOLDER', 'OUTPUT', '{}', '[]', "
                "'internal/placeholder.xlsx', :sha256_one, 'finance', CURRENT_TIMESTAMP, "
                "NULL, :mapping_snapshot, :empty_hash), "
                "('EXPORT-EMPTY', 'OUTPUT', '{}', '[]', "
                "'internal/empty.xlsx', :sha256_two, 'finance', CURRENT_TIMESTAMP, "
                "NULL, '[]', :empty_hash)"
            ),
            {
                "sha256_one": "3" * 64,
                "sha256_two": "4" * 64,
                "mapping_snapshot": (
                    '[{"field_key":"employee_id",'
                    '"target":{"worksheet":"employees"}}]'
                ),
                "empty_hash": empty_hash,
            },
        )
    engine.dispose()

    services = build_services(Settings(data_root=tmp_path))

    with services.engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT export_batch_id, mapping_hash FROM export_batches "
                "ORDER BY export_batch_id"
            )
        ).all()
        hashes = {batch_id: mapping_hash for batch_id, mapping_hash in rows}
    assert hashes == {
        "EXPORT-EMPTY": empty_hash,
        "EXPORT-PLACEHOLDER": expected_nonempty_hash,
    }
    assert services.repository.get_export_batch("EXPORT-PLACEHOLDER") is not None
    assert services.repository.get_export_batch("EXPORT-EMPTY") is not None
    services.engine.dispose()

    rebuilt = build_services(Settings(data_root=tmp_path))

    assert rebuilt.repository.get_export_batch("EXPORT-PLACEHOLDER").mapping_hash == (  # type: ignore[union-attr]
        expected_nonempty_hash
    )
    assert rebuilt.repository.get_export_batch("EXPORT-EMPTY").mapping_hash == empty_hash  # type: ignore[union-attr]


def test_partial_export_batch_schema_rejects_invalid_mapping_json_clearly(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "demo.db"
    database_path.parent.mkdir(parents=True)
    engine = create_engine(f"sqlite:///{database_path}")
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
                "CREATE TABLE export_batches ("
                "export_batch_id VARCHAR PRIMARY KEY, export_type VARCHAR NOT NULL, "
                "filters JSON NOT NULL, included_records JSON NOT NULL, "
                "file_path VARCHAR NOT NULL UNIQUE, file_sha256 VARCHAR(64) NOT NULL, "
                "exported_by VARCHAR NOT NULL, exported_at DATETIME NOT NULL, "
                "supersedes_batch_id VARCHAR, mapping_snapshot JSON NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO export_batches "
                "(export_batch_id, export_type, filters, included_records, file_path, "
                "file_sha256, exported_by, exported_at, supersedes_batch_id, "
                "mapping_snapshot) VALUES ("
                "'EXPORT-INVALID', 'OUTPUT', '{}', '[]', "
                "'internal/invalid.xlsx', :sha256, 'finance', CURRENT_TIMESTAMP, "
                "NULL, 'not-json')"
            ),
            {"sha256": "2" * 64},
        )
    engine.dispose()

    with pytest.raises(SchemaRevisionError, match="EXPORT-INVALID"):
        build_services(Settings(data_root=tmp_path))


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
