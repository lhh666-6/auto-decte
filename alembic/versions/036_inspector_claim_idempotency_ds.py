"""Add claim_idempotency_key and claim_payload_hash to bamboo_inspection_windows.

Revision ID: 036
Revises: 035
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "036"
down_revision: str | None = "035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("bamboo_inspection_windows") as batch:
        batch.add_column(
            sa.Column("claim_idempotency_key", sa.String(), nullable=True)
        )
        batch.add_column(
            sa.Column("claim_payload_hash", sa.String(64), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("bamboo_inspection_windows") as batch:
        batch.drop_column("claim_payload_hash")
        batch.drop_column("claim_idempotency_key")
