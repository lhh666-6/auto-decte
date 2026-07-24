"""Repair mojibake, missing factory scoping, and incomplete payroll
chains in Bamboo demonstration data.

The repair is intentionally update-only: it never provisions employees, access
profiles, assignments, factories, roles, or mobile credentials.

P0 fixes covered:
- Chinese display name mojibake
- Missing factory_id / factory_name on worker access profiles
  (causes plant manager queries to return empty results)
- Missing daily export batches / items for records with PENDING_EFFECTIVE
  payroll facts (causes plant manager payroll queries to return empty)
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BambooDailyExportBatchRow,
    BambooDailyExportItemRow,
    BambooFactoryRow,
    BambooPayrollFactRow,
    BambooRecordRow,
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

# Minimum number of known demo employees that must exist for the database
# to be accepted as a legitimate demo target.
_MIN_DEMO_EMPLOYEE_COUNT = 3


def _require_demo_database(session: Session) -> None:
    """Refuse to repair a database that does not contain the known demo factory
    and a minimum set of known demo employees.

    This is a hard safety guard: the repair must never approve payroll items
    on a production or test database that happens to share a table schema.
    """
    factory = session.get(BambooFactoryRow, FACTORY_ID)
    if factory is None:
        raise RuntimeError(
            f"Refusing to repair: demo factory {FACTORY_ID!r} not found. "
            "This database does not appear to be the Bamboo demo database."
        )

    demo_employee_count = session.scalar(
        select(func.count()).select_from(MasterDataRecordRow).where(
            MasterDataRecordRow.catalog == EMPLOYEE_CATALOG,
            MasterDataRecordRow.code.in_(DEMO_IDENTITIES),
        )
    )
    if demo_employee_count is None or demo_employee_count < _MIN_DEMO_EMPLOYEE_COUNT:
        raise RuntimeError(
            f"Refusing to repair: only {demo_employee_count or 0} of "
            f"{len(DEMO_IDENTITIES)} known demo employees found "
            f"(minimum {_MIN_DEMO_EMPLOYEE_COUNT}). "
            "This database does not appear to be the Bamboo demo database."
        )


def _repair_payroll_chain(session: Session) -> int:
    """Create missing daily-export items for PENDING_EFFECTIVE payroll facts
    and approve any PENDING items left by incomplete finance review.

    Idempotent: skips facts that already have daily-export items, never
    creates duplicate batches or items, and leaves already-APPROVED items
    untouched.

    Returns the number of changed rows (facts activated + items created/approved).
    """
    changed = 0
    now = datetime.now(UTC)

    # ── Pass 1: approve PENDING items ONLY for the demo factory ──
    pending_items = session.scalars(
        select(BambooDailyExportItemRow)
        .join(
            BambooDailyExportBatchRow,
            BambooDailyExportBatchRow.batch_id == BambooDailyExportItemRow.batch_id,
        )
        .where(
            BambooDailyExportItemRow.status == "PENDING",
            BambooDailyExportBatchRow.factory_id == FACTORY_ID,
        )
    ).all()
    for item in pending_items:
        item.status = "APPROVED"
        item.decision_by = "CW001"
        item.decision_at = now
        item.decision_note = "demo repair: auto-approved"
        item.revision += 1
        changed += 1

    # ── Pass 2: create missing daily-export items for PENDING_EFFECTIVE facts ──
    facts = session.scalars(
        select(BambooPayrollFactRow)
        .join(BambooRecordRow, BambooRecordRow.record_id == BambooPayrollFactRow.record_id)
        .where(
            BambooPayrollFactRow.status == "PENDING_EFFECTIVE",
            BambooRecordRow.current_stage.in_(["PLANT_AUDIT", "COMPLETED", None]),
            BambooRecordRow.factory_id == FACTORY_ID,
        )
    ).all()

    batch_cache: dict[tuple[str, str], BambooDailyExportBatchRow] = {}

    for fact in facts:
        # Check if this fact already has a daily export item
        existing = session.scalar(
            select(BambooDailyExportItemRow).where(
                BambooDailyExportItemRow.payroll_fact_id == fact.fact_id,
            )
        )
        if existing is not None:
            # Already has an item (approved in Pass 1) — activate the fact
            fact.status = "EFFECTIVE"
            fact.effective_at = now
            changed += 1
            continue

        # Get the record for factory_id and business_date
        record = session.get(BambooRecordRow, fact.record_id)
        if record is None:
            continue

        factory_id = record.factory_id
        business_date = fact.created_at.date().isoformat()
        cache_key = (factory_id, business_date)

        # Get or create batch
        if cache_key not in batch_cache:
            batch = session.scalar(
                select(BambooDailyExportBatchRow).where(
                    BambooDailyExportBatchRow.factory_id == factory_id,
                    BambooDailyExportBatchRow.business_date == business_date,
                    BambooDailyExportBatchRow.version == 1,
                )
            )
            if batch is None:
                batch = BambooDailyExportBatchRow(
                    batch_id=str(uuid4()),
                    factory_id=factory_id,
                    business_date=business_date,
                    version=1,
                    status="OPEN",
                    supplemental=False,
                    source_batch_id=None,
                    created_by="CW001",
                    created_at=now,
                )
                session.add(batch)
                session.flush()
                changed += 1
            batch_cache[cache_key] = batch
        else:
            batch = batch_cache[cache_key]

        # Create items for each allocation
        for allocation in fact.allocations:
            emp_code = str(allocation["employee_code"])
            amount = str(allocation["amount"])
            # Skip if item already exists (defense-in-depth)
            dup = session.scalar(
                select(BambooDailyExportItemRow).where(
                    BambooDailyExportItemRow.batch_id == batch.batch_id,
                    BambooDailyExportItemRow.payroll_fact_id == fact.fact_id,
                    BambooDailyExportItemRow.employee_code == emp_code,
                )
            )
            if dup is not None:
                if dup.status != "APPROVED":
                    dup.status = "APPROVED"
                    dup.decision_by = "CW001"
                    dup.decision_at = now
                    dup.decision_note = "demo repair: auto-approved"
                    dup.revision += 1
                    changed += 1
                continue

            session.add(
                BambooDailyExportItemRow(
                    item_id=str(uuid4()),
                    batch_id=batch.batch_id,
                    payroll_fact_id=fact.fact_id,
                    record_id=fact.record_id,
                    employee_code=emp_code,
                    amount=amount,
                    status="APPROVED",
                    decision_by="CW001",
                    decision_at=now,
                    decision_note="demo repair: auto-approved",
                    source_snapshot={
                        "display_no": record.display_no,
                        "fact_type": fact.fact_type,
                        "rule_version_id": fact.rule_version_id,
                        "allocation": allocation,
                    },
                    revision=1,
                )
            )
            changed += 1

        # Activate the fact
        fact.status = "EFFECTIVE"
        fact.effective_at = now
        changed += 1

    return changed


def repair_bamboo_demo_data(engine: Engine) -> int:
    """Repair existing known demo rows and return the number of changed rows.

    Raises RuntimeError if the database does not contain the known demo
    factory and a minimum set of known demo employees — this repair must
    never operate on a production database.
    """
    changed_rows = 0
    with Session(engine) as session, session.begin():
        _require_demo_database(session)
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
            # P0-1/P0-2: fix missing factory scoping on worker access profiles.
            # Workers with empty factory_id cannot be queried by their plant
            # manager, and the manager's own queries return empty results.
            if not profile.factory_id or profile.factory_id != FACTORY_ID:
                profile.factory_id = FACTORY_ID
                changed_rows += 1
            if not profile.factory_name or profile.factory_name != FACTORY_NAME:
                profile.factory_name = FACTORY_NAME
                changed_rows += 1

        factory = session.get(BambooFactoryRow, FACTORY_ID)
        if factory is not None and factory.name != FACTORY_NAME:
            factory.name = FACTORY_NAME
            changed_rows += 1

        # P0-2: complete the payroll chain for records with PENDING_EFFECTIVE facts
        payroll_changes = _repair_payroll_chain(session)
        changed_rows += payroll_changes

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
