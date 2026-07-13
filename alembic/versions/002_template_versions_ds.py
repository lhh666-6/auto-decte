"""Persist template versions, fields and generated printable artifacts.

Revision ID: 002
Revises: 001
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "template_versions",
        sa.Column("version_id", sa.String(), nullable=False),
        sa.Column("template_key", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("page", sa.JSON(), nullable=False),
        sa.Column("parent_version_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("version_id"),
        sa.UniqueConstraint("template_key", "version"),
    )
    op.create_table(
        "template_fields",
        sa.Column("field_id", sa.String(), nullable=False),
        sa.Column("version_id", sa.String(), nullable=False),
        sa.Column("field_key", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["template_versions.version_id"]),
        sa.PrimaryKeyConstraint("field_id"),
        sa.UniqueConstraint("version_id", "field_key"),
    )
    op.create_index(None, "template_fields", ["version_id"])
    op.create_table(
        "template_artifacts",
        sa.Column("artifact_id", sa.String(), nullable=False),
        sa.Column("version_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("download_name", sa.String(), nullable=False),
        sa.Column("internal_uri", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["template_versions.version_id"]),
        sa.PrimaryKeyConstraint("artifact_id"),
        sa.UniqueConstraint("internal_uri"),
    )
    op.create_index(None, "template_artifacts", ["version_id"])


def downgrade() -> None:
    op.drop_table("template_artifacts")
    op.drop_table("template_fields")
    op.drop_table("template_versions")
