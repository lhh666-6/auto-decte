"""Phase 5 governed payroll requests."""

from typing import Any

from pydantic import BaseModel, Field


class CreatePayrollRuleRequest(BaseModel):
    rule_key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    factory_id: str = Field(min_length=1, max_length=100)
    position: str = Field(min_length=1, max_length=100)
    dsl: dict[str, Any]


class PayrollDecisionRequest(BaseModel):
    approved: bool
    note: str = Field(default="", max_length=500)


class CalculatePayrollRequest(BaseModel):
    rule_version_id: str
    period_start: str
    period_end: str


class RecalculatePayrollRequest(BaseModel):
    source_batch_id: str
    new_rule_version_id: str
