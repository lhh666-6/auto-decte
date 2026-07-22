"""Persistence boundary for bamboo production records."""

from typing import Protocol

from app.modules.bamboo_process.models_ds import (
    BambooRecord,
    ElectronicSignature,
    StageSubmission,
)


class BambooRecordRepository(Protocol):
    def next_display_sequence(self, factory_id: str, production_date: str) -> int: ...

    def add(self, record: BambooRecord) -> None: ...

    def get(self, record_id: str) -> BambooRecord | None: ...

    def find_idempotent_result(
        self,
        actor_id: str,
        idempotency_key: str,
    ) -> BambooRecord | None: ...

    def append_stage(
        self,
        *,
        record: BambooRecord,
        submission: StageSubmission,
        signature: ElectronicSignature,
        expected_revision: int,
    ) -> BambooRecord: ...
