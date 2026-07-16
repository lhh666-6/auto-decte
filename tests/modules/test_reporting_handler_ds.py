from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from typing import Any

import pytest
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from app.adapters.database.models import Base, ExportBatchRow, TaskRow
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.adapters.export.xlsx import XlsxExporter
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.export_forms import ExportForms
from app.application.import_forms import ImportForms
from app.application.query_forms import FormFilters, QueryForms
from app.application.review_forms import ReviewForms
from app.domain.models import ExportBatch, ExportStatus, ReviewStatus
from app.domain.templates_ds import (
    ExportTarget,
    FieldDefinition,
    PageSpec,
    Rect,
    TemplateVersion,
)
from app.infrastructure.database.sqlite_ds import create_sqlite_engine
from app.infrastructure.tasks.sqlite_store_ds import SqliteTaskStore
from app.modules.tasks.models_ds import TaskClaimConflict, TaskCommand, TaskStatus
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


def test_atomic_completion_uses_monotonic_task_and_event_timestamps(
    tmp_path: Path,
) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, store = _build_export_services(tmp_path)
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "monotonic-completion-time",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )

    batch = ExportHandler(
        exports, tasks, repository, tmp_path / "exports"
    ).handle(task.task_id)

    events = store.list_events(task.task_id)
    event_times = [event.created_at for event in events]
    last_progress = [event for event in events if event.event_type == "PROGRESS"][-1]
    persisted_task = tasks.get(task.task_id)
    assert event_times == sorted(event_times)
    assert persisted_task.updated_at >= last_progress.created_at
    assert persisted_task.updated_at >= batch.exported_at


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


def test_final_xlsx_is_not_visible_before_database_commit(tmp_path: Path) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    original_complete = repository.complete_export
    inspected = False

    def inspect_publication_order(batch: ExportBatch) -> None:
        nonlocal inspected
        final = Path(batch.file_path)
        pending = final.with_name(f"{final.name}.pending")
        assert not final.exists()
        assert pending.exists()
        inspected = True
        original_complete(batch)

    repository.complete_export = inspect_publication_order  # type: ignore[method-assign]
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "publication-order",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )

    batch = ExportHandler(exports, tasks, repository, tmp_path / "exports").handle(
        task.task_id
    )

    assert inspected
    assert Path(batch.file_path).exists()
    assert not Path(f"{batch.file_path}.pending").exists()
    assert tasks.get(task.task_id).status is TaskStatus.SUCCEEDED


def test_existing_batch_recovers_pending_file_after_post_commit_publish_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    handler = ExportHandler(exports, tasks, repository, tmp_path / "exports")
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "recover-publication",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )
    original_replace = Path.replace

    def fail_final_publish(source: Path, target: Path) -> Path:
        if source.name.endswith(".pending") and Path(target).suffix == ".xlsx":
            raise OSError("publish interrupted")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_final_publish)
    with pytest.raises(OSError, match="publish interrupted"):
        handler.handle(task.task_id)

    batch = repository.get_export_batch_by_task(task.task_id)
    assert batch is not None
    final = Path(batch.file_path)
    pending = Path(f"{batch.file_path}.pending")
    assert tasks.get(task.task_id).status is TaskStatus.SUCCEEDED
    assert not final.exists()
    assert pending.exists()
    assert exporter.write_calls == 1

    monkeypatch.undo()
    assert handler.handle(task.task_id) == batch
    assert final.exists()
    assert not pending.exists()
    assert exporter.write_calls == 1


class _SucceedMustNotBeCalled(TaskService):
    def succeed(self, task_id: str) -> object:
        del task_id
        raise RuntimeError("separate task success failed")


def test_batch_completion_atomically_succeeds_task_without_separate_update(
    tmp_path: Path,
) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, store = _build_export_services(tmp_path)
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "atomic-task-success",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )
    handler_tasks = _SucceedMustNotBeCalled(store)

    batch = ExportHandler(
        exports, handler_tasks, repository, tmp_path / "exports"
    ).handle(task.task_id)

    assert tasks.get(task.task_id).status is TaskStatus.SUCCEEDED
    assert repository.get_export_batch_by_task(task.task_id) == batch
    assert Path(batch.file_path).exists()


class _BlockingExporter(XlsxExporter):
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self._lock = Lock()
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
        with self._lock:
            self.write_calls += 1
        self.started.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test did not release writer")
        super().write(destination, batch_id, export_type, results, filters, mappings)


def test_two_workers_write_once_and_loser_can_read_winning_batch(
    tmp_path: Path,
) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, templates, _, tasks, _ = _build_export_services(tmp_path)
    exporter = _BlockingExporter()
    exports = ExportForms(
        repository,
        exporter,
        QueryForms(repository),
        template_repository=templates,
    )
    handler = ExportHandler(exports, tasks, repository, tmp_path / "exports")
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "concurrent-workers",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        winner = executor.submit(handler.handle, task.task_id)
        assert exporter.started.wait(timeout=2)
        loser = executor.submit(handler.handle, task.task_id)
        try:
            with pytest.raises(TaskClaimConflict):
                loser.result(timeout=2)
        finally:
            exporter.release.set()
        batch = winner.result(timeout=5)

    assert handler.handle(task.task_id) == batch
    assert exporter.write_calls == 1
    assert tasks.get(task.task_id).status is TaskStatus.SUCCEEDED


def test_existing_batch_reconciles_legacy_pending_task_to_succeeded(
    tmp_path: Path,
) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    engine, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    handler = ExportHandler(exports, tasks, repository, tmp_path / "exports")
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "legacy-pending-task",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )
    batch = handler.handle(task.task_id)
    with Session(engine) as session, session.begin():
        row = session.get(TaskRow, task.task_id)
        assert row is not None
        row.status = TaskStatus.PENDING.value
        row.progress = 75

    assert handler.handle(task.task_id) == batch
    assert tasks.get(task.task_id).status is TaskStatus.SUCCEEDED
    assert tasks.get(task.task_id).progress == 100


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


def test_reexport_required_form_must_name_superseded_batch(tmp_path: Path) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    handler = ExportHandler(exports, tasks, repository, tmp_path / "exports")
    first_task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "reexport-base",
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
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "reexport-without-base",
            {
                "export_type": "OUTPUT",
                "filters": {"export_status": "REEXPORT_REQUIRED"},
            },
        )
    )

    with pytest.raises(ValueError, match="supersedes_batch_id is required"):
        handler.handle(task.task_id)

    assert tasks.get(task.task_id).status is TaskStatus.FAILED
    assert repository.get_export_batch_by_task(task.task_id) is None
    assert Path(first.file_path).exists()
    assert len(repository.list_export_batches()) == 1
    assert len(list((tmp_path / "exports").glob("*.xlsx"))) == 1


@pytest.mark.parametrize(
    "invalid_records",
    [(('FORM-OTHER', 1),), (("FORM-1", 2),)],
)
def test_reexport_rejects_batch_without_older_version_of_same_form(
    tmp_path: Path, invalid_records: tuple[tuple[str, int], ...]
) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    handler = ExportHandler(exports, tasks, repository, tmp_path / "exports")
    first_task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "valid-reexport-base",
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
    invalid_base = ExportBatch(
        export_batch_id="EXPORT-INVALID-BASE",
        export_type="OUTPUT",
        filters={},
        included_records=invalid_records,
        file_path=str(tmp_path / "invalid-base.xlsx"),
        file_sha256="0" * 64,
        exported_by="finance",
    )
    repository.add_export_batch(invalid_base)
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "invalid-reexport-base",
            {
                "export_type": "OUTPUT",
                "filters": {"export_status": "REEXPORT_REQUIRED"},
                "supersedes_batch_id": invalid_base.export_batch_id,
            },
        )
    )

    with pytest.raises(ValueError, match="older version of FORM-1"):
        handler.handle(task.task_id)

    assert tasks.get(task.task_id).status is TaskStatus.FAILED
    assert repository.get_export_batch_by_task(task.task_id) is None
    assert Path(first.file_path).exists()
    assert len(repository.list_export_batches()) == 2
    assert len(list((tmp_path / "exports").glob("*.xlsx"))) == 1


def test_non_reexport_request_cannot_claim_to_supersede_batch(tmp_path: Path) -> None:
    from app.modules.reporting.handler_ds import ExportHandler

    _, repository, _, exports, tasks, _ = _build_export_services(tmp_path)
    handler = ExportHandler(exports, tasks, repository, tmp_path / "exports")
    first_task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "ordinary-export",
            {"export_type": "OUTPUT", "filters": {}},
        )
    )
    first = handler.handle(first_task.task_id)
    task = tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "exports",
            "finance",
            "false-supersession",
            {
                "export_type": "OUTPUT",
                "filters": {"export_status": "EXPORTED"},
                "supersedes_batch_id": first.export_batch_id,
            },
        )
    )

    with pytest.raises(ValueError, match="only valid for REEXPORT_REQUIRED"):
        handler.handle(task.task_id)

    assert tasks.get(task.task_id).status is TaskStatus.FAILED
    assert repository.get_export_batch_by_task(task.task_id) is None
    assert len(repository.list_export_batches()) == 1
    assert len(list((tmp_path / "exports").glob("*.xlsx"))) == 1


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
