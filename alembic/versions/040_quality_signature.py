"""040_quality_signature

V1 Final Truth Closure: Quality Disposition signature hash persistence.

Adds signature_hash VARCHAR(64) to quality_dispositions table for
electronic signature evidence (P0-05 fix).

Revision ID: 040_quality_signature
Revises: 039_form_version_binding
Create Date: 2026-07-25
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "040_quality_signature"
down_revision: str | None = "039_form_version_binding"
branch_labels: Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("quality_dispositions") as batch_op:
        batch_op.add_column(
            sa.Column("signature_hash", sa.String(64), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("quality_dispositions") as batch_op:
        batch_op.drop_column("signature_hash")
