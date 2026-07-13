"""Interfaces implemented by infrastructure adapters."""

from pathlib import Path
from typing import BinaryIO, Protocol

from app.domain.models import (
    AuditEvent,
    EvidenceFile,
    ExportStatus,
    Form,
    FormField,
    RecordVersion,
    ReviewStatus,
)


class FormRepository(Protocol):
    def add_form(self, form: Form) -> None: ...
    def get_form(self, form_id: str) -> Form | None: ...
    def add_record_version(self, version: RecordVersion) -> None: ...
    def list_record_versions(self, form_id: str) -> list[RecordVersion]: ...
    def set_review_status(self, form_id: str, status: ReviewStatus) -> None: ...
    def set_export_status(self, form_id: str, status: ExportStatus) -> None: ...
    def add_form_field(self, field: FormField) -> None: ...


class EvidenceRepository(Protocol):
    def add_evidence(self, evidence: EvidenceFile) -> None: ...
    def find_by_sha256(self, sha256: str) -> EvidenceFile | None: ...


class AuditRepository(Protocol):
    def add_audit_event(self, event: AuditEvent) -> None: ...


class EvidenceStorage(Protocol):
    def store(self, source: BinaryIO, suffix: str, category: str) -> tuple[str, Path]: ...
