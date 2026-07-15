"""Limit global content deduplication to original imported images.

Revision ID: 005
Revises: 004
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    unique_constraints = inspector.get_unique_constraints("evidence_files")
    sha_constraint = next(
        (
            item
            for item in unique_constraints
            if item.get("column_names") == ["sha256"]
        ),
        None,
    )
    if sha_constraint is not None:
        naming_convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
        constraint_name = sha_constraint.get("name") or "uq_evidence_files_sha256"
        with op.batch_alter_table(
            "evidence_files",
            recreate="always",
            naming_convention=naming_convention,
        ) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="unique")
    op.drop_index("ix_evidence_files_sha256", table_name="evidence_files")
    op.create_index(
        "ix_evidence_files_sha256", "evidence_files", ["sha256"], unique=False
    )
    op.create_index(
        "ux_evidence_files_original_sha256",
        "evidence_files",
        ["sha256"],
        unique=True,
        sqlite_where=sa.text("type = 'ORIGINAL_IMAGE'"),
    )


def downgrade() -> None:
    op.drop_index("ux_evidence_files_original_sha256", table_name="evidence_files")
    op.drop_index("ix_evidence_files_sha256", table_name="evidence_files")
    op.create_index(
        "ix_evidence_files_sha256", "evidence_files", ["sha256"], unique=True
    )
