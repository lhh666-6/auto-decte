"""Persistent XLSX export task handler."""

import re
from datetime import datetime
from pathlib import Path

from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.application.export_forms import ExportForms, ExportIntegrityError
from app.application.query_forms import FormFilters
from app.domain.models import (
    ExportBatch,
    ExportStatus,
    ReviewStatus,
    thaw_json,
)
from app.modules.tasks.models_ds import TaskStatus
from app.modules.tasks.service_ds import TaskService


class ExportHandler:
    """Execute one persisted XLSX_EXPORT task synchronously."""

    def __init__(
        self,
        exports: ExportForms,
        tasks: TaskService,
        repository: SqlAlchemyFormRepository,
        output_directory: Path,
    ) -> None:
        self._exports = exports
        self._tasks = tasks
        self._repository = repository
        self._output_directory = output_directory

    def handle(self, task_id: str) -> ExportBatch:
        task = self._tasks.get(task_id)
        if task.operation != "XLSX_EXPORT":
            raise ValueError(f"Unsupported task operation: {task.operation}")
        existing = self._repository.get_export_batch_by_task(task_id)
        if existing is not None:
            self._exports.recover_publication(existing)
            self._tasks.reconcile_succeeded(
                task_id, {"export_batch_id": existing.export_batch_id}
            )
            return existing
        self._tasks.claim(task_id)
        batch: ExportBatch | None = None
        try:
            export_type = task.payload.get("export_type")
            if not isinstance(export_type, str) or not export_type.strip():
                raise ValueError("export_type is required")
            if re.fullmatch(r"[A-Za-z0-9_-]+", export_type) is None:
                raise ValueError("export_type must be a safe identifier")
            if "filters" not in task.payload:
                raise ValueError("filters is required")
            filters = _deserialize_filters(task.payload["filters"])
            supersedes = task.payload.get("supersedes_batch_id")
            if supersedes is not None and not isinstance(supersedes, str):
                raise ValueError("supersedes_batch_id must be a string")
            self._tasks.report(task_id, 10, "validating")
            preview = self._exports.preview(filters, task.actor_id)
            if not preview.included:
                raise ValueError("No exportable records")

            def report(value: int, step: str) -> None:
                self._tasks.report(task_id, value, step)

            batch = self._exports.prepare(
                export_type,
                filters,
                self._output_directory,
                task.actor_id,
                task_id=task_id,
                supersedes_batch_id=supersedes,
                progress=report,
            )
            self._tasks.record_prepared(task_id, _prepared_detail(batch))
        except Exception as error:
            if batch is not None:
                self._exports.cleanup(batch)
            if self._tasks.get(task_id).status is TaskStatus.RUNNING:
                self._tasks.fail(task_id, str(error))
            raise
        assert batch is not None
        try:
            self._exports.publish(batch)
        except ExportIntegrityError as error:
            self._exports.cleanup(batch)
            self._tasks.fail(task_id, str(error))
            raise
        except OSError:
            self._tasks.interrupt(task_id)
            raise
        try:
            self._exports.complete(batch)
            return batch
        except Exception as error:
            self._exports.cleanup(batch)
            if self._tasks.get(task_id).status is TaskStatus.RUNNING:
                self._tasks.fail(task_id, str(error))
            raise

    def recover_prepared(self) -> list[ExportBatch]:
        """Resume interrupted exports from append-only prepared task events."""
        recovered: list[ExportBatch] = []
        candidates = self._tasks.list_operation_tasks(
            "XLSX_EXPORT", (TaskStatus.INTERRUPTED,)
        )
        for task in candidates:
            event = self._tasks.latest_prepared(task.task_id)
            if event is None or event.detail is None:
                continue
            if self._tasks.claim_recovery(task.task_id) is None:
                continue
            try:
                batch = _batch_from_prepared_detail(event.detail)
            except Exception as error:
                self._tasks.fail(task.task_id, str(error))
                continue
            existing = self._repository.get_export_batch_by_task(task.task_id)
            if existing is not None:
                try:
                    self._exports.publish(existing)
                except OSError:
                    self._tasks.interrupt(task.task_id)
                    continue
                self._tasks.reconcile_succeeded(
                    task.task_id, {"export_batch_id": existing.export_batch_id}
                )
                recovered.append(existing)
                continue
            try:
                self._exports.publish(batch)
            except ExportIntegrityError as error:
                self._exports.cleanup(batch)
                self._tasks.fail(task.task_id, str(error))
                continue
            except OSError:
                self._tasks.interrupt(task.task_id)
                continue
            try:
                self._exports.complete(batch)
            except Exception as error:
                self._exports.cleanup(batch)
                if self._tasks.get(task.task_id).status is TaskStatus.RECOVERING:
                    self._tasks.fail(task.task_id, str(error))
                continue
            recovered.append(batch)
        return recovered


def _deserialize_filters(raw: object) -> FormFilters:
    if not isinstance(raw, dict):
        raise ValueError("filters must be an object")
    unknown = set(raw) - {
        "form_id",
        "employee_id",
        "work_order_id",
        "review_status",
        "export_status",
    }
    if unknown:
        raise ValueError(f"Unknown export filters: {', '.join(sorted(unknown))}")
    scalar_values: dict[str, str | None] = {}
    for key in ("form_id", "employee_id", "work_order_id"):
        value = raw.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        scalar_values[key] = value
    review_value = raw.get("review_status")
    export_value = raw.get("export_status")
    if review_value is not None and not isinstance(review_value, str):
        raise ValueError("review_status must be a string")
    if export_value is not None and not isinstance(export_value, str):
        raise ValueError("export_status must be a string")
    return FormFilters(
        form_id=scalar_values["form_id"],
        employee_id=scalar_values["employee_id"],
        work_order_id=scalar_values["work_order_id"],
        review_status=ReviewStatus(review_value) if review_value is not None else None,
        export_status=ExportStatus(export_value) if export_value is not None else None,
    )


def _prepared_detail(batch: ExportBatch) -> dict[str, object]:
    destination = Path(batch.file_path)
    return {
        "batch": {
            "export_batch_id": batch.export_batch_id,
            "export_type": batch.export_type,
            "filters": thaw_json(batch.filters),
            "included_records": [list(item) for item in batch.included_records],
            "file_path": batch.file_path,
            "file_sha256": batch.file_sha256,
            "exported_by": batch.exported_by,
            "exported_at": batch.exported_at.isoformat(),
            "supersedes_batch_id": batch.supersedes_batch_id,
            "task_id": batch.task_id,
            "template_snapshot": thaw_json(batch.template_snapshot),
            "mapping_snapshot": thaw_json(batch.mapping_snapshot),
            "mapping_hash": batch.mapping_hash,
            "download_name": batch.download_name,
        },
        "pending_name": f"{destination.name}.pending",
        "final_name": destination.name,
    }


def _batch_from_prepared_detail(detail: dict[str, object]) -> ExportBatch:
    raw = detail.get("batch")
    if not isinstance(raw, dict):
        raise ValueError("EXPORT_PREPARED event is missing its batch snapshot")
    included = raw.get("included_records")
    mappings = raw.get("mapping_snapshot")
    filters = raw.get("filters")
    templates = raw.get("template_snapshot")
    if not isinstance(included, list) or not isinstance(mappings, list):
        raise ValueError("EXPORT_PREPARED batch snapshot has invalid records")
    if not isinstance(filters, dict) or not isinstance(templates, dict):
        raise ValueError("EXPORT_PREPARED batch snapshot has invalid metadata")
    return ExportBatch(
        export_batch_id=_required_string(raw, "export_batch_id"),
        export_type=_required_string(raw, "export_type"),
        filters=filters,
        included_records=tuple(
            (_record_form_id(item), _record_version(item)) for item in included
        ),
        file_path=_required_string(raw, "file_path"),
        file_sha256=_required_string(raw, "file_sha256"),
        exported_by=_required_string(raw, "exported_by"),
        exported_at=datetime.fromisoformat(_required_string(raw, "exported_at")),
        supersedes_batch_id=_optional_string(raw, "supersedes_batch_id"),
        task_id=_optional_string(raw, "task_id"),
        template_snapshot=templates,
        mapping_snapshot=tuple(
            item for item in mappings if isinstance(item, dict)
        ),
        mapping_hash=_required_string(raw, "mapping_hash"),
        download_name=_required_string(raw, "download_name"),
    )


def _required_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"EXPORT_PREPARED batch snapshot has invalid {key}")
    return value


def _optional_string(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"EXPORT_PREPARED batch snapshot has invalid {key}")
    return value


def _record_form_id(value: object) -> str:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("EXPORT_PREPARED batch snapshot has invalid included record")
    form_id = value[0]
    if isinstance(form_id, str):
        return form_id
    raise ValueError("EXPORT_PREPARED batch snapshot has invalid included record")


def _record_version(value: object) -> int:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("EXPORT_PREPARED batch snapshot has invalid included record")
    version = value[1]
    if isinstance(version, int):
        return version
    raise ValueError("EXPORT_PREPARED batch snapshot has invalid included record")
