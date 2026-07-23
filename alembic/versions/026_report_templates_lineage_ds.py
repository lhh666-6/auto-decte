"""Add governed report templates, mappings, export files and cell lineage.

Revision ID: 026
Revises: 025
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "026"
down_revision: str | None = "025"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_template_versions",
        sa.Column("template_version_id", sa.String(), primary_key=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("structure", sa.JSON(), nullable=False),
        sa.Column("structure_hash", sa.String(length=64), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_report_template_status",
        "report_template_versions",
        ["status", "created_at"],
    )
    op.create_table(
        "report_mapping_versions",
        sa.Column("mapping_version_id", sa.String(), primary_key=True),
        sa.Column(
            "template_version_id",
            sa.String(),
            sa.ForeignKey("report_template_versions.template_version_id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("mapping_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by", sa.String()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "template_version_id", "version", name="ux_report_mapping_template_version"
        ),
    )
    op.create_index(
        "ix_report_mapping_status",
        "report_mapping_versions",
        ["template_version_id", "status"],
    )
    op.create_table(
        "governed_export_batches",
        sa.Column("export_batch_id", sa.String(), primary_key=True),
        sa.Column("idempotency_key", sa.String(), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "template_version_id",
            sa.String(),
            sa.ForeignKey("report_template_versions.template_version_id"),
            nullable=False,
        ),
        sa.Column(
            "mapping_version_id",
            sa.String(),
            sa.ForeignKey("report_mapping_versions.mapping_version_id"),
            nullable=False,
        ),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("data_watermark", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("file_content", sa.LargeBinary(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("download_name", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_governed_export_status",
        "governed_export_batches",
        ["status", "created_at"],
    )
    op.create_table(
        "export_cell_lineage",
        sa.Column("lineage_id", sa.String(), primary_key=True),
        sa.Column(
            "export_batch_id",
            sa.String(),
            sa.ForeignKey("governed_export_batches.export_batch_id"),
            nullable=False,
        ),
        sa.Column("sheet_name", sa.String(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("column_index", sa.Integer(), nullable=False),
        sa.Column("cell_address", sa.String(), nullable=False),
        sa.Column("submission_id", sa.String(), nullable=False),
        sa.Column("field_key", sa.String(), nullable=False),
        sa.UniqueConstraint(
            "export_batch_id", "sheet_name", "cell_address", name="ux_export_cell_lineage"
        ),
    )
    op.create_index(
        "ix_export_lineage_submission",
        "export_cell_lineage",
        ["submission_id", "field_key"],
    )


def downgrade() -> None:
    op.drop_table("export_cell_lineage")
    op.drop_table("governed_export_batches")
    op.drop_table("report_mapping_versions")
    op.drop_table("report_template_versions")
