"""Re-backfill create_payload_hash with client-fields-only canonical payload.

Revision ID: 032
Revises: 031
Create Date: 2026-07-24

Migration 031 backfilled create_payload_hash with the full validated base_info
(including server-injected options_version and net_weight).  The router now
hashes only client-supplied fields so that admin preset updates do not cause
false IDEMPOTENCY_CONFLICT on replay.  This migration recomputes every
MOBILE_CREATED record's hash using the same client-fields-only filter.
"""

import hashlib
import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "032"
down_revision: str | None = "031"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CLIENT_KEYS = frozenset({
    "mode", "special_classes", "length", "shade", "grade",
    "supplier", "cage_no", "bundle_count",
})


def _canonical_create_hash(actor_id: str, form_type: str, base_info: dict) -> str:
    payload = {
        "actor_id": actor_id,
        "form_type": form_type,
        "base_info": {
            key: value
            for key, value in base_info.items()
            if key in _CLIENT_KEYS
        },
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def upgrade() -> None:
    bind = op.get_bind()
    # Re-compute every backfilled create_payload_hash using client fields only
    result = bind.execute(
        sa.text(
            "SELECT record_id, created_by, form_type, base_info "
            "FROM bamboo_records "
            "WHERE source_type = 'MOBILE_CREATED' "
            "AND source_ref IS NOT NULL AND source_ref <> ''"
        )
    ).mappings().all()

    updated = 0
    for row in result:
        try:
            base_info = row["base_info"]
            if isinstance(base_info, str):
                base_info = json.loads(base_info)
            if not isinstance(base_info, dict):
                continue
            form_type = row["form_type"] or "SORTING"
            new_hash = _canonical_create_hash(
                row["created_by"], form_type, dict(base_info)
            )
            bind.execute(
                sa.text(
                    "UPDATE bamboo_records "
                    "SET create_payload_hash = :hash "
                    "WHERE record_id = :rid"
                ),
                {"hash": new_hash, "rid": row["record_id"]},
            )
            updated += 1
        except (json.JSONDecodeError, TypeError, KeyError):
            continue

    # Also update the migration's own hash helper for documentation
    # (the 031 function body stays as committed; 032 is the correction).


def downgrade() -> None:
    # 031's backfill format is lost after 032's recomputation.
    # Downgrading 032 keeps the corrected hashes — this is intentional
    # because the corrected hashes are the desired state.
    pass
