"""Add immutable finance ledger, effective projection, corrections and tasks.

Revision ID: 024
Revises: 023
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "024"
down_revision: str | None = "023"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finance_ledger_events",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("submission_id", sa.String(), nullable=False),
        sa.Column("root_submission_id", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("business_date", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "event_type", "submission_id", name="ux_finance_event_submission_type"
        ),
    )
    op.create_index(
        "ix_finance_ledger_period",
        "finance_ledger_events",
        ["factory_id", "business_date", "occurred_at"],
    )
    op.create_table(
        "finance_effective_records",
        sa.Column("root_submission_id", sa.String(), primary_key=True),
        sa.Column("effective_submission_id", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("subject_employee_code", sa.String(), nullable=False),
        sa.Column("definition_version_id", sa.String(), nullable=False),
        sa.Column("business_date", sa.String(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "effective_submission_id", name="ux_finance_effective_submission"
        ),
    )
    op.create_index(
        "ix_finance_effective_period",
        "finance_effective_records",
        ["factory_id", "business_date", "status"],
    )
    op.create_table(
        "submission_corrections",
        sa.Column("correction_id", sa.String(), primary_key=True),
        sa.Column("root_submission_id", sa.String(), nullable=False),
        sa.Column("original_submission_id", sa.String(), nullable=False),
        sa.Column("replacement_submission_id", sa.String()),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("delegate_reason", sa.String(), nullable=False, server_default=""),
        sa.Column("original_actor_id", sa.String(), nullable=False),
        sa.Column("actual_actor_id", sa.String()),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("reviewed_by", sa.String()),
        sa.Column("review_note", sa.String(), nullable=False, server_default=""),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replaced_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_submission_correction_queue",
        "submission_corrections",
        ["factory_id", "status", "created_at"],
    )
    op.create_table(
        "business_tasks",
        sa.Column("task_id", sa.String(), primary_key=True),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("assigned_to", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_business_task_inbox",
        "business_tasks",
        ["assigned_to", "status", "created_at"],
    )
    op.create_index(
        "ix_business_task_factory",
        "business_tasks",
        ["factory_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("business_tasks")
    op.drop_table("submission_corrections")
    op.drop_table("finance_effective_records")
    op.drop_table("finance_ledger_events")
