"""Add governed electronic form versions, plant activation, and notices.

Revision ID: 022
Revises: 021
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "022"
down_revision: str | None = "021"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "electronic_form_definitions",
        sa.Column("definition_id", sa.String(), primary_key=True),
        sa.Column("form_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("owner_role", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("form_key"),
    )
    op.create_index(
        "ix_electronic_form_definitions_form_key",
        "electronic_form_definitions",
        ["form_key"],
        unique=True,
    )
    op.create_table(
        "electronic_form_versions",
        sa.Column("version_id", sa.String(), primary_key=True),
        sa.Column(
            "definition_id",
            sa.String(),
            sa.ForeignKey("electronic_form_definitions.definition_id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_comment", sa.String(), nullable=False, server_default=""),
        sa.UniqueConstraint(
            "definition_id",
            "version",
            name="ux_managed_form_version",
        ),
    )
    op.create_index(
        "ix_electronic_form_versions_definition_id",
        "electronic_form_versions",
        ["definition_id"],
    )
    op.create_index(
        "ix_managed_form_versions_status",
        "electronic_form_versions",
        ["status", "created_at"],
    )
    op.create_table(
        "form_plant_activations",
        sa.Column("activation_id", sa.String(), primary_key=True),
        sa.Column(
            "form_version_id",
            sa.String(),
            sa.ForeignKey("electronic_form_versions.version_id"),
            nullable=False,
        ),
        sa.Column("plant_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("activated_by", sa.String(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "form_version_id",
            "plant_id",
            name="ux_form_plant_activation",
        ),
    )
    op.create_index(
        "ix_form_plant_activations_form_version_id",
        "form_plant_activations",
        ["form_version_id"],
    )
    op.create_index(
        "ix_form_plant_activations_plant_status",
        "form_plant_activations",
        ["plant_id", "status"],
    )
    op.create_table(
        "management_notifications",
        sa.Column("notification_id", sa.String(), primary_key=True),
        sa.Column("notification_type", sa.String(), nullable=False),
        sa.Column("plant_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_by", sa.String()),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_management_notifications_recipient",
        "management_notifications",
        ["plant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("management_notifications")
    op.drop_table("form_plant_activations")
    op.drop_table("electronic_form_versions")
    op.drop_table("electronic_form_definitions")
