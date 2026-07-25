"""038_v1_foundation

V1 Final Cutover foundation migration:
- One-active-position partial unique index on employee_bamboo_assignments
- employee account_state on mobile_access_profiles
- quality_dispositions table (Plant Manager final quality decisions)
- business_preset_versions table (decoupled from payroll rules)
- management_salary_versions table (admin-managed fixed salaries)
- payroll_field_registry table (allowlisted formula fields per position)

Revision ID: 038_v1_foundation
Revises: 037_retire_legacy_archive
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "038_v1_foundation"
down_revision: Union[str, None] = "037_retire_legacy_archive"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # ── 1. One-active-position partial unique index ──
    with op.get_context().autocommit_block():
        op.create_index(
            "ux_employee_one_active_assignment",
            "employee_bamboo_assignments",
            ["employee_catalog", "employee_code"],
            unique=True,
            postgresql_where=sa.text("status = 'ACTIVE'"),
            sqlite_where=sa.text("status = 'ACTIVE'"),
        )

    # ── 2. Employee account_state ──
    op.add_column(
        "mobile_access_profiles",
        sa.Column(
            "account_state",
            sa.String(),
            nullable=False,
            server_default="ACTIVE",
        ),
    )

    # ── 3. Quality dispositions ──
    op.create_table(
        "quality_dispositions",
        sa.Column("disposition_id", sa.String(), nullable=False),
        sa.Column("record_id", sa.String(), nullable=False),
        sa.Column("inspection_id", sa.String(), nullable=True),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("cage_no", sa.String(), nullable=False),
        sa.Column("responsible_stage", sa.String(), nullable=False),
        sa.Column("responsible_submission_id", sa.String(), nullable=True),
        sa.Column("responsible_employee_code", sa.String(), nullable=False),
        sa.Column("responsible_employee_name_snapshot", sa.String(), nullable=False),
        sa.Column("responsible_position_snapshot", sa.String(), nullable=False),
        sa.Column("original_grade", sa.String(), nullable=False),
        sa.Column("effective_grade", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("decision_note", sa.String(), nullable=False, server_default=""),
        sa.Column("decided_by", sa.String(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("disposition_id"),
        sa.UniqueConstraint("record_id", name="ux_quality_disposition_record"),
        sa.ForeignKeyConstraint(
            ["record_id"], ["bamboo_records.record_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"], ["bamboo_inspections.inspection_id"]
        ),
        sa.ForeignKeyConstraint(
            ["factory_id"], ["bamboo_factories.factory_id"]
        ),
        sa.ForeignKeyConstraint(
            ["responsible_submission_id"],
            ["bamboo_stage_submissions.submission_id"],
        ),
    )
    op.create_index(
        "ix_quality_disposition_factory",
        "quality_dispositions",
        ["factory_id", "decided_at"],
    )

    # ── 4. Business preset versions ──
    op.create_table(
        "business_preset_versions",
        sa.Column("preset_version_id", sa.String(), nullable=False),
        sa.Column("preset_key", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.String(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("preset_version_id"),
        sa.UniqueConstraint("preset_key", "version", name="ux_business_preset_version"),
    )
    op.create_index(
        "ix_business_preset_status",
        "business_preset_versions",
        ["status", "preset_key"],
    )

    # ── 5. Management salary versions ──
    op.create_table(
        "management_salary_versions",
        sa.Column("salary_version_id", sa.String(), nullable=False),
        sa.Column("employee_code", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("position_snapshot", sa.String(), nullable=False),
        sa.Column("role_code_snapshot", sa.String(), nullable=False),
        sa.Column("salary_type", sa.String(), nullable=False),
        sa.Column("amount", sa.String(), nullable=False),
        sa.Column("effective_from", sa.String(), nullable=False),
        sa.Column("effective_until", sa.String(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_version_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("salary_version_id"),
        sa.UniqueConstraint(
            "employee_code", "version", name="ux_management_salary_version"
        ),
        sa.ForeignKeyConstraint(
            ["factory_id"], ["bamboo_factories.factory_id"]
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_version_id"],
            ["management_salary_versions.salary_version_id"],
        ),
    )
    op.create_index(
        "ix_management_salary_employee",
        "management_salary_versions",
        ["employee_code", "status"],
    )

    # ── 6. Payroll field registry ──
    op.create_table(
        "payroll_field_registry",
        sa.Column("registry_id", sa.String(), nullable=False),
        sa.Column("position_role", sa.String(), nullable=False),
        sa.Column("field_key", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("data_type", sa.String(), nullable=False),
        sa.Column("source_table", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("registry_id"),
        sa.UniqueConstraint(
            "position_role", "field_key", name="ux_payroll_field_registry"
        ),
    )


def downgrade() -> None:
    op.drop_table("payroll_field_registry")
    op.drop_table("management_salary_versions")
    op.drop_table("business_preset_versions")
    op.drop_table("quality_dispositions")
    op.drop_column("mobile_access_profiles", "account_state")
    op.drop_index("ux_employee_one_active_assignment", table_name="employee_bamboo_assignments")
