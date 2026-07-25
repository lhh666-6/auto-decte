"""HTTP contracts for the mobile bamboo workflow."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateBambooRecordRequest(BaseModel):
    form_type: Literal["SORTING"] = "SORTING"
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


class BambooUpstreamRecordResponse(BaseModel):
    record_id: str
    display_no: str
    factory_id: str
    form_type: str
    base_info: dict[str, Any]
    current_stage: str | None
    status: str
    revision: int
    submissions: list[BambooSubmissionResponse]


class BambooRecordResponse(BaseModel):
    record_id: str
    display_no: str
    factory_id: str
    source_type: str
    source_ref: str | None
    form_type: str
    production_object_id: str | None
    source_record_id: str | None
    source_snapshot: dict[str, Any]
    base_info: dict[str, Any]
    current_stage: str | None
    status: str
    revision: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    submissions: list[BambooSubmissionResponse]
    upstream_record: BambooUpstreamRecordResponse | None = None


class BambooTaskListResponse(BaseModel):
    bucket: str
    tasks: list[BambooRecordResponse]


class BambooDashboardResponse(BaseModel):
    available: int
    waiting: int
    completed: int


class CreateInspectionRequest(BaseModel):
    serial_no: str | None = Field(default=None, max_length=64)
    target_stage: str | None = None
    moisture_points: list[float] = Field(default_factory=list, max_length=20)
    conclusion: str
    note: str | None = Field(default=None, max_length=1000)
    text_evidence: str | None = Field(default=None, max_length=10000)
    device_id: str = Field(min_length=1, max_length=128)


class CloseInspectionExceptionRequest(BaseModel):
    resolution: str = Field(min_length=1, max_length=2000)


class TerminateInspectionRequest(BaseModel):
    confirm: bool
    reason: str = Field(default="", max_length=2000)


class SubmitInspectionAppealRequest(BaseModel):
    target_stage: str
    text_evidence: str = Field(min_length=1, max_length=10000)


class InspectionAppealDecisionRequest(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=2000)


class SelectiveReturnRequest(BaseModel):
    target_stages: list[str] = Field(min_length=1, max_length=3)
    reason: str = Field(min_length=1, max_length=2000)
    source: str = Field(default="SUPERVISOR", max_length=32)
    expected_revision: int = Field(ge=1)


class RoleChangeRequest(BaseModel):
    to_role: str
    reason: str = Field(min_length=1, max_length=1000)


class RoleChangeDecisionRequest(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=1000)


class CreatePersonnelTransferRequest(BaseModel):
    employee_code: str = Field(min_length=1, max_length=64)
    to_role: str = Field(min_length=1, max_length=64)
    target_factory_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=2000)


class PersonnelTransferDecisionRequest(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=2000)


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


class CreateFactoryEmployeeRequest(BaseModel):
    employee_name: str = Field(min_length=1, max_length=100)
    initial_pin: str = Field(min_length=4, max_length=12, pattern=r"^\d+$")
    role_code: str = Field(min_length=1, max_length=64)


class AdminCreateEmployeeRequest(BaseModel):
    """V1: employee_code is auto-generated server-side; not accepted from client."""
    employee_name: str = Field(min_length=1, max_length=100)
    factory_id: str = Field(min_length=1, max_length=64)
    bamboo_role: str = Field(min_length=1, max_length=64)
    web_roles: list[str] = Field(default_factory=list)
    initial_pin: str = Field(min_length=4, max_length=12, pattern=r"^\d+$")


class CreateFactoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)


class AdminCreateFactoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
