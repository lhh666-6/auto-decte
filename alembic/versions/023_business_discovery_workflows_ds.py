"""Add business discovery baselines and governed workflow versions.

Revision ID: 023
Revises: 022
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "023"
down_revision: str | None = "022"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_discovery_sessions",
        sa.Column("session_id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "business_discovery_messages",
        sa.Column("message_id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("business_discovery_sessions.session_id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_business_discovery_messages_session_id",
        "business_discovery_messages",
        ["session_id"],
    )
    op.create_table(
        "business_rule_confirmations",
        sa.Column("rule_id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("business_discovery_sessions.session_id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("confirmed_by", sa.String()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("finance_note", sa.String(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_business_rules_session_status",
        "business_rule_confirmations",
        ["session_id", "status"],
    )
    op.create_table(
        "business_logic_baselines",
        sa.Column("baseline_id", sa.String(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("confirmed_by", sa.String(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_definitions",
        sa.Column("definition_id", sa.String(), primary_key=True),
        sa.Column("workflow_key", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_workflow_definitions_workflow_key",
        "workflow_definitions",
        ["workflow_key"],
        unique=True,
    )
    op.create_table(
        "workflow_versions",
        sa.Column("version_id", sa.String(), primary_key=True),
        sa.Column(
            "definition_id",
            sa.String(),
            sa.ForeignKey("workflow_definitions.definition_id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("graph_json", sa.JSON(), nullable=False),
        sa.Column("canvas_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("validation_json", sa.JSON()),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.String()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("definition_id", "version", name="ux_workflow_version"),
    )
    op.create_index(
        "ix_workflow_versions_definition_id",
        "workflow_versions",
        ["definition_id"],
    )
    op.create_index(
        "ix_workflow_versions_status",
        "workflow_versions",
        ["status", "created_at"],
    )
    op.create_table(
        "workflow_plant_activations",
        sa.Column("activation_id", sa.String(), primary_key=True),
        sa.Column(
            "workflow_version_id",
            sa.String(),
            sa.ForeignKey("workflow_versions.version_id"),
            nullable=False,
        ),
        sa.Column("plant_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("activated_by", sa.String(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "workflow_version_id",
            "plant_id",
            name="ux_workflow_plant",
        ),
    )
    op.create_index(
        "ix_workflow_plant_activations_workflow_version_id",
        "workflow_plant_activations",
        ["workflow_version_id"],
    )
    op.create_index(
        "ix_workflow_plant_status",
        "workflow_plant_activations",
        ["plant_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("workflow_plant_activations")
    op.drop_table("workflow_versions")
    op.drop_table("workflow_definitions")
    op.drop_table("business_logic_baselines")
    op.drop_table("business_rule_confirmations")
    op.drop_table("business_discovery_messages")
    op.drop_table("business_discovery_sessions")
