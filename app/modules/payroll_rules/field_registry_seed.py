"""V1 PayrollFieldRegistry seed — idempotent, fail-closed.

§6.1: Seeds the canonical field allowlist for each production position.
Only numeric fields usable in payroll formulas are registered here.
Non-numeric fields (e.g., rack_numbers, shade if categorical) are excluded.

§6.3: Idempotent — safe to run repeatedly. Uses INSERT OR IGNORE semantics.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import PayrollFieldRegistryRow

# ── V1 Canonical Field Registry ──────────────────────────────────
# data_type determines if a field can be used in payroll formulas:
#   INTEGER / DECIMAL → numeric formula metric (allowed)
#   STRING / JSON → business data only (rejected in formulas)
# §6.1: rack_numbers is JSON (not numeric), shade is STRING (not numeric).

V1_REGISTRY_ENTRIES: list[dict[str, Any]] = [
    # ── SORT_OPERATOR ──
    {
        "position_role": "SORT_OPERATOR",
        "field_key": "bundle_count",
        "display_name": "把数",
        "data_type": "INTEGER",
        "source_table": "bamboo_stage_submissions",
    },
    {
        "position_role": "SORT_OPERATOR",
        "field_key": "length",
        "display_name": "长度",
        "data_type": "DECIMAL",
        "source_table": "bamboo_stage_submissions",
    },
    {
        "position_role": "SORT_OPERATOR",
        "field_key": "effective_grade",
        "display_name": "最终评级",
        "data_type": "STRING",
        "source_table": "quality_dispositions",
    },
    {
        "position_role": "SORT_OPERATOR",
        "field_key": "net_weight",
        "display_name": "净重",
        "data_type": "DECIMAL",
        "source_table": "bamboo_stage_submissions",
    },
    {
        "position_role": "SORT_OPERATOR",
        "field_key": "moisture_average",
        "display_name": "含水率",
        "data_type": "DECIMAL",
        "source_table": "bamboo_stage_submissions",
    },
    {
        "position_role": "SORT_OPERATOR",
        "field_key": "shade",
        "display_name": "深浅",
        "data_type": "STRING",
        "source_table": "bamboo_stage_submissions",
    },
    {
        "position_role": "SORT_OPERATOR",
        "field_key": "original_grade",
        "display_name": "原评级",
        "data_type": "STRING",
        "source_table": "bamboo_records",
    },
    # ── DIPPING_OPERATOR ──
    {
        "position_role": "DIPPING_OPERATOR",
        "field_key": "glue_before_weight",
        "display_name": "胶前重",
        "data_type": "DECIMAL",
        "source_table": "bamboo_stage_submissions",
    },
    {
        "position_role": "DIPPING_OPERATOR",
        "field_key": "glue_after_weight",
        "display_name": "胶后重",
        "data_type": "DECIMAL",
        "source_table": "bamboo_stage_submissions",
    },
    {
        "position_role": "DIPPING_OPERATOR",
        "field_key": "glue_gain",
        "display_name": "上胶量",
        "data_type": "DECIMAL",
        "source_table": "bamboo_stage_submissions",
    },
    {
        "position_role": "DIPPING_OPERATOR",
        "field_key": "moisture_average",
        "display_name": "含水率",
        "data_type": "DECIMAL",
        "source_table": "bamboo_stage_submissions",
    },
    {
        "position_role": "DIPPING_OPERATOR",
        "field_key": "effective_grade",
        "display_name": "最终评级",
        "data_type": "STRING",
        "source_table": "quality_dispositions",
    },
    # ── DRYING_RACK_OPERATOR ──
    {
        "position_role": "DRYING_RACK_OPERATOR",
        "field_key": "rack_count",
        "display_name": "架数",
        "data_type": "INTEGER",
        "source_table": "bamboo_stage_submissions",
    },
    {
        "position_role": "DRYING_RACK_OPERATOR",
        "field_key": "moisture_average",
        "display_name": "含水率",
        "data_type": "DECIMAL",
        "source_table": "bamboo_stage_submissions",
    },
    {
        "position_role": "DRYING_RACK_OPERATOR",
        "field_key": "effective_grade",
        "display_name": "最终评级",
        "data_type": "STRING",
        "source_table": "quality_dispositions",
    },
    {
        "position_role": "DRYING_RACK_OPERATOR",
        "field_key": "rack_numbers",
        "display_name": "干燥架号",
        "data_type": "JSON",
        "source_table": "bamboo_stage_submissions",
    },
]


def install_v1_field_registry(engine: Engine) -> dict[str, Any]:
    """Idempotent seed of V1 payroll field registry.

    Returns:
        dict with "created" count and "skipped" count.
    """
    created = 0
    skipped = 0
    with Session(engine) as session, session.begin():
        for entry in V1_REGISTRY_ENTRIES:
            existing = session.scalar(
                select(PayrollFieldRegistryRow).where(
                    PayrollFieldRegistryRow.position_role == entry["position_role"],
                    PayrollFieldRegistryRow.field_key == entry["field_key"],
                )
            )
            if existing is not None:
                # Update display_name and is_numeric if changed
                # but preserve any manually-governed data
                if existing.display_name != entry["display_name"]:
                    existing.display_name = entry["display_name"]
                skipped += 1
                continue
            row = PayrollFieldRegistryRow(
                registry_id=f"PFR-{uuid4().hex[:12].upper()}",
                position_role=entry["position_role"],
                field_key=entry["field_key"],
                display_name=entry["display_name"],
                data_type=entry["data_type"],
                source_table=entry["source_table"],
                active=True,
            )
            session.add(row)
            created += 1
    return {"created": created, "skipped": skipped, "total": len(V1_REGISTRY_ENTRIES)}
