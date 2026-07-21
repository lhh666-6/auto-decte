"""Add fact_records table for unified business facts.

Revision ID: 013
Revises: 012
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fact_records",
        sa.Column("fact_record_id", sa.String(), primary_key=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_submission_id", sa.String()),
        sa.Column("source_form_id", sa.String()),
        sa.Column("subject_employee_code", sa.String(), nullable=False),
        sa.Column("subject_employee_name", sa.String(), nullable=False, server_default=""),
        sa.Column("workshop", sa.String(), nullable=False, server_default=""),
        sa.Column("work_order_id", sa.String(), nullable=False, server_default=""),
        sa.Column("product_id", sa.String(), nullable=False, server_default=""),
        sa.Column("process_id", sa.String(), nullable=False, server_default=""),
        sa.Column("production_date", sa.String(), nullable=False, server_default=""),
        sa.Column("shift", sa.String(), nullable=False, server_default=""),
        sa.Column("blocks_completed", sa.Integer()),
        sa.Column("pieces_per_block", sa.Integer()),
        sa.Column("total_pieces", sa.Integer()),
        sa.Column("measurement_values", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("anomalies", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("corrections", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("review_status", sa.String(), nullable=False),
        sa.Column("reviewed_by", sa.String(), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("export_status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_fact_records_employee_date",
        "fact_records",
        ["subject_employee_code", "production_date"],
    )
    op.create_index(
        "ix_fact_records_review_status",
        "fact_records",
        ["review_status"],
    )
    op.create_index(
        "ix_fact_records_export_status",
        "fact_records",
        ["export_status"],
    )
    op.create_index(
        "ix_fact_records_source",
        "fact_records",
        ["source_submission_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_fact_records_source", table_name="fact_records")
    op.drop_index("ix_fact_records_export_status", table_name="fact_records")
    op.drop_index("ix_fact_records_review_status", table_name="fact_records")
    op.drop_index("ix_fact_records_employee_date", table_name="fact_records")
    op.drop_table("fact_records")
