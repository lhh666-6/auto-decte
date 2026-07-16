from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from app.adapters.database.models import Base, ExportBatchRow
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.adapters.export.xlsx import XlsxExporter
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.export_forms import ExportForms
from app.application.import_forms import ImportForms
from app.application.query_forms import FormFilters, QueryForms
from app.application.review_forms import ReviewForms
from app.domain.models import ExportStatus, ReviewStatus
from app.domain.templates_ds import (
    ExportTarget,
    FieldDefinition,
    PageSpec,
    Rect,
    TemplateVersion,
)
from app.infrastructure.database.sqlite_ds import create_sqlite_engine
from app.infrastructure.tasks.sqlite_store_ds import SqliteTaskStore
from app.modules.tasks.models_ds import TaskCommand, TaskStatus
from app.modules.tasks.service_ds import TaskService
from app.services.container import build_services
from config.settings import Settings


def _build_export_services(
    tmp_path: Path,
) -> tuple[
    Engine,
    SqlAlchemyFormRepository,
    SqlAlchemyTemplateRepository,
    ExportForms,
    TaskService,
    SqliteTaskStore,
]:
    engine = create_sqlite_engine(tmp_path / "handler.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    templates = SqlAlchemyTemplateRepository(engine)
    template = TemplateVersion.draft("TPL-T1-V1", "T1", 1, PageSpec.a4_portrait())
    template.add_field(
        FieldDefinition(
            "employee_id",
            "Employee",
            "text",
            "text_box",
            Rect(0.1, 0.1, 0.2, 0.05),
            template.page,
            export_target=ExportTarget("payroll.xlsx", "employees", "employee_code"),
        )
    )
    templates.add_version(template)
    imports = ImportForms(
        repository,
        repository,
        repository,
        LocalEvidenceStorage(tmp_path / "evidence"),
    )
    image = tmp_path / "scan.png"
    image.write_bytes(b"scan")
    evidence = imports.import_image(image, "FORM-1", "T1", "1", "operator")
    ReviewForms(repository, repository).confirm(
        "FORM-1",
        0,
        {"employee_id": "E001"},
        "reviewer",
        "confirmed",
        (evidence.file_id,),
    )
    store = SqliteTaskStore(engine)
    tasks = TaskService(store)
    exports = ExportForms(
        repository,
        XlsxExporter(),
        QueryForms(repository),
        template_repository=templates,
    )
    return engine, repository, templates, exports, tasks, store


def test_handler_completes_persistent_export_with_progress_and_snapshots(
    tmp_path: Path,
) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, store = _build_export_services(tmp_path)
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "export-1",
            {"export_type": "OUTPUT", "filters": {"form_id": "FORM-1"}},
        )
    )

    batch = ExportHandler(
        exports, tasks, repository, tmp_path / "exports"
    ).handle(task.task_id)

    persisted_task = tasks.get(task.task_id)
    persisted_batch = repository.get_export_batch_by_task(task.task_id)
    assert persisted_task.status is TaskStatus.SUCCEEDED
    assert batch == persisted_batch
    assert batch.task_id == task.task_id
    assert batch.filters["form_id"] == "FORM-1"
    assert batch.included_records == (("FORM-1", 1),)
    assert batch.template_snapshot["templates"][0]["template_key"] == "T1"
    assert batch.mapping_snapshot[0]["field_key"] == "employee_id"
    assert len(batch.mapping_hash) == 64
    assert len(batch.file_sha256) == 64
    assert batch.download_name.endswith(".xlsx")
    assert Path(batch.file_path).exists()
    progress = [
        event.progress
        for event in store.list_events(task.task_id)
        if event.event_type in {"PROGRESS", "SUCCEEDED"}
    ]
    assert progress == sorted(progress)
    assert progress[-1] == 100
    assert {event.step for event in store.list_events(task.task_id)} >= {
        "validating",
        "writing",
        "persisting",
    }
    assert repository.get_form("FORM-1").export_status.value == "EXPORTED"  # type: ignore[union-attr]
    assert repository.list_audit_events("FORM-1")[-1].event_type == "EXPORT"


def test_handler_fails_when_preview_has_no_included_records(tmp_path: Path) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "empty-export",
            {"export_type": "OUTPUT", "filters": {"form_id": "MISSING"}},
        )
    )

    with pytest.raises(ValueError, match="No exportable records"):
        ExportHandler(exports, tasks, repository, tmp_path / "exports").handle(
            task.task_id
        )

    assert tasks.get(task.task_id).status is TaskStatus.FAILED
    assert repository.get_export_batch_by_task(task.task_id) is None
    assert list((tmp_path / "exports").glob("*")) == []


def test_handler_requires_filters_in_persisted_payload(tmp_path: Path) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "missing-filters",
            {"export_type": "OUTPUT"},
        )
    )

    with pytest.raises(ValueError, match="filters is required"):
        ExportHandler(exports, tasks, repository, tmp_path / "exports").handle(
            task.task_id
        )

    assert tasks.get(task.task_id).status is TaskStatus.FAILED
    assert repository.list_export_batches() == []
    assert list((tmp_path / "exports").glob("*")) == []


class _TrackingExporter(XlsxExporter):
    def __init__(self) -> None:
        self.write_calls = 0

    def write(
        self,
        destination: Path,
        batch_id: str,
        export_type: str,
        results: Any,
        filters: dict[str, Any],
        mappings: Any = None,
    ) -> None:
        self.write_calls += 1
        super().write(destination, batch_id, export_type, results, filters, mappings)


def test_handler_fails_if_record_loses_eligibility_during_final_validation(
    tmp_path: Path,
) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, templates, _, tasks, _ = _build_export_services(tmp_path)
    exporter = _TrackingExporter()
    exports = ExportForms(
        repository,
        exporter,
        QueryForms(repository),
        template_repository=templates,
    )
    original_preview = exports.preview
    preview_calls = 0

    def preview_then_revoke(
        filters: FormFilters, actor_id: str | None = None
    ) -> object:
        nonlocal preview_calls
        preview = original_preview(filters, actor_id)
        preview_calls += 1
        if preview_calls == 1:
            repository.set_review_status("FORM-1", ReviewStatus.NEEDS_REVIEW)
        return preview

    exports.preview = preview_then_revoke  # type: ignore[method-assign,assignment]
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "eligibility-race",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )

    with pytest.raises(ValueError, match="No exportable records after final validation"):
        ExportHandler(exports, tasks, repository, tmp_path / "exports").handle(
            task.task_id
        )

    assert preview_calls == 2
    assert exporter.write_calls == 0
    assert tasks.get(task.task_id).status is TaskStatus.FAILED
    assert repository.list_export_batches() == []
    assert list((tmp_path / "exports").glob("*")) == []


class _FailingExporter(XlsxExporter):
    def write(
        self,
        destination: Path,
        batch_id: str,
        export_type: str,
        results: Any,
        filters: dict[str, Any],
        mappings: Any = None,
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"partial workbook")
        raise RuntimeError("writer failed")


def test_writer_failure_marks_task_failed_and_removes_partial_file(
    tmp_path: Path,
) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, templates, _, tasks, _ = _build_export_services(tmp_path)
    exports = ExportForms(
        repository,
        _FailingExporter(),
        QueryForms(repository),
        template_repository=templates,
    )
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "writer-failure",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )

    with pytest.raises(RuntimeError, match="writer failed"):
        ExportHandler(exports, tasks, repository, tmp_path / "exports").handle(
            task.task_id
        )

    assert tasks.get(task.task_id).status is TaskStatus.FAILED
    assert repository.list_export_batches() == []
    assert list((tmp_path / "exports").glob("*")) == []
    assert repository.get_form("FORM-1").export_status is ExportStatus.NOT_EXPORTED  # type: ignore[union-attr]


def test_database_failure_rolls_back_batch_and_form_then_removes_final_file(
    tmp_path: Path,
) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "database-failure",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )

    def fail_export_flush(
        session: Session, flush_context: object, instances: object
    ) -> None:
        del flush_context, instances
        if any(isinstance(item, ExportBatchRow) for item in session.new):
            raise RuntimeError("database failed")

    event.listen(Session, "before_flush", fail_export_flush)
    try:
        with pytest.raises(RuntimeError, match="database failed"):
            ExportHandler(exports, tasks, repository, tmp_path / "exports").handle(
                task.task_id
            )
    finally:
        event.remove(Session, "before_flush", fail_export_flush)

    assert tasks.get(task.task_id).status is TaskStatus.FAILED
    assert repository.list_export_batches() == []
    assert repository.get_form("FORM-1").export_status is ExportStatus.NOT_EXPORTED  # type: ignore[union-attr]
    assert all(
        audit.event_type != "EXPORT"
        for audit in repository.list_audit_events("FORM-1")
    )
    assert list((tmp_path / "exports").glob("*")) == []


def test_reexport_supersedes_batch_and_preserves_old_file(tmp_path: Path) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    handler = ExportHandler(exports, tasks, repository, tmp_path / "exports")
    first_task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "first-export",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )
    first = handler.handle(first_task.task_id)
    ReviewForms(repository, repository).confirm(
        "FORM-1",
        1,
        {"employee_id": "E002"},
        "reviewer",
        "correction",
        (),
    )
    assert repository.get_form("FORM-1").export_status is ExportStatus.REEXPORT_REQUIRED  # type: ignore[union-attr]
    second_task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "second-export",
            {
                "export_type": "OUTPUT",
                "filters": {"export_status": "REEXPORT_REQUIRED"},
                "supersedes_batch_id": first.export_batch_id,
            },
        )
    )

    second = handler.handle(second_task.task_id)

    assert second.supersedes_batch_id == first.export_batch_id
    assert second.included_records == (("FORM-1", 2),)
    assert second.file_path != first.file_path
    assert Path(first.file_path).exists()
    assert Path(second.file_path).exists()
    assert repository.get_export_batch(first.export_batch_id) == first
    assert repository.get_export_batch(second.export_batch_id) == second


def test_handler_rejects_non_xlsx_task_without_starting_it(tmp_path: Path) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    task = tasks.submit(
        TaskCommand("FORM_RECOGNITION", "FORM-1", "operator", "recognize", {})
    )

    with pytest.raises(ValueError, match="Unsupported task operation"):
        ExportHandler(exports, tasks, repository, tmp_path / "exports").handle(
            task.task_id
        )

    assert tasks.get(task.task_id).status is TaskStatus.PENDING
    assert repository.list_export_batches() == []


def test_unknown_superseded_batch_fails_without_publishing_file(tmp_path: Path) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "missing-superseded-batch",
            {
                "export_type": "OUTPUT",
                "filters": {},
                "supersedes_batch_id": "EXPORT-MISSING",
            },
        )
    )

    with pytest.raises(KeyError, match="Unknown export batch"):
        ExportHandler(exports, tasks, repository, tmp_path / "exports").handle(
            task.task_id
        )

    assert tasks.get(task.task_id).status is TaskStatus.FAILED
    assert repository.list_export_batches() == []
    assert list((tmp_path / "exports").glob("*")) == []


def test_handler_rejects_export_type_that_is_not_a_safe_file_component(
    tmp_path: Path,
) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "unsafe-export-type",
            {"export_type": "../outside", "filters": {}},
        )
    )

    with pytest.raises(ValueError, match="safe identifier"):
        ExportHandler(exports, tasks, repository, tmp_path / "exports").handle(
            task.task_id
        )

    assert tasks.get(task.task_id).status is TaskStatus.FAILED
    assert repository.list_export_batches() == []
    assert list(tmp_path.glob("outside*.xlsx")) == []


def test_atomic_completion_rejects_record_version_changed_after_workbook_write(
    tmp_path: Path,
) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    original_complete = repository.complete_export

    def correct_before_completion(batch: object) -> None:
        ReviewForms(repository, repository).confirm(
            "FORM-1",
            1,
            {"employee_id": "E002"},
            "reviewer",
            "concurrent correction",
            (),
        )
        original_complete(batch)  # type: ignore[arg-type]

    repository.complete_export = correct_before_completion  # type: ignore[method-assign]
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "stale-record",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )

    with pytest.raises(ValueError, match="no longer exportable"):
        ExportHandler(exports, tasks, repository, tmp_path / "exports").handle(
            task.task_id
        )

    assert tasks.get(task.task_id).status is TaskStatus.FAILED
    assert repository.list_export_batches() == []
    assert repository.get_form("FORM-1").current_record_version == 2  # type: ignore[union-attr]
    assert repository.get_form("FORM-1").export_status is ExportStatus.NOT_EXPORTED  # type: ignore[union-attr]
    assert list((tmp_path / "exports").glob("*")) == []


def test_service_container_registers_template_reporting_and_export_handler(
    tmp_path: Path,
) -> None:
    from app.modules.reporting.facade_ds import ReportingFacade
    from app.modules.reporting.handler_ds import ExportHandler

    services = build_services(Settings(data_root=tmp_path / "runtime"))

    assert services.exports.preview(FormFilters()).included == ()
    assert isinstance(services.reporting, ReportingFacade)
    assert services.reporting.preview(FormFilters()).included == ()
    assert isinstance(services.export_handler, ExportHandler)
