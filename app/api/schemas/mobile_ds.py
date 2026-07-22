"""Pydantic request/response schemas for the mobile API.

Replaces bare dict[str, Any] contracts in the current prototype.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Auth ────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    employee_code: str = Field(min_length=1, max_length=32)
    pin: str = Field(min_length=1, max_length=64)
    device_id: str = Field(default="unknown", max_length=128)


class LoginResponse(BaseModel):
    employee_name: str
    employee_code: str
    team_name: str
    position: str
    roles: list[str]
    expires_at: str | None = None
    factory_id: str = ""
    factory_name: str = ""
    bamboo_role: str = ""


class SessionResponse(BaseModel):
    employee_name: str
    employee_code: str
    team_name: str
    position: str
    roles: list[str]
    allowed_form_types: list[str]
    allowed_processes: list[str]
    factory_id: str = ""
    factory_name: str = ""
    bamboo_role: str = ""


# ── Forms ───────────────────────────────────────────────────────

class AvailableFormItem(BaseModel):
    form_type: str
    title: str
    modes: list[str]
    definition_version_id: str
    allowed_processes: list[str] | None = None


class AvailableFormsResponse(BaseModel):
    forms: list[AvailableFormItem]


class FormFieldDefSchema(BaseModel):
    field_name: str
    field_type: str
    label: str
    strategy: str
    source: str
    required: bool = False
    preset_options: list[str] | None = None
    default_value: Any = None
    editable: bool = False
    input_type: str = "text"


class FormSchemaResponse(BaseModel):
    form_type: str
    title: str
    modes: list[str]
    definition_version_id: str
    version: str = "1.0"
    fields: list[FormFieldDefSchema]


# ── Context ─────────────────────────────────────────────────────

class ContextResponse(BaseModel):
    employee_name: str
    employee_code: str
    team_name: str
    position: str
    server_time: str
    server_date: str
    suggested_shift: str
    roles: list[str]


class ActiveResourceItem(BaseModel):
    resource_id: str
    short_code: str
    variety: str
    grade: str
    supplier: str
    current_status: str
    last_process: str
    last_process_time: str


class ActiveResourcesResponse(BaseModel):
    resources: list[ActiveResourceItem]


class ProductionContextResponse(BaseModel):
    context_id: str
    team_id: str
    date: str
    shift: str
    work_orders: list[str]
    products: list[str]
    specs: list[str]
    pieces_per_block: int | None = None


# ── Definitions ─────────────────────────────────────────────────

class PresentationFieldSchema(BaseModel):
    field_key: str
    display_order: int
    group: str | None = None
    strategy: str = "DEFAULT_EDITABLE"
    condition_rule: dict[str, Any] | None = None


class CreateDefinitionRequest(BaseModel):
    form_type: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    template_version_id: str | None = None
    job_profile_version_id: str | None = None
    presentation_fields: list[PresentationFieldSchema] | None = None
    groups: list[str] | None = None


class DefinitionResponse(BaseModel):
    definition_version_id: str
    form_type: str
    version: int
    status: str
    display_name: str
    template_version_id: str | None = None
    job_profile_version_id: str | None = None
    created_by: str = ""
    created_at: str | None = None
    published_at: str | None = None


# ── Drafts ──────────────────────────────────────────────────────

class SaveDraftRequest(BaseModel):
    form_type: str = Field(min_length=1, max_length=64)
    draft_id: str | None = None
    device_id: str = Field(default="unknown")
    values: dict[str, Any] = Field(default_factory=dict)


class DraftResponse(BaseModel):
    draft_id: str
    form_type: str
    updated_at: str
    values: dict[str, Any]


# ── Submissions ─────────────────────────────────────────────────

class CreateSubmissionRequest(BaseModel):
    form_type: str = Field(min_length=1, max_length=64)
    definition_version_id: str = Field(min_length=1)
    mode: str = Field(default="SELF", pattern=r"^(SELF|TEAM_LEADER_BATCH)$")
    subject_employee_code: str = Field(min_length=1, max_length=32)
    device_id: str = Field(default="unknown", max_length=128)
    values: dict[str, Any] = Field(default_factory=dict)


class SubmissionResponse(BaseModel):
    submission_id: str
    status: str
    submitted_at: str
    idempotent: bool = False


class SubmissionListItem(BaseModel):
    submission_id: str
    form_type_label: str
    form_type: str
    status: str
    submitted_at: str
    process_code: str | None = None


# ── Options ─────────────────────────────────────────────────────

class OptionsResponse(BaseModel):
    option_set: str
    options: list[str]
