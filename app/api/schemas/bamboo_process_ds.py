"""HTTP contracts for the mobile bamboo workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateBambooRecordRequest(BaseModel):
    base_info: dict[str, Any] = Field(default_factory=dict)


class SubmitBambooStageRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    device_id: str = Field(min_length=1, max_length=128)
    values: dict[str, Any] = Field(default_factory=dict)


class BambooSubmissionResponse(BaseModel):
    submission_id: str
    stage: str
    version: int
    values: dict[str, Any]
    actor_id: str
    actor_name: str
    role_code: str
    submitted_at: datetime | None


class BambooRecordResponse(BaseModel):
    record_id: str
    display_no: str
    factory_id: str
    source_type: str
    source_ref: str | None
    base_info: dict[str, Any]
    current_stage: str | None
    status: str
    revision: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    submissions: list[BambooSubmissionResponse]


class BambooTaskListResponse(BaseModel):
    bucket: str
    tasks: list[BambooRecordResponse]


class BambooDashboardResponse(BaseModel):
    available: int
    waiting: int
    completed: int
