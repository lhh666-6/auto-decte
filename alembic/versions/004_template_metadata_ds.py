"""Persist editable template-family names and descriptions.

Revision ID: 004
Revises: 003
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "template_metadata",
        sa.Column("template_key", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("template_key"),
    )
    op.execute(
        "INSERT INTO template_metadata (template_key, display_name, description) "
        "SELECT DISTINCT template_key, "
        "CASE template_key "
        "WHEN 'PAYROLL_HOURLY' THEN '计时考核单' "
        "WHEN 'PAYROLL_STANDARD_PIECE' THEN '标准计件单' "
        "WHEN 'PAYROLL_FIXED_PRODUCTION_GRID' THEN '固定生产明细单' "
        "WHEN 'PAYROLL_EQUIPMENT_PROCESS' THEN '设备工序单' "
        "ELSE template_key END, "
        "CASE template_key "
        "WHEN 'PAYROLL_HOURLY' THEN '适用于按工时统计的生产岗位' "
        "WHEN 'PAYROLL_STANDARD_PIECE' THEN '适用于标准计件生产记录' "
        "WHEN 'PAYROLL_FIXED_PRODUCTION_GRID' THEN '适用于固定生产明细岗位' "
        "WHEN 'PAYROLL_EQUIPMENT_PROCESS' THEN '适用于设备与工序计件岗位' "
        "ELSE '' END FROM template_versions"
    )


def downgrade() -> None:
    op.drop_table("template_metadata")
