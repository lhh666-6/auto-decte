"""Persist governed bamboo personnel transfers.

Revision ID: 020
Revises: 019
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "020"
down_revision: str | None = "019"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bamboo_personnel_transfers",
        sa.Column("transfer_id", sa.String(), primary_key=True),
        sa.Column("employee_code", sa.String(), nullable=False),
        sa.Column("transfer_type", sa.String(), nullable=False),
        sa.Column(
            "source_factory_id",
            sa.String(),
            sa.ForeignKey("bamboo_factories.factory_id"),
            nullable=False,
        ),
        sa.Column(
            "target_factory_id",
            sa.String(),
            sa.ForeignKey("bamboo_factories.factory_id"),
            nullable=False,
        ),
        sa.Column("from_role", sa.String(), nullable=False),
        sa.Column("to_role", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_manager_id", sa.String()),
        sa.Column("source_manager_decision", sa.String()),
        sa.Column("source_manager_decided_at", sa.DateTime(timezone=True)),
        sa.Column("target_manager_id", sa.String()),
        sa.Column("target_manager_decision", sa.String()),
        sa.Column("target_manager_decided_at", sa.DateTime(timezone=True)),
        sa.Column("admin_id", sa.String()),
        sa.Column("admin_decision", sa.String()),
        sa.Column("admin_note", sa.String()),
        sa.Column("admin_decided_at", sa.DateTime(timezone=True)),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_bamboo_personnel_transfer_queue",
        "bamboo_personnel_transfers",
        ["status", "source_factory_id", "target_factory_id", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bamboo_personnel_transfer_queue",
        table_name="bamboo_personnel_transfers",
    )
    op.drop_table("bamboo_personnel_transfers")
