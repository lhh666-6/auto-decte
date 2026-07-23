"""Add idempotency_payload_hash to bamboo_signatures and backfill create records.

Revision ID: 031
Revises: 030
Create Date: 2026-07-23
"""

import hashlib
import json
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.orm import Session

from alembic import op

revision: str = "031"
down_revision: str | None = "030"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _canonical_create_hash(actor_id: str, form_type: str, base_info: dict) -> str:
    payload = {
        "actor_id": actor_id,
        "form_type": form_type,
        "base_info": base_info,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    # --- 1. Add idempotency_payload_hash to bamboo_signatures ---
    sig_columns = {c["name"] for c in inspector.get_columns("bamboo_signatures")}
    if "idempotency_payload_hash" not in sig_columns:
        op.add_column(
            "bamboo_signatures",
            sa.Column("idempotency_payload_hash", sa.String(64), nullable=True),
        )
    if "idempotency_hash_version" not in sig_columns:
        op.add_column(
            "bamboo_signatures",
            sa.Column(
                "idempotency_hash_version",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    # --- 2. Backfill create_payload_hash for existing MOBILE_CREATED records ---
    rec_columns = {c["name"] for c in inspector.get_columns("bamboo_records")}
    if "create_payload_hash" in rec_columns:
        bind = op.get_bind()
        session = Session(bind=bind)
        try:
            rows = session.execute(
                sa.text(
                    "SELECT record_id, created_by, form_type, base_info "
                    "FROM bamboo_records "
                    "WHERE source_type = 'MOBILE_CREATED' "
                    "AND source_ref IS NOT NULL AND source_ref <> '' "
                    "AND create_payload_hash IS NULL"
                )
            ).mappings().all()

            for row in rows:
                try:
                    base_info = row["base_info"]
                    if isinstance(base_info, str):
                        base_info = json.loads(base_info)
                    if not isinstance(base_info, dict):
                        continue
                    form_type = row["form_type"] or "SORTING"
                    payload_hash = _canonical_create_hash(
                        row["created_by"], form_type, dict(base_info)
                    )
                    session.execute(
                        sa.text(
                            "UPDATE bamboo_records "
                            "SET create_payload_hash = :hash "
                            "WHERE record_id = :rid"
                        ),
                        {"hash": payload_hash, "rid": row["record_id"]},
                    )
                except (json.JSONDecodeError, TypeError, KeyError):
                    # Cannot reliably reconstruct — leave NULL for safe rejection
                    continue

            session.commit()
        finally:
            session.close()


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    sig_columns = {c["name"] for c in inspector.get_columns("bamboo_signatures")}
    if "idempotency_payload_hash" in sig_columns:
        op.drop_column("bamboo_signatures", "idempotency_payload_hash")
    if "idempotency_hash_version" in sig_columns:
        op.drop_column("bamboo_signatures", "idempotency_hash_version")
    # create_payload_hash values are intentionally retained; the column was added by 030
