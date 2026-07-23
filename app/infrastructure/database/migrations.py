"""Programmatic Alembic migration entrypoints for local deployments and tests."""

import json
from pathlib import Path

from alembic.config import Config
from sqlalchemy import Connection, Engine, inspect, text

from alembic import command
from app.domain.models import stable_json_sha256

HEAD_REVISION = "027"
LEGACY_RETIREMENT_SOURCE_REVISION = "026"
LEGACY_RETIREMENT_TABLES = frozenset(
    {
        "recognition_attempts",
        "evidence_files",
        "ai_reviews",
        "review_leases",
        "review_drafts",
        "task_events",
        "tasks",
        "export_batches",
    }
)

_EMPTY_MAPPING_HASH = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"


class SchemaRevisionError(RuntimeError):
    pass


def _archive_duplicate_bamboo_mobile_records(connection: Connection) -> None:
    rows = connection.execute(
        text(
            "SELECT record_id, created_by, source_ref "
            "FROM bamboo_records "
            "WHERE source_type = 'MOBILE_CREATED' "
            "AND source_ref IS NOT NULL AND source_ref <> '' "
            "ORDER BY created_by, source_ref, created_at, record_id"
        )
    ).mappings().all()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row["created_by"]), str(row["source_ref"]))
        if key not in seen:
            seen.add(key)
            continue
        connection.execute(
            text(
                "UPDATE bamboo_records "
                "SET source_type = 'MOBILE_CREATED_DUPLICATE', "
                "source_ref = :source_ref "
                "WHERE record_id = :record_id"
            ),
            {
                "record_id": row["record_id"],
                "source_ref": f"{row['source_ref']}#duplicate:{row['record_id']}",
            },
        )


def is_alembic_managed(engine: Engine) -> bool:
    """Return whether this database has a populated Alembic revision ledger."""
    if "alembic_version" not in inspect(engine).get_table_names():
        return False
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).scalar()
    return bool(revision)


def ensure_auto_created_schema_compatibility(engine: Engine) -> None:
    """Add columns that SQLAlchemy create_all cannot add to legacy local databases."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "mobile_access_profiles" in tables:
        profile_columns = {
            column["name"]
            for column in inspector.get_columns("mobile_access_profiles")
        }
        with engine.begin() as connection:
            if "factory_id" not in profile_columns:
                connection.execute(
                    text(
                        "ALTER TABLE mobile_access_profiles "
                        "ADD COLUMN factory_id VARCHAR NOT NULL DEFAULT ''"
                    )
                )
            if "factory_name" not in profile_columns:
                connection.execute(
                    text(
                        "ALTER TABLE mobile_access_profiles "
                        "ADD COLUMN factory_name VARCHAR NOT NULL DEFAULT ''"
                    )
                )
    if "forms" in tables:
        form_columns = {column["name"] for column in inspector.get_columns("forms")}
        with engine.begin() as connection:
            if "priority" not in form_columns:
                connection.execute(
                    text(
                        "ALTER TABLE forms ADD COLUMN priority "
                        "INTEGER NOT NULL DEFAULT 0"
                    )
                )
            if "job_profile_key" not in form_columns:
                connection.execute(
                    text("ALTER TABLE forms ADD COLUMN job_profile_key VARCHAR")
                )
            if "job_profile_version" not in form_columns:
                connection.execute(
                    text("ALTER TABLE forms ADD COLUMN job_profile_version VARCHAR")
                )
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "bamboo_records" in tables:
        bamboo_columns = {
            column["name"] for column in inspector.get_columns("bamboo_records")
        }
        with engine.begin() as connection:
            if "form_type" not in bamboo_columns:
                connection.execute(
                    text(
                        "ALTER TABLE bamboo_records ADD COLUMN form_type "
                        "VARCHAR NOT NULL DEFAULT 'SORTING'"
                    )
                )
            if "production_object_id" not in bamboo_columns:
                connection.execute(
                    text(
                        "ALTER TABLE bamboo_records ADD COLUMN "
                        "production_object_id VARCHAR"
                    )
                )
            if "source_record_id" not in bamboo_columns:
                connection.execute(
                    text("ALTER TABLE bamboo_records ADD COLUMN source_record_id VARCHAR")
                )
            if "source_snapshot" not in bamboo_columns:
                connection.execute(
                    text(
                        "ALTER TABLE bamboo_records ADD COLUMN source_snapshot "
                        "JSON NOT NULL DEFAULT '{}'"
                    )
                )
            connection.execute(
                text(
                    "UPDATE bamboo_records SET form_type = 'SORTING' "
                    "WHERE form_type IS NULL OR form_type = ''"
                )
            )
            connection.execute(
                text(
                    "UPDATE bamboo_records SET production_object_id = record_id "
                    "WHERE production_object_id IS NULL OR production_object_id = ''"
                )
            )
            connection.execute(
                text(
                    "UPDATE bamboo_records SET source_snapshot = '{}' "
                    "WHERE source_snapshot IS NULL"
                )
            )
        inspector = inspect(engine)
        bamboo_indexes = {
            item["name"] for item in inspector.get_indexes("bamboo_records")
        }
        if "ix_bamboo_records_source_lookup" not in bamboo_indexes:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX ix_bamboo_records_source_lookup "
                        "ON bamboo_records (form_type, source_record_id)"
                    )
                )
        if "ux_bamboo_records_mobile_create_idempotency" not in bamboo_indexes:
            with engine.begin() as connection:
                _archive_duplicate_bamboo_mobile_records(connection)
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX "
                        "ux_bamboo_records_mobile_create_idempotency "
                        "ON bamboo_records (created_by, source_type, source_ref) "
                        "WHERE source_type = 'MOBILE_CREATED' "
                        "AND source_ref IS NOT NULL AND source_ref <> ''"
                    )
                )
    inspector = inspect(engine)
    if "evidence_files" in inspector.get_table_names():
        evidence_indexes = {item["name"]: item for item in inspector.get_indexes("evidence_files")}
        sha_index = evidence_indexes.get("ix_evidence_files_sha256")
        with engine.begin() as connection:
            if sha_index is not None and sha_index.get("unique"):
                connection.execute(text("DROP INDEX ix_evidence_files_sha256"))
                connection.execute(
                    text("CREATE INDEX ix_evidence_files_sha256 ON evidence_files (sha256)")
                )
            if "ux_evidence_files_original_sha256" not in evidence_indexes:
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX ux_evidence_files_original_sha256 "
                        "ON evidence_files (sha256) WHERE type = 'ORIGINAL_IMAGE'"
                    )
                )
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "export_batches" in tables:
        export_columns = {
            column["name"] for column in inspector.get_columns("export_batches")
        }
        mapping_hash_was_missing = "mapping_hash" not in export_columns
        missing_columns = {
            "task_id": "VARCHAR",
            "template_snapshot": "JSON NOT NULL DEFAULT '{}'",
            "mapping_snapshot": "JSON NOT NULL DEFAULT '[]'",
            "mapping_hash": (
                f"VARCHAR(64) NOT NULL DEFAULT '{_EMPTY_MAPPING_HASH}'"
            ),
            "download_name": "VARCHAR NOT NULL DEFAULT 'export.xlsx'",
        }
        with engine.begin() as connection:
            for column_name, definition in missing_columns.items():
                if column_name not in export_columns:
                    connection.execute(
                        text(
                            f"ALTER TABLE export_batches ADD COLUMN "
                            f"{column_name} {definition}"
                        )
                    )
            connection.execute(
                text(
                    "UPDATE export_batches SET template_snapshot = '{}' "
                    "WHERE template_snapshot IS NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE export_batches SET mapping_snapshot = '[]' "
                    "WHERE mapping_snapshot IS NULL"
                )
            )
            rows = connection.execute(
                text(
                    "SELECT export_batch_id, mapping_snapshot, mapping_hash "
                    "FROM export_batches"
                )
            ).mappings().all()
            for row in rows:
                stored_hash = row["mapping_hash"]
                if (
                    not mapping_hash_was_missing
                    and stored_hash not in {None, "", _EMPTY_MAPPING_HASH}
                ):
                    continue
                raw_snapshot = row["mapping_snapshot"]
                try:
                    snapshot = (
                        json.loads(raw_snapshot)
                        if isinstance(raw_snapshot, str | bytes | bytearray)
                        else raw_snapshot
                    )
                    if not isinstance(snapshot, list) or any(
                        not isinstance(item, dict) for item in snapshot
                    ):
                        raise TypeError("mapping snapshot must be a list of objects")
                    mapping_hash = stable_json_sha256(snapshot)
                except (TypeError, UnicodeDecodeError, ValueError) as error:
                    batch_id = row["export_batch_id"]
                    raise SchemaRevisionError(
                        f"Export batch {batch_id!r} has invalid mapping_snapshot JSON"
                    ) from error
                if stored_hash == mapping_hash:
                    continue
                connection.execute(
                    text(
                        "UPDATE export_batches SET mapping_hash = :mapping_hash "
                        "WHERE export_batch_id = :batch_id"
                    ),
                    {
                        "mapping_hash": mapping_hash,
                        "batch_id": row["export_batch_id"],
                    },
                )
            connection.execute(
                text(
                    "UPDATE export_batches SET download_name = 'export.xlsx' "
                    "WHERE download_name IS NULL OR download_name = ''"
                )
            )
        inspector = inspect(engine)
        export_indexes = {
            item["name"] for item in inspector.get_indexes("export_batches")
        }
        if "ux_export_batches_task_id" not in export_indexes:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX ux_export_batches_task_id "
                        "ON export_batches (task_id)"
                    )
                )
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "template_versions" in tables:
        version_columns = {
            column["name"] for column in inspector.get_columns("template_versions")
        }
        with engine.begin() as connection:
            if "static_elements" not in version_columns:
                connection.execute(
                    text(
                        "ALTER TABLE template_versions ADD COLUMN static_elements "
                        "JSON NOT NULL DEFAULT '[]'"
                    )
                )
            if "print_imposition" not in version_columns:
                connection.execute(
                    text("ALTER TABLE template_versions ADD COLUMN print_imposition JSON")
                )
            connection.execute(
                text(
                    "UPDATE template_versions SET static_elements = '[]' "
                    "WHERE static_elements IS NULL"
                )
            )
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
    if {"template_versions", "template_metadata"} <= tables:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO template_metadata "
                    "(template_key, display_name, description) "
                    "SELECT DISTINCT v.template_key, "
                    "CASE v.template_key "
                    "WHEN 'PAYROLL_HOURLY' THEN '计时考核单' "
                    "WHEN 'PAYROLL_STANDARD_PIECE' THEN '标准计件单' "
                    "WHEN 'PAYROLL_FIXED_PRODUCTION_GRID' THEN '固定生产明细单' "
                    "WHEN 'PAYROLL_EQUIPMENT_PROCESS' THEN '设备工序单' "
                    "ELSE v.template_key END, "
                    "CASE v.template_key "
                    "WHEN 'PAYROLL_HOURLY' THEN '适用于按工时统计的生产岗位' "
                    "WHEN 'PAYROLL_STANDARD_PIECE' THEN '适用于标准计件生产记录' "
                    "WHEN 'PAYROLL_FIXED_PRODUCTION_GRID' THEN '适用于固定生产明细岗位' "
                    "WHEN 'PAYROLL_EQUIPMENT_PROCESS' THEN '适用于设备与工序计件岗位' "
                    "ELSE '' END FROM template_versions v "
                    "WHERE NOT EXISTS ("
                    "SELECT 1 FROM template_metadata m "
                    "WHERE m.template_key = v.template_key)"
                )
            )


def upgrade_database(database_path: Path) -> None:
    """Upgrade an explicit SQLite database to the current schema revision."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(_alembic_config(database_path), "head")


def stamp_database(database_path: Path, revision: str) -> None:
    """Adopt a schema created by the pre-Alembic local runtime."""
    command.stamp(_alembic_config(database_path), revision)


def _alembic_config(database_path: Path) -> Config:
    project_root = Path(__file__).resolve().parents[3]
    config = Config(str(project_root / "alembic.ini"))
    config.attributes["database_path"] = database_path.resolve()
    return config


def verify_database_revision(engine: Engine) -> None:
    """Require the database to already be at this application's Alembic head."""
    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
    except Exception as error:
        raise SchemaRevisionError("Database has not been migrated with Alembic") from error
    if revision != HEAD_REVISION:
        raise SchemaRevisionError(
            f"Database revision {revision!r} does not match required revision {HEAD_REVISION!r}"
        )
