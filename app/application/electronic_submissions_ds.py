"""Electronic submission integration — bridges PWA submissions into the
existing form import → review → audit → export pipeline.

Per Task 5 of the PWA plan: creates Form, FormField, audit event, and
receipt in one atomic transaction. Submissions enter NEEDS_REVIEW and
follow the same review workflow as paper-scanned forms.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.application.transform_facts import transform_electronic_submission
from app.domain.models import (
    AuditEvent,
    ExportStatus,
    Form,
    FormField,
    ReviewStatus,
    ValueSource,
    utc_now,
)
from app.infrastructure.database.electronic_submission_uow_ds import (
    ElectronicSubmissionUnitOfWork,
)
from app.modules.electronic_forms.facade_ds import _payload_hash
from app.modules.electronic_forms.models_ds import (
    ElectronicSubmissionReceipt,
    IdempotencyConflict,
    ReceiptOperation,
    SubmissionReceiptStatus,
)


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


# ── Integration service ─────────────────────────────────────────

class ElectronicFormIntegration:
    """Accepts a validated electronic submission and creates the main-system
    Form + FormField + audit + receipt records, then generates FactRecords."""

    def __init__(
        self,
        uow_factory: Callable[[], ElectronicSubmissionUnitOfWork],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock or utc_now

    def accept(
        self, command: ElectronicFormCommand,
    ) -> ElectronicSubmissionReceipt:
        payload_hash = _payload_hash(command.values)
        with self._uow_factory() as uow:
            existing = uow.receipts.find_idempotent(
                actor_id=command.actor_id,
                device_id=command.device_id,
                operation=ReceiptOperation.CREATE_ELECTRONIC_FORM.value,
                client_submission_id=command.client_submission_id,
            )
            if existing:
                if existing.payload_hash != payload_hash:
                    raise IdempotencyConflict(command.client_submission_id)
                return existing

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
            fields = [
                FormField(
                    field_id=f"ef-{form_id}-{field_key}",
                    form_id=form_id,
                    field_name=field_key,
                    source_region={},
                    current_value=value,
                    current_value_source=ValueSource.ELECTRONIC_SUBMITTED,
                )
                for field_key, value in command.values.items()
            ]
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

            uow.forms.add_form(form)
            uow.flush()
            for field in fields:
                uow.forms.add_form_field(field)
            uow.forms.add_audit_event(audit)
            uow.receipts.add(receipt)

            payload: dict[str, Any] = {"values": command.values}
            if command.mode == "TEAM_LEADER_BATCH":
                payload["team_members"] = _extract_team_members(command)
            for record in transform_electronic_submission(
                receipt, payload, employee_name=command.subject_employee_name,
            ):
                uow.facts.add(record)

            return receipt

    def list_receipts(
        self,
        actor_id: str,
        limit: int = 50,
    ) -> list[ElectronicSubmissionReceipt]:
        with self._uow_factory() as uow:
            return uow.receipts.list_by_actor(actor_id, limit=limit)


def _extract_team_members(command: ElectronicFormCommand) -> list[dict[str, Any]]:
    """Extract team member entries from the command values."""
    values = command.values
    members_raw = values.get("team_members", [])
    if isinstance(members_raw, list):
        return [
            {
                "employee_code": m.get("employee_code", ""),
                "employee_name": m.get("employee_name", ""),
                "values": m.get("values", {}),
            }
            if isinstance(m, dict)
            else {"employee_code": "", "employee_name": "", "values": {}}
            for m in members_raw
        ]
    return []
