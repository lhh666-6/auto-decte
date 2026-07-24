"""037_retire_legacy_archive_tables

Drop the legacy_archive_* tables that were renamed in migration 027.
These tables served the old Paper OCR / Review Workbench system and
are no longer referenced by any V1 runtime code.

Revision ID: 037_retire_legacy_archive
Revises: 036
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "037_retire_legacy_archive"
down_revision: Union[str, None] = "036"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[str, None] = None


LEGACY_ARCHIVE_TABLES = [
    "legacy_archive_recognition_attempts",
    "legacy_archive_evidence_files",
    "legacy_archive_ai_reviews",
    "legacy_archive_review_leases",
    "legacy_archive_review_drafts",
    "legacy_archive_tasks",
    "legacy_archive_task_events",
    "legacy_archive_export_batches",
]


def upgrade() -> None:
    for table in LEGACY_ARCHIVE_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")


def downgrade() -> None:
    # Cannot restore dropped tables from migration 027 — raise error
    raise NotImplementedError(
        "Cannot downgrade migration 037: legacy_archive_* tables "
        "were irreversibly dropped. Restore from backup if needed."
    )
