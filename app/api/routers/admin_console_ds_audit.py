"""P0 audit-log endpoint — minimal read-only view over existing fact tables."""

from typing import Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BambooDailyExportBatchRow,
    BambooPlantAuditRow,
    BambooReturnRow,
    SubmissionCorrectionRow,
)

audit_router = APIRouter(prefix="/api/v1/admin", tags=["admin-audit"])


def _audits(session: Session, limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in session.scalars(
        select(BambooPlantAuditRow).order_by(
            BambooPlantAuditRow.audited_at.desc()
        ).limit(limit)
    ).all():
        result.append({
            "id": f"audit-{row.audit_id}",
            "timestamp": row.audited_at.isoformat() if row.audited_at else "",
            "actor_name": row.actor_id,
            "actor_code": row.actor_id,
            "action": "厂长签字",
            "object_type": "bamboo_record",
            "object_id": row.record_id,
            "factory_id": "",
            "request_id": "",
        })
    return result


def _returns(session: Session, limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in session.scalars(
        select(BambooReturnRow).order_by(
            BambooReturnRow.created_at.desc()
        ).limit(limit)
    ).all():
        result.append({
            "id": f"return-{row.return_id}",
            "timestamp": row.created_at.isoformat() if row.created_at else "",
            "actor_name": row.actor_id,
            "actor_code": row.actor_id,
            "action": "生产打回",
            "object_type": "bamboo_return",
            "object_id": row.return_id,
            "factory_id": "",
            "request_id": row.idempotency_key or "",
        })
    return result


def _corrections(session: Session, limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in session.scalars(
        select(SubmissionCorrectionRow).order_by(
            SubmissionCorrectionRow.created_at.desc()
        ).limit(limit)
    ).all():
        result.append({
            "id": f"corr-{row.correction_id}",
            "timestamp": row.created_at.isoformat() if row.created_at else "",
            "actor_name": row.requested_by or "",
            "actor_code": row.requested_by or "",
            "action": "财务更正",
            "object_type": "submission_correction",
            "object_id": row.correction_id,
            "factory_id": "",
            "request_id": "",
        })
    return result


def _exports(session: Session, limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in session.scalars(
        select(BambooDailyExportBatchRow).order_by(
            BambooDailyExportBatchRow.created_at.desc()
        ).limit(limit)
    ).all():
        result.append({
            "id": f"export-{row.batch_id}",
            "timestamp": row.created_at.isoformat() if row.created_at else "",
            "actor_name": row.created_by or "",
            "actor_code": row.created_by or "",
            "action": "财务导出",
            "object_type": "daily_export_batch",
            "object_id": row.batch_id,
            "factory_id": row.factory_id or "",
            "request_id": "",
        })
    return result


@audit_router.get("/audit-log")
def audit_log(
    request: Request,
    actor: str = Query(default=""),
    factory: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, object]:
    """Read-only audit log assembled from operational fact tables."""
    from app.api.routers.admin_console_ds import _admin_actor  # noqa: PLC0415
    _admin_actor(request)
    engine = request.app.state.services.engine
    with Session(engine) as session:
        items = (
            _audits(session, limit)
            + _returns(session, limit)
            + _corrections(session, limit)
            + _exports(session, limit)
        )

    items.sort(key=lambda i: str(i.get("timestamp", "")), reverse=True)

    if actor:
        items = [i for i in items if actor.lower() in str(i.get("actor_name", "")).lower()
                 or actor.lower() in str(i.get("actor_code", "")).lower()]
    if factory:
        items = [i for i in items if str(i.get("factory_id", "")) == factory]

    return {"items": items[:limit]}
