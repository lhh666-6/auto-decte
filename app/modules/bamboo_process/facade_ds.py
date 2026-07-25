"""Application service for the bamboo production workflow."""

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime

from app.modules.bamboo_process.errors_ds import (
    BambooPermissionDenied,
    BambooRecordNotFound,
    StaleBambooRevision,
)
from app.modules.bamboo_process.models_ds import (
    BambooActor,
    BambooFormType,
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
    FORM_STAGE_ORDER,
    STAGE_ROLE,
    can_submit_stage,
    next_stage,
    visible_to_role,
)


@dataclass(frozen=True)
class InspectionContext:
    """Pre-fetched inspection data for the INSPECTOR task model.

    Passed from the DB layer because the facade is persistence-agnostic.
    """

    open_window_record_ids: frozenset[str]
    """Records whose inspection windows are OPEN and inside the deadline."""

    completed_record_ids: frozenset[str]
    """Records this actor has already inspected (formal)."""


def _sha256_canonical(payload: object) -> str:
    """SHA-256 of a canonical JSON payload (sorted keys, no whitespace)."""
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


class BambooProcessFacade:
    def __init__(
        self,
        repository: BambooRecordRepository,
        *,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
        form_resolver: Callable[[str, str], tuple[str, str] | None] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._id_factory = id_factory
        # V1 Final Verification §4: resolves (form_version_id, form_definition_id)
        # for the active approved form version in a given factory.
        self._form_resolver = form_resolver

    def create_record(
        self,
        *,
        actor: BambooActor,
        base_info: dict[str, object],
        source_type: str,
        source_ref: str | None,
        form_type: BambooFormType = BambooFormType.SORTING,
        create_payload_hash: str | None = None,
    ) -> BambooRecord:
        if actor.role is not BambooRole.SORT_OPERATOR:
            raise BambooPermissionDenied("only a sort operator can create a bamboo record")
        if form_type is not BambooFormType.SORTING:
            raise BambooPermissionDenied("linked production forms are created by the system")
        if source_ref:
            repeated = self._repository.find_created_result(
                actor.actor_id, source_ref, payload_hash=create_payload_hash
            )
            if repeated is not None:
                return repeated

        now = self._clock()
        production_date = now.date().isoformat()
        sequence = self._repository.next_display_sequence(
            actor.factory_id,
            production_date,
        )
        record_id = self._id_factory()
        # V1 Final Verification §4: Resolve active form version binding
        form_version_id: str | None = None
        form_definition_id: str | None = None
        if self._form_resolver is not None:
            resolved = self._form_resolver(actor.factory_id, form_type.value)
            if resolved is not None:
                form_version_id, form_definition_id = resolved
        record = BambooRecord(
            record_id=record_id,
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
            form_type=form_type,
            production_object_id=record_id,
            create_payload_hash=create_payload_hash,
            form_version_id=form_version_id,
            form_definition_id=form_definition_id,
        )
        cage_no = str(base_info.get("cage_no") or "").strip()
        if cage_no:
            return self._repository.add_sorting_with_cage_occupancy(record, cage_no)
        return self._repository.add(record)

    def list_tasks(
        self,
        *,
        actor: BambooActor,
        bucket: TaskBucket,
        cage_no: str | None = None,
        inspection_context: InspectionContext | None = None,
    ) -> list[BambooRecord]:
        records = (
            self._repository.list_all()
            if actor.role in {BambooRole.FINANCE_APPROVER, BambooRole.SYSTEM_ADMIN}
            else self._repository.list_for_factory(actor.factory_id)
        )
        completed = {
            record.record_id
            for record in records
            if any(
                submission.role_code == actor.role.value and not submission.invalidated
                for submission in record.submissions
            )
        }
        if bucket is TaskBucket.AVAILABLE:
            if actor.role is BambooRole.INSPECTOR and inspection_context is not None:
                available = [
                    record
                    for record in records
                    if record.status is BambooRecordStatus.ACTIVE
                    and record.record_id in inspection_context.open_window_record_ids
                ]
            elif actor.role is BambooRole.INSPECTOR:
                # Fallback when context not provided: use production stage
                # (kept for read-only dashboard queries that bypass this path).
                available = [
                    record
                    for record in records
                    if record.status is BambooRecordStatus.ACTIVE
                    and record.current_stage is BambooStage.SUPERVISOR
                    and visible_to_role(record.submissions, actor.role, record.form_type)
                ]
            else:
                available = [
                    record
                    for record in records
                    if record.record_id not in completed
                    and record.status is BambooRecordStatus.ACTIVE
                    and record.current_stage is not None
                    and can_submit_stage(actor.role, record.current_stage, record.form_type)
                ]
            return _filter_by_cage(available, cage_no)
        if bucket is TaskBucket.COMPLETED:
            if actor.role is BambooRole.INSPECTOR and inspection_context is not None:
                return _filter_by_cage(
                    [
                        record
                        for record in records
                        if record.record_id in inspection_context.completed_record_ids
                    ],
                    cage_no,
                )
            return _filter_by_cage(
                [record for record in records if record.record_id in completed],
                cage_no,
            )
        if bucket is TaskBucket.WAITING:
            if actor.role is BambooRole.INSPECTOR:
                # INSPECTOR waiting = active records where production is
                # finished (SUPERVISOR / PLANT_AUDIT) but no inspection
                # window exists and no inspection has been submitted.
                waiting: list[BambooRecord] = []
                if inspection_context is not None:
                    for record in records:
                        if (
                            record.status is not BambooRecordStatus.ACTIVE
                            or record.record_id in inspection_context.open_window_record_ids
                            or record.record_id in inspection_context.completed_record_ids
                        ):
                            continue
                        # Production is done when the supervisor stage has
                        # been signed (but before plant audit).
                        has_supervisor = any(
                            submission.stage is BambooStage.SUPERVISOR
                            and not submission.invalidated
                            for submission in record.submissions
                        )
                        if has_supervisor:
                            waiting.append(record)
                    return _filter_by_cage(waiting, cage_no)
                # Fallback without context
                for record in records:
                    if (
                        record.status is not BambooRecordStatus.ACTIVE
                        or record.record_id in completed
                        or record.current_stage is None
                    ):
                        continue
                    if visible_to_role(record.submissions, actor.role, record.form_type):
                        waiting.append(record)
                return _filter_by_cage(waiting, cage_no)
            _waiting: list[BambooRecord] = []
            for record in records:
                if (
                    record.status is not BambooRecordStatus.ACTIVE
                    or record.record_id in completed
                    or record.current_stage is None
                ):
                    continue
                stage_order = FORM_STAGE_ORDER[record.form_type]
                if record.current_stage not in stage_order:
                    continue
                role_stage = next(
                    (stage for stage in stage_order if STAGE_ROLE[stage] is actor.role),
                    None,
                )
                if role_stage is None:
                    continue
                if stage_order.index(record.current_stage) < stage_order.index(role_stage):
                    _waiting.append(record)
            return _filter_by_cage(_waiting, cage_no)
        return []

    def get_visible(
        self,
        record_id: str,
        *,
        actor: BambooActor,
    ) -> BambooRecord | None:
        record = self._repository.get(record_id)
        if record is None:
            return None
        if actor.role in {BambooRole.FINANCE_APPROVER, BambooRole.SYSTEM_ADMIN}:
            return record
        if record.factory_id != actor.factory_id:
            return None
        if actor.role in {
            BambooRole.INSPECTOR,
            BambooRole.SUPERVISOR,
            BambooRole.PLANT_MANAGER,
        }:
            return record
        if not visible_to_role(record.submissions, actor.role, record.form_type):
            return None
        return record

    def get_upstream(
        self,
        record: BambooRecord,
        *,
        actor: BambooActor,
    ) -> BambooRecord | None:
        if not record.source_record_id:
            return None
        visible_record = self.get_visible(record.record_id, actor=actor)
        if visible_record is None:
            return None
        source = self._repository.get(record.source_record_id)
        if source is None or source.factory_id != record.factory_id:
            return None
        return source

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
        # ── 1. Read current record once for stage_version (hash input) ──
        pre = self._repository.get(record_id)
        if pre is None:
            raise BambooRecordNotFound(record_id)
        stage_version = (
            sum(submission.stage is stage for submission in pre.submissions) + 1
        )

        # ── 2. Compute the *new* idempotency hash (version ≥ 1) ──
        idempotency_payload_obj = {
            "actor_id": actor.actor_id,
            "record_id": record_id,
            "stage": stage.value,
            "expected_revision": expected_revision,
            "device_id": device_id,
            "values": values,
        }
        idempotency_payload_hash = _sha256_canonical(idempotency_payload_obj)

        # ── 3. Compute legacy comparison hash (for v0 signatures) ──
        # Uses the *stored* version from the last same-stage submission
        # so that the hash is stable across replays.
        existing = [
            s for s in pre.submissions if s.stage is stage and not s.invalidated
        ]
        stored_version = existing[-1].version if existing else 0
        legacy_obj = {
            "record_id": record_id,
            "stage": stage.value,
            "version": stored_version,
            "values": values,
        }
        legacy_comparison_hash = (
            _sha256_canonical(legacy_obj) if stored_version > 0 else None
        )

        # ── 4. Idempotency gate (before any state mutation) ──
        repeated = self._repository.find_idempotent_result(
            actor.actor_id,
            idempotency_key,
            idempotency_payload_hash=idempotency_payload_hash,
            legacy_comparison_hash=legacy_comparison_hash,
        )
        if repeated is not None:
            if repeated.form_type is BambooFormType.SORTING and any(
                submission.stage is BambooStage.SORT and not submission.invalidated
                for submission in repeated.submissions
            ):
                self._ensure_linked_record(repeated, actor=actor)
            return repeated

        # ── 5. State / permission gates ──
        current = self._repository.get(record_id)
        if current is None:
            raise BambooRecordNotFound(record_id)
        if current.factory_id != actor.factory_id:
            raise BambooPermissionDenied("record belongs to another factory")
        if not can_submit_stage(actor.role, stage, current.form_type):
            raise BambooPermissionDenied("role cannot submit this stage")
        if current.current_stage is not stage:
            raise BambooPermissionDenied("stage is not open for submission")
        if current.revision != expected_revision:
            raise StaleBambooRevision(expected_revision, current.revision)

        # ── 6. Build submission, advance state, sign ──
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
        following_stage = next_stage(submissions, current.form_type)
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
        # payload_hash retains the legacy audit format
        audit_payload_obj = {
            "record_id": record_id,
            "stage": stage.value,
            "version": stage_version,
            "values": values,
        }
        audit_payload_hash = _sha256_canonical(audit_payload_obj)
        signature = ElectronicSignature(
            signature_id=self._id_factory(),
            submission_id=submission_id,
            actor_id=actor.actor_id,
            employee_code=actor.employee_code,
            actor_name=actor.employee_name,
            factory_id=actor.factory_id,
            role_code=actor.role.value,
            payload_hash=audit_payload_hash,
            signed_at=now,
            device_id=device_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            idempotency_payload_hash=idempotency_payload_hash,
            idempotency_hash_version=1,
        )
        linked_record = (
            self._build_linked_record(updated, actor=actor)
            if stage is BambooStage.SORT
            and updated.form_type is BambooFormType.SORTING
            else None
        )
        stored = self._repository.append_stage(
            record=updated,
            submission=submission,
            signature=signature,
            expected_revision=expected_revision,
            linked_record=linked_record,
        )
        return stored

    def _ensure_linked_record(
        self,
        source: BambooRecord,
        *,
        actor: BambooActor,
    ) -> BambooRecord:
        existing = self._repository.find_linked(
            BambooFormType.DIPPING_DRYING,
            source.record_id,
        )
        if existing is not None:
            return existing
        linked = self._build_linked_record(source, actor=actor)
        if linked is None:
            existing = self._repository.find_linked(
                BambooFormType.DIPPING_DRYING,
                source.record_id,
            )
            if existing is None:  # pragma: no cover - concurrent insert disappeared
                raise RuntimeError("linked bamboo record disappeared")
            return existing
        return self._repository.add(linked)

    def _build_linked_record(
        self,
        source: BambooRecord,
        *,
        actor: BambooActor,
    ) -> BambooRecord | None:
        if self._repository.find_linked(
            BambooFormType.DIPPING_DRYING,
            source.record_id,
        ) is not None:
            return None
        now = self._clock()
        sequence = self._repository.next_display_sequence(
            source.factory_id,
            now.date().isoformat(),
        )
        # V1 Final Verification §4: Resolve active form version for linked record
        form_version_id: str | None = None
        form_definition_id: str | None = None
        if self._form_resolver is not None:
            resolved = self._form_resolver(
                source.factory_id, BambooFormType.DIPPING_DRYING.value
            )
            if resolved is not None:
                form_version_id, form_definition_id = resolved
        return BambooRecord(
            record_id=self._id_factory(),
            display_no=f"ZS-{now:%Y%m%d}-{sequence:03d}",
            factory_id=source.factory_id,
            source_type="SYSTEM_LINKED",
            source_ref=source.record_id,
            base_info=deepcopy(source.base_info),
            current_stage=BambooStage.DIPPING,
            status=BambooRecordStatus.ACTIVE,
            revision=1,
            created_by=actor.actor_id,
            created_at=now,
            updated_at=now,
            form_type=BambooFormType.DIPPING_DRYING,
            production_object_id=source.production_object_id or source.record_id,
            source_record_id=source.record_id,
            source_snapshot={
                "record_id": source.record_id,
                "display_no": source.display_no,
                "revision": source.revision,
                "base_info": deepcopy(source.base_info),
            },
            form_version_id=form_version_id,
            form_definition_id=form_definition_id,
        )


def _filter_by_cage(records: list[BambooRecord], cage_no: str | None) -> list[BambooRecord]:
    query = (cage_no or "").strip().casefold()
    if not query:
        return records
    return [
        record
        for record in records
        if query in str(record.base_info.get("cage_no", "")).strip().casefold()
    ]
