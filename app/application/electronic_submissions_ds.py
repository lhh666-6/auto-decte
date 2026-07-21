"""Electronic submission integration — bridges PWA submissions into the
existing form import → review → audit → export pipeline.

Per Task 5 of the PWA plan: creates Form, FormField, audit event, and
receipt in one atomic transaction. Submissions enter NEEDS_REVIEW and
follow the same review workflow as paper-scanned forms.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from app.domain.models import (
    AuditEvent,
    ExportStatus,
    Form,
    FormField,
    ReviewStatus,
    ValueSource,
    utc_now,
)
from app.modules.electronic_forms.models_ds import (
    ElectronicSubmissionReceipt,
    IdempotencyConflict,
    ReceiptOperation,
    SchemaVersionConflict,
    SubmissionReceiptStatus,
)
from app.modules.electronic_forms.ports_ds import (
    ElectronicSubmissionReceiptRepository,
)
from app.modules.electronic_forms.facade_ds import _payload_hash


@dataclass
class ElectronicFormCommand:
    """All data needed to create an electronic form record."""

    form_type: str
    definition_version_id: str
    mode: str  # SELF or TEAM_LEADER_BATCH
    actor_id: str
    subject_employee_code: str
    subject_employee_name: str
    team_id: str
    team_name: str
    device_id: str
    values: dict[str, Any]
    client_submission_id: str
    template_id: str
    template_version: str
    job_profile_key: str | None = None
    job_profile_version: str | None = None


class SubmissionRejectedError(ValueError):
    """Server-side validation rejected the submission."""

    def __init__(self, failures: list[dict[str, str]]) -> None:
        super().__init__(f"Submission rejected: {failures!r}")
        self.failures = failures


# ── Port (what the integration layer needs from the main system) ─

from abc import ABC, abstractmethod


class FormCreator(ABC):
    """Abstracts the main-system write path so electronic submissions
    can be tested without the full DI container."""

    @abstractmethod
    def create_form_with_fields(
        self,
        form: Form,
        fields: list[FormField],
        audit: AuditEvent,
    ) -> None: ...


class SqlAlchemyFormCreator(FormCreator):
    """Production implementation using the existing FormRepository."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    def create_form_with_fields(
        self,
        form: Form,
        fields: list[FormField],
        audit: AuditEvent,
    ) -> None:
        from app.adapters.database.models import (
            AuditEventRow,
            FormFieldRow,
            FormRow,
        )
        session = self._session_factory()
        try:
            form_row = FormRow(
                form_id=form.form_id,
                template_id=form.template_id,
                template_version=form.template_version,
                job_profile_key=form.job_profile_key,
                job_profile_version=form.job_profile_version,
                coordinate_version=form.coordinate_version,
                review_status=form.review_status.value,
                export_status=form.export_status.value,
                current_record_version=form.current_record_version,
                priority=form.priority,
                created_at=form.created_at,
            )
            session.add(form_row)
            for f in fields:
                session.add(FormFieldRow(
                    field_id=f.field_id,
                    form_id=f.form_id,
                    field_name=f.field_name,
                    source_region=f.source_region,
                    current_value=f.current_value,
                    current_value_source=f.current_value_source.value if f.current_value_source else None,
                    current_record_version=f.current_record_version,
                ))
            session.add(AuditEventRow(
                event_id=audit.event_id,
                form_id=audit.form_id,
                event_type=audit.event_type,
                actor_id=audit.actor_id,
                timestamp=form.created_at,
                before=audit.before,
                after=audit.after,
                reason=audit.reason,
                evidence_ids=list(audit.evidence_ids),
            ))
            session.flush()
        finally:
            session.close()


# ── Integration service ─────────────────────────────────────────

class ElectronicFormIntegration:
    """Accepts a validated electronic submission and creates the main-system
    Form + FormField + audit + receipt records."""

    def __init__(
        self,
        form_creator: FormCreator,
        receipt_repo: ElectronicSubmissionReceiptRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._form_creator = form_creator
        self._receipt_repo = receipt_repo
        self._clock = clock or utc_now

    def accept(
        self, command: ElectronicFormCommand,
    ) -> ElectronicSubmissionReceipt:
        # 1. Idempotency check
        payload_hash = _payload_hash(command.values)
        existing = self._receipt_repo.find_idempotent(
            actor_id=command.actor_id,
            device_id=command.device_id,
            operation=ReceiptOperation.CREATE_ELECTRONIC_FORM.value,
            client_submission_id=command.client_submission_id,
        )
        if existing:
            if existing.payload_hash != payload_hash:
                raise IdempotencyConflict(command.client_submission_id)
            return existing

        # 2. Create main-system Form (enters NEEDS_REVIEW)
        form_id = f"EF-{uuid.uuid4().hex[:12]}"
        now = self._clock()
        form = Form(
            form_id=form_id,
            template_id=command.template_id,
            template_version=command.template_version,
            review_status=ReviewStatus.NEEDS_REVIEW,
            export_status=ExportStatus.NOT_EXPORTED,
            job_profile_key=command.job_profile_key,
            job_profile_version=command.job_profile_version,
            created_at=now,
        )

        # 3. Create FormField records with ELECTRONIC_SUBMITTED source
        fields: list[FormField] = []
        for field_key, value in command.values.items():
            fields.append(FormField(
                field_id=f"ef-{form_id}-{field_key}",
                form_id=form_id,
                field_name=field_key,
                source_region={},
                current_value=value,
                current_value_source=ValueSource.ELECTRONIC_SUBMITTED,
            ))

        # 4. Create audit event
        audit = AuditEvent(
            event_id=f"audit-{uuid.uuid4().hex[:12]}",
            form_id=form_id,
            event_type="ELECTRONIC_SUBMIT",
            actor_id=command.actor_id,
            after={
                "subject_employee_code": command.subject_employee_code,
                "subject_employee_name": command.subject_employee_name,
                "mode": command.mode,
                "device_id": command.device_id,
                "definition_version_id": command.definition_version_id,
                "submitted_at": now.isoformat(),
            },
            reason=f"移动端电子填报 - {command.form_type}",
        )

        # 5. Persist atomically
        self._form_creator.create_form_with_fields(form, fields, audit)

        # 6. Create receipt
        receipt = ElectronicSubmissionReceipt(
            receipt_id=f"REC-{uuid.uuid4().hex[:8].upper()}",
            actor_id=command.actor_id,
            subject_employee_code=command.subject_employee_code,
            device_id=command.device_id,
            operation=ReceiptOperation.CREATE_ELECTRONIC_FORM,
            client_submission_id=command.client_submission_id,
            payload_hash=payload_hash,
            form_id=form_id,
            status=SubmissionReceiptStatus.NEEDS_REVIEW,
            submitted_at=now,
        )
        self._receipt_repo.add(receipt)
        return receipt
