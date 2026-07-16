"""XLSX export / reporting module facade."""

from pathlib import Path

from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.adapters.export.xlsx import XlsxExporter
from app.application.export_forms import ExportForms
from app.application.query_forms import FormFilters, QueryForms, SearchResult
from app.domain.models import ExportBatch
from app.modules.reporting.models_ds import ExportPreview


class ReportingFacade:
    """Reporting and XLSX export boundary backed by the export service."""

    def __init__(
        self,
        repository: SqlAlchemyFormRepository,
        queries: QueryForms,
        exporter: XlsxExporter | None = None,
        template_repository: SqlAlchemyTemplateRepository | None = None,
    ) -> None:
        self._repository = repository
        self._exporter = exporter or XlsxExporter()
        self._service = ExportForms(
            repository=repository,
            exporter=self._exporter,
            queries=queries,
            template_repository=template_repository,
        )

    def preview(
        self, filters: FormFilters, actor_id: str | None = None
    ) -> ExportPreview:
        """Return a read-only export eligibility and mapping preview."""
        return self._service.preview(filters, actor_id)

    def export(
        self,
        export_type: str,
        filters: FormFilters,
        output_directory: Path,
        actor_id: str,
    ) -> ExportBatch:
        """Run an export: query confirmed forms, write XLSX, persist the batch."""
        return self._service.export(export_type, filters, output_directory, actor_id)

    def write_xlsx(
        self,
        destination: Path,
        batch_id: str,
        export_type: str,
        results: list[SearchResult],
        filters: dict[str, object],
    ) -> None:
        """Write a raw XLSX workbook without persisting a batch record."""
        self._exporter.write(destination, batch_id, export_type, results, filters)

    def list_batches(self) -> list[ExportBatch]:
        """List all export batches from the repository."""
        return self._repository.list_export_batches()
