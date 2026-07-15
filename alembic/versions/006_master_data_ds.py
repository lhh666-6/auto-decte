"""Add versioned master-data records and audits.

Revision ID: 006
Revises: 005
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "master_data_records",
        sa.Column("catalog", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("catalog", "code"),
    )
    op.create_index(
        "ix_master_data_records_catalog_active_name",
        "master_data_records",
        ["catalog", "active", "display_name", "code"],
        unique=False,
    )
    op.create_table(
        "master_data_audits",
        sa.Column("audit_id", sa.String(), nullable=False),
        sa.Column("catalog", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index(
        "ix_master_data_audits_catalog_code_revision",
        "master_data_audits",
        ["catalog", "code", "revision"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_master_data_audits_catalog_code_revision",
        table_name="master_data_audits",
    )
    op.drop_table("master_data_audits")
    op.drop_index(
        "ix_master_data_records_catalog_active_name",
        table_name="master_data_records",
    )
    op.drop_table("master_data_records")
