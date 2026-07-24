"""Add correction idempotency fields and export supersedes lineage.

Revision ID: 033
Revises: 032
Create Date: 2026-07-24

Adds:
  - SubmissionCorrectionRow.idempotency_key + request_hash
  - UniqueConstraint(requested_by, idempotency_key)
  - GovernedExportBatchRow.supersedes_batch_id

SQLite compatibility: no ALTER ADD CONSTRAINT — the unique constraint and
index are created via batch mode.  The self-referencing FK on
supersedes_batch_id is omitted (application-layer integrity for SQLite).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "033"
down_revision: str | None = "032"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # ── GovernedExportBatchRow: supersedes_batch_id (plain column, no FK in SQLite) ──
    op.add_column(
        "governed_export_batches",
        sa.Column("supersedes_batch_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_governed_export_supersedes",
        "governed_export_batches",
        ["supersedes_batch_id"],
    )

    # ── SubmissionCorrectionRow: idempotency fields + unique constraint ─────
    op.add_column(
        "submission_corrections",
        sa.Column("idempotency_key", sa.String(), nullable=True),
    )
    op.add_column(
        "submission_corrections",
        sa.Column("request_hash", sa.String(64), nullable=True),
    )
    with op.batch_alter_table("submission_corrections") as batch_op:
        batch_op.create_unique_constraint(
            "ux_submission_correction_idempotency",
            ["requested_by", "idempotency_key"],
        )


def downgrade() -> None:
    op.drop_index("ix_governed_export_supersedes", table_name="governed_export_batches")
    op.drop_column("governed_export_batches", "supersedes_batch_id")

    with op.batch_alter_table("submission_corrections") as batch_op:
        batch_op.drop_constraint(
            "ux_submission_correction_idempotency",
            type_="unique",
        )
        batch_op.drop_column("request_hash")
        batch_op.drop_column("idempotency_key")
