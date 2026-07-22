"""Persistence boundary for bamboo production records."""

from typing import Protocol

from app.modules.bamboo_process.models_ds import (
    BambooFormType,
    BambooRecord,
    ElectronicSignature,
    StageSubmission,
)


class BambooRecordRepository(Protocol):
    def next_display_sequence(self, factory_id: str, production_date: str) -> int: ...

    def add(self, record: BambooRecord) -> None: ...

    def get(self, record_id: str) -> BambooRecord | None: ...

    def list_for_factory(self, factory_id: str) -> list[BambooRecord]: ...

    def find_created_result(
        self,
        actor_id: str,
        source_ref: str,
    ) -> BambooRecord | None: ...

    def find_idempotent_result(
        self,
        actor_id: str,
        idempotency_key: str,
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
