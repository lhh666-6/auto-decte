"""Persistence boundary for append-only report definitions."""

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import ReportDefinitionVersionRow
from app.modules.reporting.models_ds import (
    BUILTIN_REPORT_DEFINITIONS,
    AggregateOperation,
    ReportAggregate,
    ReportColumn,
    ReportDefinition,
    ReportDefinitionStatus,
    ReportKind,
)


class ReportDefinitionConflict(ValueError):
    """The immutable key/version already exists with different content."""


class SqlAlchemyReportDefinitionRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, definition: ReportDefinition) -> None:
        with Session(self._engine) as session, session.begin():
            persisted = session.get(ReportDefinitionVersionRow, definition.definition_id)
            if persisted is None:
                persisted = session.scalar(
                    select(ReportDefinitionVersionRow).where(
                        ReportDefinitionVersionRow.report_key == definition.report_key,
                        ReportDefinitionVersionRow.version == definition.version,
                    )
                )
            if persisted is not None:
                if _from_row(persisted) == definition:
                    return
                raise ReportDefinitionConflict(
                    "Report definition "
                    f"{definition.report_key} v{definition.version} already exists"
                )
            session.add(_to_row(definition))

    def get(self, definition_id: str) -> ReportDefinition | None:
        with Session(self._engine) as session:
            row = session.get(ReportDefinitionVersionRow, definition_id)
            return _from_row(row) if row is not None else None

    def get_by_key_version(self, report_key: str, version: int) -> ReportDefinition | None:
        with Session(self._engine) as session:
            row = session.scalar(
                select(ReportDefinitionVersionRow).where(
                    ReportDefinitionVersionRow.report_key == report_key,
                    ReportDefinitionVersionRow.version == version,
                )
            )
            return _from_row(row) if row is not None else None

    def list(self) -> list[ReportDefinition]:
        with Session(self._engine) as session:
            rows = session.scalars(
                select(ReportDefinitionVersionRow).order_by(
                    ReportDefinitionVersionRow.report_key,
                    ReportDefinitionVersionRow.version,
                )
            ).all()
            return [_from_row(row) for row in rows]


def install_builtin_report_definitions(
    repository: SqlAlchemyReportDefinitionRepository,
) -> None:
    for definition in BUILTIN_REPORT_DEFINITIONS:
        repository.add(definition)


def _to_row(definition: ReportDefinition) -> ReportDefinitionVersionRow:
    return ReportDefinitionVersionRow(
        definition_id=definition.definition_id,
        report_key=definition.report_key,
        version=definition.version,
        display_name=definition.display_name,
        kind=definition.kind.value,
        status=definition.status.value,
        configuration={
            "columns": [
                {"source_field": column.source_field, "header": column.header}
                for column in definition.columns
            ],
            "filters": list(definition.filters),
            "group_by": list(definition.group_by),
            "aggregates": [
                {
                    "source_field": aggregate.source_field,
                    "operation": aggregate.operation.value,
                    "header": aggregate.header,
                }
                for aggregate in definition.aggregates
            ],
            "sort_by": list(definition.sort_by),
            "worksheet": definition.worksheet,
        },
    )


def _from_row(row: ReportDefinitionVersionRow) -> ReportDefinition:
    config = row.configuration
    return ReportDefinition(
        definition_id=row.definition_id,
        report_key=row.report_key,
        version=row.version,
        display_name=row.display_name,
        kind=ReportKind(row.kind),
        status=ReportDefinitionStatus(row.status),
        columns=tuple(
            ReportColumn(item["source_field"], item["header"]) for item in config.get("columns", [])
        ),
        filters=tuple(config.get("filters", [])),
        group_by=tuple(config.get("group_by", [])),
        aggregates=tuple(
            ReportAggregate(
                item["source_field"],
                AggregateOperation(item["operation"]),
                item["header"],
            )
            for item in config.get("aggregates", [])
        ),
        sort_by=tuple(config.get("sort_by", [])),
        worksheet=config.get("worksheet", "报表"),
    )
