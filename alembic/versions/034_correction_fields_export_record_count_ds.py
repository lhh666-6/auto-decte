"""Add correction_type, supplementary_note to submission_corrections
and record_count to governed_export_batches.

Revision ID: 034
Revises: 033
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "034"
down_revision: str | None = "033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("submission_corrections") as batch:
        batch.add_column(
            sa.Column("correction_type", sa.String(50), nullable=True)
        )
        batch.add_column(
            sa.Column("supplementary_note", sa.String(500), nullable=True)
        )

    with op.batch_alter_table("governed_export_batches") as batch:
        batch.add_column(
            sa.Column("record_count", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("governed_export_batches") as batch:
        batch.drop_column("record_count")

    with op.batch_alter_table("submission_corrections") as batch:
        batch.drop_column("supplementary_note")
        batch.drop_column("correction_type")
