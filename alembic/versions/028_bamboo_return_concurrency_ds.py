"""Protect bamboo returns with idempotency and optimistic revisions.

Revision ID: 028
Revises: 027
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "028"
down_revision: str | None = "027"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    existing_columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("bamboo_returns")
    }
    new_columns = {"actor_id", "idempotency_key", "payload_hash", "result_payload"}
    if new_columns <= existing_columns:
        return
    op.add_column("bamboo_returns", sa.Column("actor_id", sa.String(), nullable=True))
    op.add_column("bamboo_returns", sa.Column("idempotency_key", sa.String(), nullable=True))
    op.add_column("bamboo_returns", sa.Column("payload_hash", sa.String(64), nullable=True))
    op.add_column("bamboo_returns", sa.Column("result_payload", sa.JSON(), nullable=True))
    op.execute(
        "UPDATE bamboo_returns SET "
        "actor_id = requested_by, "
        "idempotency_key = 'legacy:' || return_id, "
        "payload_hash = 'legacy:' || return_id, "
        "result_payload = '{}'"
    )
    with op.batch_alter_table("bamboo_returns") as batch:
        batch.alter_column("actor_id", existing_type=sa.String(), nullable=False)
        batch.alter_column("idempotency_key", existing_type=sa.String(), nullable=False)
        batch.alter_column("payload_hash", existing_type=sa.String(64), nullable=False)
        batch.alter_column("result_payload", existing_type=sa.JSON(), nullable=False)
        batch.create_unique_constraint(
            "ux_bamboo_return_actor_idempotency",
            ["actor_id", "idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("bamboo_returns") as batch:
        batch.drop_constraint(
            "ux_bamboo_return_actor_idempotency",
            type_="unique",
        )
        batch.drop_column("result_payload")
        batch.drop_column("payload_hash")
        batch.drop_column("idempotency_key")
        batch.drop_column("actor_id")
