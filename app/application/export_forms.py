"""XLSX export orchestration and batch persistence."""

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.adapters.export.xlsx import XlsxExporter
from app.application.query_forms import FormFilters, QueryForms, SearchResult
from app.domain.models import (
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
    ExportReasonScope,
    ExportValidationReason,
    ReportDefinition,
    ReportDefinitionStatus,
)


class ExportRepository(Protocol):
    def complete_export(self, batch: ExportBatch) -> None: ...
    def get_export_batch(self, batch_id: str) -> ExportBatch | None: ...


class ExportTemplateRepository(Protocol):
    def get_version_by_key_version(
        self, template_key: str, version: int
    ) -> TemplateVersion | None: ...


class ExportReportDefinitionRepository(Protocol):
    def get(self, definition_id: str) -> ReportDefinition | None: ...


class ExportIntegrityError(ValueError):
    """A prepared or published workbook does not match its immutable batch."""


class ExportForms:
    def __init__(
        self,
        repository: ExportRepository,
        exporter: XlsxExporter,
        queries: QueryForms,
        template_repository: ExportTemplateRepository | None = None,
        report_definition_repository: ExportReportDefinitionRepository | None = None,
    ) -> None:
        self._repository = repository
        self._exporter = exporter
        self._queries = queries
        self._template_repository = template_repository
        self._report_definition_repository = report_definition_repository

    def recover_publication(self, batch: ExportBatch) -> None:
        """Finish publishing a committed batch without rewriting its workbook."""
        self.publish(batch)

    def publish(self, batch: ExportBatch) -> None:
        """Idempotently publish and verify a prepared workbook."""
        destination = Path(batch.file_path)
        pending = destination.with_name(f"{destination.name}.pending")
        last_missing: FileNotFoundError | None = None
        for _ in range(3):
            try:
                if self._accept_published_workbook(destination, pending, batch):
                    return
                if not pending.exists():
                    continue
                if _file_sha256(pending) != batch.file_sha256:
                    raise ExportIntegrityError(
                        f"Pending export hash does not match batch {batch.export_batch_id}"
                    )
                pending.replace(destination)
            except FileNotFoundError as error:
                last_missing = error
                continue
        try:
            if self._accept_published_workbook(destination, pending, batch):
                return
        except FileNotFoundError as error:
            last_missing = error
        raise FileNotFoundError(
            f"No pending workbook for export batch {batch.export_batch_id}"
        ) from last_missing

    @staticmethod
    def _accept_published_workbook(destination: Path, pending: Path, batch: ExportBatch) -> bool:
        if not destination.exists():
            return False
        if _file_sha256(destination) != batch.file_sha256:
            raise ExportIntegrityError(
                f"Published export hash does not match batch {batch.export_batch_id}"
            )
        pending.unlink(missing_ok=True)
        return True

    def complete(self, batch: ExportBatch) -> None:
        """Commit an already-published and verified export."""
        self._repository.complete_export(batch)

    @staticmethod
    def cleanup(batch: ExportBatch) -> None:
        """Remove all transient and published files for an uncommitted batch."""
        destination = Path(batch.file_path)
        destination.with_name(f"{destination.name}.partial").unlink(missing_ok=True)
        destination.with_name(f"{destination.name}.pending").unlink(missing_ok=True)
        destination.unlink(missing_ok=True)

    def preview(self, filters: FormFilters, actor_id: str | None = None) -> ExportPreview:
        """Classify filtered forms for export without mutating persisted state."""
        if self._template_repository is None:
            raise RuntimeError("template repository is required for export preview")
        del actor_id
        included: list[ExportPreviewItem] = []
        excluded: list[ExportPreviewItem] = []
        mappings: dict[tuple[str, str, str], ExportMapping] = {}
        mapping_order: dict[tuple[str, str, str], tuple[str, int, int]] = {}
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
                    replace(
                        item,
                        reason=ExportExclusionReason.NOT_CONFIRMED,
                        reasons=self._form_reasons(ExportExclusionReason.NOT_CONFIRMED),
                    )
                )
                continue
            if result is None:
                excluded.append(
                    replace(
                        item,
                        reason=ExportExclusionReason.FINAL_VALIDATION_FAILED,
                        reasons=self._form_reasons(ExportExclusionReason.FINAL_VALIDATION_FAILED),
                    )
                )
                continue
            result = self._canonicalize_result_values(result)
            template = self._resolve_template(form.template_id, form.template_version)
            if template is None:
                excluded.append(
                    replace(
                        item,
                        reason=ExportExclusionReason.TEMPLATE_NOT_FOUND,
                        reasons=self._form_reasons(ExportExclusionReason.TEMPLATE_NOT_FOUND),
                    )
                )
                continue
            template_mappings = self._template_mappings(template)
            if not template_mappings:
                excluded.append(
                    replace(
                        item,
                        reason=ExportExclusionReason.NO_VALID_MAPPING,
                        reasons=self._form_reasons(ExportExclusionReason.NO_VALID_MAPPING),
                    )
                )
                continue
            validation_reasons = self._final_validation_reasons(result.current_record, template)
            if validation_reasons:
                excluded.append(
                    replace(
                        item,
                        reason=ExportExclusionReason.FINAL_VALIDATION_FAILED,
                        reasons=validation_reasons,
                    )
                )
                continue
            included.append(item)
            for field_index, mapping in enumerate(template_mappings):
                key = (mapping.template_id, mapping.template_version, mapping.field_key)
                mappings[key] = mapping
                mapping_order[key] = (
                    mapping.template_id,
                    template.version,
                    field_index,
                )
        return ExportPreview(
            included=tuple(included),
            excluded=tuple(excluded),
            mapping_snapshot=tuple(
                mappings[key] for key in sorted(mappings, key=mapping_order.__getitem__)
            ),
        )

    def _resolve_template(self, template_id: str, template_version: str) -> TemplateVersion | None:
        if self._template_repository is None:
            return None
        try:
            version = int(template_version)
        except ValueError:
            return None
        return self._template_repository.get_version_by_key_version(template_id, version)

    def _canonicalize_result_values(self, result: SearchResult) -> SearchResult:
        """Expose historical runtime field IDs through stable template field keys."""
        values = dict(result.current_record.values)
        for field in self._queries.workbench(result.form.form_id).fields:
            if field.field_name not in values and field.field_id in values:
                values[field.field_name] = values[field.field_id]
        if values == result.current_record.values:
            return result
        return replace(result, current_record=replace(result.current_record, values=values))

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
        return not ExportForms._final_validation_reasons(record, template)

    @staticmethod
    def _form_reasons(reason: ExportExclusionReason) -> tuple[ExportValidationReason, ...]:
        messages = {
            ExportExclusionReason.NOT_CONFIRMED: "Form is not confirmed.",
            ExportExclusionReason.TEMPLATE_NOT_FOUND: "Template version was not found.",
            ExportExclusionReason.NO_VALID_MAPPING: "Template has no valid export mapping.",
            ExportExclusionReason.FINAL_VALIDATION_FAILED: "Record failed final validation.",
        }
        return (ExportValidationReason(ExportReasonScope.FORM, reason.value, messages[reason]),)

    @staticmethod
    def _final_validation_reasons(
        record: RecordVersion, template: TemplateVersion
    ) -> tuple[ExportValidationReason, ...]:
        if record.status not in {RecordStatus.CONFIRMED, RecordStatus.CORRECTED}:
            return ExportForms._form_reasons(ExportExclusionReason.FINAL_VALIDATION_FAILED)
        reasons: list[ExportValidationReason] = []
        values = record.values
        for field in template.fields:
            value = values.get(field.field_key)
            empty = value is None or (isinstance(value, str) and not value.strip())
            rules = field.rules
            if rules.required and empty:
                reasons.append(
                    ExportValidationReason(
                        ExportReasonScope.FIELD,
                        "REQUIRED_VALUE_MISSING",
                        "Required value is missing.",
                        field.field_key,
                        required=True,
                    )
                )
                continue
            if empty:
                continue
            if rules.allowed_values and str(value) not in rules.allowed_values:
                reasons.append(
                    ExportValidationReason(
                        ExportReasonScope.FIELD,
                        "VALUE_NOT_ALLOWED",
                        "Value is not in the allowed set.",
                        field.field_key,
                        allowed_values=rules.allowed_values,
                    )
                )
            if rules.minimum_value is not None or rules.maximum_value is not None:
                if isinstance(value, bool) or not isinstance(value, int | float):
                    reasons.append(
                        ExportValidationReason(
                            ExportReasonScope.FIELD,
                            "VALUE_NOT_NUMERIC",
                            "Value must be numeric.",
                            field.field_key,
                            minimum_value=rules.minimum_value,
                            maximum_value=rules.maximum_value,
                        )
                    )
                    continue
                if rules.minimum_value is not None and value < rules.minimum_value:
                    reasons.append(
                        ExportValidationReason(
                            ExportReasonScope.FIELD,
                            "VALUE_BELOW_MINIMUM",
                            "Value is below the minimum.",
                            field.field_key,
                            minimum_value=rules.minimum_value,
                            maximum_value=rules.maximum_value,
                        )
                    )
                if rules.maximum_value is not None and value > rules.maximum_value:
                    reasons.append(
                        ExportValidationReason(
                            ExportReasonScope.FIELD,
                            "VALUE_ABOVE_MAXIMUM",
                            "Value is above the maximum.",
                            field.field_key,
                            minimum_value=rules.minimum_value,
                            maximum_value=rules.maximum_value,
                        )
                    )
        return tuple(reasons)

    def export(
        self,
        export_type: str,
        filters: FormFilters,
        output_directory: Path,
        actor_id: str,
        *,
        task_id: str | None = None,
        supersedes_batch_id: str | None = None,
        progress: Callable[[int, str], None] | None = None,
        report_definition_id: str | None = None,
    ) -> ExportBatch:
        batch = self.prepare(
            export_type,
            filters,
            output_directory,
            actor_id,
            task_id=task_id,
            supersedes_batch_id=supersedes_batch_id,
            progress=progress,
            report_definition_id=report_definition_id,
        )
        try:
            self.publish(batch)
            self.complete(batch)
            return batch
        except Exception:
            self.cleanup(batch)
            raise

    def prepare(
        self,
        export_type: str,
        filters: FormFilters,
        output_directory: Path,
        actor_id: str,
        *,
        task_id: str | None = None,
        supersedes_batch_id: str | None = None,
        progress: Callable[[int, str], None] | None = None,
        report_definition_id: str | None = None,
    ) -> ExportBatch:
        """Validate and write an unpublished immutable workbook candidate."""
        confirmed_filters = replace(filters, review_status=ReviewStatus.CONFIRMED)
        results = [
            self._canonicalize_result_values(result)
            for result in self._queries.search(confirmed_filters)
        ]
        mapping_snapshot: tuple[ExportMapping, ...] | None = None
        template_snapshot: dict[str, object] = {}
        report_definition = self._resolve_report_definition(export_type, report_definition_id)
        if self._template_repository is not None:
            preview = self.preview(filters, actor_id)
            included_records = {(item.form_id, item.record_version) for item in preview.included}
            results = [
                result
                for result in results
                if (result.form.form_id, result.current_record.version) in included_records
            ]
            mapping_snapshot = preview.mapping_snapshot
            template_snapshot = self._template_snapshot(results)
        if report_definition is not None:
            template_snapshot["report_definition"] = _report_definition_snapshot(report_definition)
        if not results:
            raise ValueError("No exportable records after final validation")
        reexport_results = [
            result
            for result in results
            if result.form.export_status is ExportStatus.REEXPORT_REQUIRED
        ]
        if reexport_results and supersedes_batch_id is None:
            raise ValueError("supersedes_batch_id is required for REEXPORT_REQUIRED records")
        superseded_batch = (
            self._repository.get_export_batch(supersedes_batch_id)
            if supersedes_batch_id is not None
            else None
        )
        if supersedes_batch_id is not None and superseded_batch is None:
            raise KeyError(f"Unknown export batch: {supersedes_batch_id}")
        if superseded_batch is not None:
            if not reexport_results:
                raise ValueError("supersedes_batch_id is only valid for REEXPORT_REQUIRED records")
            previous_versions: dict[str, list[int]] = {}
            for form_id, version in superseded_batch.included_records:
                previous_versions.setdefault(form_id, []).append(version)
            for result in reexport_results:
                versions = previous_versions.get(result.form.form_id, [])
                if not any(version < result.current_record.version for version in versions):
                    raise ValueError(
                        f"Superseded batch must contain an older version of {result.form.form_id}"
                    )
        batch_id = f"EXPORT-{uuid4().hex}"
        timestamp = datetime.now(UTC)
        destination = output_directory / f"{export_type}-{timestamp:%Y%m%dT%H%M%S}-{batch_id}.xlsx"
        partial = destination.with_name(f"{destination.name}.partial")
        pending = destination.with_name(f"{destination.name}.pending")
        serialized_filters = {
            key: value.value if hasattr(value, "value") else value
            for key, value in asdict(confirmed_filters).items()
            if value is not None
        }
        try:
            if progress is not None:
                progress(35, "writing")
            if report_definition is None:
                self._exporter.write(
                    partial,
                    batch_id,
                    export_type,
                    results,
                    serialized_filters,
                    mappings=mapping_snapshot,
                )
            else:
                self._exporter.write(
                    partial,
                    batch_id,
                    export_type,
                    results,
                    serialized_filters,
                    mappings=mapping_snapshot,
                    report_definition=report_definition,
                )
            digest = hashlib.sha256(partial.read_bytes()).hexdigest()
            destination.parent.mkdir(parents=True, exist_ok=True)
            partial.replace(pending)
            serialized_mappings = tuple(asdict(mapping) for mapping in (mapping_snapshot or ()))
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
                supersedes_batch_id=supersedes_batch_id,
                task_id=task_id,
                template_snapshot=template_snapshot,
                mapping_snapshot=serialized_mappings,
                download_name=destination.name,
            )
            if progress is not None:
                progress(75, "persisting")
            return batch
        except Exception:
            partial.unlink(missing_ok=True)
            pending.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

    def _resolve_report_definition(
        self, export_type: str, definition_id: str | None
    ) -> ReportDefinition | None:
        if definition_id is None:
            return None
        if self._report_definition_repository is None:
            raise RuntimeError("report definition repository is required")
        definition = self._report_definition_repository.get(definition_id)
        if definition is None:
            raise KeyError(f"Unknown report definition: {definition_id}")
        if definition.status is not ReportDefinitionStatus.PUBLISHED:
            raise ValueError("report definition must be published")
        if definition.report_key != export_type:
            raise ValueError("export_type must match the report definition key")
        return definition

    def _template_snapshot(self, results: list[SearchResult]) -> dict[str, object]:
        templates: dict[tuple[str, str], Mapping[str, object]] = {}
        for result in results:
            key = (result.form.template_id, result.form.template_version)
            template = self._resolve_template(*key)
            if template is None:
                continue
            templates[key] = {
                "version_id": template.version_id,
                "template_key": template.template_key,
                "version": template.version,
                "status": template.status.value,
                "page": asdict(template.page),
                "fields": [asdict(field) for field in template.fields],
            }
        return {"templates": [templates[key] for key in sorted(templates)]}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report_definition_snapshot(definition: ReportDefinition) -> dict[str, object]:
    return {
        "definition_id": definition.definition_id,
        "report_key": definition.report_key,
        "version": definition.version,
        "display_name": definition.display_name,
        "kind": definition.kind.value,
        "status": definition.status.value,
        "columns": [asdict(column) for column in definition.columns],
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
    }
