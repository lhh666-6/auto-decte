"""Split bamboo production into independently audited linked forms.

Revision ID: 017
Revises: 016
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "017"
down_revision: str | None = "016"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _archive_duplicate_mobile_records() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT record_id, created_by, source_ref "
            "FROM bamboo_records "
            "WHERE source_type = 'MOBILE_CREATED' "
            "AND source_ref IS NOT NULL AND source_ref <> '' "
            "ORDER BY created_by, source_ref, created_at, record_id"
        )
    ).mappings().all()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row["created_by"]), str(row["source_ref"]))
        if key not in seen:
            seen.add(key)
            continue
        connection.execute(
            sa.text(
                "UPDATE bamboo_records "
                "SET source_type = 'MOBILE_CREATED_DUPLICATE', "
                "source_ref = :source_ref "
                "WHERE record_id = :record_id"
            ),
            {
                "record_id": row["record_id"],
                "source_ref": f"{row['source_ref']}#duplicate:{row['record_id']}",
            },
        )


def upgrade() -> None:
    with op.batch_alter_table("bamboo_records") as batch_op:
        batch_op.add_column(
            sa.Column(
                "form_type",
                sa.String(),
                nullable=False,
                server_default="SORTING",
            )
        )
        batch_op.add_column(sa.Column("production_object_id", sa.String()))
        batch_op.add_column(sa.Column("source_record_id", sa.String()))
        batch_op.add_column(
            sa.Column(
                "source_snapshot",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )
        batch_op.create_foreign_key(
            "fk_bamboo_records_source_record",
            "bamboo_records",
            ["source_record_id"],
            ["record_id"],
        )
    op.execute(
        "UPDATE bamboo_records SET production_object_id = record_id "
        "WHERE production_object_id IS NULL"
    )
    op.create_index(
        "ix_bamboo_records_source_lookup",
        "bamboo_records",
        ["form_type", "source_record_id"],
        unique=True,
    )
    _archive_duplicate_mobile_records()
    op.create_index(
        "ux_bamboo_records_mobile_create_idempotency",
        "bamboo_records",
        ["created_by", "source_type", "source_ref"],
        unique=True,
        sqlite_where=sa.text(
            "source_type = 'MOBILE_CREATED' "
            "AND source_ref IS NOT NULL AND source_ref <> ''"
        ),
        postgresql_where=sa.text(
            "source_type = 'MOBILE_CREATED' "
            "AND source_ref IS NOT NULL AND source_ref <> ''"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_bamboo_records_mobile_create_idempotency",
        table_name="bamboo_records",
    )
    op.drop_index("ix_bamboo_records_source_lookup", table_name="bamboo_records")
    with op.batch_alter_table("bamboo_records") as batch_op:
        batch_op.drop_constraint(
            "fk_bamboo_records_source_record",
            type_="foreignkey",
        )
        batch_op.drop_column("source_snapshot")
        batch_op.drop_column("source_record_id")
        batch_op.drop_column("production_object_id")
        batch_op.drop_column("form_type")
