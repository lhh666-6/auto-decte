"""Application service for the bamboo production workflow."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from app.modules.bamboo_process.errors_ds import (
    BambooPermissionDenied,
    BambooRecordNotFound,
    StaleBambooRevision,
)
from app.modules.bamboo_process.models_ds import (
    BambooActor,
    BambooRecord,
    BambooRecordStatus,
    BambooRole,
    BambooStage,
    ElectronicSignature,
    StageSubmission,
    TaskBucket,
)
from app.modules.bamboo_process.ports_ds import BambooRecordRepository
from app.modules.bamboo_process.state_machine_ds import (
    can_submit_stage,
    next_stage,
    visible_to_role,
)


class BambooProcessFacade:
    def __init__(
        self,
        repository: BambooRecordRepository,
        *,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._id_factory = id_factory

    def create_record(
        self,
        *,
        actor: BambooActor,
        base_info: dict[str, object],
        source_type: str,
        source_ref: str | None,
    ) -> BambooRecord:
        if actor.role is not BambooRole.SORT_OPERATOR:
            raise BambooPermissionDenied("only a sort operator can create a bamboo record")
        if source_ref:
            repeated = self._repository.find_created_result(actor.actor_id, source_ref)
            if repeated is not None:
                return repeated

        now = self._clock()
        production_date = now.date().isoformat()
        sequence = self._repository.next_display_sequence(
            actor.factory_id,
            production_date,
        )
        record = BambooRecord(
            record_id=self._id_factory(),
            display_no=f"ZS-{now:%Y%m%d}-{sequence:03d}",
            factory_id=actor.factory_id,
            source_type=source_type,
            source_ref=source_ref,
            base_info=dict(base_info),
            current_stage=BambooStage.SORT,
            status=BambooRecordStatus.ACTIVE,
            revision=1,
            created_by=actor.actor_id,
            created_at=now,
            updated_at=now,
        )
        self._repository.add(record)
        return record

    def list_tasks(
        self,
        *,
        actor: BambooActor,
        bucket: TaskBucket,
    ) -> list[BambooRecord]:
        records = self._repository.list_for_factory(actor.factory_id)
        if bucket is TaskBucket.AVAILABLE:
            return [
                record
                for record in records
                if record.current_stage is not None
                and can_submit_stage(actor.role, record.current_stage)
            ]
        if bucket is TaskBucket.WAITING:
            return [
                record
                for record in records
                if record.status is BambooRecordStatus.ACTIVE
                and any(
                    submission.role_code == actor.role.value
                    and not submission.invalidated
                    for submission in record.submissions
                )
                and not (
                    record.current_stage is not None
                    and can_submit_stage(actor.role, record.current_stage)
                )
            ]
        return [
            record
            for record in records
            if record.status is BambooRecordStatus.COMPLETED
            and visible_to_role(record.submissions, actor.role)
        ]

    def get_visible(
        self,
        record_id: str,
        *,
        actor: BambooActor,
    ) -> BambooRecord | None:
        record = self._repository.get(record_id)
        if record is None or record.factory_id != actor.factory_id:
            return None
        if not visible_to_role(record.submissions, actor.role):
            return None
        return record

    def submit_stage(
        self,
        record_id: str,
        *,
        actor: BambooActor,
        stage: BambooStage,
        values: dict[str, object],
        expected_revision: int,
        idempotency_key: str,
        device_id: str,
        request_id: str,
    ) -> BambooRecord:
        repeated = self._repository.find_idempotent_result(
            actor.actor_id,
            idempotency_key,
        )
        if repeated is not None:
            return repeated

        current = self._repository.get(record_id)
        if current is None:
            raise BambooRecordNotFound(record_id)
        if current.factory_id != actor.factory_id:
            raise BambooPermissionDenied("record belongs to another factory")
        if not can_submit_stage(actor.role, stage):
            raise BambooPermissionDenied("role cannot submit this stage")
        if current.current_stage is not stage:
            raise BambooPermissionDenied("stage is not open for submission")
        if current.revision != expected_revision:
            raise StaleBambooRevision(expected_revision, current.revision)

        now = self._clock()
        stage_version = (
            sum(submission.stage is stage for submission in current.submissions) + 1
        )
        submission_id = self._id_factory()
        submission = StageSubmission(
            submission_id=submission_id,
            record_id=record_id,
            stage=stage,
            version=stage_version,
            values=dict(values),
            actor_id=actor.actor_id,
            actor_name=actor.employee_name,
            role_code=actor.role.value,
            factory_id=actor.factory_id,
            submitted_at=now,
        )
        submissions = (*current.submissions, submission)
        following_stage = next_stage(submissions)
        updated = replace(
            current,
            current_stage=following_stage,
            status=(
                BambooRecordStatus.COMPLETED
                if following_stage is None
                else BambooRecordStatus.ACTIVE
            ),
            revision=current.revision + 1,
            updated_at=now,
            submissions=submissions,
        )
        payload = {
            "record_id": record_id,
            "stage": stage.value,
            "version": stage_version,
            "values": values,
        }
        canonical_payload = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        signature = ElectronicSignature(
            signature_id=self._id_factory(),
            submission_id=submission_id,
            actor_id=actor.actor_id,
            employee_code=actor.employee_code,
            actor_name=actor.employee_name,
            factory_id=actor.factory_id,
            role_code=actor.role.value,
            payload_hash=hashlib.sha256(canonical_payload).hexdigest(),
            signed_at=now,
            device_id=device_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )
        return self._repository.append_stage(
            record=updated,
            submission=submission,
            signature=signature,
            expected_revision=expected_revision,
        )
