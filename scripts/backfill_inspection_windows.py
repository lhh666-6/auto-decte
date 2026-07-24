"""Backfill inspection windows for ACTIVE records whose last production stage
has been submitted but no inspection window exists.

Rules (per spec section 5.3):
- record.status == ACTIVE AND last production stage submitted AND no Window → backfill
- COMPLETED / VOID records → skip
- No duplicate windows
- opened_at = current time (not historical, to avoid immediate expiry)

Usage:
  python scripts/backfill_inspection_windows.py [--dry-run] [--db-path data/database/demo.db]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.adapters.database.models import (  # noqa: E402
    BambooInspectionWindowRow,
    BambooRecordRow,
    BambooStageSubmissionRow,
)
from app.infrastructure.database.sqlite_ds import create_sqlite_engine  # noqa: E402


def _utc(dt: datetime) -> datetime:
    """Normalise a datetime to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def backfill(engine: Engine, *, dry_run: bool = False) -> list[dict[str, object]]:
    """Find and backfill missing inspection windows. Returns list of created windows."""
    now = datetime.now(UTC)
    created: list[dict[str, object]] = []

    with Session(engine) as session, session.begin():
        # Find ACTIVE records without windows
        records = session.execute(
            BambooRecordRow.__table__.select()
            .where(BambooRecordRow.status == "ACTIVE")
            .order_by(BambooRecordRow.created_at)
        ).all()

        for record in records:
            record_id = record.record_id
            display_no = record.display_no
            form_type = record.form_type
            factory_id = record.factory_id

            # Check if window already exists
            existing = session.get(BambooInspectionWindowRow, record_id)
            if existing is not None:
                continue

            # Determine which production stages must be complete
            if form_type == "SORTING":
                required_stage = "SORT"
            elif form_type == "DIPPING_DRYING":
                required_stage = "DRYING"
            else:
                print(f"  [{display_no}] Unknown form_type={form_type}, skipping")
                continue

            # Check if required production stage has been submitted
            submission = session.execute(
                BambooStageSubmissionRow.__table__.select()
                .where(
                    BambooStageSubmissionRow.record_id == record_id,
                    BambooStageSubmissionRow.stage_key == required_stage,
                    BambooStageSubmissionRow.invalidated.is_(False),
                )
            ).first()

            if submission is None:
                print(f"  [{display_no}] {required_stage} stage not submitted yet, skipping")
                continue

            # Create the window
            opened_at = now  # Use current time to avoid immediate expiry
            deadline_at = opened_at + timedelta(hours=2)

            if dry_run:
                print(
                    f"  [DRY-RUN] [{display_no}] Would create window: "
                    f"form_type={form_type}, opened_at={opened_at.isoformat()}"
                )
                created.append({
                    "record_id": record_id,
                    "display_no": display_no,
                    "form_type": form_type,
                    "factory_id": factory_id,
                    "opened_at": opened_at.isoformat(),
                    "backfilled": True,
                })
                continue

            window = BambooInspectionWindowRow(
                record_id=record_id,
                factory_id=factory_id,
                opened_at=opened_at,
                deadline_at=deadline_at,
                status="OPEN",
                revision=1,
            )
            session.add(window)
            print(
                f"  [CREATED] [{display_no}] Window OPEN: "
                f"form_type={form_type}, opened_at={opened_at.isoformat()}"
            )
            created.append({
                "record_id": record_id,
                "display_no": display_no,
                "form_type": form_type,
                "factory_id": factory_id,
                "opened_at": opened_at.isoformat(),
                "backfilled": True,
            })

    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill inspection windows")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument(
        "--db-path",
        default=str(PROJECT_ROOT / "data" / "database" / "demo.db"),
        help="Path to SQLite database",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Error: database not found at {db_path}")
        sys.exit(1)

    print(f"Database: {db_path}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")

    engine = create_sqlite_engine(db_path)
    try:
        created = backfill(engine, dry_run=args.dry_run)
    finally:
        engine.dispose()

    print(f"\nBackfill complete: {len(created)} windows {'would be' if args.dry_run else ''} created.")
    for w in created:
        print(f"  {w['display_no']} → {w['form_type']} → OPEN")


if __name__ == "__main__":
    main()
