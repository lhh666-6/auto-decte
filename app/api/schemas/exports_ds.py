"""Safe HTTP DTOs for template-driven exports."""

from pydantic import BaseModel, Field

from app.domain.models import ExportStatus, ReviewStatus


class ExportReasonResponse(BaseModel):
    scope: str
    code: str
    field_key: str | None = None
    message: str


class ExportPreviewItemResponse(BaseModel):
    form_id: str
    record_version: int
    reason: str | None = None
    reasons: list[ExportReasonResponse] = Field(default_factory=list)


class ExportMappingResponse(BaseModel):
    template_id: str
    template_version: str
    field_key: str
    workbook: str
    worksheet: str
    business_column: str


class ExportPreviewResponse(BaseModel):
    included: list[ExportPreviewItemResponse]
    excluded: list[ExportPreviewItemResponse]
    mapping_snapshot: list[ExportMappingResponse]


class ExportFiltersRequest(BaseModel):
    form_id: str | None = None
    employee_id: str | None = None
    work_order_id: str | None = None
    review_status: ReviewStatus | None = None
    export_status: ExportStatus | None = None


class ExportCreateRequest(BaseModel):
    export_type: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    filters: ExportFiltersRequest
    supersedes_batch_id: str | None = Field(default=None, min_length=1)


class IncludedRecordResponse(BaseModel):
    form_id: str
    record_version: int


class ExportBatchResponse(BaseModel):
    export_batch_id: str
    export_type: str
    task_id: str | None
    template_snapshot: dict[str, object]
    mapping_snapshot: list[dict[str, object]]
    mapping_hash: str
    filters: dict[str, object]
    included_records: list[IncludedRecordResponse]
    file_sha256: str
    exported_by: str
    exported_at: str
    supersedes_batch_id: str | None
    download_url: str
    download_name: str
