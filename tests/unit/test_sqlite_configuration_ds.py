from pathlib import Path

from app.infrastructure.database.sqlite_ds import create_sqlite_engine


def test_sqlite_engine_enables_wal_foreign_keys_and_busy_timeout(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "demo.db")

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() >= 5000
