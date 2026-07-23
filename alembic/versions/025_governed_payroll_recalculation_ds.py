"""Add governed payroll rules, immutable calculations and access audit.

Revision ID: 025
Revises: 024
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "025"
down_revision: str | None = "024"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governed_payroll_rule_versions",
        sa.Column("rule_version_id", sa.String(), primary_key=True),
        sa.Column("rule_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("position", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("dsl", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.String()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.String(), nullable=False, server_default=""),
        sa.UniqueConstraint(
            "rule_key", "factory_id", "version", name="ux_governed_payroll_rule_version"
        ),
    )
    op.create_index(
        "ix_governed_payroll_rule_status",
        "governed_payroll_rule_versions",
        ["status", "factory_id", "created_at"],
    )
    op.create_table(
        "payroll_calculation_batches",
        sa.Column("batch_id", sa.String(), primary_key=True),
        sa.Column("batch_type", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("period_start", sa.String(), nullable=False),
        sa.Column("period_end", sa.String(), nullable=False),
        sa.Column("data_watermark", sa.String(), nullable=False),
        sa.Column(
            "rule_version_id",
            sa.String(),
            sa.ForeignKey("governed_payroll_rule_versions.rule_version_id"),
            nullable=False,
        ),
        sa.Column(
            "source_batch_id",
            sa.String(),
            sa.ForeignKey("payroll_calculation_batches.batch_id"),
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by", sa.String()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_payroll_batch_period",
        "payroll_calculation_batches",
        ["factory_id", "period_start", "period_end", "status"],
    )
    op.create_table(
        "payroll_calculation_results",
        sa.Column("result_id", sa.String(), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(),
            sa.ForeignKey("payroll_calculation_batches.batch_id"),
            nullable=False,
        ),
        sa.Column("root_submission_id", sa.String(), nullable=False),
        sa.Column("employee_code", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("business_date", sa.String(), nullable=False),
        sa.Column(
            "rule_version_id",
            sa.String(),
            sa.ForeignKey("governed_payroll_rule_versions.rule_version_id"),
            nullable=False,
        ),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("amount", sa.String(), nullable=False),
        sa.Column("original_amount", sa.String()),
        sa.Column("delta_amount", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "root_submission_id", name="ux_payroll_batch_source"),
    )
    op.create_index(
        "ix_payroll_result_employee",
        "payroll_calculation_results",
        ["employee_code", "business_date"],
    )
    op.create_table(
        "payroll_access_audits",
        sa.Column("audit_id", sa.String(), primary_key=True),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_role", sa.String(), nullable=False),
        sa.Column("requested_factory_id", sa.String(), nullable=False),
        sa.Column("requested_employee_code", sa.String(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_payroll_access_actor",
        "payroll_access_audits",
        ["actor_id", "viewed_at"],
    )


def downgrade() -> None:
    op.drop_table("payroll_access_audits")
    op.drop_table("payroll_calculation_results")
    op.drop_table("payroll_calculation_batches")
    op.drop_table("governed_payroll_rule_versions")
