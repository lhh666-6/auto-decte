"""Immutable reporting values used to preview template-driven exports."""

import re
from dataclasses import dataclass
from enum import StrEnum

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ExportMapping:
    """A stable template field mapping independent of its display label."""

    template_id: str
    template_version: str
    field_key: str
    workbook: str
    worksheet: str
    business_column: str


class ExportExclusionReason(StrEnum):
    """Machine-readable reason a candidate form cannot be exported."""

    NOT_CONFIRMED = "NOT_CONFIRMED"
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    NO_VALID_MAPPING = "NO_VALID_MAPPING"
    FINAL_VALIDATION_FAILED = "FINAL_VALIDATION_FAILED"


class ExportReasonScope(StrEnum):
    """The record level addressed by an export exclusion reason."""

    FORM = "FORM"
    FIELD = "FIELD"


class ExportTaskPublicError(StrEnum):
    """Stable task errors safe to expose through external APIs."""

    FAILED = "EXPORT_FAILED: Export could not be completed."
    STORAGE_ACCESS_FAILED = "EXPORT_STORAGE_ACCESS_FAILED: Export storage is unavailable."
    INTEGRITY_FAILED = "EXPORT_INTEGRITY_FAILED: Export file failed integrity verification."
    VALIDATION_FAILED = "EXPORT_VALIDATION_FAILED: Export request failed validation."
    COMPLETION_FAILED = "EXPORT_COMPLETION_FAILED: Export source data changed before completion."
    RECOVERY_FAILED = "EXPORT_RECOVERY_FAILED: Export recovery could not be completed."


@dataclass(frozen=True, slots=True)
class ExportValidationReason:
    """A safe, structured explanation for an excluded form."""

    scope: ExportReasonScope
    code: str
    message: str
    field_key: str | None = None
    required: bool | None = None
    allowed_values: tuple[str, ...] | None = None
    minimum_value: float | None = None
    maximum_value: float | None = None


@dataclass(frozen=True, slots=True)
class ExportPreviewItem:
    """One versioned candidate and its optional exclusion reason."""

    form_id: str
    record_version: int
    reason: ExportExclusionReason | None = None
    reasons: tuple[ExportValidationReason, ...] = ()


@dataclass(frozen=True, slots=True)
class ExportPreview:
    """Read-only decision result for a filtered export request."""

    included: tuple[ExportPreviewItem, ...]
    excluded: tuple[ExportPreviewItem, ...]
    mapping_snapshot: tuple[ExportMapping, ...]


class ReportKind(StrEnum):
    DETAIL = "DETAIL"
    SUMMARY = "SUMMARY"
    FIXED = "FIXED"


class ReportDefinitionStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


class AggregateOperation(StrEnum):
    SUM = "SUM"
    COUNT = "COUNT"
    MIN = "MIN"
    MAX = "MAX"
    AVERAGE = "AVERAGE"


def _require_safe_field(value: str) -> None:
    if _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{value!r} is not a safe field identifier")


@dataclass(frozen=True, slots=True)
class ReportColumn:
    source_field: str
    header: str

    def __post_init__(self) -> None:
        _require_safe_field(self.source_field)
        if not self.header.strip():
            raise ValueError("column header is required")


@dataclass(frozen=True, slots=True)
class ReportAggregate:
    source_field: str
    operation: AggregateOperation
    header: str

    def __post_init__(self) -> None:
        _require_safe_field(self.source_field)
        if not self.header.strip():
            raise ValueError("aggregate header is required")


@dataclass(frozen=True, slots=True)
class ReportDefinition:
    definition_id: str
    report_key: str
    version: int
    display_name: str
    kind: ReportKind
    status: ReportDefinitionStatus
    columns: tuple[ReportColumn, ...] = ()
    filters: tuple[str, ...] = ()
    group_by: tuple[str, ...] = ()
    aggregates: tuple[ReportAggregate, ...] = ()
    sort_by: tuple[str, ...] = ()
    worksheet: str = "报表"

    def __post_init__(self) -> None:
        if not self.definition_id.strip():
            raise ValueError("definition_id is required")
        _require_safe_field(self.report_key)
        if self.version < 1:
            raise ValueError("version must be positive")
        if not self.display_name.strip():
            raise ValueError("display_name is required")
        if not self.worksheet.strip() or len(self.worksheet) > 31:
            raise ValueError("worksheet must contain 1 to 31 characters")
        if any(character in self.worksheet for character in "[]:*?/\\"):
            raise ValueError("worksheet contains an invalid character")
        for field_name in (*self.filters, *self.group_by, *self.sort_by):
            _require_safe_field(field_name)
        if self.kind is ReportKind.SUMMARY and not self.group_by:
            raise ValueError("summary report requires group_by")
        if self.kind is ReportKind.SUMMARY and not self.aggregates:
            raise ValueError("summary report requires aggregates")
        headers = [column.header for column in self.columns]
        headers.extend(aggregate.header for aggregate in self.aggregates)
        if len(headers) != len(set(headers)):
            raise ValueError("report headers must be unique")


BUILTIN_REPORT_DEFINITIONS = (
    ReportDefinition(
        "PAYROLL_DETAIL:1",
        "PAYROLL_DETAIL",
        1,
        "工资明细",
        ReportKind.DETAIL,
        ReportDefinitionStatus.PUBLISHED,
        columns=(
            ReportColumn("employee_id", "员工编号"),
            ReportColumn("employee_name", "姓名"),
            ReportColumn("work_order_id", "工单编号"),
            ReportColumn("quantity", "数量"),
            ReportColumn("unit_price", "单价"),
            ReportColumn("amount", "金额"),
        ),
        filters=("employee_id", "work_order_id"),
        sort_by=("employee_id", "work_order_id"),
        worksheet="工资明细",
    ),
    ReportDefinition(
        "EMPLOYEE_PAYROLL_SUMMARY:1",
        "EMPLOYEE_PAYROLL_SUMMARY",
        1,
        "员工工资汇总",
        ReportKind.SUMMARY,
        ReportDefinitionStatus.PUBLISHED,
        columns=(ReportColumn("employee_id", "员工编号"), ReportColumn("employee_name", "姓名")),
        filters=("employee_id",),
        group_by=("employee_id", "employee_name"),
        aggregates=(ReportAggregate("amount", AggregateOperation.SUM, "工资合计"),),
        sort_by=("employee_id",),
        worksheet="员工工资汇总",
    ),
    ReportDefinition(
        "WORK_ORDER_OUTPUT_SUMMARY:1",
        "WORK_ORDER_OUTPUT_SUMMARY",
        1,
        "工单产量汇总",
        ReportKind.SUMMARY,
        ReportDefinitionStatus.PUBLISHED,
        columns=(ReportColumn("work_order_id", "工单编号"),),
        filters=("work_order_id",),
        group_by=("work_order_id",),
        aggregates=(ReportAggregate("quantity", AggregateOperation.SUM, "产量合计"),),
        sort_by=("work_order_id",),
        worksheet="工单产量汇总",
    ),
    ReportDefinition(
        "PRODUCT_PROCESS_STATISTICS:1",
        "PRODUCT_PROCESS_STATISTICS",
        1,
        "产品/工序统计",
        ReportKind.SUMMARY,
        ReportDefinitionStatus.PUBLISHED,
        columns=(ReportColumn("product_id", "产品"), ReportColumn("process_id", "工序")),
        filters=("product_id", "process_id"),
        group_by=("product_id", "process_id"),
        aggregates=(ReportAggregate("quantity", AggregateOperation.SUM, "数量合计"),),
        sort_by=("product_id", "process_id"),
        worksheet="产品工序统计",
    ),
    ReportDefinition(
        "WORKSHOP_DAILY:1",
        "WORKSHOP_DAILY",
        1,
        "车间日报",
        ReportKind.SUMMARY,
        ReportDefinitionStatus.PUBLISHED,
        columns=(ReportColumn("work_date", "日期"), ReportColumn("workshop_id", "车间")),
        filters=("work_date", "workshop_id"),
        group_by=("work_date", "workshop_id"),
        aggregates=(ReportAggregate("quantity", AggregateOperation.SUM, "当日产量"),),
        sort_by=("work_date", "workshop_id"),
        worksheet="车间日报",
    ),
    ReportDefinition(
        "FINANCE_ACCOUNTING:1",
        "FINANCE_ACCOUNTING",
        1,
        "财务核算表",
        ReportKind.FIXED,
        ReportDefinitionStatus.PUBLISHED,
        columns=(
            ReportColumn("employee_id", "员工编号"),
            ReportColumn("employee_name", "姓名"),
            ReportColumn("amount", "应付金额"),
        ),
        filters=("employee_id",),
        sort_by=("employee_id",),
        worksheet="财务核算表",
    ),
)
