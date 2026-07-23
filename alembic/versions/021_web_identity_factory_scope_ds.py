"""Persist factory scope on the shared employee access profile.

Revision ID: 021
Revises: 020
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "021"
down_revision: str | None = "020"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mobile_access_profiles",
        sa.Column("factory_id", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "mobile_access_profiles",
        sa.Column("factory_name", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    with op.batch_alter_table("mobile_access_profiles") as batch:
        batch.drop_column("factory_name")
        batch.drop_column("factory_id")
