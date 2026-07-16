"""Persist immutable export-batch snapshots and task linkage.

Revision ID: 007
Revises: 006
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_EMPTY_MAPPING_HASH = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"


def upgrade() -> None:
    op.add_column(
        "export_batches",
        sa.Column("task_id", sa.String(), nullable=True),
    )
    op.add_column(
        "export_batches",
        sa.Column(
            "template_snapshot",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "export_batches",
        sa.Column(
            "mapping_snapshot",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "export_batches",
        sa.Column(
            "mapping_hash",
            sa.String(length=64),
            nullable=False,
            server_default=_EMPTY_MAPPING_HASH,
        ),
    )
    op.add_column(
        "export_batches",
        sa.Column(
            "download_name",
            sa.String(),
            nullable=False,
            server_default="export.xlsx",
        ),
    )
    op.create_index(
        "ux_export_batches_task_id",
        "export_batches",
        ["task_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_export_batches_task_id", table_name="export_batches")
    op.drop_column("export_batches", "download_name")
    op.drop_column("export_batches", "mapping_hash")
    op.drop_column("export_batches", "mapping_snapshot")
    op.drop_column("export_batches", "template_snapshot")
    op.drop_column("export_batches", "task_id")
