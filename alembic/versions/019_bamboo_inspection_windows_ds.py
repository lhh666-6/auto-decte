"""Persist bamboo inspection windows, appeals, and notifications.

Revision ID: 019
Revises: 018
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bamboo_inspections",
        sa.Column(
            "inspection_kind",
            sa.String(),
            nullable=False,
            server_default="LEGACY",
        ),
    )
    op.create_index(
        "ux_bamboo_inspection_formal_record",
        "bamboo_inspections",
        ["record_id"],
        unique=True,
        sqlite_where=sa.text("inspection_kind = 'FORMAL'"),
        postgresql_where=sa.text("inspection_kind = 'FORMAL'"),
    )
    op.create_table(
        "bamboo_inspection_windows",
        sa.Column(
            "record_id",
            sa.String(),
            sa.ForeignKey("bamboo_records.record_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "factory_id",
            sa.String(),
            sa.ForeignKey("bamboo_factories.factory_id"),
            nullable=False,
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("claimed_by", sa.String()),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "inspection_id",
            sa.String(),
            sa.ForeignKey("bamboo_inspections.inspection_id"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("terminated_by", sa.String()),
        sa.Column("terminated_at", sa.DateTime(timezone=True)),
        sa.Column("appeal_deadline_at", sa.DateTime(timezone=True)),
        sa.Column("appeal_claimed_by", sa.String()),
        sa.Column("appeal_claimed_at", sa.DateTime(timezone=True)),
        sa.Column("appeal_payload", sa.JSON()),
        sa.Column("appeal_submitted_at", sa.DateTime(timezone=True)),
        sa.Column("appeal_decision", sa.String()),
        sa.Column("appeal_decision_note", sa.String()),
        sa.Column("appeal_decided_by", sa.String()),
        sa.Column("appeal_decided_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_bamboo_inspection_window_queue",
        "bamboo_inspection_windows",
        ["factory_id", "status", "deadline_at"],
    )
    op.create_table(
        "mobile_notifications",
        sa.Column("notification_id", sa.String(), primary_key=True),
        sa.Column("recipient_actor_id", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("link", sa.String()),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_mobile_notification_inbox",
        "mobile_notifications",
        ["recipient_actor_id", "read_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_mobile_notification_inbox", table_name="mobile_notifications")
    op.drop_table("mobile_notifications")
    op.drop_index(
        "ix_bamboo_inspection_window_queue",
        table_name="bamboo_inspection_windows",
    )
    op.drop_table("bamboo_inspection_windows")
    op.drop_index(
        "ux_bamboo_inspection_formal_record",
        table_name="bamboo_inspections",
    )
    op.drop_column("bamboo_inspections", "inspection_kind")
