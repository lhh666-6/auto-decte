"""Persistent XLSX export task handler."""

import re
from pathlib import Path

from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.application.export_forms import ExportForms
from app.application.query_forms import FormFilters
from app.domain.models import ExportBatch, ExportStatus, ReviewStatus
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

            batch = self._exports.export(
                export_type,
                filters,
                self._output_directory,
                task.actor_id,
                task_id=task_id,
                supersedes_batch_id=supersedes,
                progress=report,
            )
            return batch
        except Exception as error:
            if self._tasks.get(task_id).status is TaskStatus.RUNNING:
                self._tasks.fail(task_id, str(error))
            raise


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
