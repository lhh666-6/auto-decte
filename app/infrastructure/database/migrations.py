"""Programmatic Alembic migration entrypoints for local deployments and tests."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from alembic import command

HEAD_REVISION = "007"

_EMPTY_MAPPING_HASH = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"


class SchemaRevisionError(RuntimeError):
    pass


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
    if "forms" in tables:
        form_columns = {column["name"] for column in inspector.get_columns("forms")}
        if "priority" not in form_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE forms ADD COLUMN priority "
                        "INTEGER NOT NULL DEFAULT 0"
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
            connection.execute(
                text(
                    "UPDATE export_batches SET mapping_hash = :mapping_hash "
                    "WHERE mapping_hash IS NULL OR mapping_hash = ''"
                ),
                {"mapping_hash": _EMPTY_MAPPING_HASH},
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
    project_root = Path(__file__).resolve().parents[3]
    config = Config(str(project_root / "alembic.ini"))
    config.attributes["database_path"] = database_path.resolve()
    command.upgrade(config, "head")


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
