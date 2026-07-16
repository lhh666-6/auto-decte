"""Traceable four-sheet XLSX writer."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from app.application.query_forms import SearchResult
from app.modules.reporting.models_ds import ExportMapping


class XlsxExporter:
    def write(
        self,
        destination: Path,
        batch_id: str,
        export_type: str,
        results: Iterable[SearchResult],
        filters: dict[str, Any],
        mappings: Iterable[ExportMapping] | None = None,
    ) -> None:
        rows = list(results)
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
            worksheet.append(
                ["export_batch_id", "form_id", "record_version", *columns]
            )

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
                            result.current_record.values.get(
                                record_mappings[column].field_key
                            )
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
