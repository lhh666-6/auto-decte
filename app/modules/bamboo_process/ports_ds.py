"""Persistence boundary for bamboo production records."""

from typing import Protocol

from app.modules.bamboo_process.models_ds import (
    BambooFormType,
    BambooRecord,
    ElectronicSignature,
    StageSubmission,
)


class BambooRepositoryConflict(RuntimeError):
    """A persistence uniqueness conflict that callers may safely retry."""


class BambooCageOccupied(BambooRepositoryConflict):
    def __init__(self, cage_no: str, sorting_record_id: str) -> None:
        self.cage_no = cage_no
        self.sorting_record_id = sorting_record_id
        super().__init__(f"cage {cage_no!r} is already used by {sorting_record_id}")


class BambooRecordRepository(Protocol):
    def next_display_sequence(self, factory_id: str, production_date: str) -> int: ...

    def add(self, record: BambooRecord) -> BambooRecord: ...

    def add_sorting_with_cage_occupancy(
        self,
        record: BambooRecord,
        cage_no: str,
    ) -> BambooRecord: ...

    def get(self, record_id: str) -> BambooRecord | None: ...

    def list_for_factory(self, factory_id: str) -> list[BambooRecord]: ...

    def list_all(self) -> list[BambooRecord]: ...

    def find_created_result(
        self,
        actor_id: str,
        source_ref: str,
        *,
        payload_hash: str | None = None,
    ) -> BambooRecord | None: ...

    def find_idempotent_result(
        self,
        actor_id: str,
        idempotency_key: str,
        *,
        idempotency_payload_hash: str | None = None,
        legacy_comparison_hash: str | None = None,
    ) -> BambooRecord | None: ...

    def find_linked(
        self,
        form_type: BambooFormType,
        source_record_id: str,
    ) -> BambooRecord | None: ...

    def append_stage(
        self,
        *,
        record: BambooRecord,
        submission: StageSubmission,
        signature: ElectronicSignature,
        expected_revision: int,
        linked_record: BambooRecord | None = None,
    ) -> BambooRecord: ...
