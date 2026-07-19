"""Store optional job-profile identity on imported forms.

Revision ID: 010
Revises: 009
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("forms", sa.Column("job_profile_key", sa.String(), nullable=True))
    op.add_column("forms", sa.Column("job_profile_version", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("forms", "job_profile_version")
    op.drop_column("forms", "job_profile_key")
