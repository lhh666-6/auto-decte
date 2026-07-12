"""Transactional review workflow facade."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from app.application.review_forms import ConcurrentReviewError
from app.domain.models import AuditEvent, ExportStatus, RecordStatus, RecordVersion, ReviewStatus
from app.infrastructure.database.uow import UnitOfWork
from app.modules.audit.facade import AuditFacade


@dataclass(frozen=True, slots=True)
class ConfirmReviewCommand:
    form_id: str
    expected_version: int
    values: dict[str, object]
    actor_id: str
    reason: str
    evidence_ids: tuple[str, ...]


class AuditWriter(Protocol):
    def add_audit_event(self, event: AuditEvent) -> None: ...


class ReviewFacade:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        audits: AuditWriter | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._audits = audits

    def confirm(self, command: ConfirmReviewCommand) -> RecordVersion:
        with self._uow_factory() as uow:
            form = uow.forms.get_form(command.form_id)
            if form is None:
                raise KeyError(f"Unknown form: {command.form_id}")
            if form.current_record_version != command.expected_version:
                raise ConcurrentReviewError(
                    f"Expected version {command.expected_version}, "
                    f"current is {form.current_record_version}"
                )
            versions = uow.forms.list_record_versions(command.form_id)
            before = versions[-1].values if versions else None
            record = RecordVersion(
                record_id=f"RECORD-{uuid4().hex}",
                form_id=command.form_id,
                version=command.expected_version + 1,
                previous_version=command.expected_version or None,
                status=(
                    RecordStatus.CONFIRMED
                    if command.expected_version == 0
                    else RecordStatus.CORRECTED
                ),
                values=command.values,
                change_reason=command.reason,
                confirmed_by=command.actor_id,
            )
            uow.forms.add_record_version(record)
            uow.forms.set_review_status(command.form_id, ReviewStatus.CONFIRMED)
            if form.export_status is ExportStatus.EXPORTED:
                uow.forms.set_export_status(command.form_id, ExportStatus.REEXPORT_REQUIRED)
            event = AuditEvent(
                event_id=f"EVENT-{uuid4().hex}",
                form_id=command.form_id,
                event_type="CONFIRM" if command.expected_version == 0 else "CORRECT",
                actor_id=command.actor_id,
                before=before,
                after=command.values,
                reason=command.reason,
                evidence_ids=command.evidence_ids,
            )
            if self._audits is None:
                AuditFacade(uow.audits).append(event)
            else:
                self._audits.add_audit_event(event)
            return record
