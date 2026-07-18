"""Persist physical template layout and print imposition.

Revision ID: 008
Revises: 007
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "template_versions",
        sa.Column(
            "static_elements",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "template_versions",
        sa.Column("print_imposition", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("template_versions", "print_imposition")
    op.drop_column("template_versions", "static_elements")
