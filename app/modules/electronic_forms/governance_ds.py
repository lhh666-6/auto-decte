"""Versioned Web governance for electronic forms."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, Select, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    FormPlantActivationRow,
    ManagedFormDefinitionRow,
    ManagedFormVersionRow,
    ManagementNotificationRow,
    MobileAccessProfileRow,
    MobileNotificationRow,
)


class ManagedFormStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class ActivationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    RETIRED = "RETIRED"


class ManagedFormError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _now() -> datetime:
    return datetime.now(UTC)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:16]}"


def _content_hash(schema_json: dict[str, Any]) -> str:
    canonical = json.dumps(
        schema_json,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ManagedFormService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_definition(
        self,
        *,
        form_key: str,
        name: str,
        owner_role: str,
        schema_json: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        now = _now()
        with Session(self._engine) as session, session.begin():
            if session.scalar(
                select(ManagedFormDefinitionRow).where(
                    ManagedFormDefinitionRow.form_key == form_key
                )
            ):
                raise ManagedFormError("FORM_KEY_EXISTS", "表单标识已经存在。")
            definition = ManagedFormDefinitionRow(
                definition_id=_id("form-def"),
                form_key=form_key,
                name=name,
                owner_role=owner_role,
                created_by=actor_id,
                created_at=now,
                retired_at=None,
            )
            version = ManagedFormVersionRow(
                version_id=_id("form-ver"),
                definition_id=definition.definition_id,
                version=1,
                schema_json=schema_json,
                content_hash=_content_hash(schema_json),
                status=ManagedFormStatus.DRAFT.value,
                revision=1,
                created_by=actor_id,
                created_at=now,
                submitted_at=None,
                reviewed_by=None,
                reviewed_at=None,
                review_comment="",
            )
            session.add_all([definition, version])
            session.flush()
            return self._version_payload(definition, version)

    def list_definitions(self) -> list[dict[str, Any]]:
        statement = (
            select(ManagedFormDefinitionRow, ManagedFormVersionRow)
            .join(
                ManagedFormVersionRow,
                ManagedFormVersionRow.definition_id
                == ManagedFormDefinitionRow.definition_id,
            )
            .order_by(
                ManagedFormDefinitionRow.form_key,
                ManagedFormVersionRow.version.desc(),
            )
        )
        with Session(self._engine) as session:
            rows = session.execute(statement).all()
            return [self._version_payload(definition, version) for definition, version in rows]

    def get_version(self, version_id: str) -> dict[str, Any]:
        with Session(self._engine) as session:
            definition, version = self._load(session, version_id)
            return self._version_payload(definition, version)

    def update_draft(
        self,
        version_id: str,
        *,
        expected_revision: int,
        schema_json: dict[str, Any],
    ) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            definition, version = self._load(session, version_id)
            if version.status != ManagedFormStatus.DRAFT.value:
                raise ManagedFormError(
                    "FORM_VERSION_IMMUTABLE",
                    "只有草稿版本可以修改；已提交或已启用版本不可变。",
                )
            if version.revision != expected_revision:
                raise ManagedFormError(
                    "FORM_VERSION_REVISION_CONFLICT",
                    "表单草稿已被更新，请刷新后继续。",
                )
            version.schema_json = schema_json
            version.content_hash = _content_hash(schema_json)
            version.revision += 1
            session.flush()
            return self._version_payload(definition, version)

    def submit_approval(self, version_id: str) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            definition, version = self._load(session, version_id)
            if version.status != ManagedFormStatus.DRAFT.value:
                raise ManagedFormError("FORM_VERSION_NOT_DRAFT", "只有草稿可以提交审核。")
            version.status = ManagedFormStatus.PENDING_APPROVAL.value
            version.submitted_at = _now()
            session.flush()
            return self._version_payload(definition, version)

    def clone(self, version_id: str, actor_id: str) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            definition, source = self._load(session, version_id)
            latest = session.scalar(
                select(ManagedFormVersionRow.version)
                .where(ManagedFormVersionRow.definition_id == definition.definition_id)
                .order_by(ManagedFormVersionRow.version.desc())
                .limit(1)
            )
            clone = ManagedFormVersionRow(
                version_id=_id("form-ver"),
                definition_id=definition.definition_id,
                version=int(latest or 0) + 1,
                schema_json=source.schema_json,
                content_hash=source.content_hash,
                status=ManagedFormStatus.DRAFT.value,
                revision=1,
                created_by=actor_id,
                created_at=_now(),
                submitted_at=None,
                reviewed_by=None,
                reviewed_at=None,
                review_comment="",
            )
            session.add(clone)
            session.flush()
            return self._version_payload(definition, clone)

    def list_approvals(self) -> list[dict[str, Any]]:
        statement = self._version_statement().where(
            ManagedFormVersionRow.status == ManagedFormStatus.PENDING_APPROVAL.value
        ).order_by(ManagedFormVersionRow.submitted_at)
        with Session(self._engine) as session:
            return [
                self._version_payload(definition, version)
                for definition, version in session.execute(statement)
            ]

    def decide(
        self,
        version_id: str,
        *,
        decision: str,
        comment: str,
        actor_id: str,
    ) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            definition, version = self._load(session, version_id)
            if version.status != ManagedFormStatus.PENDING_APPROVAL.value:
                raise ManagedFormError(
                    "FORM_VERSION_NOT_PENDING",
                    "该版本当前不在待审核状态。",
                )
            normalized = decision.upper()
            if normalized not in {"APPROVE", "REJECT"}:
                raise ManagedFormError("INVALID_APPROVAL_DECISION", "审核决定无效。")
            version.status = (
                ManagedFormStatus.APPROVED.value
                if normalized == "APPROVE"
                else ManagedFormStatus.REJECTED.value
            )
            version.reviewed_by = actor_id
            version.reviewed_at = _now()
            version.review_comment = comment
            session.flush()
            return self._version_payload(definition, version)

    def set_activation(
        self,
        version_id: str,
        *,
        plant_ids: list[str],
        action: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if not plant_ids or any(not plant_id.strip() for plant_id in plant_ids):
            raise ManagedFormError("PLANT_REQUIRED", "必须选择至少一个工厂。")
        target = {
            "activate": ActivationStatus.ACTIVE,
            "disable": ActivationStatus.DISABLED,
            "restore": ActivationStatus.ACTIVE,
            "retire": ActivationStatus.RETIRED,
        }.get(action)
        if target is None:
            raise ManagedFormError("INVALID_ACTIVATION_ACTION", "启用操作无效。")

        with Session(self._engine) as session, session.begin():
            definition, version = self._load(session, version_id)
            if version.status != ManagedFormStatus.APPROVED.value:
                raise ManagedFormError(
                    "FORM_VERSION_NOT_APPROVED",
                    "只有管理员已批准的版本可以调整工厂启用状态。",
                )
            now = _now()
            for plant_id in dict.fromkeys(plant_ids):
                activation = session.scalar(
                    select(FormPlantActivationRow).where(
                        FormPlantActivationRow.form_version_id == version_id,
                        FormPlantActivationRow.plant_id == plant_id,
                    )
                )
                if action in {"disable", "restore", "retire"} and activation is None:
                    raise ManagedFormError(
                        "FORM_ACTIVATION_NOT_FOUND",
                        f"工厂 {plant_id} 没有该版本的启用记录。",
                    )
                if action in {"activate", "restore"}:
                    self._disable_other_versions(
                        session,
                        definition.definition_id,
                        plant_id,
                        version_id,
                        actor_id,
                        now,
                    )
                if activation is None:
                    activation = FormPlantActivationRow(
                        activation_id=_id("activation"),
                        form_version_id=version_id,
                        plant_id=plant_id,
                        status=target.value,
                        activated_by=actor_id,
                        activated_at=now,
                        updated_by=actor_id,
                        updated_at=now,
                    )
                    session.add(activation)
                else:
                    activation.status = target.value
                    activation.updated_by = actor_id
                    activation.updated_at = now
                self._notify(
                    session,
                    plant_id=plant_id,
                    action=action,
                    form_name=definition.name,
                    version_id=version_id,
                    now=now,
                )
            session.flush()
            return {
                "version_id": version_id,
                "status": target.value,
                "plant_ids": list(dict.fromkeys(plant_ids)),
            }

    def list_plant_forms(self, plant_id: str) -> list[dict[str, Any]]:
        statement = (
            self._version_statement()
            .join(
                FormPlantActivationRow,
                FormPlantActivationRow.form_version_id == ManagedFormVersionRow.version_id,
            )
            .where(
                FormPlantActivationRow.plant_id == plant_id,
                FormPlantActivationRow.status == ActivationStatus.ACTIVE.value,
            )
            .order_by(ManagedFormDefinitionRow.name)
        )
        with Session(self._engine) as session:
            return [
                {
                    **self._version_payload(definition, version),
                    "activation_status": ActivationStatus.ACTIVE.value,
                    "plant_id": plant_id,
                }
                for definition, version in session.execute(statement)
            ]

    def resolve_active_form(
        self,
        plant_id: str,
        form_key: str,
        roles: list[str],
    ) -> dict[str, Any] | None:
        statement = (
            self._version_statement()
            .join(
                FormPlantActivationRow,
                FormPlantActivationRow.form_version_id == ManagedFormVersionRow.version_id,
            )
            .where(
                FormPlantActivationRow.plant_id == plant_id,
                FormPlantActivationRow.status == ActivationStatus.ACTIVE.value,
                ManagedFormDefinitionRow.form_key == form_key,
                ManagedFormDefinitionRow.owner_role.in_(roles),
            )
        )
        with Session(self._engine) as session:
            row = session.execute(statement).one_or_none()
            if row is None:
                return None
            definition, version = row
            return {
                **self._version_payload(definition, version),
                "activation_status": ActivationStatus.ACTIVE.value,
                "plant_id": plant_id,
            }

    def list_notifications(self, plant_id: str) -> list[dict[str, Any]]:
        statement = (
            select(ManagementNotificationRow)
            .where(ManagementNotificationRow.plant_id == plant_id)
            .order_by(ManagementNotificationRow.created_at.desc())
        )
        with Session(self._engine) as session:
            return [self._notification_payload(row) for row in session.scalars(statement)]

    def acknowledge_notification(
        self,
        notification_id: str,
        *,
        plant_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            row = session.get(ManagementNotificationRow, notification_id)
            if row is None or row.plant_id != plant_id:
                raise ManagedFormError("NOTIFICATION_NOT_FOUND", "通知不存在。")
            if row.acknowledged_at is None:
                row.acknowledged_by = actor_id
                row.acknowledged_at = _now()
            session.flush()
            return self._notification_payload(row)

    @staticmethod
    def _version_statement() -> Select[tuple[ManagedFormDefinitionRow, ManagedFormVersionRow]]:
        return select(ManagedFormDefinitionRow, ManagedFormVersionRow).join(
            ManagedFormVersionRow,
            ManagedFormVersionRow.definition_id == ManagedFormDefinitionRow.definition_id,
        )

    def _load(
        self,
        session: Session,
        version_id: str,
    ) -> tuple[ManagedFormDefinitionRow, ManagedFormVersionRow]:
        row = session.execute(
            self._version_statement().where(ManagedFormVersionRow.version_id == version_id)
        ).one_or_none()
        if row is None:
            raise ManagedFormError("FORM_VERSION_NOT_FOUND", "表单版本不存在。")
        return row[0], row[1]

    @staticmethod
    def _version_payload(
        definition: ManagedFormDefinitionRow,
        version: ManagedFormVersionRow,
    ) -> dict[str, Any]:
        return {
            "definition_id": definition.definition_id,
            "form_key": definition.form_key,
            "name": definition.name,
            "owner_role": definition.owner_role,
            "version_id": version.version_id,
            "version": version.version,
            "schema_json": version.schema_json,
            "content_hash": version.content_hash,
            "status": version.status,
            "revision": version.revision,
            "created_by": version.created_by,
            "created_at": version.created_at,
            "submitted_at": version.submitted_at,
            "reviewed_by": version.reviewed_by,
            "reviewed_at": version.reviewed_at,
            "review_comment": version.review_comment,
        }

    @staticmethod
    def _disable_other_versions(
        session: Session,
        definition_id: str,
        plant_id: str,
        version_id: str,
        actor_id: str,
        now: datetime,
    ) -> None:
        statement = (
            select(FormPlantActivationRow)
            .join(
                ManagedFormVersionRow,
                ManagedFormVersionRow.version_id
                == FormPlantActivationRow.form_version_id,
            )
            .where(
                ManagedFormVersionRow.definition_id == definition_id,
                FormPlantActivationRow.plant_id == plant_id,
                FormPlantActivationRow.form_version_id != version_id,
                FormPlantActivationRow.status == ActivationStatus.ACTIVE.value,
            )
        )
        for row in session.scalars(statement):
            row.status = ActivationStatus.DISABLED.value
            row.updated_by = actor_id
            row.updated_at = now

    @staticmethod
    def _notify(
        session: Session,
        *,
        plant_id: str,
        action: str,
        form_name: str,
        version_id: str,
        now: datetime,
    ) -> None:
        labels = {
            "activate": "已启用",
            "disable": "已停用",
            "restore": "已恢复",
            "retire": "已退役",
        }
        label = labels[action]
        session.add(
            ManagementNotificationRow(
                notification_id=_id("notice"),
                notification_type=f"FORM_{action.upper()}",
                plant_id=plant_id,
                title=f"表单{label}",
                body=f"{form_name}{label}，请知悉。",
                resource_type="FORM_VERSION",
                resource_id=version_id,
                created_at=now,
                acknowledged_by=None,
                acknowledged_at=None,
            )
        )
        recipients = session.scalars(
            select(MobileAccessProfileRow).where(
                MobileAccessProfileRow.factory_id == plant_id,
                MobileAccessProfileRow.active.is_(True),
            )
        ).all()
        for profile in recipients:
            if "PLANT_MANAGER" not in profile.roles:
                continue
            session.add(
                MobileNotificationRow(
                    notification_id=_id("notice"),
                    recipient_actor_id=profile.employee_code,
                    category=f"FORM_{action.upper()}",
                    title=f"表单{label}",
                    body=f"{form_name}{label}，请知悉。",
                    link="/plant/forms",
                    payload={
                        "resource_type": "FORM_VERSION",
                        "resource_id": version_id,
                        "plant_id": plant_id,
                    },
                    read_at=None,
                    created_at=now,
                )
            )

    @staticmethod
    def _notification_payload(row: ManagementNotificationRow) -> dict[str, Any]:
        return {
            "notification_id": row.notification_id,
            "type": row.notification_type,
            "plant_id": row.plant_id,
            "title": row.title,
            "body": row.body,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "created_at": row.created_at,
            "acknowledged_by": row.acknowledged_by,
            "acknowledged_at": row.acknowledged_at,
        }
