import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.modules.bamboo_process.facade_ds import (
    BambooPermissionDenied,
    BambooProcessFacade,
    StaleBambooRevision,
)
from app.modules.bamboo_process.models_ds import (
    BambooActor,
    BambooRecord,
    BambooRole,
    BambooStage,
    ElectronicSignature,
    StageSubmission,
)


class _MemoryBambooRepository:
    def __init__(self) -> None:
        self.records: dict[str, BambooRecord] = {}
        self.signatures: list[ElectronicSignature] = []
        self.idempotent_results: dict[tuple[str, str], BambooRecord] = {}

    def next_display_sequence(self, factory_id: str, production_date: str) -> int:
        del factory_id, production_date
        return len(self.records) + 1

    def add(self, record: BambooRecord) -> None:
        self.records[record.record_id] = record

    def get(self, record_id: str) -> BambooRecord | None:
        return self.records.get(record_id)

    def find_idempotent_result(
        self, actor_id: str, idempotency_key: str
    ) -> BambooRecord | None:
        return self.idempotent_results.get((actor_id, idempotency_key))

    def append_stage(
        self,
        *,
        record: BambooRecord,
        submission: StageSubmission,
        signature: ElectronicSignature,
        expected_revision: int,
    ) -> BambooRecord:
        current = self.records[record.record_id]
        if current.revision != expected_revision:
            raise StaleBambooRevision(expected_revision, current.revision)
        self.records[record.record_id] = record
        self.signatures.append(signature)
        self.idempotent_results[(signature.actor_id, signature.idempotency_key)] = record
        return record


def _sort_actor() -> BambooActor:
    return BambooActor(
        actor_id="E-SORT-01",
        employee_code="E-SORT-01",
        employee_name="王分选",
        factory_id="FACTORY-A",
        factory_name="竹丝一厂",
        role=BambooRole.SORT_OPERATOR,
    )


def test_sort_operator_creates_factory_scoped_record() -> None:
    repository = _MemoryBambooRepository()
    service = BambooProcessFacade(
        repository,
        clock=lambda: datetime(2026, 7, 22, 2, 30, tzinfo=UTC),
        id_factory=lambda: "BR-001",
    )

    record = service.create_record(
        actor=_sort_actor(),
        base_info={
            "cage_no": "3-018",
            "length": "2.3",
            "grade": "A",
            "bundle_count": 16,
        },
        source_type="MOBILE_CREATED",
        source_ref=None,
    )

    assert record.record_id == "BR-001"
    assert record.display_no == "ZS-20260722-001"
    assert record.factory_id == "FACTORY-A"
    assert record.current_stage is BambooStage.SORT
    assert record.revision == 1
    assert repository.get(record.record_id) == record


def test_submit_stage_advances_revision_and_captures_session_signature() -> None:
    repository = _MemoryBambooRepository()
    identifiers = iter(["BR-002", "SUB-001", "SIG-001"])
    now = datetime(2026, 7, 22, 2, 30, tzinfo=UTC)
    service = BambooProcessFacade(
        repository,
        clock=lambda: now,
        id_factory=lambda: next(identifiers),
    )
    actor = _sort_actor()
    record = service.create_record(
        actor=actor,
        base_info={"cage_no": "3-018"},
        source_type="MOBILE_CREATED",
        source_ref=None,
    )
    values: dict[str, object] = {"moisture": [12, 13, 12]}

    signed = service.submit_stage(
        record.record_id,
        actor=actor,
        stage=BambooStage.SORT,
        values=values,
        expected_revision=1,
        idempotency_key="sort-1",
        device_id="device-a",
        request_id="request-a",
    )

    assert signed.current_stage is BambooStage.DIPPING
    assert signed.revision == 2
    assert len(signed.submissions) == 1
    signature = repository.signatures[0]
    canonical_payload = json.dumps(
        {
            "record_id": record.record_id,
            "stage": "SORT",
            "version": 1,
            "values": values,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    assert signature.payload_hash == hashlib.sha256(canonical_payload).hexdigest()
    assert signature.actor_id == actor.actor_id
    assert signature.factory_id == actor.factory_id
    assert signature.role_code == actor.role.value
    assert signature.signed_at == now


def test_duplicate_idempotency_key_returns_original_result() -> None:
    repository = _MemoryBambooRepository()
    identifiers = iter(["BR-003", "SUB-001", "SIG-001"])
    service = BambooProcessFacade(
        repository,
        clock=lambda: datetime(2026, 7, 22, 2, 30, tzinfo=UTC),
        id_factory=lambda: next(identifiers),
    )
    actor = _sort_actor()
    record = service.create_record(
        actor=actor,
        base_info={},
        source_type="MOBILE_CREATED",
        source_ref=None,
    )
    first = service.submit_stage(
        record.record_id,
        actor=actor,
        stage=BambooStage.SORT,
        values={},
        expected_revision=1,
        idempotency_key="same-key",
        device_id="device-a",
        request_id="request-a",
    )

    repeated = service.submit_stage(
        record.record_id,
        actor=actor,
        stage=BambooStage.SORT,
        values={},
        expected_revision=1,
        idempotency_key="same-key",
        device_id="device-a",
        request_id="request-b",
    )

    assert repeated == first
    assert len(repository.signatures) == 1


def test_submit_rejects_stale_revision_wrong_role_and_cross_factory_actor() -> None:
    repository = _MemoryBambooRepository()
    service = BambooProcessFacade(
        repository,
        clock=lambda: datetime(2026, 7, 22, 2, 30, tzinfo=UTC),
        id_factory=iter(["BR-004", "SUB-001", "SIG-001"]).__next__,
    )
    owner = _sort_actor()
    record = service.create_record(
        actor=owner,
        base_info={},
        source_type="MOBILE_CREATED",
        source_ref=None,
    )

    with pytest.raises(StaleBambooRevision):
        service.submit_stage(
            record.record_id,
            actor=owner,
            stage=BambooStage.SORT,
            values={},
            expected_revision=99,
            idempotency_key="stale",
            device_id="device-a",
            request_id="request-a",
        )

    wrong_role = replace(owner, role=BambooRole.DIPPING_OPERATOR)
    with pytest.raises(BambooPermissionDenied):
        service.submit_stage(
            record.record_id,
            actor=wrong_role,
            stage=BambooStage.SORT,
            values={},
            expected_revision=1,
            idempotency_key="wrong-role",
            device_id="device-a",
            request_id="request-b",
        )

    other_factory = replace(owner, factory_id="FACTORY-B")
    assert service.get_visible(record.record_id, actor=other_factory) is None
