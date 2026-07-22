"""Persist bamboo payroll, inspection, audit, and finance operations.

Revision ID: 016
Revises: 015
Create Date: 2026-07-22
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bamboo_payroll_rule_versions",
        sa.Column("rule_version_id", sa.String(), primary_key=True),
        sa.Column("rule_key", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["factory_id"], ["bamboo_factories.factory_id"]),
        sa.UniqueConstraint(
            "rule_key", "factory_id", "version", name="ux_bamboo_payroll_rule_version"
        ),
    )
    op.create_index(
        "ix_bamboo_payroll_rule_current",
        "bamboo_payroll_rule_versions",
        ["rule_key", "factory_id", "active", "effective_at"],
    )
    now = datetime.now(UTC)
    rule_table = sa.table(
        "bamboo_payroll_rule_versions",
        sa.column("rule_version_id", sa.String()),
        sa.column("rule_key", sa.String()),
        sa.column("factory_id", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("configuration", sa.JSON()),
        sa.column("active", sa.Boolean()),
        sa.column("effective_at", sa.DateTime(timezone=True)),
        sa.column("created_by", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        rule_table,
        [
            {
                "rule_version_id": "system-sort-v1",
                "rule_key": "SORT",
                "factory_id": None,
                "version": 1,
                "configuration": {
                    "unit_rate": "1.00",
                    "length_multipliers": {"2.1": "5", "2.3": "6", "2.5": "7"},
                },
                "active": True,
                "effective_at": now,
                "created_by": "SYSTEM",
                "created_at": now,
            },
            {
                "rule_version_id": "system-joint-v1",
                "rule_key": "DIPPING_DRYING_JOINT",
                "factory_id": None,
                "version": 1,
                "configuration": {"dipping_rate": "1.00", "drying_rate": "1.00"},
                "active": True,
                "effective_at": now,
                "created_by": "SYSTEM",
                "created_at": now,
            },
        ],
    )

    op.create_table(
        "bamboo_payroll_facts",
        sa.Column("fact_id", sa.String(), primary_key=True),
        sa.Column("record_id", sa.String(), nullable=False),
        sa.Column("fact_type", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("rule_version_id", sa.String(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("allocations", sa.JSON(), nullable=False),
        sa.Column("total_amount", sa.String(), nullable=False),
        sa.Column("source_submission_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["record_id"], ["bamboo_records.record_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["rule_version_id"], ["bamboo_payroll_rule_versions.rule_version_id"]
        ),
        sa.UniqueConstraint(
            "record_id", "fact_type", "version", name="ux_bamboo_payroll_fact_version"
        ),
    )
    op.create_index(
        "ix_bamboo_payroll_fact_status",
        "bamboo_payroll_facts",
        ["record_id", "status", "fact_type"],
    )

    op.create_table(
        "bamboo_inspections",
        sa.Column("inspection_id", sa.String(), primary_key=True),
        sa.Column("record_id", sa.String(), nullable=False),
        sa.Column("serial_no", sa.String(), nullable=False),
        sa.Column("target_stage", sa.String(), nullable=False),
        sa.Column("moisture_points", sa.JSON(), nullable=False),
        sa.Column("average_value", sa.String(), nullable=False),
        sa.Column("conclusion", sa.String(), nullable=False),
        sa.Column("note", sa.String()),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_name", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("role_code", sa.String(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("window_revision", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["bamboo_records.record_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["factory_id"], ["bamboo_factories.factory_id"]),
        sa.UniqueConstraint("record_id", "serial_no", name="ux_bamboo_inspection_serial"),
        sa.UniqueConstraint("actor_id", "idempotency_key", name="ux_bamboo_inspection_idempotency"),
    )
    op.create_index("ix_bamboo_inspection_record", "bamboo_inspections", ["record_id", "signed_at"])
    op.create_table(
        "bamboo_evidence_assets",
        sa.Column("asset_id", sa.String(), primary_key=True),
        sa.Column("inspection_id", sa.String(), nullable=False),
        sa.Column("evidence_type", sa.String(), nullable=False),
        sa.Column("file_id", sa.String()),
        sa.Column("uri", sa.String()),
        sa.Column("mime_type", sa.String()),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("sha256", sa.String(length=64)),
        sa.Column("text_content", sa.String()),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["inspection_id"], ["bamboo_inspections.inspection_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "bamboo_inspection_exceptions",
        sa.Column("exception_id", sa.String(), primary_key=True),
        sa.Column("inspection_id", sa.String(), nullable=False, unique=True),
        sa.Column("record_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("resolution", sa.String()),
        sa.Column("closed_by", sa.String()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["inspection_id"], ["bamboo_inspections.inspection_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["record_id"], ["bamboo_records.record_id"], ondelete="CASCADE"),
    )

    op.create_table(
        "bamboo_returns",
        sa.Column("return_id", sa.String(), primary_key=True),
        sa.Column("record_id", sa.String(), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("requested_role", sa.String(), nullable=False),
        sa.Column("target_stages", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_revision", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["bamboo_records.record_id"], ondelete="CASCADE"),
    )
    op.create_table(
        "bamboo_plant_audits",
        sa.Column("audit_id", sa.String(), primary_key=True),
        sa.Column("record_id", sa.String(), nullable=False),
        sa.Column("submission_id", sa.String()),
        sa.Column("earliest_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audited_at", sa.DateTime(timezone=True)),
        sa.Column("actor_id", sa.String()),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["record_id"], ["bamboo_records.record_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["bamboo_stage_submissions.submission_id"]),
    )
    op.create_table(
        "bamboo_role_change_requests",
        sa.Column("request_id", sa.String(), primary_key=True),
        sa.Column("employee_code", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("from_role", sa.String(), nullable=False),
        sa.Column("to_role", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.String()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_note", sa.String()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["factory_id"], ["bamboo_factories.factory_id"]),
    )
    op.create_index(
        "ix_bamboo_role_change_pending",
        "bamboo_role_change_requests",
        ["factory_id", "status", "requested_at"],
    )

    op.create_table(
        "bamboo_daily_export_batches",
        sa.Column("batch_id", sa.String(), primary_key=True),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("business_date", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("supplemental", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_batch_id", sa.String()),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["factory_id"], ["bamboo_factories.factory_id"]),
        sa.ForeignKeyConstraint(["source_batch_id"], ["bamboo_daily_export_batches.batch_id"]),
        sa.UniqueConstraint(
            "factory_id", "business_date", "version", name="ux_bamboo_daily_batch_version"
        ),
    )
    op.create_table(
        "bamboo_daily_export_items",
        sa.Column("item_id", sa.String(), primary_key=True),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("payroll_fact_id", sa.String(), nullable=False),
        sa.Column("record_id", sa.String(), nullable=False),
        sa.Column("employee_code", sa.String(), nullable=False),
        sa.Column("amount", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("decision_by", sa.String()),
        sa.Column("decision_at", sa.DateTime(timezone=True)),
        sa.Column("decision_note", sa.String()),
        sa.Column("source_snapshot", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["bamboo_daily_export_batches.batch_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["payroll_fact_id"], ["bamboo_payroll_facts.fact_id"]),
        sa.ForeignKeyConstraint(["record_id"], ["bamboo_records.record_id"]),
        sa.UniqueConstraint(
            "batch_id", "payroll_fact_id", "employee_code", name="ux_bamboo_daily_fact_employee"
        ),
    )
    op.create_index(
        "ix_bamboo_daily_item_status", "bamboo_daily_export_items", ["batch_id", "status"]
    )
    op.create_table(
        "bamboo_finance_inquiries",
        sa.Column("inquiry_id", sa.String(), primary_key=True),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("factory_id", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["bamboo_daily_export_items.item_id"]),
        sa.ForeignKeyConstraint(["factory_id"], ["bamboo_factories.factory_id"]),
    )
    op.create_table(
        "bamboo_finance_inquiry_messages",
        sa.Column("message_id", sa.String(), primary_key=True),
        sa.Column("inquiry_id", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_name", sa.String(), nullable=False),
        sa.Column("role_code", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["inquiry_id"], ["bamboo_finance_inquiries.inquiry_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "bamboo_correction_cases",
        sa.Column("case_id", sa.String(), primary_key=True),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("record_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("supplement_batch_id", sa.String()),
        sa.ForeignKeyConstraint(["item_id"], ["bamboo_daily_export_items.item_id"]),
        sa.ForeignKeyConstraint(["record_id"], ["bamboo_records.record_id"]),
        sa.ForeignKeyConstraint(["supplement_batch_id"], ["bamboo_daily_export_batches.batch_id"]),
    )


def downgrade() -> None:
    op.drop_table("bamboo_correction_cases")
    op.drop_table("bamboo_finance_inquiry_messages")
    op.drop_table("bamboo_finance_inquiries")
    op.drop_index("ix_bamboo_daily_item_status", table_name="bamboo_daily_export_items")
    op.drop_table("bamboo_daily_export_items")
    op.drop_table("bamboo_daily_export_batches")
    op.drop_index("ix_bamboo_role_change_pending", table_name="bamboo_role_change_requests")
    op.drop_table("bamboo_role_change_requests")
    op.drop_table("bamboo_plant_audits")
    op.drop_table("bamboo_returns")
    op.drop_table("bamboo_inspection_exceptions")
    op.drop_table("bamboo_evidence_assets")
    op.drop_index("ix_bamboo_inspection_record", table_name="bamboo_inspections")
    op.drop_table("bamboo_inspections")
    op.drop_index("ix_bamboo_payroll_fact_status", table_name="bamboo_payroll_facts")
    op.drop_table("bamboo_payroll_facts")
    op.drop_index("ix_bamboo_payroll_rule_current", table_name="bamboo_payroll_rule_versions")
    op.drop_table("bamboo_payroll_rule_versions")
