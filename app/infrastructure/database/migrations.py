"""Programmatic Alembic migration entrypoints for local deployments and tests."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from alembic import command

HEAD_REVISION = "003"


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
