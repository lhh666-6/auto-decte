"""Add termination_reason to bamboo_inspection_windows and
target_manager_note to bamboo_personnel_transfers.

Revision ID: 035
Revises: 034
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "035"
down_revision: str | None = "034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("bamboo_inspection_windows") as batch:
        batch.add_column(
            sa.Column("termination_reason", sa.String(2000), nullable=True)
        )

    with op.batch_alter_table("bamboo_personnel_transfers") as batch:
        batch.add_column(
            sa.Column("target_manager_note", sa.String(2000), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("bamboo_personnel_transfers") as batch:
        batch.drop_column("target_manager_note")

    with op.batch_alter_table("bamboo_inspection_windows") as batch:
        batch.drop_column("termination_reason")
