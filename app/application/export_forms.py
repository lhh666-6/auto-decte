"""XLSX export orchestration and batch persistence."""

import hashlib
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.adapters.export.xlsx import XlsxExporter
from app.application.query_forms import FormFilters, QueryForms
from app.domain.models import (
    AuditEvent,
    ExportBatch,
    ExportStatus,
    RecordStatus,
    RecordVersion,
    ReviewStatus,
)
from app.domain.templates_ds import TemplateVersion
from app.modules.reporting.models_ds import (
    ExportExclusionReason,
    ExportMapping,
    ExportPreview,
    ExportPreviewItem,
)


class ExportRepository(Protocol):
    def add_export_batch(self, batch: ExportBatch) -> None: ...
    def set_export_status(self, form_id: str, status: ExportStatus) -> None: ...
    def add_audit_event(self, event: AuditEvent) -> None: ...


class ExportTemplateRepository(Protocol):
    def get_version_by_key_version(
        self, template_key: str, version: int
    ) -> TemplateVersion | None: ...


class ExportForms:
    def __init__(
        self,
        repository: ExportRepository,
        exporter: XlsxExporter,
        queries: QueryForms,
        template_repository: ExportTemplateRepository | None = None,
    ) -> None:
        self._repository = repository
        self._exporter = exporter
        self._queries = queries
        self._template_repository = template_repository

    def preview(self, filters: FormFilters, actor_id: str | None = None) -> ExportPreview:
        """Classify filtered forms for export without mutating persisted state."""
        if self._template_repository is None:
            raise RuntimeError("template repository is required for export preview")
        del actor_id
        included: list[ExportPreviewItem] = []
        excluded: list[ExportPreviewItem] = []
        mappings: dict[tuple[str, str, str], ExportMapping] = {}
        results_by_id = {result.form.form_id: result for result in self._queries.search(filters)}
        candidates = [
            form
            for form in self._queries.list_forms()
            if (filters.form_id is None or form.form_id == filters.form_id)
            and (filters.review_status is None or form.review_status is filters.review_status)
            and (filters.export_status is None or form.export_status is filters.export_status)
            and (
                (filters.employee_id is None and filters.work_order_id is None)
                or form.form_id in results_by_id
            )
        ]
        for form in sorted(candidates, key=lambda candidate: candidate.form_id):
            result = results_by_id.get(form.form_id)
            item = ExportPreviewItem(form.form_id, form.current_record_version)
            if form.review_status is not ReviewStatus.CONFIRMED:
                excluded.append(
                    replace(item, reason=ExportExclusionReason.NOT_CONFIRMED)
                )
                continue
            if result is None:
                excluded.append(
                    replace(item, reason=ExportExclusionReason.FINAL_VALIDATION_FAILED)
                )
                continue
            template = self._resolve_template(
                form.template_id, form.template_version
            )
            if template is None:
                excluded.append(
                    replace(item, reason=ExportExclusionReason.TEMPLATE_NOT_FOUND)
                )
                continue
            template_mappings = self._template_mappings(template)
            if not template_mappings:
                excluded.append(
                    replace(item, reason=ExportExclusionReason.NO_VALID_MAPPING)
                )
                continue
            if not self._passes_final_validation(result.current_record, template):
                excluded.append(
                    replace(item, reason=ExportExclusionReason.FINAL_VALIDATION_FAILED)
                )
                continue
            included.append(item)
            for mapping in template_mappings:
                key = (mapping.template_id, mapping.template_version, mapping.field_key)
                mappings[key] = mapping
        return ExportPreview(
            included=tuple(included),
            excluded=tuple(excluded),
            mapping_snapshot=tuple(mappings[key] for key in sorted(mappings)),
        )

    def _resolve_template(
        self, template_id: str, template_version: str
    ) -> TemplateVersion | None:
        if self._template_repository is None:
            return None
        try:
            version = int(template_version)
        except ValueError:
            return None
        return self._template_repository.get_version_by_key_version(template_id, version)

    @staticmethod
    def _template_mappings(template: TemplateVersion) -> tuple[ExportMapping, ...]:
        mappings: list[ExportMapping] = []
        for field in template.fields:
            target = field.export_target
            if target is None:
                continue
            mappings.append(
                ExportMapping(
                    template_id=template.template_key,
                    template_version=str(template.version),
                    field_key=field.field_key,
                    workbook=target.workbook,
                    worksheet=target.worksheet,
                    business_column=target.business_column,
                )
            )
        return tuple(mappings)

    @staticmethod
    def _passes_final_validation(record: RecordVersion, template: TemplateVersion) -> bool:
        if record.status not in {RecordStatus.CONFIRMED, RecordStatus.CORRECTED}:
            return False
        values = record.values
        for field in template.fields:
            value = values.get(field.field_key)
            empty = value is None or (isinstance(value, str) and not value.strip())
            rules = field.rules
            if rules.required and empty:
                return False
            if empty:
                continue
            if rules.allowed_values and str(value) not in rules.allowed_values:
                return False
            if rules.minimum_value is not None or rules.maximum_value is not None:
                if isinstance(value, bool) or not isinstance(value, int | float):
                    return False
                if rules.minimum_value is not None and value < rules.minimum_value:
                    return False
                if rules.maximum_value is not None and value > rules.maximum_value:
                    return False
        return True

    def export(
        self,
        export_type: str,
        filters: FormFilters,
        output_directory: Path,
        actor_id: str,
    ) -> ExportBatch:
        confirmed_filters = replace(filters, review_status=ReviewStatus.CONFIRMED)
        results = self._queries.search(confirmed_filters)
        if self._template_repository is not None:
            included_records = {
                (item.form_id, item.record_version)
                for item in self.preview(filters, actor_id).included
            }
            results = [
                result
                for result in results
                if (result.form.form_id, result.current_record.version) in included_records
            ]
        batch_id = f"EXPORT-{uuid4().hex}"
        timestamp = datetime.now(UTC)
        destination = output_directory / f"{export_type}-{timestamp:%Y%m%dT%H%M%S}-{batch_id}.xlsx"
        serialized_filters = {
            key: value.value if hasattr(value, "value") else value
            for key, value in asdict(confirmed_filters).items()
            if value is not None
        }
        self._exporter.write(destination, batch_id, export_type, results, serialized_filters)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        batch = ExportBatch(
            export_batch_id=batch_id,
            export_type=export_type,
            filters=serialized_filters,
            included_records=tuple(
                (result.form.form_id, result.current_record.version) for result in results
            ),
            file_path=str(destination),
            file_sha256=digest,
            exported_by=actor_id,
            exported_at=timestamp,
        )
        self._repository.add_export_batch(batch)
        for result in results:
            self._repository.set_export_status(result.form.form_id, ExportStatus.EXPORTED)
            self._repository.add_audit_event(
                AuditEvent(
                    event_id=f"EVENT-{uuid4().hex}",
                    form_id=result.form.form_id,
                    event_type="EXPORT",
                    actor_id=actor_id,
                    after={
                        "export_batch_id": batch_id,
                        "record_version": result.current_record.version,
                    },
                )
            )
        return batch
