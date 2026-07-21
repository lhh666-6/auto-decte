"""SQLAlchemy implementations of electronic forms repository interfaces."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    ElectronicDraftRow,
    ElectronicFormDefinitionVersionRow,
    ElectronicSubmissionReceiptRow,
)
from app.modules.electronic_forms.models_ds import (
    DefinitionStatus,
    ElectronicDraft,
    ElectronicFormDefinitionVersion,
    ElectronicSubmissionReceipt,
    PresentationConfig,
    PresentationField,
    ReceiptOperation,
    SubmissionReceiptStatus,
)
from app.modules.electronic_forms.ports_ds import (
    ElectronicDraftRepository,
    ElectronicFormDefinitionRepository,
    ElectronicSubmissionReceiptRepository,
)


def _now() -> datetime:
    return datetime.now(UTC)


# ── Definition repository ───────────────────────────────────────

class SqlAlchemyElectronicFormDefinitionRepository(ElectronicFormDefinitionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, definition: ElectronicFormDefinitionVersion) -> None:
        row = ElectronicFormDefinitionVersionRow(
            definition_version_id=definition.definition_version_id,
            form_type=definition.form_type,
            version=definition.version,
            status=definition.status.value,
            display_name=definition.display_name,
            template_version_id=definition.template_version_id,
            job_profile_version_id=definition.job_profile_version_id,
            presentation_config=_presentation_config_to_dict(definition.presentation_config),
            created_by=definition.created_by,
            created_at=definition.created_at,
            published_at=definition.published_at,
        )
        self._session.merge(row)

    def get(self, definition_version_id: str) -> ElectronicFormDefinitionVersion | None:
        row = self._session.get(ElectronicFormDefinitionVersionRow, definition_version_id)
        return _definition_from_row(row) if row else None

    def get_published(self, form_type: str) -> ElectronicFormDefinitionVersion | None:
        stmt = (
            select(ElectronicFormDefinitionVersionRow)
            .where(
                ElectronicFormDefinitionVersionRow.form_type == form_type,
                ElectronicFormDefinitionVersionRow.status == DefinitionStatus.PUBLISHED.value,
            )
            .order_by(ElectronicFormDefinitionVersionRow.version.desc())
            .limit(1)
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return _definition_from_row(row) if row else None

    def list_by_form_type(self, form_type: str) -> list[ElectronicFormDefinitionVersion]:
        stmt = (
            select(ElectronicFormDefinitionVersionRow)
            .where(ElectronicFormDefinitionVersionRow.form_type == form_type)
            .order_by(ElectronicFormDefinitionVersionRow.version.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_definition_from_row(r) for r in rows]


# ── Draft repository ────────────────────────────────────────────

class SqlAlchemyElectronicDraftRepository(ElectronicDraftRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, draft: ElectronicDraft) -> None:
        row = ElectronicDraftRow(
            draft_id=draft.draft_id,
            owner_actor_id=draft.owner_actor_id,
            subject_employee_code=draft.subject_employee_code,
            device_id=draft.device_id,
            definition_version_id=draft.definition_version_id,
            values=draft.values,
            revision=draft.revision,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )
        self._session.add(row)

    def get(self, draft_id: str) -> ElectronicDraft | None:
        row = self._session.get(ElectronicDraftRow, draft_id)
        return _draft_from_row(row) if row else None

    def list_by_owner(self, owner_actor_id: str, device_id: str) -> list[ElectronicDraft]:
        stmt = (
            select(ElectronicDraftRow)
            .where(
                ElectronicDraftRow.owner_actor_id == owner_actor_id,
                ElectronicDraftRow.device_id == device_id,
            )
            .order_by(ElectronicDraftRow.updated_at.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_draft_from_row(r) for r in rows]

    def update(self, draft: ElectronicDraft) -> None:
        row = self._session.get(ElectronicDraftRow, draft.draft_id)
        if row is None:
            raise ValueError(f"Draft {draft.draft_id} not found.")
        row.values = draft.values
        row.revision = draft.revision
        row.updated_at = draft.updated_at

    def delete(self, draft_id: str) -> None:
        row = self._session.get(ElectronicDraftRow, draft_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()


# ── Receipt repository ──────────────────────────────────────────

class SqlAlchemyElectronicSubmissionReceiptRepository(ElectronicSubmissionReceiptRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, receipt: ElectronicSubmissionReceipt) -> None:
        row = ElectronicSubmissionReceiptRow(
            receipt_id=receipt.receipt_id,
            actor_id=receipt.actor_id,
            subject_employee_code=receipt.subject_employee_code,
            device_id=receipt.device_id,
            operation=receipt.operation.value,
            client_submission_id=receipt.client_submission_id,
            payload_hash=receipt.payload_hash,
            form_id=receipt.form_id,
            record_version=receipt.record_version,
            status=receipt.status.value,
            submitted_at=receipt.submitted_at,
        )
        self._session.add(row)

    def get(self, receipt_id: str) -> ElectronicSubmissionReceipt | None:
        row = self._session.get(ElectronicSubmissionReceiptRow, receipt_id)
        return _receipt_from_row(row) if row else None

    def find_idempotent(
        self,
        actor_id: str,
        device_id: str,
        operation: str,
        client_submission_id: str,
    ) -> ElectronicSubmissionReceipt | None:
        stmt = (
            select(ElectronicSubmissionReceiptRow)
            .where(
                ElectronicSubmissionReceiptRow.actor_id == actor_id,
                ElectronicSubmissionReceiptRow.device_id == device_id,
                ElectronicSubmissionReceiptRow.operation == operation,
                ElectronicSubmissionReceiptRow.client_submission_id == client_submission_id,
            )
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return _receipt_from_row(row) if row else None

    def list_by_actor(self, actor_id: str, limit: int = 50) -> list[ElectronicSubmissionReceipt]:
        stmt = (
            select(ElectronicSubmissionReceiptRow)
            .where(ElectronicSubmissionReceiptRow.actor_id == actor_id)
            .order_by(ElectronicSubmissionReceiptRow.submitted_at.desc())
            .limit(limit)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_receipt_from_row(r) for r in rows]


# ── Row ↔ Domain mappers ────────────────────────────────────────

def _definition_from_row(row: ElectronicFormDefinitionVersionRow) -> ElectronicFormDefinitionVersion:
    return ElectronicFormDefinitionVersion(
        definition_version_id=row.definition_version_id,
        form_type=row.form_type,
        version=row.version,
        status=DefinitionStatus(row.status),
        display_name=row.display_name,
        template_version_id=row.template_version_id,
        job_profile_version_id=row.job_profile_version_id,
        presentation_config=_presentation_config_from_dict(row.presentation_config),
        created_by=row.created_by,
        created_at=row.created_at,
        published_at=row.published_at,
    )


def _draft_from_row(row: ElectronicDraftRow) -> ElectronicDraft:
    return ElectronicDraft(
        draft_id=row.draft_id,
        owner_actor_id=row.owner_actor_id,
        subject_employee_code=row.subject_employee_code,
        device_id=row.device_id,
        definition_version_id=row.definition_version_id,
        values=row.values,
        revision=row.revision,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _receipt_from_row(row: ElectronicSubmissionReceiptRow) -> ElectronicSubmissionReceipt:
    return ElectronicSubmissionReceipt(
        receipt_id=row.receipt_id,
        actor_id=row.actor_id,
        subject_employee_code=row.subject_employee_code,
        device_id=row.device_id,
        operation=ReceiptOperation(row.operation),
        client_submission_id=row.client_submission_id,
        payload_hash=row.payload_hash,
        form_id=row.form_id,
        record_version=row.record_version,
        status=SubmissionReceiptStatus(row.status),
        submitted_at=row.submitted_at,
    )


def _presentation_config_to_dict(config: PresentationConfig | None) -> dict | None:
    if config is None:
        return None
    return {
        "fields": [
            {
                "field_key": pf.field_key,
                "display_order": pf.display_order,
                "group": pf.group,
                "strategy": pf.strategy,
                "condition_rule": pf.condition_rule,
            }
            for pf in config.fields
        ],
        "groups": config.groups,
    }


def _presentation_config_from_dict(data: dict | None) -> PresentationConfig | None:
    if data is None:
        return None
    return PresentationConfig(
        fields=[
            PresentationField(
                field_key=f["field_key"],
                display_order=f["display_order"],
                group=f.get("group"),
                strategy=f.get("strategy", "DEFAULT_EDITABLE"),
                condition_rule=f.get("condition_rule"),
            )
            for f in data.get("fields", [])
        ],
        groups=data.get("groups"),
    )
