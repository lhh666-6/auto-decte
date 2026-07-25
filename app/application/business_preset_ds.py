"""Business Preset Service — decoupled from Payroll Rules.

V1 Final Cutover: Business field presets (grades, lengths, shades,
special_classes, weight_factors) are now managed independently by
Finance (draft) and Admin (approve/publish).

Records bind to a specific preset_version_id at creation time so
historical data is stable regardless of future preset changes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import BusinessPresetVersionRow


class BusinessPresetError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


# ── Default V1 presets (frozen per Final Cutover §2) ─────────────

V1_DEFAULT_PRESETS: dict[str, dict[str, Any]] = {
    "SORT_FIELD_OPTIONS": {
        "display_name": "分选字段选项",
        "options": {
            "special_classes": ["直装", "防霉"],
            "lengths": ["2.1", "2.3", "2.5"],
            "shades": ["深", "浅"],
            "grades": ["A", "B"],
            "weight_factors": {"2.1": "5", "2.3": "6", "2.5": "7"},
        },
    },
}

VALID_PRESET_STATUSES = {"DRAFT", "PENDING_APPROVAL", "PUBLISHED", "REJECTED", "SUPERSEDED"}


def _now() -> datetime:
    return datetime.now(UTC)


def _content_hash(options: dict[str, Any]) -> str:
    canonical = json.dumps(options, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class BusinessPresetService:
    """Versioned business field presets.

    Finance creates drafts → Admin approves/publishes.
    Published presets are immutable; new versions supersede.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def install_v1_defaults(self) -> dict[str, Any]:
        """Idempotently install V1 default presets. Called at startup."""
        installed: list[str] = []
        existing: list[str] = []
        with Session(self._engine) as session, session.begin():
            for preset_key, preset_data in V1_DEFAULT_PRESETS.items():
                current = session.scalar(
                    select(BusinessPresetVersionRow)
                    .where(BusinessPresetVersionRow.preset_key == preset_key)
                    .order_by(BusinessPresetVersionRow.version.desc())
                    .limit(1)
                )
                if current is None:
                    row = BusinessPresetVersionRow(
                        preset_version_id=f"PRESET-{preset_key}-V1",
                        preset_key=preset_key,
                        display_name=preset_data["display_name"],
                        version=1,
                        options=preset_data["options"],
                        content_hash=_content_hash(preset_data["options"]),
                        status="PUBLISHED",
                        created_by="SYSTEM",
                        created_at=_now(),
                        reviewed_by="SYSTEM",
                        reviewed_at=_now(),
                    )
                    session.add(row)
                    installed.append(preset_key)
                else:
                    existing.append(preset_key)
        return {"installed": installed, "existing": existing}

    def get_published(self, preset_key: str) -> dict[str, Any] | None:
        with Session(self._engine) as session:
            row = session.scalar(
                select(BusinessPresetVersionRow)
                .where(
                    BusinessPresetVersionRow.preset_key == preset_key,
                    BusinessPresetVersionRow.status == "PUBLISHED",
                )
                .order_by(BusinessPresetVersionRow.version.desc())
                .limit(1)
            )
            return self._to_dict(row) if row else None

    def create_draft(
        self,
        preset_key: str,
        display_name: str,
        options: dict[str, Any],
        created_by: str,
    ) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            latest = session.scalar(
                select(BusinessPresetVersionRow)
                .where(BusinessPresetVersionRow.preset_key == preset_key)
                .order_by(BusinessPresetVersionRow.version.desc())
                .limit(1)
            )
            next_version = (latest.version + 1) if latest else 1
            row = BusinessPresetVersionRow(
                preset_version_id=f"PRESET-{preset_key}-V{next_version}",
                preset_key=preset_key,
                display_name=display_name,
                version=next_version,
                options=options,
                content_hash=_content_hash(options),
                status="DRAFT",
                created_by=created_by,
                created_at=_now(),
            )
            session.add(row)
            return self._to_dict(row)

    def list_presets(self) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            # Return latest version per preset_key
            subq = (
                select(
                    BusinessPresetVersionRow.preset_key,
                    BusinessPresetVersionRow.preset_version_id,
                )
                .order_by(
                    BusinessPresetVersionRow.preset_key,
                    BusinessPresetVersionRow.version.desc(),
                )
                .subquery()
            )
            rows = session.scalars(
                select(BusinessPresetVersionRow)
                .where(
                    BusinessPresetVersionRow.preset_version_id.in_(
                        select(subq.c.preset_version_id)
                    )
                )
                .order_by(BusinessPresetVersionRow.preset_key)
            ).all()
            return [self._to_dict(row) for row in rows]

    @staticmethod
    def _to_dict(row: BusinessPresetVersionRow) -> dict[str, Any]:
        return {
            "preset_version_id": row.preset_version_id,
            "preset_key": row.preset_key,
            "display_name": row.display_name,
            "version": row.version,
            "options": row.options,
            "content_hash": row.content_hash,
            "status": row.status,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "reviewed_by": row.reviewed_by,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        }
