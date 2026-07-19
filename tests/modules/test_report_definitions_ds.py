from dataclasses import FrozenInstanceError

import pytest

import app.modules.reporting.models_ds as reporting


def test_report_definition_model_is_versioned_immutable_and_controlled() -> None:
    assert hasattr(reporting, "ReportDefinition")
    definition = reporting.ReportDefinition(
        definition_id="PAYROLL_DETAIL:1",
        report_key="PAYROLL_DETAIL",
        version=1,
        display_name="工资明细",
        kind=reporting.ReportKind.DETAIL,
        status=reporting.ReportDefinitionStatus.PUBLISHED,
        columns=(reporting.ReportColumn("employee_id", "员工编号"),),
        filters=("employee_id",),
        sort_by=("employee_id",),
        worksheet="工资明细",
    )

    assert definition.version == 1
    with pytest.raises(FrozenInstanceError):
        definition.display_name = "被修改"  # type: ignore[misc]
    with pytest.raises(ValueError, match="safe field identifier"):
        reporting.ReportColumn("quantity * unit_price", "任意公式")


def test_summary_definition_requires_grouping_and_controlled_aggregate() -> None:
    with pytest.raises(ValueError, match="group_by"):
        reporting.ReportDefinition(
            definition_id="EMPLOYEE_PAYROLL_SUMMARY:1",
            report_key="EMPLOYEE_PAYROLL_SUMMARY",
            version=1,
            display_name="员工工资汇总",
            kind=reporting.ReportKind.SUMMARY,
            status=reporting.ReportDefinitionStatus.PUBLISHED,
            aggregates=(
                reporting.ReportAggregate("amount", reporting.AggregateOperation.SUM, "工资合计"),
            ),
        )


def test_six_builtin_report_definitions_are_stable_published_versions() -> None:
    assert [item.report_key for item in reporting.BUILTIN_REPORT_DEFINITIONS] == [
        "PAYROLL_DETAIL",
        "EMPLOYEE_PAYROLL_SUMMARY",
        "WORK_ORDER_OUTPUT_SUMMARY",
        "PRODUCT_PROCESS_STATISTICS",
        "WORKSHOP_DAILY",
        "FINANCE_ACCOUNTING",
    ]
    assert {item.kind for item in reporting.BUILTIN_REPORT_DEFINITIONS} == {
        reporting.ReportKind.DETAIL,
        reporting.ReportKind.SUMMARY,
        reporting.ReportKind.FIXED,
    }
    assert all(
        item.version == 1 and item.status is reporting.ReportDefinitionStatus.PUBLISHED
        for item in reporting.BUILTIN_REPORT_DEFINITIONS
    )


def test_fixed_report_mapping_uses_bounded_cells_and_table_columns() -> None:
    assert hasattr(reporting, "FixedCellMapping")
    definition = reporting.ReportDefinition(
        definition_id="TIMEKEEPING_DAILY_FIXED:1",
        report_key="TIMEKEEPING_DAILY_FIXED",
        version=1,
        display_name="计时工日工资表（原格式）",
        kind=reporting.ReportKind.FIXED,
        status=reporting.ReportDefinitionStatus.PUBLISHED,
        worksheet="计时",
        fixed_template_key="LEGACY_TIMEKEEPING_DAILY",
        fixed_template_sha256="0" * 64,
        fixed_cells=(reporting.FixedCellMapping("H2", "work_date"),),
        fixed_table=reporting.FixedTableMapping(
            start_row=5,
            max_rows=8,
            columns=(
                reporting.FixedTableColumn("A", "employee_name"),
                reporting.FixedTableColumn("D", "hours"),
                reporting.FixedTableColumn("E", "assessment"),
            ),
        ),
    )

    assert definition.fixed_table.max_rows == 8  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="Excel cell"):
        reporting.FixedCellMapping("XFE1", "work_date")
    with pytest.raises(ValueError, match="positive"):
        reporting.FixedTableMapping(
            start_row=0,
            max_rows=8,
            columns=(reporting.FixedTableColumn("A", "employee_name"),),
        )
    with pytest.raises(ValueError, match="SHA-256"):
        reporting.ReportDefinition(
            definition_id="UNHASHED_FIXED:1",
            report_key="UNHASHED_FIXED",
            version=1,
            display_name="无哈希固定表",
            kind=reporting.ReportKind.FIXED,
            status=reporting.ReportDefinitionStatus.PUBLISHED,
            fixed_template_key="LEGACY_TIMEKEEPING_DAILY",
            fixed_cells=(reporting.FixedCellMapping("H2", "work_date"),),
        )
    with pytest.raises(ValueError, match="template key"):
        reporting.ReportDefinition(
            definition_id="KEYLESS_FIXED:1",
            report_key="KEYLESS_FIXED",
            version=1,
            display_name="无资产键固定表",
            kind=reporting.ReportKind.FIXED,
            status=reporting.ReportDefinitionStatus.PUBLISHED,
            fixed_cells=(reporting.FixedCellMapping("H2", "work_date"),),
        )


def test_representative_fixed_report_is_published_with_trusted_asset_hash() -> None:
    assert hasattr(reporting, "BUILTIN_FIXED_REPORT_DEFINITIONS")
    definitions = reporting.BUILTIN_FIXED_REPORT_DEFINITIONS

    assert len(definitions) == 1
    definition = definitions[0]
    assert definition.report_key == "TIMEKEEPING_DAILY_FIXED"
    assert definition.status is reporting.ReportDefinitionStatus.PUBLISHED
    assert definition.fixed_template_key == "LEGACY_TIMEKEEPING_DAILY"
    assert definition.fixed_template_sha256 == (
        "2757f427bca00dcb0f87adc854762925a601fdf3b5cd970b1056766fc30068dd"
    )
