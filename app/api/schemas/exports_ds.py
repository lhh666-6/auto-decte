"""Safe HTTP DTOs for template-driven exports."""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import ExportStatus, ReviewStatus
from app.modules.reporting.models_ds import (
    AggregateOperation,
    ReportDefinitionStatus,
    ReportKind,
)


class ExportReasonResponse(BaseModel):
    scope: str
    code: str
    field_key: str | None = None
    message: str
    required: bool | None = None
    allowed_values: list[str] | None = None
    minimum_value: float | None = None
    maximum_value: float | None = None


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
    model_config = ConfigDict(extra="forbid")

    form_id: str | None = None
    employee_id: str | None = None
    work_order_id: str | None = None
    review_status: ReviewStatus | None = None
    export_status: ExportStatus | None = None


class ExportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_type: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    filters: ExportFiltersRequest
    supersedes_batch_id: str | None = Field(default=None, min_length=1)
    report_definition_id: str | None = Field(
        default=None, min_length=1, pattern=r"^[A-Za-z0-9_:-]+$"
    )


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


class ReportColumnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_field: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    header: str = Field(min_length=1)


class ReportAggregateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_field: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    operation: AggregateOperation
    header: str = Field(min_length=1)


class FixedCellMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell: str = Field(pattern=r"^[A-Z]{1,3}[1-9][0-9]*$")
    source_field: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")


class FixedTableColumnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str = Field(pattern=r"^[A-Z]{1,3}$")
    source_field: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")


class FixedTableMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_row: int = Field(ge=1)
    max_rows: int = Field(ge=1)
    columns: list[FixedTableColumnRequest] = Field(min_length=1)


class ReportDefinitionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_:-]+$")
    report_key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    version: int = Field(ge=1)
    display_name: str = Field(min_length=1)
    kind: ReportKind
    status: ReportDefinitionStatus
    columns: list[ReportColumnRequest] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregates: list[ReportAggregateRequest] = Field(default_factory=list)
    sort_by: list[str] = Field(default_factory=list)
    worksheet: str = Field(default="报表", min_length=1, max_length=31)
    fixed_template_key: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    fixed_template_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    fixed_cells: list[FixedCellMappingRequest] = Field(default_factory=list)
    fixed_table: FixedTableMappingRequest | None = None


class ReportDefinitionResponse(ReportDefinitionCreateRequest):
    pass


class ReportAssistantPreviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    included_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    reason_codes: list[str] = Field(
        default_factory=list,
        max_length=30,
    )


class ReportAssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=1000)
    selected_report_definition_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_:-]+$")
    preview_summary: ReportAssistantPreviewSummary | None = None


class ReportAssistantResponse(BaseModel):
    status: str
    answer: str
    suggested_report_definition_id: str | None = None
    suggested_filter_fields: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    requires_user_confirmation: bool
