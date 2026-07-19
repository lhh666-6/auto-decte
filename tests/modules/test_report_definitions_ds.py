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
