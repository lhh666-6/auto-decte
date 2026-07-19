from importlib.util import find_spec

import pytest
from sqlalchemy import create_engine

import app.adapters.database.report_definition_repository_ds as persistence
from app.adapters.database.models import Base
from app.modules.reporting.models_ds import (
    BUILTIN_FIXED_REPORT_DEFINITIONS,
    BUILTIN_REPORT_DEFINITIONS,
    FixedCellMapping,
    FixedTableColumn,
    FixedTableMapping,
    ReportColumn,
    ReportDefinition,
    ReportDefinitionStatus,
    ReportKind,
)


def test_report_definition_repository_module_exists() -> None:
    assert find_spec("app.adapters.database.report_definition_repository_ds") is not None


def test_report_definitions_round_trip_and_builtin_install_is_idempotent() -> None:
    assert hasattr(persistence, "SqlAlchemyReportDefinitionRepository")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    repository = persistence.SqlAlchemyReportDefinitionRepository(engine)

    persistence.install_builtin_report_definitions(repository)
    persistence.install_builtin_report_definitions(repository)

    expected = (*BUILTIN_REPORT_DEFINITIONS, *BUILTIN_FIXED_REPORT_DEFINITIONS)
    assert repository.list() == sorted(expected, key=lambda item: (item.report_key, item.version))
    assert repository.get("PAYROLL_DETAIL:1") == BUILTIN_REPORT_DEFINITIONS[0]
    assert repository.get_by_key_version("PAYROLL_DETAIL", 1) == BUILTIN_REPORT_DEFINITIONS[0]


def test_report_definition_versions_are_append_only_and_conflicts_do_not_overwrite() -> None:
    assert hasattr(persistence, "SqlAlchemyReportDefinitionRepository")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    repository = persistence.SqlAlchemyReportDefinitionRepository(engine)
    original = ReportDefinition(
        "CUSTOM_DETAIL:1",
        "CUSTOM_DETAIL",
        1,
        "自定义明细",
        ReportKind.DETAIL,
        ReportDefinitionStatus.PUBLISHED,
        columns=(ReportColumn("employee_id", "员工编号"),),
    )
    conflict = ReportDefinition(
        "CUSTOM_DETAIL:other",
        "CUSTOM_DETAIL",
        1,
        "被替换的名称",
        ReportKind.DETAIL,
        ReportDefinitionStatus.PUBLISHED,
        columns=(ReportColumn("employee_id", "员工编号"),),
    )

    repository.add(original)
    repository.add(original)
    with pytest.raises(persistence.ReportDefinitionConflict):
        repository.add(conflict)

    assert repository.get_by_key_version("CUSTOM_DETAIL", 1) == original


def test_fixed_mapping_round_trips_without_losing_bounded_coordinates() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    repository = persistence.SqlAlchemyReportDefinitionRepository(engine)
    definition = ReportDefinition(
        "FIXED_DAILY:1",
        "FIXED_DAILY",
        1,
        "固定日报",
        ReportKind.FIXED,
        ReportDefinitionStatus.PUBLISHED,
        worksheet="计时",
        fixed_template_key="LEGACY_TIMEKEEPING_DAILY",
        fixed_template_sha256="0" * 64,
        fixed_cells=(FixedCellMapping("H2", "work_date"),),
        fixed_table=FixedTableMapping(
            5,
            8,
            (FixedTableColumn("A", "employee_name"),),
        ),
    )

    repository.add(definition)

    assert repository.get("FIXED_DAILY:1") == definition
