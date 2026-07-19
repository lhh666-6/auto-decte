"""Traceable four-sheet XLSX writer."""

from collections.abc import Iterable
from decimal import Decimal
from functools import reduce
from operator import add
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from app.application.query_forms import SearchResult
from app.modules.reporting.models_ds import (
    AggregateOperation,
    ExportMapping,
    ReportAggregate,
    ReportDefinition,
    ReportKind,
)


class XlsxExporter:
    def write(
        self,
        destination: Path,
        batch_id: str,
        export_type: str,
        results: Iterable[SearchResult],
        filters: dict[str, Any],
        mappings: Iterable[ExportMapping] | None = None,
        report_definition: ReportDefinition | None = None,
    ) -> None:
        rows = list(results)
        if report_definition is not None:
            self._write_report(destination, batch_id, rows, report_definition)
            return
        if mappings is not None:
            self._write_mapped(destination, batch_id, rows, tuple(mappings))
            return
        workbook = Workbook()
        official = workbook.active
        assert official is not None
        official.title = "正式数据"
        field_names = sorted({key for result in rows for key in result.current_record.values})
        official.append(["export_batch_id", "form_id", "record_version", *field_names])
        for result in rows:
            official.append(
                [
                    batch_id,
                    result.form.form_id,
                    result.current_record.version,
                    *(result.current_record.values.get(name) for name in field_names),
                ]
            )

        review = workbook.create_sheet("异常与复核")
        review.append(["form_id", "record_version", "status", "change_reason", "confirmed_by"])
        for result in rows:
            record = result.current_record
            review.append(
                [
                    result.form.form_id,
                    record.version,
                    record.status.value,
                    record.change_reason,
                    record.confirmed_by,
                ]
            )

        summary = workbook.create_sheet("汇总")
        summary.append(["export_type", "record_count", "total_quantity", "qualified_quantity"])
        summary.append(
            [
                export_type,
                len(rows),
                sum(int(row.current_record.values.get("total_quantity", 0)) for row in rows),
                sum(int(row.current_record.values.get("qualified_quantity", 0)) for row in rows),
            ]
        )

        information = workbook.create_sheet("导出说明")
        information.append(["export_batch_id", batch_id])
        information.append(["export_type", export_type])
        information.append(["filters", str(filters)])
        destination.parent.mkdir(parents=True, exist_ok=True)
        _neutralize_text_cells(workbook)
        workbook.save(destination)

    @staticmethod
    def _write_report(
        destination: Path,
        batch_id: str,
        rows: list[SearchResult],
        definition: ReportDefinition,
    ) -> None:
        workbook = Workbook()
        worksheet = workbook.active
        assert worksheet is not None
        worksheet.title = definition.worksheet
        ordered_rows = sorted(rows, key=lambda row: _report_sort_key(row, definition.sort_by))
        if definition.kind is ReportKind.SUMMARY:
            worksheet.append(
                [
                    "export_batch_id",
                    *(column.header for column in definition.columns),
                    *(aggregate.header for aggregate in definition.aggregates),
                ]
            )
            grouped: dict[tuple[object, ...], list[SearchResult]] = {}
            for row in ordered_rows:
                key = tuple(_report_value(row, field) for field in definition.group_by)
                grouped.setdefault(key, []).append(row)
            for group_rows in grouped.values():
                representative = group_rows[0]
                worksheet.append(
                    [
                        batch_id,
                        *(
                            _report_value(representative, column.source_field)
                            for column in definition.columns
                        ),
                        *(_aggregate(group_rows, aggregate) for aggregate in definition.aggregates),
                    ]
                )
        else:
            worksheet.append(
                [
                    "export_batch_id",
                    "form_id",
                    "record_version",
                    *(column.header for column in definition.columns),
                ]
            )
            for row in ordered_rows:
                worksheet.append(
                    [
                        batch_id,
                        row.form.form_id,
                        row.current_record.version,
                        *(_report_value(row, column.source_field) for column in definition.columns),
                    ]
                )
        destination.parent.mkdir(parents=True, exist_ok=True)
        _neutralize_text_cells(workbook)
        workbook.save(destination)

    @staticmethod
    def _write_mapped(
        destination: Path,
        batch_id: str,
        rows: list[SearchResult],
        mappings: tuple[ExportMapping, ...],
    ) -> None:
        _validate_mappings(mappings)
        workbooks = {mapping.workbook for mapping in mappings}
        if len(workbooks) > 1:
            raise ValueError("an export mapping snapshot must target exactly one workbook")

        workbook = Workbook()
        default_sheet = workbook.active
        assert default_sheet is not None
        columns_by_worksheet: dict[str, list[str]] = {}
        for mapping in mappings:
            columns = columns_by_worksheet.setdefault(mapping.worksheet, [])
            if mapping.business_column not in columns:
                columns.append(mapping.business_column)

        for worksheet_name, columns in columns_by_worksheet.items():
            worksheet = workbook.create_sheet(worksheet_name)
            worksheet.append(["export_batch_id", "form_id", "record_version", *columns])

        for result in rows:
            matching = tuple(
                mapping
                for mapping in mappings
                if mapping.template_id == result.form.template_id
                and mapping.template_version == result.form.template_version
            )
            for worksheet_name, columns in columns_by_worksheet.items():
                record_mappings = {
                    mapping.business_column: mapping
                    for mapping in matching
                    if mapping.worksheet == worksheet_name
                }
                if not record_mappings:
                    continue
                workbook[worksheet_name].append(
                    [
                        batch_id,
                        result.form.form_id,
                        result.current_record.version,
                        *(
                            result.current_record.values.get(record_mappings[column].field_key)
                            if column in record_mappings
                            else None
                            for column in columns
                        ),
                    ]
                )

        if columns_by_worksheet:
            workbook.remove(default_sheet)
        else:
            default_sheet.title = "Export information"
            default_sheet.append(["export_batch_id", batch_id])
        destination.parent.mkdir(parents=True, exist_ok=True)
        _neutralize_text_cells(workbook)
        workbook.save(destination)


def _neutralize_text_cells(workbook: Workbook) -> None:
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if not isinstance(cell.value, str):
                    continue
                text = cell.value.lstrip("\ufeff")
                cell.value = f"'{text}" if text.startswith(("=", "+", "-", "@")) else text
                cell.data_type = "s"


def _validate_mappings(mappings: tuple[ExportMapping, ...]) -> None:
    worksheet_names: dict[str, str] = {}
    fields_by_column: dict[tuple[str, str, str, str], str] = {}
    for mapping in mappings:
        worksheet_key = mapping.worksheet.casefold()
        existing_name = worksheet_names.setdefault(worksheet_key, mapping.worksheet)
        if existing_name != mapping.worksheet:
            raise ValueError(
                "worksheet names must be unique ignoring case: "
                f"{existing_name!r} conflicts with {mapping.worksheet!r}"
            )

        column_key = (
            mapping.template_id,
            mapping.template_version,
            worksheet_key,
            mapping.business_column,
        )
        existing_field = fields_by_column.setdefault(column_key, mapping.field_key)
        if existing_field != mapping.field_key:
            raise ValueError(
                "business columns must be unique per template worksheet: "
                f"{mapping.business_column!r} maps both {existing_field!r} "
                f"and {mapping.field_key!r}"
            )


def _report_value(result: SearchResult, field_name: str) -> object:
    metadata: dict[str, object] = {
        "form_id": result.form.form_id,
        "template_id": result.form.template_id,
        "record_version": result.current_record.version,
    }
    if field_name in metadata:
        return metadata[field_name]
    values = result.current_record.values
    if field_name in values:
        return values[field_name]
    aliases = {
        "employee_id": ("worker_number",),
        "employee_name": ("worker_name",),
        "work_order_id": ("work_order_number", "order_number_1"),
        "product_id": ("product_spec", "product_spec_1"),
        "process_id": ("position_name",),
        "workshop_id": ("team_name",),
        "unit_price": ("piece_rate",),
        "amount": ("calculated_wage", "task_reward", "furnace_wage"),
    }
    for alias in aliases.get(field_name, ()):
        if alias in values:
            return values[alias]
    if field_name == "quantity":
        for prefix in (
            "qualified_quantity_",
            "completed_quantity_",
            "input_quantity_",
        ):
            matching = [
                value
                for key, value in values.items()
                if key.startswith(prefix) and value not in (None, "")
            ]
            if matching:
                if not all(
                    isinstance(value, int | float | Decimal) and not isinstance(value, bool)
                    for value in matching
                ):
                    raise ValueError(f"quantity source {prefix!r} must be numeric")
                return reduce(add, matching)
    return None


def _report_sort_key(result: SearchResult, fields: tuple[str, ...]) -> tuple[tuple[bool, str], ...]:
    return tuple(
        (value is None, "" if value is None else str(value))
        for value in (_report_value(result, field) for field in fields)
    )


def _aggregate(rows: list[SearchResult], aggregate: ReportAggregate) -> object:
    values = [
        value
        for row in rows
        if (value := _report_value(row, aggregate.source_field)) not in (None, "")
    ]
    if aggregate.operation is AggregateOperation.COUNT:
        return len(values)
    if not values:
        return None
    if aggregate.operation in {AggregateOperation.SUM, AggregateOperation.AVERAGE}:
        if not all(
            isinstance(value, int | float | Decimal) and not isinstance(value, bool)
            for value in values
        ):
            raise ValueError(
                f"aggregate field {aggregate.source_field!r} must contain numeric values"
            )
        total = reduce(add, values)
        if aggregate.operation is AggregateOperation.SUM:
            return total
        return total / len(values)  # type: ignore[operator]
    if aggregate.operation is AggregateOperation.MIN:
        return min(values)  # type: ignore[type-var]
    if aggregate.operation is AggregateOperation.MAX:
        return max(values)  # type: ignore[type-var]
    raise ValueError(f"unsupported aggregate operation: {aggregate.operation}")
