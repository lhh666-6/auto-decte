"""Master-data CRUD, lifecycle and audit HTTP endpoints."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.api.dependencies_ds import get_current_actor, get_services
from app.modules.identity_access.models_ds import Actor, Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.modules.master_data.models_ds import (
    MasterDataAlreadyExists,
    MasterDataAudit,
    MasterDataCatalog,
    MasterDataNotFound,
    MasterDataRecord,
    MasterDataRevisionConflict,
)
from app.services.container import Services

router = APIRouter(prefix="/api/v1/master-data", tags=["master-data"])

MasterDataCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
MasterDataName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
ChangeReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class CreateMasterDataRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: MasterDataCode
    display_name: MasterDataName
    attributes: dict[str, Any] = Field(default_factory=dict)
    reason: ChangeReason


class UpdateMasterDataRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    display_name: MasterDataName | None = None
    attributes: dict[str, Any] | None = None
    reason: ChangeReason


class LifecycleMasterDataRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    reason: ChangeReason


class MasterDataResponse(BaseModel):
    catalog: MasterDataCatalog
    code: str
    display_name: str
    attributes: dict[str, Any]
    active: bool
    revision: int
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


class MasterDataListResponse(BaseModel):
    items: list[MasterDataResponse]


class MasterDataAuditResponse(BaseModel):
    audit_id: str
    catalog: MasterDataCatalog
    code: str
    revision: int
    event_type: str
    actor_id: str
    timestamp: datetime
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str


def _actor(request: Request, services: Services) -> Actor:
    return get_current_actor(request, services)


def _require(actor: Actor, permission: Permission) -> None:
    try:
        PermissionPolicy().require(actor, permission)
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail={"code": "PERMISSION_DENIED", "detail": str(error)},
        ) from error


def _record_response(record: MasterDataRecord) -> MasterDataResponse:
    return MasterDataResponse(
        catalog=record.catalog,
        code=record.code,
        display_name=record.display_name,
        attributes=record.attributes,
        active=record.active,
        revision=record.revision,
        created_at=record.created_at,
        updated_at=record.updated_at,
        created_by=record.created_by,
        updated_by=record.updated_by,
    )


def _audit_response(audit: MasterDataAudit) -> MasterDataAuditResponse:
    return MasterDataAuditResponse(
        audit_id=audit.audit_id,
        catalog=audit.catalog,
        code=audit.code,
        revision=audit.revision,
        event_type=audit.event_type,
        actor_id=audit.actor_id,
        timestamp=audit.timestamp,
        before=audit.before,
        after=audit.after,
        reason=audit.reason,
    )


def _set_etag(response: Response, revision: int) -> None:
    response.headers["ETag"] = f'"{revision}"'


def _revision(if_match: str | None, body_revision: int) -> int:
    if if_match is None:
        return body_revision
    value = if_match.strip()
    if value.startswith("W/"):
        value = value[2:]
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1]
    try:
        revision = int(value)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_IF_MATCH", "detail": "If-Match must contain a revision."},
        ) from error
    if revision < 1:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_IF_MATCH", "detail": "If-Match must be positive."},
        )
    return revision


def _translate(error: Exception) -> HTTPException:
    if isinstance(error, MasterDataAlreadyExists):
        return HTTPException(
            status_code=409,
            detail={
                "code": "MASTER_DATA_ALREADY_EXISTS",
                "detail": "The master-data code already exists.",
            },
        )
    if isinstance(error, MasterDataNotFound):
        return HTTPException(
            status_code=404,
            detail={
                "code": "MASTER_DATA_NOT_FOUND",
                "detail": "The master-data record does not exist.",
            },
        )
    if isinstance(error, MasterDataRevisionConflict):
        return HTTPException(
            status_code=409,
            detail={
                "code": "MASTER_DATA_REVISION_CONFLICT",
                "detail": str(error),
                "submitted_revision": error.submitted_revision,
                "current_revision": error.current_revision,
            },
        )
    return HTTPException(status_code=500, detail="Unexpected master-data error")


@router.get("/{catalog}", response_model=MasterDataListResponse)
def list_master_data(
    catalog: MasterDataCatalog,
    request: Request,
    include_inactive: bool = False,
    query: str | None = None,
    services: Services = Depends(get_services),  # noqa: B008
) -> MasterDataListResponse:
    _require(_actor(request, services), Permission.MASTER_DATA_READ)
    return MasterDataListResponse(
        items=[
            _record_response(record)
            for record in services.master_data.list_records(
                catalog, include_inactive=include_inactive, query=query
            )
        ]
    )


@router.post("/{catalog}", response_model=MasterDataResponse, status_code=201)
def create_master_data(
    catalog: MasterDataCatalog,
    body: CreateMasterDataRequest,
    request: Request,
    response: Response,
    services: Services = Depends(get_services),  # noqa: B008
) -> MasterDataResponse:
    actor = _actor(request, services)
    _require(actor, Permission.MASTER_DATA_WRITE)
    try:
        record = services.master_data.create(
            catalog,
            body.code,
            body.display_name,
            body.attributes,
            actor.actor_id,
            body.reason,
        )
    except (MasterDataAlreadyExists, MasterDataNotFound, MasterDataRevisionConflict) as error:
        raise _translate(error) from error
    _set_etag(response, record.revision)
    return _record_response(record)


@router.get("/{catalog}/{code}", response_model=MasterDataResponse)
def get_master_data(
    catalog: MasterDataCatalog,
    code: str,
    request: Request,
    response: Response,
    services: Services = Depends(get_services),  # noqa: B008
) -> MasterDataResponse:
    _require(_actor(request, services), Permission.MASTER_DATA_READ)
    try:
        record = services.master_data.get(catalog, code)
    except MasterDataNotFound as error:
        raise _translate(error) from error
    _set_etag(response, record.revision)
    return _record_response(record)


@router.patch("/{catalog}/{code}", response_model=MasterDataResponse)
def update_master_data(
    catalog: MasterDataCatalog,
    code: str,
    body: UpdateMasterDataRequest,
    request: Request,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    services: Services = Depends(get_services),  # noqa: B008
) -> MasterDataResponse:
    actor = _actor(request, services)
    _require(actor, Permission.MASTER_DATA_WRITE)
    try:
        record = services.master_data.update(
            catalog,
            code,
            _revision(if_match, body.expected_revision),
            actor.actor_id,
            body.reason,
            display_name=body.display_name,
            attributes=body.attributes,
        )
    except (MasterDataNotFound, MasterDataRevisionConflict) as error:
        raise _translate(error) from error
    _set_etag(response, record.revision)
    return _record_response(record)


def _set_lifecycle(
    catalog: MasterDataCatalog,
    code: str,
    body: LifecycleMasterDataRequest,
    request: Request,
    response: Response,
    if_match: str | None,
    services: Services,
    *,
    active: bool,
) -> MasterDataResponse:
    actor = _actor(request, services)
    _require(actor, Permission.MASTER_DATA_WRITE)
    try:
        record = services.master_data.set_active(
            catalog,
            code,
            active,
            _revision(if_match, body.expected_revision),
            actor.actor_id,
            body.reason,
        )
    except (MasterDataNotFound, MasterDataRevisionConflict) as error:
        raise _translate(error) from error
    _set_etag(response, record.revision)
    return _record_response(record)


@router.post("/{catalog}/{code}/deactivate", response_model=MasterDataResponse)
def deactivate_master_data(
    catalog: MasterDataCatalog,
    code: str,
    body: LifecycleMasterDataRequest,
    request: Request,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    services: Services = Depends(get_services),  # noqa: B008
) -> MasterDataResponse:
    return _set_lifecycle(catalog, code, body, request, response, if_match, services, active=False)


@router.post("/{catalog}/{code}/reactivate", response_model=MasterDataResponse)
def reactivate_master_data(
    catalog: MasterDataCatalog,
    code: str,
    body: LifecycleMasterDataRequest,
    request: Request,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    services: Services = Depends(get_services),  # noqa: B008
) -> MasterDataResponse:
    return _set_lifecycle(catalog, code, body, request, response, if_match, services, active=True)


@router.get("/{catalog}/{code}/audit", response_model=list[MasterDataAuditResponse])
def list_master_data_audit(
    catalog: MasterDataCatalog,
    code: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> list[MasterDataAuditResponse]:
    actor = _actor(request, services)
    _require(actor, Permission.MASTER_DATA_READ)
    _require(actor, Permission.AUDIT_READ)
    try:
        return [_audit_response(audit) for audit in services.master_data.audits(catalog, code)]
    except MasterDataNotFound as error:
        raise _translate(error) from error
