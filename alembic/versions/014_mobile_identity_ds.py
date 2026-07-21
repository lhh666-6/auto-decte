"""Persist mobile credentials, access profiles, and sessions.

Revision ID: 014
Revises: 013
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    employee_foreign_key = ["employee_catalog", "employee_code"]
    employee_target = [
        "master_data_records.catalog",
        "master_data_records.code",
    ]
    op.create_table(
        "mobile_credentials",
        sa.Column("employee_catalog", sa.String(), primary_key=True),
        sa.Column("employee_code", sa.String(), primary_key=True),
        sa.Column("pin_salt", sa.String(), nullable=False),
        sa.Column("pin_hash", sa.String(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(employee_foreign_key, employee_target),
    )
    op.create_table(
        "mobile_access_profiles",
        sa.Column("employee_catalog", sa.String(), primary_key=True),
        sa.Column("employee_code", sa.String(), primary_key=True),
        sa.Column("team_id", sa.String(), nullable=False, server_default=""),
        sa.Column("team_name", sa.String(), nullable=False, server_default=""),
        sa.Column("position", sa.String(), nullable=False, server_default=""),
        sa.Column("roles", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("allowed_form_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("allowed_processes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(employee_foreign_key, employee_target),
    )
    op.create_table(
        "mobile_sessions",
        sa.Column("session_id", sa.String(), primary_key=True),
        sa.Column("employee_catalog", sa.String(), nullable=False),
        sa.Column("employee_code", sa.String(), nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(employee_foreign_key, employee_target),
    )
    op.create_index(
        "ix_mobile_sessions_employee",
        "mobile_sessions",
        ["employee_catalog", "employee_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_mobile_sessions_employee", table_name="mobile_sessions")
    op.drop_table("mobile_sessions")
    op.drop_table("mobile_access_profiles")
    op.drop_table("mobile_credentials")
