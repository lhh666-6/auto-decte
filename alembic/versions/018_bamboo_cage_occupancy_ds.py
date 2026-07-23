"""Persist active bamboo cage occupancy.

Revision ID: 018
Revises: 017
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "018"
down_revision: str | None = "017"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bamboo_cage_occupancies",
        sa.Column("occupancy_id", sa.String(), primary_key=True),
        sa.Column(
            "factory_id",
            sa.String(),
            sa.ForeignKey("bamboo_factories.factory_id"),
            nullable=False,
        ),
        sa.Column("cage_no", sa.String(), nullable=False),
        sa.Column("cage_no_key", sa.String(), nullable=False),
        sa.Column(
            "sorting_record_id",
            sa.String(),
            sa.ForeignKey("bamboo_records.record_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column(
            "released_by_submission_id",
            sa.String(),
            sa.ForeignKey("bamboo_stage_submissions.submission_id"),
        ),
    )
    op.create_index(
        "ux_bamboo_cage_occupancy_active",
        "bamboo_cage_occupancies",
        ["factory_id", "cage_no_key"],
        unique=True,
        sqlite_where=sa.text("released_at IS NULL"),
        postgresql_where=sa.text("released_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_bamboo_cage_occupancy_active",
        table_name="bamboo_cage_occupancies",
    )
    op.drop_table("bamboo_cage_occupancies")
