"""Programmatic Alembic migration entrypoints for local deployments and tests."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, text

from alembic import command

HEAD_REVISION = "001"


class SchemaRevisionError(RuntimeError):
    pass


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
