"""Add create_payload_hash to bamboo_records for idempotency payload binding.

Revision ID: 030
Revises: 029
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "030"
down_revision: str | None = "029"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("bamboo_records")
    }
    if "create_payload_hash" not in columns:
        op.add_column(
            "bamboo_records",
            sa.Column(
                "create_payload_hash",
                sa.String(64),
                nullable=True,
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("bamboo_records")
    }
    if "create_payload_hash" in columns:
        op.drop_column("bamboo_records", "create_payload_hash")
