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
    BambooFormType,
    BambooRecord,
    BambooRole,
    BambooStage,
    ElectronicSignature,
    StageSubmission,
    TaskBucket,
)


class _MemoryBambooRepository:
    def __init__(self) -> None:
        self.records: dict[str, BambooRecord] = {}
        self.signatures: list[ElectronicSignature] = []
        self.idempotent_results: dict[tuple[str, str], BambooRecord] = {}

    def next_display_sequence(self, factory_id: str, production_date: str) -> int:
        del factory_id, production_date
        return len(self.records) + 1

    def add(self, record: BambooRecord) -> BambooRecord:
        self.records[record.record_id] = record
        return record

    def get(self, record_id: str) -> BambooRecord | None:
        return self.records.get(record_id)

    def list_for_factory(self, factory_id: str) -> list[BambooRecord]:
        return [record for record in self.records.values() if record.factory_id == factory_id]

    def find_created_result(
        self, actor_id: str, source_ref: str
    ) -> BambooRecord | None:
        return next(
            (
                record
                for record in self.records.values()
                if record.created_by == actor_id and record.source_ref == source_ref
            ),
            None,
        )

    def find_idempotent_result(
        self, actor_id: str, idempotency_key: str
    ) -> BambooRecord | None:
        return self.idempotent_results.get((actor_id, idempotency_key))

    def find_linked(
        self,
        form_type: BambooFormType,
        source_record_id: str,
    ) -> BambooRecord | None:
        return next(
            (
                record
                for record in self.records.values()
                if record.form_type is form_type
                and record.source_record_id == source_record_id
            ),
            None,
        )

    def append_stage(
        self,
        *,
        record: BambooRecord,
        submission: StageSubmission,
        signature: ElectronicSignature,
        expected_revision: int,
        linked_record: BambooRecord | None = None,
    ) -> BambooRecord:
        del submission
        current = self.records[record.record_id]
        if current.revision != expected_revision:
            raise StaleBambooRevision(expected_revision, current.revision)
        self.records[record.record_id] = record
        if linked_record is not None and self.find_linked(
            linked_record.form_type,
            linked_record.source_record_id or "",
        ) is None:
            self.records[linked_record.record_id] = linked_record
        self.signatures.append(signature)
        self.idempotent_results[(signature.actor_id, signature.idempotency_key)] = record
        return record


def _actor(role: BambooRole) -> BambooActor:
    return BambooActor(
        actor_id=f"E-{role.value}",
        employee_code=f"E-{role.value}",
        employee_name=role.value,
        factory_id="FACTORY-A",
        factory_name="竹丝一厂",
        role=role,
    )


def _service(
    repository: _MemoryBambooRepository,
    identifiers: list[str],
) -> BambooProcessFacade:
    iterator = iter(identifiers)
    return BambooProcessFacade(
        repository,
        clock=lambda: datetime(2026, 7, 22, 2, 30, tzinfo=UTC),
        id_factory=lambda: next(iterator),
    )


def test_sort_operator_creates_factory_scoped_sorting_record() -> None:
    repository = _MemoryBambooRepository()
    service = _service(repository, ["BR-001"])

    record = service.create_record(
        actor=_actor(BambooRole.SORT_OPERATOR),
        base_info={"cage_no": "3-018", "length": "2.3", "bundle_count": 16},
        source_type="MOBILE_CREATED",
        source_ref=None,
    )

    assert record.record_id == "BR-001"
    assert record.display_no == "ZS-20260722-001"
    assert record.form_type is BambooFormType.SORTING
    assert record.production_object_id == record.record_id
    assert record.source_record_id is None
    assert record.source_snapshot == {}
    assert record.current_stage is BambooStage.SORT
    assert repository.get(record.record_id) == record


def test_sort_submission_advances_sorting_and_atomically_creates_linked_form() -> None:
    repository = _MemoryBambooRepository()
    service = _service(repository, ["BR-SORT", "SUB-SORT", "SIG-SORT", "BR-JOINT"])
    actor = _actor(BambooRole.SORT_OPERATOR)
    record = service.create_record(
        actor=actor,
        base_info={"cage_no": "3-018", "length": "2.3", "bundle_count": 16},
        source_type="MOBILE_CREATED",
        source_ref="create-sort",
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

    assert signed.current_stage is BambooStage.SUPERVISOR
    assert signed.revision == 2
    linked_records = [
        item
        for item in repository.records.values()
        if item.form_type is BambooFormType.DIPPING_DRYING
    ]
    assert len(linked_records) == 1
    linked = linked_records[0]
    assert linked.current_stage is BambooStage.DIPPING
    assert linked.production_object_id == signed.production_object_id
    assert linked.source_record_id == signed.record_id
    assert linked.source_snapshot == {
        "record_id": signed.record_id,
        "display_no": signed.display_no,
        "revision": 2,
        "base_info": signed.base_info,
    }

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
    assert signature.role_code == BambooRole.SORT_OPERATOR.value


def test_sort_idempotent_replay_does_not_duplicate_linked_form() -> None:
    repository = _MemoryBambooRepository()
    service = _service(repository, ["BR-SORT", "SUB-SORT", "SIG-SORT", "BR-JOINT"])
    actor = _actor(BambooRole.SORT_OPERATOR)
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
    assert sum(
        record.form_type is BambooFormType.DIPPING_DRYING
        for record in repository.records.values()
    ) == 1


def test_task_buckets_use_role_completion_and_independent_form_stage() -> None:
    repository = _MemoryBambooRepository()
    service = _service(repository, ["BR-SORT", "SUB-SORT", "SIG-SORT", "BR-JOINT"])
    sort_actor = _actor(BambooRole.SORT_OPERATOR)
    record = service.create_record(
        actor=sort_actor,
        base_info={},
        source_type="MOBILE_CREATED",
        source_ref=None,
    )
    service.submit_stage(
        record.record_id,
        actor=sort_actor,
        stage=BambooStage.SORT,
        values={},
        expected_revision=1,
        idempotency_key="sort-complete",
        device_id="device-a",
        request_id="request-a",
    )

    completed = service.list_tasks(actor=sort_actor, bucket=TaskBucket.COMPLETED)
    waiting = service.list_tasks(
        actor=_actor(BambooRole.DRYING_RACK_OPERATOR),
        bucket=TaskBucket.WAITING,
    )

    assert [item.form_type for item in completed] == [BambooFormType.SORTING]
    assert [item.form_type for item in waiting] == [BambooFormType.DIPPING_DRYING]
    assert waiting[0].current_stage is BambooStage.DIPPING


def test_submit_rejects_stale_revision_wrong_role_and_cross_factory_actor() -> None:
    repository = _MemoryBambooRepository()
    service = _service(repository, ["BR-004"])
    owner = _actor(BambooRole.SORT_OPERATOR)
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
