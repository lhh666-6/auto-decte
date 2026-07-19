"""Add versioned payroll job configurations.

Revision ID: 009
Revises: 008
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_profile_versions",
        sa.Column("profile_version_id", sa.String(), nullable=False),
        sa.Column("profile_key", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("core_layout", sa.String(), nullable=False),
        sa.Column("template_version_id", sa.String(), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("parent_profile_version_id", sa.String(), nullable=True),
        sa.Column("unit", sa.String(), nullable=False, server_default=""),
        sa.Column("fixed_options", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("pricing_rules", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("deduction_rules", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("export_mapping", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(
            ["template_version_id"], ["template_versions.version_id"]
        ),
        sa.PrimaryKeyConstraint("profile_version_id"),
        sa.UniqueConstraint(
            "profile_key", "version", name="uq_job_profile_versions_key_version"
        ),
    )
    op.create_index(
        "ix_job_profile_versions_profile_key",
        "job_profile_versions",
        ["profile_key"],
    )
    op.create_index(
        "ix_job_profile_versions_template_version_id",
        "job_profile_versions",
        ["template_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_job_profile_versions_template_version_id",
        table_name="job_profile_versions",
    )
    op.drop_index(
        "ix_job_profile_versions_profile_key", table_name="job_profile_versions"
    )
    op.drop_table("job_profile_versions")
