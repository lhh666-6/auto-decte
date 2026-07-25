"""Unit tests for electronic forms domain models and facade services.

Per Task 2 of the PWA plan: verify definition immutability, draft revision
conflicts, receipt idempotency, and payload conflict detection.
"""

import pytest

from app.modules.electronic_forms.facade_ds import (
    ElectronicDefinitionService,
    ElectronicDraftService,
    ElectronicSubmissionService,
    _payload_hash,
)
from app.modules.electronic_forms.models_ds import (
    DefinitionNotPublished,
    DefinitionStatus,
    DraftRevisionConflict,
    ElectronicDraft,
    ElectronicFormDefinitionVersion,
    ElectronicSubmissionReceipt,
    IdempotencyConflict,
    ReceiptOperation,
    SchemaVersionConflict,
    SubmissionReceiptStatus,
)
from app.modules.electronic_forms.ports_ds import (
    ElectronicDraftRepository,
    ElectronicFormDefinitionRepository,
    ElectronicSubmissionReceiptRepository,
)

# ── In-memory fakes for unit-test isolation ─────────────────────


class _FakeDefinitionRepo(ElectronicFormDefinitionRepository):
    def __init__(self) -> None:
        self._store: dict[str, ElectronicFormDefinitionVersion] = {}

    def add(self, d: ElectronicFormDefinitionVersion) -> None:
        self._store[d.definition_version_id] = d

    def get(self, did: str) -> ElectronicFormDefinitionVersion | None:
        return self._store.get(did)

    def get_published(self, form_type: str) -> ElectronicFormDefinitionVersion | None:
        for d in self._store.values():
            if d.form_type == form_type and d.status == DefinitionStatus.PUBLISHED:
                return d
        return None

    def list_by_form_type(self, form_type: str) -> list[ElectronicFormDefinitionVersion]:
        return [d for d in self._store.values() if d.form_type == form_type]


class _FakeDraftRepo(ElectronicDraftRepository):
    def __init__(self) -> None:
        self._store: dict[str, ElectronicDraft] = {}

    def add(self, d: ElectronicDraft) -> None:
        self._store[d.draft_id] = d

    def get(self, did: str) -> ElectronicDraft | None:
        return self._store.get(did)

    def list_by_owner(self, owner: str, device: str) -> list[ElectronicDraft]:
        return [
            d for d in self._store.values() if d.owner_actor_id == owner and d.device_id == device
        ]

    def update(self, d: ElectronicDraft) -> None:
        if d.draft_id not in self._store:
            raise ValueError("not found")
        self._store[d.draft_id] = d

    def delete(self, did: str) -> None:
        self._store.pop(did, None)


class _FakeReceiptRepo(ElectronicSubmissionReceiptRepository):
    def __init__(self) -> None:
        self._store: dict[str, ElectronicSubmissionReceipt] = {}

    def add(self, r: ElectronicSubmissionReceipt) -> None:
        self._store[r.receipt_id] = r

    def get(self, rid: str) -> ElectronicSubmissionReceipt | None:
        return self._store.get(rid)

    def find_idempotent(
        self,
        actor_id: str,
        device_id: str,
        operation: str,
        client_submission_id: str,
    ) -> ElectronicSubmissionReceipt | None:
        for r in self._store.values():
            if (
                r.actor_id == actor_id
                and r.device_id == device_id
                and r.operation.value == operation
                and r.client_submission_id == client_submission_id
            ):
                return r
        return None

    def list_by_actor(self, actor_id: str, limit: int = 50) -> list[ElectronicSubmissionReceipt]:
        items = [r for r in self._store.values() if r.actor_id == actor_id]
        items.sort(key=lambda r: r.submitted_at, reverse=True)
        return items[:limit]


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def def_repo() -> _FakeDefinitionRepo:
    return _FakeDefinitionRepo()


@pytest.fixture
def def_svc(def_repo: _FakeDefinitionRepo) -> ElectronicDefinitionService:
    return ElectronicDefinitionService(def_repo)


@pytest.fixture
def draft_repo() -> _FakeDraftRepo:
    return _FakeDraftRepo()


@pytest.fixture
def draft_svc(draft_repo: _FakeDraftRepo) -> ElectronicDraftService:
    return ElectronicDraftService(draft_repo)


@pytest.fixture
def receipt_repo() -> _FakeReceiptRepo:
    return _FakeReceiptRepo()


@pytest.fixture
def sub_svc(
    receipt_repo: _FakeReceiptRepo, def_svc: ElectronicDefinitionService
) -> ElectronicSubmissionService:
    # Publish a definition first
    d = def_svc.create_draft(
        form_type="SHEET_PIECE_MEASUREMENT",
        display_name="配片工作记录",
        template_version_id="tpl-v1",
        created_by="test",
    )
    def_svc.publish(d.definition_version_id)
    return ElectronicSubmissionService(receipt_repo, def_svc)


# ── Definition tests ───────────────────────────────────────────


class TestDefinitionLifecycle:
    def test_create_draft_increments_version(self, def_svc: ElectronicDefinitionService) -> None:
        v1 = def_svc.create_draft("NEW_TYPE", "新类型", created_by="u1")
        v2 = def_svc.create_draft("NEW_TYPE", "新类型 v2", created_by="u1")
        assert v1.version == 1
        assert v2.version == 2

    def test_can_publish_without_template(self, def_svc: ElectronicDefinitionService) -> None:
        # OCR retired: template_version_id is optional. Electronic forms
        # can be published standalone without a paper template reference.
        d = def_svc.create_draft("NO_TPL", "无模板", created_by="u1")
        published = def_svc.publish(d.definition_version_id)
        assert published.status == DefinitionStatus.PUBLISHED

    def test_publish_sets_status_and_timestamp(self, def_svc: ElectronicDefinitionService) -> None:
        d = def_svc.create_draft(
            "WITH_TPL",
            "有模板",
            template_version_id="tpl-v1",
            created_by="u1",
        )
        published = def_svc.publish(d.definition_version_id)
        assert published.status == DefinitionStatus.PUBLISHED
        assert published.published_at is not None

    def test_get_published_raises_when_not_published(
        self, def_svc: ElectronicDefinitionService
    ) -> None:
        with pytest.raises(DefinitionNotPublished):
            def_svc.get_published("NONEXISTENT")

    def test_retire_changes_status(self, def_svc: ElectronicDefinitionService) -> None:
        d = def_svc.create_draft(
            "RETIRE_TEST",
            "可废弃",
            template_version_id="tpl-v1",
            created_by="u1",
        )
        def_svc.publish(d.definition_version_id)
        retired = def_svc.retire(d.definition_version_id)
        assert retired.status == DefinitionStatus.RETIRED


# ── Draft tests ────────────────────────────────────────────────


class TestDraftLifecycle:
    def test_save_new_draft(self, draft_svc: ElectronicDraftService) -> None:
        d = draft_svc.save(
            owner_actor_id="actor-1",
            subject_employee_code="E001",
            device_id="dev-a",
            definition_version_id="efd-1",
            values={"block_count": 5},
        )
        assert d.revision == 1
        assert d.values["block_count"] == 5

    def test_update_existing_draft_requires_revision_match(
        self,
        draft_svc: ElectronicDraftService,
    ) -> None:
        d = draft_svc.save("actor-1", "E001", "dev-a", "efd-1", {"x": 1})
        # Update with correct revision
        d2 = draft_svc.save(
            "actor-1",
            "E001",
            "dev-a",
            "efd-1",
            {"x": 2},
            draft_id=d.draft_id,
        )
        assert d2.revision == 2

    def test_update_fails_when_owner_mismatch(
        self,
        draft_svc: ElectronicDraftService,
        draft_repo: _FakeDraftRepo,
    ) -> None:
        d = draft_svc.save("actor-1", "E001", "dev-a", "efd-1", {"x": 1})
        with pytest.raises(ValueError, match="does not belong"):
            draft_svc.save(
                "actor-2",
                "E001",
                "dev-a",
                "efd-1",
                {"x": 2},
                draft_id=d.draft_id,
            )

    def test_list_drafts_filters_by_owner_and_device(
        self,
        draft_svc: ElectronicDraftService,
    ) -> None:
        draft_svc.save("actor-1", "E001", "dev-a", "efd-1", {"x": 1})
        draft_svc.save("actor-1", "E001", "dev-b", "efd-1", {"x": 2})
        draft_svc.save("actor-2", "E001", "dev-a", "efd-1", {"x": 3})

        actor1_dev_a = draft_svc.list_drafts("actor-1", "dev-a")
        assert len(actor1_dev_a) == 1
        assert actor1_dev_a[0].values["x"] == 1

    def test_delete_draft(self, draft_svc: ElectronicDraftService) -> None:
        d = draft_svc.save("actor-1", "E001", "dev-a", "efd-1", {"x": 1})
        draft_svc.delete_draft(d.draft_id)
        assert draft_svc.list_drafts("actor-1", "dev-a") == []


# ── Submission / receipt tests ─────────────────────────────────


class TestSubmissionIdempotency:
    def test_same_client_id_same_payload_returns_same_receipt(
        self,
        sub_svc: ElectronicSubmissionService,
    ) -> None:
        r1 = sub_svc.submit(
            form_type="SHEET_PIECE_MEASUREMENT",
            definition_version_id=_pub_def_id(sub_svc),
            mode="SELF",
            actor_id="actor-1",
            subject_employee_code="E001",
            device_id="dev-a",
            values={"block_count": 5},
            client_submission_id="cs-001",
        )
        r2 = sub_svc.submit(
            form_type="SHEET_PIECE_MEASUREMENT",
            definition_version_id=_pub_def_id(sub_svc),
            mode="SELF",
            actor_id="actor-1",
            subject_employee_code="E001",
            device_id="dev-a",
            values={"block_count": 5},
            client_submission_id="cs-001",
        )
        assert r2.receipt_id == r1.receipt_id

    def test_same_client_id_different_payload_raises_conflict(
        self,
        sub_svc: ElectronicSubmissionService,
    ) -> None:
        sub_svc.submit(
            form_type="SHEET_PIECE_MEASUREMENT",
            definition_version_id=_pub_def_id(sub_svc),
            mode="SELF",
            actor_id="actor-1",
            subject_employee_code="E001",
            device_id="dev-a",
            values={"block_count": 5},
            client_submission_id="cs-002",
        )
        with pytest.raises(IdempotencyConflict):
            sub_svc.submit(
                form_type="SHEET_PIECE_MEASUREMENT",
                definition_version_id=_pub_def_id(sub_svc),
                mode="SELF",
                actor_id="actor-1",
                subject_employee_code="E001",
                device_id="dev-a",
                values={"block_count": 999},
                client_submission_id="cs-002",
            )

    def test_idempotency_is_scoped_to_actor_and_device(
        self,
        sub_svc: ElectronicSubmissionService,
    ) -> None:
        sub_svc.submit(
            form_type="SHEET_PIECE_MEASUREMENT",
            definition_version_id=_pub_def_id(sub_svc),
            mode="SELF",
            actor_id="actor-1",
            subject_employee_code="E001",
            device_id="dev-a",
            values={"block_count": 1},
            client_submission_id="cs-scoped",
        )
        # Different actor, same client id — should succeed as new submission
        r2 = sub_svc.submit(
            form_type="SHEET_PIECE_MEASUREMENT",
            definition_version_id=_pub_def_id(sub_svc),
            mode="SELF",
            actor_id="actor-2",
            subject_employee_code="E002",
            device_id="dev-b",
            values={"block_count": 1},
            client_submission_id="cs-scoped",
        )
        assert r2.actor_id == "actor-2"

    def test_schema_version_mismatch_raises_conflict(
        self,
        sub_svc: ElectronicSubmissionService,
        def_svc: ElectronicDefinitionService,
    ) -> None:
        # Create a second draft (not published)
        def_svc.create_draft(
            "SHEET_PIECE_MEASUREMENT",
            "配片 v2",
            template_version_id="tpl-v1",
            created_by="test",
        )
        with pytest.raises(SchemaVersionConflict):
            sub_svc.submit(
                form_type="SHEET_PIECE_MEASUREMENT",
                definition_version_id="efd-nonexistent",
                mode="SELF",
                actor_id="actor-1",
                subject_employee_code="E001",
                device_id="dev-a",
                values={},
                client_submission_id="cs-003",
            )


class TestPayloadHash:
    def test_hash_is_deterministic(self) -> None:
        h1 = _payload_hash({"a": 1, "b": 2})
        h2 = _payload_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_hash_differs_for_different_values(self) -> None:
        h1 = _payload_hash({"x": 1})
        h2 = _payload_hash({"x": 2})
        assert h1 != h2


class TestReceiptImmutability:
    def test_receipt_fields_are_stable(self) -> None:
        receipt = ElectronicSubmissionReceipt(
            receipt_id="REC-001",
            actor_id="a1",
            subject_employee_code="E001",
            device_id="d1",
            payload_hash="abc",
        )
        assert receipt.receipt_id == "REC-001"
        assert receipt.operation == ReceiptOperation.CREATE_ELECTRONIC_FORM
        assert receipt.status == SubmissionReceiptStatus.ACCEPTED


class TestDraftRevisionConflict:
    def test_revision_conflict_contains_ids(self) -> None:
        err = DraftRevisionConflict("draft-1", 2, 3)
        assert err.draft_id == "draft-1"
        assert "expected 2" in str(err)
        assert "actual 3" in str(err)


# ── Helpers ─────────────────────────────────────────────────────


def _pub_def_id(sub_svc: ElectronicSubmissionService) -> str:
    d = sub_svc._definitions.get_published("SHEET_PIECE_MEASUREMENT")
    return d.definition_version_id
