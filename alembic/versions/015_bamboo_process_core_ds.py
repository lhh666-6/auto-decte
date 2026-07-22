"""Persist factory-scoped bamboo workflow core records.

Revision ID: 015
Revises: 014
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bamboo_factories",
        sa.Column("factory_id", sa.String(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "bamboo_role_definitions",
        sa.Column("role_code", sa.String(), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("self_requestable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "employee_bamboo_assignments",
        sa.Column("assignment_id", sa.String(), primary_key=True),
        sa.Column("employee_catalog", sa.String(), nullable=False),
        sa.Column("employee_code", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("role_code", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_catalog", "employee_code"],
            ["master_data_records.catalog", "master_data_records.code"],
        ),
        sa.ForeignKeyConstraint(["factory_id"], ["bamboo_factories.factory_id"]),
        sa.ForeignKeyConstraint(["role_code"], ["bamboo_role_definitions.role_code"]),
    )
    op.create_index(
        "ix_employee_bamboo_assignment_current",
        "employee_bamboo_assignments",
        ["employee_catalog", "employee_code", "status", "effective_at"],
    )
    op.create_table(
        "bamboo_records",
        sa.Column("record_id", sa.String(), primary_key=True),
        sa.Column("display_no", sa.String(), nullable=False, unique=True),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_ref", sa.String()),
        sa.Column("base_info", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("current_stage", sa.String()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["factory_id"], ["bamboo_factories.factory_id"]),
    )
    op.create_index(
        "ix_bamboo_records_factory_stage",
        "bamboo_records",
        ["factory_id", "current_stage", "status", "updated_at"],
    )
    op.create_table(
        "bamboo_stage_submissions",
        sa.Column("submission_id", sa.String(), primary_key=True),
        sa.Column("record_id", sa.String(), nullable=False),
        sa.Column("stage_key", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_name", sa.String(), nullable=False),
        sa.Column("role_code", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invalidated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["record_id"], ["bamboo_records.record_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["factory_id"], ["bamboo_factories.factory_id"]),
        sa.UniqueConstraint("record_id", "stage_key", "version", name="ux_bamboo_stage_version"),
    )
    op.create_index(
        "ix_bamboo_stage_submissions_record_stage",
        "bamboo_stage_submissions",
        ["record_id", "stage_key", "version"],
    )
    op.create_table(
        "bamboo_signatures",
        sa.Column("signature_id", sa.String(), primary_key=True),
        sa.Column("submission_id", sa.String(), nullable=False, unique=True),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("employee_code", sa.String(), nullable=False),
        sa.Column("actor_name", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("role_code", sa.String(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["bamboo_stage_submissions.submission_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["factory_id"], ["bamboo_factories.factory_id"]),
        sa.UniqueConstraint("actor_id", "idempotency_key", name="ux_bamboo_signature_idempotency"),
    )


def downgrade() -> None:
    op.drop_table("bamboo_signatures")
    op.drop_index(
        "ix_bamboo_stage_submissions_record_stage",
        table_name="bamboo_stage_submissions",
    )
    op.drop_table("bamboo_stage_submissions")
    op.drop_index("ix_bamboo_records_factory_stage", table_name="bamboo_records")
    op.drop_table("bamboo_records")
    op.drop_index(
        "ix_employee_bamboo_assignment_current",
        table_name="employee_bamboo_assignments",
    )
    op.drop_table("employee_bamboo_assignments")
    op.drop_table("bamboo_role_definitions")
    op.drop_table("bamboo_factories")
