"""Programmatic Alembic migration entrypoints for local deployments and tests."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from alembic import command

HEAD_REVISION = "005"


class SchemaRevisionError(RuntimeError):
    pass


def is_alembic_managed(engine: Engine) -> bool:
    """Return whether this database has an Alembic revision ledger."""
    return "alembic_version" in inspect(engine).get_table_names()


def ensure_auto_created_schema_compatibility(engine: Engine) -> None:
    """Add columns that SQLAlchemy create_all cannot add to legacy local databases."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "forms" not in tables:
        return
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
