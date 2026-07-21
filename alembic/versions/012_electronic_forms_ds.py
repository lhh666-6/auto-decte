"""Persist electronic form definitions, drafts, and submission receipts.

Revision ID: 012
Revises: 011
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "electronic_form_definition_versions",
        sa.Column("definition_version_id", sa.String(), primary_key=True),
        sa.Column("form_type", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False, server_default=""),
        sa.Column("template_version_id", sa.String()),
        sa.Column("job_profile_version_id", sa.String()),
        sa.Column("presentation_config", sa.JSON()),
        sa.Column("created_by", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("form_type", "version"),
    )
    op.create_index(
        "ix_ef_def_versions_form_type_status",
        "electronic_form_definition_versions",
        ["form_type", "status"],
    )

    op.create_table(
        "electronic_drafts",
        sa.Column("draft_id", sa.String(), primary_key=True),
        sa.Column("owner_actor_id", sa.String(), nullable=False, index=True),
        sa.Column("subject_employee_code", sa.String(), nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("definition_version_id", sa.String(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "electronic_submission_receipts",
        sa.Column("receipt_id", sa.String(), primary_key=True),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("subject_employee_code", sa.String(), nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("client_submission_id", sa.String(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("form_id", sa.String()),
        sa.Column("record_version", sa.Integer()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "actor_id", "device_id", "operation", "client_submission_id",
            name="ux_electronic_receipts_idempotency",
        ),
    )
    op.create_index(
        "ix_es_receipts_actor_submitted",
        "electronic_submission_receipts",
        ["actor_id", "submitted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_es_receipts_actor_submitted",
        table_name="electronic_submission_receipts",
    )
    op.drop_table("electronic_submission_receipts")
    op.drop_table("electronic_drafts")
    op.drop_index(
        "ix_ef_def_versions_form_type_status",
        table_name="electronic_form_definition_versions",
    )
    op.drop_table("electronic_form_definition_versions")
