"""Core value objects for the bamboo production workflow."""

from dataclasses import dataclass, field
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
    submitted_at: str = ""
    invalidated: bool = False
