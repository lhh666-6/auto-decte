"""Integration tests for electronic forms SQLAlchemy repositories.

Uses in-memory SQLite to verify persistence, idempotency constraints,
and optimistic draft revision checks.
"""

from importlib.util import find_spec

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.database.electronic_forms_repository_ds import (
    SqlAlchemyElectronicFormDefinitionRepository,
    SqlAlchemyElectronicDraftRepository,
    SqlAlchemyElectronicSubmissionReceiptRepository,
)
from app.adapters.database.models import Base
from app.modules.electronic_forms.models_ds import (
    DefinitionStatus,
    DraftRevisionConflict,
    ElectronicDraft,
    ElectronicFormDefinitionVersion,
    ElectronicSubmissionReceipt,
    IdempotencyConflict,
    PresentationConfig,
    PresentationField,
    ReceiptOperation,
    SubmissionReceiptStatus,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")  # use file-based path for shared tests
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def def_repo(session: Session) -> SqlAlchemyElectronicFormDefinitionRepository:
    return SqlAlchemyElectronicFormDefinitionRepository(session)


@pytest.fixture
def draft_repo(session: Session) -> SqlAlchemyElectronicDraftRepository:
    return SqlAlchemyElectronicDraftRepository(session)


@pytest.fixture
def receipt_repo(session: Session) -> SqlAlchemyElectronicSubmissionReceiptRepository:
    return SqlAlchemyElectronicSubmissionReceiptRepository(session)


# ── Definition repository ───────────────────────────────────────

class TestDefinitionRepository:
    def test_add_and_retrieve(self, def_repo: SqlAlchemyElectronicFormDefinitionRepository) -> None:
        d = ElectronicFormDefinitionVersion(
            definition_version_id="efd-test-001",
            form_type="SHEET_PIECE_MEASUREMENT",
            version=1,
            status=DefinitionStatus.DRAFT,
            display_name="配片 v1",
            template_version_id="tpl-v1",
            created_by="test",
        )
        def_repo.add(d)
        retrieved = def_repo.get("efd-test-001")
        assert retrieved is not None
        assert retrieved.form_type == "SHEET_PIECE_MEASUREMENT"
        assert retrieved.status == DefinitionStatus.DRAFT

    def test_get_published_returns_latest(self, def_repo: SqlAlchemyElectronicFormDefinitionRepository) -> None:
        v1 = ElectronicFormDefinitionVersion(
            definition_version_id="efd-v1", form_type="FT", version=1,
            status=DefinitionStatus.PUBLISHED, display_name="v1",
            template_version_id="tpl-1", created_by="t",
        )
        v2 = ElectronicFormDefinitionVersion(
            definition_version_id="efd-v2", form_type="FT", version=2,
            status=DefinitionStatus.PUBLISHED, display_name="v2",
            template_version_id="tpl-1", created_by="t",
        )
        def_repo.add(v1)
        def_repo.add(v2)
        pub = def_repo.get_published("FT")
        assert pub is not None
        assert pub.version == 2

    def test_get_published_ignores_draft(self, def_repo: SqlAlchemyElectronicFormDefinitionRepository) -> None:
        v1 = ElectronicFormDefinitionVersion(
            definition_version_id="efd-draft", form_type="FT2", version=1,
            status=DefinitionStatus.DRAFT, display_name="草稿",
            template_version_id="tpl-1", created_by="t",
        )
        def_repo.add(v1)
        assert def_repo.get_published("FT2") is None

    def test_unique_form_type_version(self, def_repo: SqlAlchemyElectronicFormDefinitionRepository) -> None:
        v1 = ElectronicFormDefinitionVersion(
            definition_version_id="efd-u1", form_type="FT3", version=1,
            status=DefinitionStatus.DRAFT, display_name="v1", created_by="t",
        )
        v1_dup = ElectronicFormDefinitionVersion(
            definition_version_id="efd-u2", form_type="FT3", version=1,
            status=DefinitionStatus.DRAFT, display_name="dup", created_by="t",
        )
        def_repo.add(v1)
        with pytest.raises(IntegrityError):
            def_repo.add(v1_dup)
            def_repo._session.flush()

    def test_presentation_config_round_trip(self, def_repo: SqlAlchemyElectronicFormDefinitionRepository) -> None:
        config = PresentationConfig(
            fields=[
                PresentationField(
                    field_key="block_count", display_order=1,
                    strategy="MANUAL_REQUIRED", group="主信息",
                ),
                PresentationField(
                    field_key="total_piece_count", display_order=2,
                    strategy="COMPUTED_READ_ONLY",
                ),
            ],
            groups=["主信息"],
        )
        d = ElectronicFormDefinitionVersion(
            definition_version_id="efd-config", form_type="FT4", version=1,
            status=DefinitionStatus.DRAFT, display_name="带配置",
            template_version_id="tpl-1", created_by="t",
            presentation_config=config,
        )
        def_repo.add(d)
        retrieved = def_repo.get("efd-config")
        assert retrieved is not None
        assert retrieved.presentation_config is not None
        assert len(retrieved.presentation_config.fields) == 2
        assert retrieved.presentation_config.fields[0].field_key == "block_count"
        assert retrieved.presentation_config.fields[0].strategy == "MANUAL_REQUIRED"


# ── Draft repository ────────────────────────────────────────────

class TestDraftRepository:
    def test_add_and_retrieve(self, draft_repo: SqlAlchemyElectronicDraftRepository) -> None:
        d = ElectronicDraft(
            draft_id="draft-001",
            owner_actor_id="actor-1",
            subject_employee_code="E001",
            device_id="dev-a",
            definition_version_id="efd-1",
            values={"block_count": 3},
        )
        draft_repo.add(d)
        retrieved = draft_repo.get("draft-001")
        assert retrieved is not None
        assert retrieved.values["block_count"] == 3

    def test_update_increments_revision(self, draft_repo: SqlAlchemyElectronicDraftRepository) -> None:
        d = ElectronicDraft(draft_id="draft-002", owner_actor_id="a1",
                            subject_employee_code="E001", device_id="d1",
                            definition_version_id="efd-1", values={"x": 1})
        draft_repo.add(d)
        retrieved = draft_repo.get("draft-002")
        assert retrieved is not None
        retrieved.update_values({"x": 2}, expected_revision=1)
        draft_repo.update(retrieved)
        updated = draft_repo.get("draft-002")
        assert updated is not None
        assert updated.values["x"] == 2
        assert updated.revision == 2

    def test_list_by_owner_filters_correctly(self, draft_repo: SqlAlchemyElectronicDraftRepository) -> None:
        draft_repo.add(ElectronicDraft("d1", "a1", "E001", "dev-a", "efd-1"))
        draft_repo.add(ElectronicDraft("d2", "a1", "E001", "dev-a", "efd-1"))
        draft_repo.add(ElectronicDraft("d3", "a2", "E001", "dev-a", "efd-1"))
        assert len(draft_repo.list_by_owner("a1", "dev-a")) == 2
        assert len(draft_repo.list_by_owner("a1", "dev-b")) == 0

    def test_delete_removes(self, draft_repo: SqlAlchemyElectronicDraftRepository) -> None:
        draft_repo.add(ElectronicDraft("d-del", "a1", "E001", "dev-a", "efd-1"))
        draft_repo.delete("d-del")
        assert draft_repo.get("d-del") is None


# ── Receipt repository ──────────────────────────────────────────

class TestReceiptRepository:
    def test_add_and_retrieve(self, receipt_repo: SqlAlchemyElectronicSubmissionReceiptRepository) -> None:
        r = ElectronicSubmissionReceipt(
            receipt_id="REC-001", actor_id="a1",
            subject_employee_code="E001", device_id="d1",
            client_submission_id="cs-1", payload_hash="abc",
        )
        receipt_repo.add(r)
        retrieved = receipt_repo.get("REC-001")
        assert retrieved is not None
        assert retrieved.client_submission_id == "cs-1"

    def test_find_idempotent_scoped_to_actor_device_operation(self, receipt_repo: SqlAlchemyElectronicSubmissionReceiptRepository) -> None:
        r = ElectronicSubmissionReceipt(
            receipt_id="REC-002", actor_id="a1",
            subject_employee_code="E001", device_id="d1",
            client_submission_id="cs-scope", payload_hash="hash",
        )
        receipt_repo.add(r)
        found = receipt_repo.find_idempotent(
            actor_id="a1", device_id="d1",
            operation="CREATE_ELECTRONIC_FORM",
            client_submission_id="cs-scope",
        )
        assert found is not None

        not_found = receipt_repo.find_idempotent(
            actor_id="a2", device_id="d1",
            operation="CREATE_ELECTRONIC_FORM",
            client_submission_id="cs-scope",
        )
        assert not_found is None

    def test_unique_constraint_on_idempotency(self, receipt_repo: SqlAlchemyElectronicSubmissionReceiptRepository) -> None:
        r1 = ElectronicSubmissionReceipt(
            receipt_id="REC-u1", actor_id="a1",
            subject_employee_code="E001", device_id="d1",
            client_submission_id="cs-uniq", payload_hash="h1",
        )
        r1_dup = ElectronicSubmissionReceipt(
            receipt_id="REC-u2", actor_id="a1",
            subject_employee_code="E001", device_id="d1",
            client_submission_id="cs-uniq", payload_hash="h2",
        )
        receipt_repo.add(r1)
        with pytest.raises(IntegrityError):
            receipt_repo.add(r1_dup)
            receipt_repo._session.flush()
