"""Mobile production context sourced from master data."""

from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, HTTPException, Request

from app.api.routers.mobile_auth_ds import require_mobile_actor
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services

router = APIRouter()


def _services(request: Request) -> Services:
    return cast(Services, request.app.state.services)


@router.get("/context")
def context(request: Request) -> dict[str, object]:
    actor = require_mobile_actor(request)
    now = datetime.now(UTC)
    return {
        "employee_name": actor.employee_name,
        "employee_code": actor.employee_code,
        "team_name": actor.team_name,
        "position": actor.position,
        "server_time": now.isoformat(),
        "server_date": now.date().isoformat(),
        "suggested_shift": "白班" if 7 <= now.hour < 19 else "夜班",
        "roles": actor.roles,
    }


@router.get("/options/{catalog}")
def options(catalog: MasterDataCatalog, request: Request) -> dict[str, object]:
    require_mobile_actor(request)
    records = _services(request).master_data.list_records(catalog)
    return {
        "option_set": catalog.value,
        "options": [
            {"value": record.code, "label": record.display_name}
            for record in records
        ],
    }


@router.get("/active-resources")
def active_resources(request: Request) -> None:
    require_mobile_actor(request)
    raise HTTPException(
        status_code=503,
        detail={
            "code": "RESOURCE_PROVIDER_UNAVAILABLE",
            "detail": "当前尚未接入正式笼资源数据，暂不可填写该表单。",
        },
    )


@router.get("/team-members")
def team_members(request: Request) -> dict[str, object]:
    actor = require_mobile_actor(request)
    members = _services(request).mobile_identity_repository.list_team_members(
        actor.team_id
    )
    return {
        "members": [
            {"employee_code": code, "employee_name": name}
            for code, name in members
        ]
    }


@router.get("/production-contexts/current")
def production_context(request: Request) -> dict[str, object]:
    actor = require_mobile_actor(request)
    services = _services(request)
    now = datetime.now(UTC)
    work_orders = services.master_data.list_records(MasterDataCatalog.WORK_ORDERS)
    products = services.master_data.list_records(MasterDataCatalog.PRODUCTS)
    specs = sorted(
        {
            str(record.attributes["spec"])
            for record in products
            if record.attributes.get("spec")
        }
    )
    pieces_per_block: int | None = None
    for record in products:
        configured_pieces = record.attributes.get("pieces_per_block")
        if isinstance(configured_pieces, int):
            pieces_per_block = configured_pieces
            break
    return {
        "context_id": f"{actor.team_id}:{now.date().isoformat()}",
        "team_id": actor.team_id,
        "date": now.date().isoformat(),
        "shift": "白班" if 7 <= now.hour < 19 else "夜班",
        "work_orders": [record.code for record in work_orders],
        "products": [record.code for record in products],
        "specs": specs,
        "pieces_per_block": pieces_per_block,
    }
