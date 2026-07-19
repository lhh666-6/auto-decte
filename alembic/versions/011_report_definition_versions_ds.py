"""Persist append-only report definition versions.

Revision ID: 011
Revises: 010
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_definition_versions",
        sa.Column("definition_id", sa.String(), primary_key=True),
        sa.Column("report_key", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.UniqueConstraint("report_key", "version"),
    )
    op.create_index(
        "ix_report_definition_versions_report_key",
        "report_definition_versions",
        ["report_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_report_definition_versions_report_key",
        table_name="report_definition_versions",
    )
    op.drop_table("report_definition_versions")
