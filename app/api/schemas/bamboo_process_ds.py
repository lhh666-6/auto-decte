"""HTTP contracts for the mobile bamboo workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateBambooRecordRequest(BaseModel):
    base_info: dict[str, Any] = Field(default_factory=dict)


class BambooRecordOptionsResponse(BaseModel):
    options_version: str
    special_classes: list[str]
    lengths: list[str]
    shades: list[str]
    grades: list[str]
    weight_factors: dict[str, str]


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


class CreateInspectionRequest(BaseModel):
    serial_no: str = Field(min_length=1, max_length=64)
    target_stage: str
    moisture_points: list[float] = Field(min_length=1, max_length=20)
    conclusion: str
    note: str | None = Field(default=None, max_length=1000)
    text_evidence: str | None = Field(default=None, max_length=10000)
    device_id: str = Field(min_length=1, max_length=128)


class CloseInspectionExceptionRequest(BaseModel):
    resolution: str = Field(min_length=1, max_length=2000)


class SelectiveReturnRequest(BaseModel):
    target_stages: list[str] = Field(min_length=1, max_length=3)
    reason: str = Field(min_length=1, max_length=2000)
    source: str = Field(default="SUPERVISOR", max_length=32)


class RoleChangeRequest(BaseModel):
    to_role: str
    reason: str = Field(min_length=1, max_length=1000)


class RoleChangeDecisionRequest(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=1000)


class FinanceDecisionRequest(BaseModel):
    decision: str
    note: str = Field(default="", max_length=2000)


class FinanceInquiryRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)


class FinanceInquiryReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    close: bool = False


class PayrollRuleRequest(BaseModel):
    rule_key: str
    configuration: dict[str, Any]
    system_default: bool = False


class EmployeeRoleAssignmentRequest(BaseModel):
    employee_code: str = Field(min_length=1, max_length=64)
    role_code: str = Field(min_length=1, max_length=64)
    factory_id: str | None = Field(default=None, max_length=64)


class CreateFactoryRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
