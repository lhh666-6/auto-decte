"""Transactional review workflow facade."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from app.domain.models import (
    AuditEvent,
    ExportStatus,
    Form,
    RecordStatus,
    RecordVersion,
    ReviewStatus,
)
from app.domain.templates_ds import TemplateVersion
from app.infrastructure.database.uow_ds import UnitOfWork
from app.modules.audit.facade_ds import AuditFacade
from app.modules.identity_access.models_ds import Actor, Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.modules.review.lease_service_ds import ReviewLeaseService
from app.modules.review.models_ds import (
    LeaseOwnershipError,
    ReviewDraft,
    ReviewLease,
    ReviewRuleBlocked,
    ReviewRuleFailure,
    ReviewVersionConflict,
)


@dataclass(frozen=True, slots=True)
class ConfirmReviewCommand:
    form_id: str
    expected_version: int
    values: dict[str, object]
    actor_id: str
    reason: str
    evidence_ids: tuple[str, ...]
    manually_confirmed_field_keys: tuple[str, ...] = ()
    actor: Actor | None = None
    lease_token: str | None = None


@dataclass(frozen=True, slots=True)
class SaveReviewDraftCommand:
    form_id: str
    expected_version: int
    values: dict[str, object]
    actor_id: str
    lease_token: str
    actor: Actor | None = None


@dataclass(frozen=True, slots=True)
class ReviewDispositionCommand:
    form_id: str
    expected_version: int
    actor_id: str
    lease_token: str
    reason: str
    evidence_ids: tuple[str, ...]
    actor: Actor | None = None


@dataclass(frozen=True, slots=True)
class ConfirmAndClaimNextCommand:
    form_id: str
    expected_version: int
    values: dict[str, object]
    actor_id: str
    reason: str
    evidence_ids: tuple[str, ...]
    lease_token: str
    queue_key: str
    manually_confirmed_field_keys: tuple[str, ...] = ()
    actor: Actor | None = None


@dataclass(frozen=True, slots=True)
class ConfirmAndClaimNextResult:
    record: RecordVersion
    next_form_id: str | None
    next_lease: ReviewLease | None


class AuditWriter(Protocol):
    def add_audit_event(self, event: AuditEvent) -> None: ...


class TemplateVersionResolver(Protocol):
    def get_version_by_key_version(
        self, template_key: str, version: int
    ) -> TemplateVersion | None: ...


class MasterDataLookup(Protocol):
    def is_active(self, source: str, code: str) -> bool: ...


_CLAIMABLE_REVIEW_STATUSES = (
    ReviewStatus.IMPORTED,
    ReviewStatus.CLASSIFIED,
    ReviewStatus.RECOGNIZED,
    ReviewStatus.NEEDS_REVIEW,
)


class ReviewFacade:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        audits: AuditWriter | None = None,
        policy: PermissionPolicy | None = None,
        leases: ReviewLeaseService | None = None,
        template_versions: TemplateVersionResolver | None = None,
        master_data: MasterDataLookup | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        lease_ttl_seconds: int = 300,
    ) -> None:
        self._uow_factory = uow_factory
        self._audits = audits
        self._policy = policy or PermissionPolicy()
        self._leases = leases
        self._template_versions = template_versions
        self._master_data = master_data
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lease_ttl = timedelta(seconds=lease_ttl_seconds)

    def confirm(self, command: ConfirmReviewCommand) -> RecordVersion:
        command = replace(command, reason=self._require_reason(command.reason))
        self._require_actor(
            command.actor,
            command.actor_id,
            Permission.REVIEW_CONFIRM
            if command.expected_version == 0
            else Permission.REVIEW_CORRECT,
        )
        if self._leases is not None:
            if command.lease_token is None:
                raise ValueError("An active review lease token is required")
            self._leases.assert_owned(command.form_id, command.actor_id, command.lease_token)
        with self._uow_factory() as uow:
            form = self._require_form_and_version(uow, command.form_id, command.expected_version)
            normalized_values = self._prepare_template_values(
                uow,
                command.form_id,
                form.template_id,
                form.template_version,
                command.values,
                command.manually_confirmed_field_keys,
            )
            record = self._append_confirmation(
                uow, form, replace(command, values=normalized_values)
            )
            uow.review_state.delete_draft(command.form_id)
            return record

    def save_draft(self, command: SaveReviewDraftCommand) -> ReviewDraft:
        self._require_actor(command.actor, command.actor_id, Permission.FORM_EDIT_DRAFT)
        now = self._clock()
        with self._uow_factory() as uow:
            self._require_form_and_version(uow, command.form_id, command.expected_version)
            self._assert_owned(uow, command.form_id, command.actor_id, command.lease_token, now)
            before = uow.review_state.get_draft(command.form_id)
            draft = ReviewDraft(
                form_id=command.form_id,
                expected_version=command.expected_version,
                values=dict(command.values),
                saved_by=command.actor_id,
                updated_at=now,
            )
            uow.review_state.save_draft(draft)
            self._audit(
                uow,
                AuditEvent(
                    event_id=f"EVENT-{uuid4().hex}",
                    form_id=command.form_id,
                    event_type="SAVE_DRAFT",
                    actor_id=command.actor_id,
                    before=before.values if before is not None else None,
                    after=draft.values,
                    reason="人工审核草稿保存",
                ),
            )
            return draft

    def return_form(self, command: ReviewDispositionCommand) -> ReviewStatus:
        self._require_actor(command.actor, command.actor_id, Permission.REVIEW_RETURN)
        reason = self._require_reason(command.reason)
        now = self._clock()
        with self._uow_factory() as uow:
            form = self._require_form_and_version(uow, command.form_id, command.expected_version)
            self._assert_owned(uow, command.form_id, command.actor_id, command.lease_token, now)
            self._require_non_terminal(form.review_status)
            draft = uow.review_state.get_draft(command.form_id)
            uow.forms.set_review_status(command.form_id, ReviewStatus.RECAPTURE_REQUIRED)
            uow.review_state.delete_draft(command.form_id)
            uow.review_state.delete(command.form_id)
            self._audit(
                uow,
                AuditEvent(
                    event_id=f"EVENT-{uuid4().hex}",
                    form_id=command.form_id,
                    event_type="RETURN",
                    actor_id=command.actor_id,
                    before={
                        "review_status": form.review_status.value,
                        "draft_values": draft.values if draft is not None else None,
                    },
                    after={"review_status": ReviewStatus.RECAPTURE_REQUIRED.value},
                    reason=reason,
                    evidence_ids=command.evidence_ids,
                ),
            )
            return ReviewStatus.RECAPTURE_REQUIRED

    def void_form(self, command: ReviewDispositionCommand) -> RecordVersion:
        self._require_actor(command.actor, command.actor_id, Permission.REVIEW_VOID)
        reason = self._require_reason(command.reason)
        now = self._clock()
        with self._uow_factory() as uow:
            form = self._require_form_and_version(uow, command.form_id, command.expected_version)
            self._assert_owned(uow, command.form_id, command.actor_id, command.lease_token, now)
            self._require_non_terminal(form.review_status)
            versions = uow.forms.list_record_versions(command.form_id)
            draft = uow.review_state.get_draft(command.form_id)
            before = versions[-1].values if versions else None
            values = dict(
                draft.values if draft is not None else (versions[-1].values if versions else {})
            )
            record = RecordVersion(
                record_id=f"RECORD-{uuid4().hex}",
                form_id=command.form_id,
                version=command.expected_version + 1,
                previous_version=command.expected_version or None,
                status=RecordStatus.VOIDED,
                values=values,
                change_reason=reason,
                confirmed_by=command.actor_id,
            )
            uow.forms.add_record_version(record)
            uow.forms.set_review_status(command.form_id, ReviewStatus.VOIDED)
            if form.export_status is ExportStatus.EXPORTED:
                uow.forms.set_export_status(command.form_id, ExportStatus.REEXPORT_REQUIRED)
            uow.review_state.delete_draft(command.form_id)
            uow.review_state.delete(command.form_id)
            self._audit(
                uow,
                AuditEvent(
                    event_id=f"EVENT-{uuid4().hex}",
                    form_id=command.form_id,
                    event_type="VOID",
                    actor_id=command.actor_id,
                    before=before,
                    after=values,
                    reason=reason,
                    evidence_ids=command.evidence_ids,
                ),
            )
            return record

    def confirm_and_claim_next(
        self, command: ConfirmAndClaimNextCommand
    ) -> ConfirmAndClaimNextResult:
        command = replace(command, reason=self._require_reason(command.reason))
        if command.queue_key != "review":
            raise ValueError("Only the review queue supports confirm-and-claim-next")
        self._require_actor(
            command.actor,
            command.actor_id,
            Permission.REVIEW_CONFIRM
            if command.expected_version == 0
            else Permission.REVIEW_CORRECT,
        )
        now = self._clock()
        with self._uow_factory() as uow:
            form = self._require_form_and_version(uow, command.form_id, command.expected_version)
            if form.review_status not in _CLAIMABLE_REVIEW_STATUSES:
                raise ValueError("The current form does not belong to the review queue snapshot")
            self._assert_owned(uow, command.form_id, command.actor_id, command.lease_token, now)
            normalized_values = self._prepare_template_values(
                uow,
                command.form_id,
                form.template_id,
                form.template_version,
                command.values,
                command.manually_confirmed_field_keys,
            )
            record = self._append_confirmation(
                uow,
                form,
                ConfirmReviewCommand(
                    form_id=command.form_id,
                    expected_version=command.expected_version,
                    values=normalized_values,
                    actor_id=command.actor_id,
                    reason=command.reason,
                    evidence_ids=command.evidence_ids,
                    manually_confirmed_field_keys=command.manually_confirmed_field_keys,
                ),
            )
            uow.review_state.delete_draft(command.form_id)
            uow.review_state.delete(command.form_id)
            self._audit(
                uow,
                AuditEvent(
                    event_id=f"EVENT-{uuid4().hex}",
                    form_id=command.form_id,
                    event_type="LEASE_RELEASE",
                    actor_id=command.actor_id,
                    reason="确认后原子释放当前审核锁",
                ),
            )
            next_form_id = uow.review_state.next_claimable_form_id(
                review_statuses=_CLAIMABLE_REVIEW_STATUSES,
                exclude_form_id=command.form_id,
                now=now,
            )
            next_lease = None
            if next_form_id is not None:
                next_lease = ReviewLease(
                    form_id=next_form_id,
                    owner_id=command.actor_id,
                    lease_token=uuid4().hex,
                    acquired_at=now,
                    expires_at=now + self._lease_ttl,
                    heartbeat_at=now,
                )
                if not uow.review_state.try_acquire(next_lease, now):
                    raise RuntimeError("The next review form could not be claimed atomically")
                self._audit(
                    uow,
                    AuditEvent(
                        event_id=f"EVENT-{uuid4().hex}",
                        form_id=next_form_id,
                        event_type="LEASE_ACQUIRE",
                        actor_id=command.actor_id,
                        reason="确认后原子领取下一张",
                    ),
                )
            return ConfirmAndClaimNextResult(record, next_form_id, next_lease)

    def _append_confirmation(
        self, uow: UnitOfWork, form: Form, command: ConfirmReviewCommand
    ) -> RecordVersion:
        versions = uow.forms.list_record_versions(command.form_id)
        before = versions[-1].values if versions else None
        record = RecordVersion(
            record_id=f"RECORD-{uuid4().hex}",
            form_id=command.form_id,
            version=command.expected_version + 1,
            previous_version=command.expected_version or None,
            status=(
                RecordStatus.CONFIRMED if command.expected_version == 0 else RecordStatus.CORRECTED
            ),
            values=dict(command.values),
            change_reason=command.reason,
            confirmed_by=command.actor_id,
        )
        uow.forms.add_record_version(record)
        uow.forms.set_review_status(command.form_id, ReviewStatus.CONFIRMED)
        if form.export_status is ExportStatus.EXPORTED:
            uow.forms.set_export_status(command.form_id, ExportStatus.REEXPORT_REQUIRED)
        self._audit(
            uow,
            AuditEvent(
                event_id=f"EVENT-{uuid4().hex}",
                form_id=command.form_id,
                event_type="CONFIRM" if command.expected_version == 0 else "CORRECT",
                actor_id=command.actor_id,
                before=before,
                after=dict(command.values),
                reason=command.reason,
                evidence_ids=command.evidence_ids,
            ),
        )
        return record

    def _prepare_template_values(
        self,
        uow: UnitOfWork,
        form_id: str,
        template_key: str,
        template_version: str,
        values: dict[str, object],
        manually_confirmed_field_keys: tuple[str, ...],
    ) -> dict[str, object]:
        normalized = dict(values)
        if self._template_versions is None:
            return normalized
        try:
            version_number = int(template_version)
        except ValueError:
            return normalized
        template = self._template_versions.get_version_by_key_version(template_key, version_number)
        if template is None:
            return normalized
        failures: list[ReviewRuleFailure] = []
        manual_confirmations = set(manually_confirmed_field_keys)
        form_fields = uow.forms.list_form_fields(form_id)
        ids_by_name = {field.field_name: field.field_id for field in form_fields}
        for definition in template.fields:
            has_value = definition.field_key in values
            value = values.get(definition.field_key)
            value_key = definition.field_key
            field_id = ids_by_name.get(definition.field_key)
            if not has_value and field_id is not None and field_id in values:
                has_value = True
                value = values[field_id]
                value_key = field_id
            if has_value and isinstance(value, str) and value.strip():
                if definition.data_type == "integer":
                    try:
                        value = int(value.strip())
                        normalized[value_key] = value
                    except ValueError:
                        pass
                elif definition.data_type == "decimal":
                    try:
                        value = float(value.strip())
                        normalized[value_key] = value
                    except ValueError:
                        pass
            rules = definition.rules
            if rules.required and (
                not has_value or value is None or (isinstance(value, str) and not value.strip())
            ):
                failures.append(ReviewRuleFailure("REQUIRED", definition.field_key, "必填字段缺失"))
                continue
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            if (
                definition.requires_manual_confirmation
                and definition.field_key not in manual_confirmations
                and (field_id is None or field_id not in manual_confirmations)
            ):
                failures.append(
                    ReviewRuleFailure(
                        "MANUAL_CONFIRMATION_REQUIRED",
                        definition.field_key,
                        "姓名必须对照原图裁片人工确认",
                    )
                )
            if (
                rules.master_data_source
                and self._master_data is not None
                and not self._master_data.is_active(rules.master_data_source, str(value))
            ):
                failures.append(
                    ReviewRuleFailure(
                        (
                            "INVALID_WORKER_NUMBER"
                            if definition.field_key in {"worker_number", "employee_id"}
                            and rules.master_data_source == "employees"
                            else "INVALID_MASTER_DATA"
                        ),
                        definition.field_key,
                        (
                            "工号未在员工库中匹配，必须人工处理"
                            if definition.field_key in {"worker_number", "employee_id"}
                            and rules.master_data_source == "employees"
                            else "字段值不在有效主数据中"
                        ),
                    )
                )
            if rules.allowed_values and str(value) not in rules.allowed_values:
                failures.append(
                    ReviewRuleFailure(
                        "NOT_ALLOWED",
                        definition.field_key,
                        "字段值不在模板允许范围内",
                    )
                )
            if rules.minimum_value is not None or rules.maximum_value is not None:
                if isinstance(value, bool) or not isinstance(value, int | float):
                    failures.append(
                        ReviewRuleFailure("INVALID_NUMBER", definition.field_key, "字段必须是数值")
                    )
                else:
                    if rules.minimum_value is not None and value < rules.minimum_value:
                        failures.append(
                            ReviewRuleFailure(
                                "BELOW_MINIMUM",
                                definition.field_key,
                                f"字段值不能小于 {rules.minimum_value:g}",
                            )
                        )
                    if rules.maximum_value is not None and value > rules.maximum_value:
                        failures.append(
                            ReviewRuleFailure(
                                "ABOVE_MAXIMUM",
                                definition.field_key,
                                f"字段值不能大于 {rules.maximum_value:g}",
                            )
                        )
        if failures:
            raise ReviewRuleBlocked(tuple(failures))
        return normalized

    @staticmethod
    def _require_form_and_version(uow: UnitOfWork, form_id: str, expected_version: int) -> Form:
        form = uow.forms.get_form(form_id)
        if form is None:
            raise KeyError(f"Unknown form: {form_id}")
        if form.current_record_version != expected_version:
            raise ReviewVersionConflict(expected_version, form.current_record_version)
        return form

    @staticmethod
    def _assert_owned(
        uow: UnitOfWork,
        form_id: str,
        actor_id: str,
        lease_token: str,
        now: datetime,
    ) -> ReviewLease:
        lease = uow.review_state.get(form_id)
        if (
            lease is None
            or lease.expires_at <= now
            or lease.owner_id != actor_id
            or lease.lease_token != lease_token
        ):
            raise LeaseOwnershipError(
                f"Actor {actor_id} does not hold an active lease for {form_id}"
            )
        return lease

    def _require_actor(self, actor: Actor | None, actor_id: str, permission: Permission) -> None:
        if actor is None:
            return
        if actor.actor_id != actor_id:
            raise ValueError("The command actor must match actor_id")
        self._policy.require(actor, permission)

    @staticmethod
    def _require_reason(reason: str) -> str:
        cleaned = reason.strip()
        if not cleaned:
            raise ValueError("A review action reason is required")
        return cleaned

    @staticmethod
    def _require_non_terminal(status: ReviewStatus) -> None:
        if status in {
            ReviewStatus.CONFIRMED,
            ReviewStatus.CORRECTED,
            ReviewStatus.SUPERSEDED,
            ReviewStatus.VOIDED,
        }:
            raise ValueError(f"Review status {status.value} is terminal")

    def _audit(self, uow: UnitOfWork, event: AuditEvent) -> None:
        if self._audits is None:
            AuditFacade(uow.audits).append(event)
        else:
            self._audits.add_audit_event(event)
