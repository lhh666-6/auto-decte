"""Repair mojibake in the known Bamboo demonstration identities.

The repair is intentionally update-only: it never provisions employees, access
profiles, assignments, factories, roles, or mobile credentials.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BambooFactoryRow,
    MasterDataRecordRow,
    MobileAccessProfileRow,
)

EMPLOYEE_CATALOG = "employees"
FACTORY_ID = "BAMBOO-DEMO-FACTORY"
FACTORY_NAME = "竹丝示范一厂"
TEAM_NAME = "竹丝示范一厂生产组"

DEMO_IDENTITIES: dict[str, tuple[str, str]] = {
    "ZS001": ("王分选", "分选工"),
    "JZ001": ("李浸胶", "浸胶工"),
    "GZ001": ("陈干燥", "干燥工"),
    "JC001": ("周检测", "检测人"),
    "ZG001": ("赵主管", "主管"),
    "CZ001": ("钱厂长", "厂长"),
    "CW001": ("孙财务", "财务审批"),
}


def repair_bamboo_demo_data(engine: Engine) -> int:
    """Repair existing known demo rows and return the number of changed rows."""
    changed_rows = 0
    with Session(engine) as session, session.begin():
        employees = {
            row.code: row
            for row in session.scalars(
                select(MasterDataRecordRow).where(
                    MasterDataRecordRow.catalog == EMPLOYEE_CATALOG,
                    MasterDataRecordRow.code.in_(DEMO_IDENTITIES),
                )
            )
        }
        for code, employee in employees.items():
            expected_name = DEMO_IDENTITIES[code][0]
            if employee.display_name != expected_name:
                employee.display_name = expected_name
                changed_rows += 1

        profiles = session.scalars(
            select(MobileAccessProfileRow).where(
                MobileAccessProfileRow.employee_catalog == EMPLOYEE_CATALOG,
                MobileAccessProfileRow.employee_code.in_(employees),
            )
        )
        for profile in profiles:
            _name, position = DEMO_IDENTITIES[profile.employee_code]
            expected = (position, TEAM_NAME)
            current = (profile.position, profile.team_name)
            if current != expected:
                profile.position = position
                profile.team_name = TEAM_NAME
                changed_rows += 1

        factory = session.get(BambooFactoryRow, FACTORY_ID)
        if factory is not None and factory.name != FACTORY_NAME:
            factory.name = FACTORY_NAME
            changed_rows += 1

    return changed_rows


def main(argv: Sequence[str] | None = None) -> int:
    """Run the repair against an explicitly selected SQLite database."""
    parser = argparse.ArgumentParser(description="Repair known Bamboo demo Chinese identities")
    parser.add_argument("--db", default="data/database/demo.db", help="Path to SQLite database")
    args = parser.parse_args(argv)
    database_path = Path(args.db)
    if not database_path.is_file():
        parser.error(f"database not found: {database_path}")

    engine = create_engine(f"sqlite:///{database_path}")
    try:
        changed_rows = repair_bamboo_demo_data(engine)
    finally:
        engine.dispose()
    print(f"Bamboo demo data repaired: {changed_rows} row(s) changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
