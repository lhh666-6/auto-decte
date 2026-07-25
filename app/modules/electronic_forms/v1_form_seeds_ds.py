"""V1 Business Form seeds — idempotently install the two authoritative managed forms.

Per Final Cutover §2.5 and user confirmation (2026-07-24):
  SORTING        → 《竹丝装笼跟踪牌》
  DIPPING_DRYING → 《配片数计量考核表》
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import ManagedFormDefinitionRow, ManagedFormVersionRow

V1_FORM_SEEDS: list[dict[str, Any]] = [
    {
        "form_key": "SORTING",
        "name": "竹丝装笼跟踪牌",
        "owner_role": "SYSTEM_ADMIN",
        "schema_json": {
            "stages": ["SORT", "SUPERVISOR", "PLANT_AUDIT"],
            "fields": [
                {
                    "key": "mode", "label": "作业模式", "type": "select",
                    "options": ["分选", "分选+装笼"],
                },
                {"key": "cage_no", "label": "笼号", "type": "text"},
                {"key": "bundle_count", "label": "把数", "type": "integer"},
                {"key": "length", "label": "长度", "type": "select"},
                {"key": "shade", "label": "深浅", "type": "select", "options": ["深", "浅"]},
                {"key": "grade", "label": "品级", "type": "select", "options": ["A", "B"]},
                {"key": "supplier", "label": "供应商", "type": "text"},
                {"key": "special_classes", "label": "特殊类别", "type": "multi_select"},
                {"key": "moisture", "label": "含水率检测点", "type": "number_list"},
                {"key": "note", "label": "备注", "type": "text"},
            ],
        },
    },
    {
        "form_key": "DIPPING_DRYING",
        "name": "配片数计量考核表",
        "owner_role": "SYSTEM_ADMIN",
        "schema_json": {
            "stages": ["DIPPING", "DRYING", "SUPERVISOR", "PLANT_AUDIT"],
            "depends_on": "SORTING",
            "fields": [
                {"key": "source_record_id", "label": "来源分选记录", "type": "ref"},
                {"key": "glue_before_weight", "label": "胶前重", "type": "decimal"},
                {"key": "glue_after_weight", "label": "胶后重", "type": "decimal"},
                {"key": "glue_gain", "label": "上胶量", "type": "decimal"},
                {"key": "glue_batch", "label": "胶液批次", "type": "text"},
                {"key": "dipping_start", "label": "浸胶开始时间", "type": "datetime"},
                {"key": "dipping_end", "label": "浸胶结束时间", "type": "datetime"},
                {"key": "rack_numbers", "label": "干燥架号", "type": "text_list"},
                {"key": "drying_start", "label": "干燥开始时间", "type": "datetime"},
                {"key": "drying_end", "label": "干燥结束时间", "type": "datetime"},
                {"key": "moisture", "label": "含水率检测点", "type": "number_list"},
                {"key": "note", "label": "备注", "type": "text"},
            ],
        },
    },
]


def _now() -> datetime:
    return datetime.now(UTC)


def install_v1_business_form_seeds(engine: Engine) -> dict[str, Any]:
    """Idempotently install the two V1 business forms."""
    installed: list[str] = []
    existing: list[str] = []
    now = _now()
    with Session(engine) as session, session.begin():
        for seed in V1_FORM_SEEDS:
            form_key = seed["form_key"]
            existing_def = session.scalar(
                select(ManagedFormDefinitionRow).where(
                    ManagedFormDefinitionRow.form_key == form_key
                )
            )
            if existing_def is not None:
                existing.append(form_key)
                continue
            # Create definition + published V1
            def_id = f"FORM-DEF-{form_key}-V1"
            definition = ManagedFormDefinitionRow(
                definition_id=def_id,
                form_key=form_key,
                name=seed["name"],
                owner_role=seed["owner_role"],
                created_by="SYSTEM",
                created_at=now,
            )
            schema = seed["schema_json"]
            content = json.dumps(
                schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            version = ManagedFormVersionRow(
                version_id=f"FORM-VER-{form_key}-V1",
                definition_id=def_id,
                version=1,
                schema_json=schema,
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                status="APPROVED",
                revision=1,
                created_by="SYSTEM",
                created_at=now,
                submitted_at=now,
                reviewed_by="SYSTEM",
                reviewed_at=now,
            )
            session.add_all([definition, version])
            installed.append(form_key)
    return {"installed": installed, "existing": existing}
