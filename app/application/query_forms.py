"""Exact SQLite-backed form search and trace use cases."""

from dataclasses import dataclass
from typing import Protocol

from app.domain.models import (
    AuditEvent,
    EvidenceFile,
    ExportStatus,
    Form,
    FormField,
    RecognitionAttempt,
    RecordVersion,
    ReviewStatus,
)


@dataclass(frozen=True, slots=True)
class FormFilters:
    form_id: str | None = None
    employee_id: str | None = None
    work_order_id: str | None = None
    review_status: ReviewStatus | None = None
    export_status: ExportStatus | None = None


@dataclass(frozen=True, slots=True)
class SearchResult:
    form: Form
    current_record: RecordVersion


@dataclass(frozen=True, slots=True)
class FormTrace:
    form: Form
    versions: tuple[RecordVersion, ...]
    evidence: tuple[EvidenceFile, ...]
    audits: tuple[AuditEvent, ...]
    attempts: tuple[RecognitionAttempt, ...]


@dataclass(frozen=True, slots=True)
class FormWorkbench:
    """Read model consumed by the human review workbench."""

    trace: FormTrace
    fields: tuple[FormField, ...]


class QueryRepository(Protocol):
    def get_form(self, form_id: str) -> Form | None: ...
    def list_record_versions(self, form_id: str) -> list[RecordVersion]: ...
    def list_form_fields(self, form_id: str) -> list[FormField]: ...
    def list_evidence(self, form_id: str) -> list[EvidenceFile]: ...
    def list_audit_events(self, form_id: str) -> list[AuditEvent]: ...
    def list_recognition_attempts_for_form(self, form_id: str) -> list[RecognitionAttempt]: ...
    def search_current(
        self,
        *,
        form_id: str | None = None,
        employee_id: str | None = None,
        work_order_id: str | None = None,
        review_status: ReviewStatus | None = None,
        export_status: ExportStatus | None = None,
    ) -> list[tuple[Form, RecordVersion]]: ...


class QueryForms:
    def __init__(self, repository: QueryRepository) -> None:
        self._repository = repository

    def search(self, filters: FormFilters) -> list[SearchResult]:
        rows = self._repository.search_current(
            form_id=filters.form_id,
            employee_id=filters.employee_id,
            work_order_id=filters.work_order_id,
            review_status=filters.review_status,
            export_status=filters.export_status,
        )
        return [SearchResult(form, record) for form, record in rows]

    def trace(self, form_id: str) -> FormTrace:
        form = self._repository.get_form(form_id)
        if form is None:
            raise KeyError(f"Unknown form: {form_id}")
        return FormTrace(
            form=form,
            versions=tuple(self._repository.list_record_versions(form_id)),
            evidence=tuple(self._repository.list_evidence(form_id)),
            audits=tuple(self._repository.list_audit_events(form_id)),
            attempts=tuple(self._repository.list_recognition_attempts_for_form(form_id)),
        )

    def workbench(self, form_id: str) -> FormWorkbench:
        trace = self.trace(form_id)
        return FormWorkbench(
            trace=trace,
            fields=tuple(self._repository.list_form_fields(form_id)),
        )
