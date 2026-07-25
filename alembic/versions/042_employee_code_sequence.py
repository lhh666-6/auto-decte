"""V1 Employee Code Sequence — auto-generated factory-position-sequence codes.

Revision ID: 042_employee_code_sequence
Revises: 041_rename_dipping_drying_form
Create Date: 2026-07-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "042_employee_code_sequence"
down_revision: Union[str, None] = "041_rename_dipping_drying_form"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Add factory_code to bamboo_factories ──
    with op.batch_alter_table("bamboo_factories") as batch:
        batch.add_column(
            sa.Column("factory_code", sa.String(32), nullable=True)
        )
        batch.create_index(
            "ux_factory_code",
            ["factory_code"],
            unique=True,
            sqlite_where=sa.text("factory_code IS NOT NULL"),
        )

    # ── Create employee_code_sequences table ──
    op.create_table(
        "employee_code_sequences",
        sa.Column("factory_id", sa.String(64), primary_key=True),
        sa.Column("position_code", sa.String(16), primary_key=True),
        sa.Column("last_sequence", sa.Integer, nullable=False, default=0),
        sa.Column("revision", sa.Integer, nullable=False, default=1),
    )


def downgrade() -> None:
    op.drop_table("employee_code_sequences")
    with op.batch_alter_table("bamboo_factories") as batch:
        batch.drop_index("ux_factory_code")
        batch.drop_column("factory_code")
