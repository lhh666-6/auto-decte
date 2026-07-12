"""SQLite engine factory with single-node industrial runtime safeguards."""

import sqlite3
from pathlib import Path

from sqlalchemy import Engine, create_engine, event


def create_sqlite_engine(path: Path) -> Engine:
    """Create a SQLite engine with WAL, foreign keys and bounded write waiting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _configure_connection)
    return engine


def _configure_connection(connection: sqlite3.Connection, _: object) -> None:
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
