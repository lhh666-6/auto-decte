"""Read-only DTOs for the human review workbench."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FormSummaryResponse(BaseModel):
    form_id: str
    template_id: str
    template_version: str
    coordinate_version: str
    review_status: str
    export_status: str
    current_record_version: int
    created_at: datetime


class CandidateResponse(BaseModel):
    attempt_id: str
    candidate_value: Any
    confidence: float
    engine: str
    model_version: str
    crop_file_id: str


class FieldResponse(BaseModel):
    field_id: str
    field_name: str
    source_region: dict[str, int]
    current_value: Any
    current_value_source: str | None
    current_record_version: int
    candidates: list[CandidateResponse]


class EvidenceResponse(BaseModel):
    file_id: str
    type: str
    related_field_id: str | None
    sha256: str
    immutable: bool
    created_at: datetime
    download_url: str


class RecordVersionResponse(BaseModel):
    record_id: str
    version: int
    previous_version: int | None
    status: str
    values: dict[str, Any]
    change_reason: str
    confirmed_by: str | None
    created_at: datetime


class AuditEventResponse(BaseModel):
    event_id: str
    event_type: str
    actor_id: str
    timestamp: datetime
    reason: str | None
    evidence_ids: list[str]


class WorkbenchDetailResponse(BaseModel):
    form: FormSummaryResponse
    fields: list[FieldResponse]
    evidence: list[EvidenceResponse]
    current_record: RecordVersionResponse | None


class ReviewHistoryResponse(BaseModel):
    versions: list[RecordVersionResponse]
    audits: list[AuditEventResponse]
