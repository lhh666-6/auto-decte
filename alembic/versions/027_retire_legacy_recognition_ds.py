"""Retire legacy image-recognition runtime tables into read-only archives.

Revision ID: 027
Revises: 026
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "027"
down_revision: str | None = "026"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

RETIRED_TABLES = (
    "recognition_attempts",
    "evidence_files",
    "ai_reviews",
    "review_leases",
    "review_drafts",
    "task_events",
    "tasks",
    "export_batches",
)


def upgrade() -> None:
    op.create_table(
        "legacy_retirement_manifest",
        sa.Column("table_name", sa.String(), primary_key=True),
        sa.Column("archive_table_name", sa.String(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=False),
    )
    for table_name in RETIRED_TABLES:
        archive_name = f"legacy_archive_{table_name}"
        op.execute(
            sa.text(
                "INSERT INTO legacy_retirement_manifest "
                "(table_name, archive_table_name, row_count, retired_at) "
                f"SELECT :table_name, :archive_name, COUNT(*), CURRENT_TIMESTAMP "
                f"FROM {table_name}"
            ).bindparams(table_name=table_name, archive_name=archive_name)
        )
        op.rename_table(table_name, archive_name)


def downgrade() -> None:
    for table_name in reversed(RETIRED_TABLES):
        op.rename_table(f"legacy_archive_{table_name}", table_name)
    op.drop_table("legacy_retirement_manifest")
