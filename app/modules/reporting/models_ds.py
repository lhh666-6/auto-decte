"""Immutable reporting values used to preview template-driven exports."""

import re
from dataclasses import dataclass
from enum import StrEnum

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_EXCEL_CELL = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")
_EXCEL_COLUMN = re.compile(r"^[A-Z]{1,3}$")


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


def _excel_column_number(column: str) -> int:
    return sum(
        (ord(character) - 64) * 26**index for index, character in enumerate(reversed(column))
    )


def _require_excel_column(column: str) -> None:
    if _EXCEL_COLUMN.fullmatch(column) is None or _excel_column_number(column) > 16384:
        raise ValueError(f"{column!r} is not a valid Excel column")


@dataclass(frozen=True, slots=True)
class FixedCellMapping:
    cell: str
    source_field: str

    def __post_init__(self) -> None:
        match = _EXCEL_CELL.fullmatch(self.cell)
        if (
            match is None
            or _excel_column_number(match.group(1)) > 16384
            or int(match.group(2)) > 1_048_576
        ):
            raise ValueError(f"{self.cell!r} is not a valid Excel cell")
        _require_safe_field(self.source_field)


@dataclass(frozen=True, slots=True)
class FixedTableColumn:
    column: str
    source_field: str

    def __post_init__(self) -> None:
        _require_excel_column(self.column)
        _require_safe_field(self.source_field)


@dataclass(frozen=True, slots=True)
class FixedTableMapping:
    start_row: int
    max_rows: int
    columns: tuple[FixedTableColumn, ...]

    def __post_init__(self) -> None:
        if self.start_row < 1 or self.max_rows < 1:
            raise ValueError("fixed table rows must be positive")
        if self.start_row + self.max_rows - 1 > 1_048_576:
            raise ValueError("fixed table exceeds the Excel row limit")
        if not self.columns:
            raise ValueError("fixed table columns are required")
        columns = [item.column for item in self.columns]
        if len(columns) != len(set(columns)):
            raise ValueError("fixed table columns must be unique")


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
    fixed_template_key: str | None = None
    fixed_template_sha256: str | None = None
    fixed_cells: tuple[FixedCellMapping, ...] = ()
    fixed_table: FixedTableMapping | None = None

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
        has_fixed_mapping = bool(
            self.fixed_template_key
            or self.fixed_template_sha256
            or self.fixed_cells
            or self.fixed_table
        )
        if has_fixed_mapping and self.kind is not ReportKind.FIXED:
            raise ValueError("fixed mappings require a FIXED report")
        if self.fixed_template_key is None and (
            self.fixed_template_sha256 or self.fixed_cells or self.fixed_table
        ):
            raise ValueError("fixed mapping requires a fixed template key")
        if self.fixed_template_key is not None:
            _require_safe_field(self.fixed_template_key)
            if (
                self.fixed_template_sha256 is None
                or re.fullmatch(r"[0-9a-fA-F]{64}", self.fixed_template_sha256) is None
            ):
                raise ValueError("fixed template requires a SHA-256 hash")
            if not self.fixed_cells and self.fixed_table is None:
                raise ValueError("fixed template requires a cell or table mapping")


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


BUILTIN_FIXED_REPORT_DEFINITIONS = (
    ReportDefinition(
        "TIMEKEEPING_DAILY_FIXED:1",
        "TIMEKEEPING_DAILY_FIXED",
        1,
        "计时工日工资表（原格式）",
        ReportKind.FIXED,
        ReportDefinitionStatus.PUBLISHED,
        filters=("work_date", "employee_id"),
        sort_by=("employee_id",),
        worksheet="计时",
        fixed_template_key="LEGACY_TIMEKEEPING_DAILY",
        fixed_template_sha256=("2757f427bca00dcb0f87adc854762925a601fdf3b5cd970b1056766fc30068dd"),
        fixed_cells=(FixedCellMapping("H2", "work_date"),),
        fixed_table=FixedTableMapping(
            5,
            8,
            (
                FixedTableColumn("A", "employee_name"),
                FixedTableColumn("B", "fact_description"),
                FixedTableColumn("C", "time_range"),
                FixedTableColumn("D", "hours"),
                FixedTableColumn("E", "assessment"),
                FixedTableColumn("F", "labor_attitude"),
                FixedTableColumn("G", "cost_saving"),
                FixedTableColumn("H", "safety_prevention"),
                FixedTableColumn("I", "five_s"),
                FixedTableColumn("J", "equipment_maintenance"),
            ),
        ),
    ),
)
