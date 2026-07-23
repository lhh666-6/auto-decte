"""Authorized, published mobile definition routes."""

from typing import cast

from fastapi import APIRouter, HTTPException, Request

from app.api.routers.mobile_auth_ds import require_mobile_actor
from app.api.schemas.mobile_ds import (
    AvailableFormItem,
    AvailableFormsResponse,
    FormFieldDefSchema,
    FormSchemaResponse,
)
from app.application.mobile_identity_ds import MobileActor
from app.modules.electronic_forms.governance_ds import ManagedFormService
from app.modules.electronic_forms.models_ds import DefinitionNotPublished
from app.services.container import Services

router = APIRouter()


def _services(request: Request) -> Services:
    return cast(Services, request.app.state.services)


def _published(request: Request, form_type: str):  # type: ignore[no-untyped-def]
    actor = require_mobile_actor(request)
    if form_type not in actor.allowed_form_types:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORM_TYPE_FORBIDDEN", "detail": "无权填写该表单。"},
        )
    try:
        return _services(request).electronic_definitions.get_published(form_type)
    except DefinitionNotPublished as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "DEFINITION_NOT_PUBLISHED", "detail": "表单尚未发布。"},
        ) from error


def _modes(form_type: str, roles: list[str]) -> list[str]:
    if form_type.startswith("TEAM_"):
        return ["TEAM_LEADER_BATCH"] if "TEAM_LEADER" in roles else []
    return ["SELF"]


def _managed_forms(request: Request, actor: MobileActor) -> list[dict[str, object]]:
    if not actor.factory_id:
        return []
    active = ManagedFormService(_services(request).engine).list_plant_forms(actor.factory_id)
    return [
        item
        for item in active
        if str(item["owner_role"]) in actor.roles
    ]


@router.get("/available-forms", response_model=AvailableFormsResponse)
def available_forms(request: Request) -> AvailableFormsResponse:
    actor = require_mobile_actor(request)
    forms: list[AvailableFormItem] = []
    for form_type in actor.allowed_form_types:
        try:
            definition = _services(request).electronic_definitions.get_published(form_type)
        except DefinitionNotPublished:
            continue
        modes = _modes(form_type, actor.roles)
        if not modes:
            continue
        forms.append(
            AvailableFormItem(
                form_type=form_type,
                title=definition.display_name,
                modes=modes,
                definition_version_id=definition.definition_version_id,
                allowed_processes=actor.allowed_processes,
            )
        )
    known_form_types = {item.form_type for item in forms}
    for managed_definition in _managed_forms(request, actor):
        form_type = str(managed_definition["form_key"])
        if form_type in known_form_types:
            continue
        forms.append(
            AvailableFormItem(
                form_type=form_type,
                title=str(managed_definition["name"]),
                modes=_modes(form_type, actor.roles),
                definition_version_id=str(managed_definition["version_id"]),
                allowed_processes=actor.allowed_processes,
            )
        )
    return AvailableFormsResponse(forms=forms)


@router.get("/form-schemas/{form_type}", response_model=FormSchemaResponse)
def form_schema(form_type: str, request: Request) -> FormSchemaResponse:
    actor = require_mobile_actor(request)
    managed = ManagedFormService(_services(request).engine).resolve_active_form(
        actor.factory_id,
        form_type,
        actor.roles,
    )
    if managed is not None:
        schema = cast(dict[str, object], managed["schema_json"])
        raw_fields = cast(list[dict[str, object]], schema.get("fields", []))
        return FormSchemaResponse(
            form_type=form_type,
            title=str(managed["name"]),
            modes=_modes(form_type, actor.roles),
            definition_version_id=str(managed["version_id"]),
            version=str(managed["version"]),
            fields=[
                FormFieldDefSchema(
                    field_name=str(field["key"]),
                    field_type=str(field.get("type", "text")),
                    label=str(field.get("label", field["key"])),
                    strategy="MANUAL_REQUIRED"
                    if bool(field.get("required"))
                    else "DEFAULT_EDITABLE",
                    source="USER",
                    required=bool(field.get("required")),
                    editable=True,
                    input_type=str(field.get("type", "text")),
                )
                for field in raw_fields
            ],
        )
    definition = _published(request, form_type)
    config = definition.presentation_config
    fields = [
        FormFieldDefSchema(
            field_name=field.field_key,
            field_type=field.strategy,
            label=field.field_key,
            strategy=field.strategy,
            source="SERVER" if field.strategy == "COMPUTED_READ_ONLY" else "USER",
            required=field.strategy == "MANUAL_REQUIRED",
            editable=field.strategy != "COMPUTED_READ_ONLY",
        )
        for field in (config.fields if config else [])
    ]
    return FormSchemaResponse(
        form_type=form_type,
        title=definition.display_name,
        modes=_modes(form_type, actor.roles),
        definition_version_id=definition.definition_version_id,
        version=str(definition.version),
        fields=fields,
    )
