"""Human confirmation and correction use cases."""

from uuid import uuid4

from app.application.ports import AuditRepository, FormRepository
from app.domain.models import (
    AuditEvent,
    ExportStatus,
    RecordStatus,
    RecordVersion,
    ReviewStatus,
)


class ConcurrentReviewError(RuntimeError):
    pass


class ReviewForms:
    def __init__(self, forms: FormRepository, audits: AuditRepository) -> None:
        self._forms = forms
        self._audits = audits

    def confirm(
        self,
        form_id: str,
        expected_version: int,
        values: dict[str, object],
        actor_id: str,
        reason: str,
        evidence_ids: tuple[str, ...],
    ) -> RecordVersion:
        form = self._forms.get_form(form_id)
        if form is None:
            raise KeyError(f"Unknown form: {form_id}")
        if form.current_record_version != expected_version:
            raise ConcurrentReviewError(
                f"Expected version {expected_version}, current is {form.current_record_version}"
            )
        versions = self._forms.list_record_versions(form_id)
        before = versions[-1].values if versions else None
        new_version = expected_version + 1
        event_type = "CONFIRM" if expected_version == 0 else "CORRECT"
        record = RecordVersion(
            record_id=f"RECORD-{uuid4().hex}",
            form_id=form_id,
            version=new_version,
            previous_version=expected_version or None,
            status=RecordStatus.CONFIRMED if expected_version == 0 else RecordStatus.CORRECTED,
            values=values,
            change_reason=reason,
            confirmed_by=actor_id,
        )
        self._forms.add_record_version(record)
        self._forms.set_review_status(form_id, ReviewStatus.CONFIRMED)
        if form.export_status is ExportStatus.EXPORTED:
            self._forms.set_export_status(form_id, ExportStatus.REEXPORT_REQUIRED)
        self._audits.add_audit_event(
            AuditEvent(
                event_id=f"EVENT-{uuid4().hex}",
                form_id=form_id,
                event_type=event_type,
                actor_id=actor_id,
                before=before,
                after=values,
                reason=reason,
                evidence_ids=evidence_ids,
            )
        )
        return record
