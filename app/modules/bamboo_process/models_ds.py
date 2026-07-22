"""Core value objects for the bamboo production workflow."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class BambooStage(StrEnum):
    SORT = "SORT"
    DIPPING = "DIPPING"
    DRYING = "DRYING"
    SUPERVISOR = "SUPERVISOR"
    PLANT_AUDIT = "PLANT_AUDIT"


class BambooRole(StrEnum):
    SORT_OPERATOR = "SORT_OPERATOR"
    DIPPING_OPERATOR = "DIPPING_OPERATOR"
    DRYING_RACK_OPERATOR = "DRYING_RACK_OPERATOR"
    INSPECTOR = "INSPECTOR"
    SUPERVISOR = "SUPERVISOR"
    PLANT_MANAGER = "PLANT_MANAGER"
    FINANCE_APPROVER = "FINANCE_APPROVER"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class BambooRecordStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class TaskBucket(StrEnum):
    AVAILABLE = "available"
    WAITING = "waiting"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class BambooActor:
    actor_id: str
    employee_code: str
    employee_name: str
    factory_id: str
    factory_name: str
    role: BambooRole


@dataclass(frozen=True, slots=True)
class BambooRecord:
    record_id: str
    display_no: str
    factory_id: str
    source_type: str
    source_ref: str | None
    base_info: dict[str, object]
    current_stage: BambooStage | None
    status: BambooRecordStatus
    revision: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    submissions: tuple["StageSubmission", ...] = ()


@dataclass(frozen=True, slots=True)
class StageSubmission:
    submission_id: str
    record_id: str
    stage: BambooStage
    version: int
    values: dict[str, object] = field(default_factory=dict)
    actor_id: str = ""
    actor_name: str = ""
    role_code: str = ""
    factory_id: str = ""
    submitted_at: datetime | None = None
    invalidated: bool = False


@dataclass(frozen=True, slots=True)
class ElectronicSignature:
    signature_id: str
    submission_id: str
    actor_id: str
    employee_code: str
    actor_name: str
    factory_id: str
    role_code: str
    payload_hash: str
    signed_at: datetime
    device_id: str
    request_id: str
    idempotency_key: str
