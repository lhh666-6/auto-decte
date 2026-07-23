"""Repair inspection kind for databases stamped past the original migration.

Revision ID: 029
Revises: 028
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "029"
down_revision: str | None = "028"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("bamboo_inspections")
    }
    if "inspection_kind" not in columns:
        op.add_column(
            "bamboo_inspections",
            sa.Column(
                "inspection_kind",
                sa.String(),
                nullable=False,
                server_default="LEGACY",
            ),
        )

    inspector = sa.inspect(op.get_bind())
    indexes = {
        index["name"]
        for index in inspector.get_indexes("bamboo_inspections")
    }
    if "ux_bamboo_inspection_formal_record" not in indexes:
        op.create_index(
            "ux_bamboo_inspection_formal_record",
            "bamboo_inspections",
            ["record_id"],
            unique=True,
            sqlite_where=sa.text("inspection_kind = 'FORMAL'"),
            postgresql_where=sa.text("inspection_kind = 'FORMAL'"),
        )


def downgrade() -> None:
    # Revision 028 already expects this schema. 029 only repairs databases that
    # were incorrectly stamped, so downgrading the revision marker must retain it.
    pass
