"""Persist review drafts and stable queue priority.

Revision ID: 003
Revises: 002
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "forms",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "review_drafts",
        sa.Column("form_id", sa.String(), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("saved_by", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["form_id"], ["forms.form_id"]),
        sa.PrimaryKeyConstraint("form_id"),
    )
    op.create_index(
        "ix_forms_review_queue_order",
        "forms",
        ["review_status", "priority", "created_at", "form_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_forms_review_queue_order", table_name="forms")
    op.drop_table("review_drafts")
    op.drop_column("forms", "priority")
