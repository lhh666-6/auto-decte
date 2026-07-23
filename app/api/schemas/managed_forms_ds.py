"""HTTP contracts for managed electronic forms."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateManagedFormRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    form_key: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=1, max_length=120)
    owner_role: str = Field(min_length=1, max_length=64)
    schema_data: dict[str, Any] = Field(alias="schema_json")


class UpdateManagedFormVersionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    expected_revision: int = Field(ge=1)
    schema_data: dict[str, Any] = Field(alias="schema_json")


class ManagedFormVersionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    definition_id: str
    form_key: str
    name: str
    owner_role: str
    version_id: str
    version: int
    schema_data: dict[str, Any] = Field(alias="schema_json")
    content_hash: str
    status: str
    revision: int
    created_by: str
    created_at: datetime
    submitted_at: datetime | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_comment: str = ""
    activation_status: str | None = None
    plant_id: str | None = None


class ManagedFormListResponse(BaseModel):
    items: list[ManagedFormVersionResponse]


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    comment: str = Field(default="", max_length=500)


class PlantActivationRequest(BaseModel):
    plant_ids: list[str] = Field(min_length=1)


class PlantActivationResponse(BaseModel):
    version_id: str
    status: str
    plant_ids: list[str]


class ManagementNotificationResponse(BaseModel):
    notification_id: str
    type: str
    plant_id: str
    title: str
    body: str
    resource_type: str
    resource_id: str
    created_at: datetime
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None


class ManagementNotificationListResponse(BaseModel):
    items: list[ManagementNotificationResponse]
