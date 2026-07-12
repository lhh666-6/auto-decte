"""Initial migration: create all architecture and domain tables.

Revision ID: 001
Revises:
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forms",
        sa.Column("form_id", sa.String(), nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        sa.Column("template_version", sa.String(), nullable=False),
        sa.Column("coordinate_version", sa.String(), nullable=False),
        sa.Column("review_status", sa.String(), nullable=False),
        sa.Column("export_status", sa.String(), nullable=False),
        sa.Column("current_record_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("form_id"),
    )
    op.create_table(
        "review_leases",
        sa.Column("form_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("lease_token", sa.String(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("forced_release_by", sa.String(), nullable=True),
        sa.Column("forced_release_reason", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("form_id"),
        sa.UniqueConstraint("lease_token"),
    )
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("step", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("task_id"),
        sa.UniqueConstraint("actor_id", "operation", "resource_id", "idempotency_key"),
    )
    op.create_table(
        "record_versions",
        sa.Column("record_id", sa.String(), nullable=False),
        sa.Column("form_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("previous_version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("change_reason", sa.String(), nullable=False, server_default=""),
        sa.Column("confirmed_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["form_id"], ["forms.form_id"]),
        sa.PrimaryKeyConstraint("record_id"),
        sa.UniqueConstraint("form_id", "version"),
    )
    op.create_index(None, "record_versions", ["form_id"])
    op.create_table(
        "evidence_files",
        sa.Column("file_id", sa.String(), nullable=False),
        sa.Column("form_id", sa.String(), nullable=False),
        sa.Column("related_field_id", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("uri", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("immutable", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["form_id"], ["forms.form_id"]),
        sa.PrimaryKeyConstraint("file_id"),
        sa.UniqueConstraint("uri"),
        sa.UniqueConstraint("sha256"),
    )
    op.create_index(None, "evidence_files", ["form_id"])
    op.create_index(None, "evidence_files", ["sha256"])
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("form_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["form_id"], ["forms.form_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(None, "audit_events", ["form_id"])
    op.create_table(
        "form_fields",
        sa.Column("field_id", sa.String(), nullable=False),
        sa.Column("form_id", sa.String(), nullable=False),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("source_region", sa.JSON(), nullable=False),
        sa.Column("current_value", sa.JSON(), nullable=True),
        sa.Column("current_value_source", sa.String(), nullable=True),
        sa.Column("current_record_version", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["form_id"], ["forms.form_id"]),
        sa.PrimaryKeyConstraint("field_id"),
    )
    op.create_index(None, "form_fields", ["form_id"])
    op.create_table(
        "recognition_attempts",
        sa.Column("attempt_id", sa.String(), nullable=False),
        sa.Column("field_id", sa.String(), nullable=False),
        sa.Column("engine", sa.String(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("candidate_value", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("crop_file_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["field_id"], ["form_fields.field_id"]),
        sa.ForeignKeyConstraint(["crop_file_id"], ["evidence_files.file_id"]),
        sa.PrimaryKeyConstraint("attempt_id"),
    )
    op.create_index(None, "recognition_attempts", ["field_id"])
    op.create_table(
        "task_events",
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("step", sa.String(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.task_id"]),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("task_id", "sequence"),
    )
    op.create_index(None, "task_events", ["task_id"])
    op.create_table(
        "export_batches",
        sa.Column("export_batch_id", sa.String(), nullable=False),
        sa.Column("export_type", sa.String(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("included_records", sa.JSON(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("exported_by", sa.String(), nullable=False),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_batch_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("export_batch_id"),
        sa.UniqueConstraint("file_path"),
    )
    op.create_table(
        "ai_reviews",
        sa.Column("review_id", sa.String(), nullable=False),
        sa.Column("form_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["form_id"], ["forms.form_id"]),
        sa.PrimaryKeyConstraint("review_id"),
    )
    op.create_index(None, "ai_reviews", ["form_id"])


def downgrade() -> None:
    op.drop_table("ai_reviews")
    op.drop_table("export_batches")
    op.drop_table("task_events")
    op.drop_table("recognition_attempts")
    op.drop_table("form_fields")
    op.drop_table("audit_events")
    op.drop_table("evidence_files")
    op.drop_table("record_versions")
    op.drop_table("tasks")
    op.drop_table("review_leases")
    op.drop_table("forms")
