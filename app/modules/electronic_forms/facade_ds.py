"""Electronic form application services.

Coordinates domain rules across definitions, drafts, and submission
receipts before storage.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from app.modules.electronic_forms.models_ds import (
    DefinitionNotPublished,
    DefinitionStatus,
    ElectronicDraft,
    ElectronicFormDefinitionVersion,
    ElectronicSubmissionReceipt,
    IdempotencyConflict,
    PresentationConfig,
    ReceiptOperation,
    SchemaVersionConflict,
    SubmissionReceiptStatus,
)
from app.modules.electronic_forms.ports_ds import (
    ElectronicDraftRepository,
    ElectronicFormDefinitionRepository,
    ElectronicSubmissionReceiptRepository,
)


class ElectronicDefinitionService:
    """Create, publish, and query electronic form definitions."""

    def __init__(self, repo: ElectronicFormDefinitionRepository) -> None:
        self._repo = repo

    def create_draft(
        self,
        form_type: str,
        display_name: str,
        template_version_id: str | None = None,
        job_profile_version_id: str | None = None,
        presentation_config: PresentationConfig | None = None,
        created_by: str = "",
    ) -> ElectronicFormDefinitionVersion:
        existing = self._repo.list_by_form_type(form_type)
        next_version = max((v.version for v in existing), default=0) + 1
        definition = ElectronicFormDefinitionVersion(
            definition_version_id=f"efd-{uuid.uuid4().hex[:12]}",
            form_type=form_type,
            version=next_version,
            status=DefinitionStatus.DRAFT,
            template_version_id=template_version_id,
            job_profile_version_id=job_profile_version_id,
            presentation_config=presentation_config,
            display_name=display_name,
            created_by=created_by,
        )
        self._repo.add(definition)
        return definition

    def publish(self, definition_version_id: str) -> ElectronicFormDefinitionVersion:
        definition = self._repo.get(definition_version_id)
        if definition is None:
            raise DefinitionNotPublished(definition_version_id)
        definition.publish()
        self._repo.add(definition)  # upsert with new status
        return definition

    def retire(self, definition_version_id: str) -> ElectronicFormDefinitionVersion:
        definition = self._repo.get(definition_version_id)
        if definition is None:
            raise DefinitionNotPublished(definition_version_id)
        definition.retire()
        self._repo.add(definition)
        return definition

    def get_published(self, form_type: str) -> ElectronicFormDefinitionVersion:
        definition = self._repo.get_published(form_type)
        if definition is None:
            raise DefinitionNotPublished(form_type)
        return definition


class ElectronicDraftService:
    """Save and retrieve server-side drafts with revision checks."""

    def __init__(self, repo: ElectronicDraftRepository) -> None:
        self._repo = repo

    def save(
        self,
        owner_actor_id: str,
        subject_employee_code: str,
        device_id: str,
        definition_version_id: str,
        values: dict[str, Any],
        draft_id: str | None = None,
    ) -> ElectronicDraft:
        if draft_id:
            existing = self._repo.get(draft_id)
            if existing:
                if existing.owner_actor_id != owner_actor_id:
                    raise ValueError("Draft does not belong to this actor.")
                existing.update_values(values, existing.revision)
                self._repo.update(existing)
                return existing
        draft = ElectronicDraft(
            draft_id=draft_id or f"draft-{uuid.uuid4().hex[:12]}",
            owner_actor_id=owner_actor_id,
            subject_employee_code=subject_employee_code,
            device_id=device_id,
            definition_version_id=definition_version_id,
            values=values,
        )
        self._repo.add(draft)
        return draft

    def list_drafts(
        self, owner_actor_id: str, device_id: str,
    ) -> list[ElectronicDraft]:
        return self._repo.list_by_owner(owner_actor_id, device_id)

    def delete_draft(self, draft_id: str) -> None:
        self._repo.delete(draft_id)


class ElectronicSubmissionService:
    """Accept electronic submissions, enforce idempotency, produce receipts."""

    def __init__(
        self,
        receipt_repo: ElectronicSubmissionReceiptRepository,
        definition_service: ElectronicDefinitionService,
    ) -> None:
        self._receipt_repo = receipt_repo
        self._definitions = definition_service

    def submit(
        self,
        form_type: str,
        definition_version_id: str,
        mode: str,
        actor_id: str,
        subject_employee_code: str,
        device_id: str,
        values: dict[str, Any],
        client_submission_id: str,
    ) -> ElectronicSubmissionReceipt:
        # 1. Validate definition exists and is published
        definition = self._definitions.get_published(form_type)
        if definition.definition_version_id != definition_version_id:
            raise SchemaVersionConflict(form_type)

        # 2. Idempotency check scoped to actor + device
        existing = self._receipt_repo.find_idempotent(
            actor_id=actor_id,
            device_id=device_id,
            operation=ReceiptOperation.CREATE_ELECTRONIC_FORM.value,
            client_submission_id=client_submission_id,
        )
        if existing:
            new_hash = _payload_hash(values)
            if new_hash != existing.payload_hash:
                raise IdempotencyConflict(client_submission_id)
            return existing  # idempotent replay — same receipt

        # 3. Create receipt (form creation delegated to Task 5)
        payload_hash = _payload_hash(values)
        receipt = ElectronicSubmissionReceipt(
            receipt_id=f"REC-{uuid.uuid4().hex[:8].upper()}",
            actor_id=actor_id,
            subject_employee_code=subject_employee_code,
            device_id=device_id,
            operation=ReceiptOperation.CREATE_ELECTRONIC_FORM,
            client_submission_id=client_submission_id,
            payload_hash=payload_hash,
            status=SubmissionReceiptStatus.ACCEPTED,
        )
        self._receipt_repo.add(receipt)
        return receipt

    def list_receipts(
        self, actor_id: str, limit: int = 50,
    ) -> list[ElectronicSubmissionReceipt]:
        return self._receipt_repo.list_by_actor(actor_id, limit=limit)


# ── Helpers ─────────────────────────────────────────────────────

def _payload_hash(values: dict[str, Any]) -> str:
    """Deterministic hash of submission values for idempotency checking."""
    canonical = json.dumps(values, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()
