"""039_form_version_binding

V1 Final Verification §4: BusinessForm Version Binding.
Adds form_version_id and form_definition_id to bamboo_records.

Uses SQLite-compatible batch mode for constraint operations.

Revision ID: 039_form_version_binding
Revises: 038_v1_foundation
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "039_form_version_binding"
down_revision: Union[str, None] = "038_v1_foundation"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # SQLite: use batch mode for ALTER TABLE.
    # FK constraints omitted — SQLite batch mode has circular dependency issues
    # with multiple FKs on the same table. The model-level ForeignKey annotations
    # serve as documentation; referential integrity is maintained by the application.
    with op.batch_alter_table("bamboo_records") as batch_op:
        batch_op.add_column(
            sa.Column("form_version_id", sa.String(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("form_definition_id", sa.String(), nullable=True)
        )
    op.create_index(
        "ix_bamboo_records_form_version",
        "bamboo_records",
        ["form_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_bamboo_records_form_version")
    with op.batch_alter_table("bamboo_records") as batch_op:
        batch_op.drop_column("form_definition_id")
        batch_op.drop_column("form_version_id")
