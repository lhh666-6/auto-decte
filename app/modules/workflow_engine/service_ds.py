"""Versioned workflow drafts, preflight, approval, and plant activation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BusinessRuleConfirmationRow,
    FormPlantActivationRow,
    WorkflowDefinitionRow,
    WorkflowPlantActivationRow,
    WorkflowVersionRow,
)
from app.modules.workflow_engine.preflight_ds import PreflightReport, preflight_workflow


class WorkflowError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _now() -> datetime:
    return datetime.now(UTC)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:16]}"


def _hash(graph: dict[str, Any]) -> str:
    raw = json.dumps(graph, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class WorkflowService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create(
        self,
        *,
        workflow_key: str,
        name: str,
        graph_json: dict[str, Any],
        canvas_json: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        now = _now()
        with Session(self._engine) as session, session.begin():
            if session.scalar(
                select(WorkflowDefinitionRow).where(
                    WorkflowDefinitionRow.workflow_key == workflow_key
                )
            ):
                raise WorkflowError("WORKFLOW_KEY_EXISTS", "流程标识已经存在。")
            definition = WorkflowDefinitionRow(
                definition_id=_id("workflow-def"),
                workflow_key=workflow_key,
                name=name,
                created_by=actor_id,
                created_at=now,
            )
            version = WorkflowVersionRow(
                version_id=_id("workflow-ver"),
                definition_id=definition.definition_id,
                version=1,
                graph_json=graph_json,
                canvas_json=canvas_json,
                content_hash=_hash(graph_json),
                status="DRAFT",
                revision=1,
                validation_json=None,
                created_by=actor_id,
                created_at=now,
                reviewed_by=None,
                reviewed_at=None,
            )
            session.add_all([definition, version])
            session.flush()
            return self._payload(definition, version)

    def validate(self, version_id: str) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            definition, version = self._load(session, version_id)
            report = self._preflight(session, version)
            validation = self._report_payload(report)
            version.validation_json = {
                **validation,
                "content_hash": version.content_hash,
            }
            session.flush()
            return validation

    def list_pending(self) -> list[dict[str, Any]]:
        statement = (
            select(WorkflowDefinitionRow, WorkflowVersionRow)
            .join(
                WorkflowVersionRow,
                WorkflowVersionRow.definition_id == WorkflowDefinitionRow.definition_id,
            )
            .where(WorkflowVersionRow.status == "PENDING_APPROVAL")
            .order_by(WorkflowVersionRow.created_at)
        )
        with Session(self._engine) as session:
            return [
                self._payload(definition, version)
                for definition, version in session.execute(statement)
            ]

    def list_plant(self, plant_id: str) -> list[dict[str, Any]]:
        statement = (
            select(WorkflowDefinitionRow, WorkflowVersionRow)
            .join(
                WorkflowVersionRow,
                WorkflowVersionRow.definition_id == WorkflowDefinitionRow.definition_id,
            )
            .join(
                WorkflowPlantActivationRow,
                WorkflowPlantActivationRow.workflow_version_id
                == WorkflowVersionRow.version_id,
            )
            .where(
                WorkflowPlantActivationRow.plant_id == plant_id,
                WorkflowPlantActivationRow.status == "ACTIVE",
            )
            .order_by(WorkflowDefinitionRow.name)
        )
        with Session(self._engine) as session:
            return [
                self._payload(definition, version)
                for definition, version in session.execute(statement)
            ]

    def submit(self, version_id: str) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            definition, version = self._load(session, version_id)
            validation = version.validation_json or {}
            if (
                not validation.get("valid")
                or validation.get("content_hash") != version.content_hash
            ):
                raise WorkflowError(
                    "WORKFLOW_PREFLIGHT_REQUIRED",
                    "流程必须通过当前版本预检后才能提交审核。",
                )
            if version.status != "DRAFT":
                raise WorkflowError("WORKFLOW_NOT_DRAFT", "只有草稿流程可以提交。")
            version.status = "PENDING_APPROVAL"
            session.flush()
            return self._payload(definition, version)

    def decide(
        self,
        version_id: str,
        *,
        decision: str,
        actor_id: str,
    ) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            definition, version = self._load(session, version_id)
            if version.status != "PENDING_APPROVAL":
                raise WorkflowError("WORKFLOW_NOT_PENDING", "流程不在待审核状态。")
            if decision not in {"APPROVE", "REJECT"}:
                raise WorkflowError("INVALID_APPROVAL_DECISION", "审核决定无效。")
            version.status = "APPROVED" if decision == "APPROVE" else "REJECTED"
            version.reviewed_by = actor_id
            version.reviewed_at = _now()
            session.flush()
            return self._payload(definition, version)

    def activate(
        self,
        version_id: str,
        *,
        plant_ids: list[str],
        actor_id: str,
    ) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            _, version = self._load(session, version_id)
            if version.status != "APPROVED":
                raise WorkflowError("WORKFLOW_NOT_APPROVED", "流程尚未获得管理员批准。")
            report = self._preflight(session, version)
            if not report.valid:
                raise WorkflowError("WORKFLOW_PREFLIGHT_FAILED", "流程当前预检不通过。")
            now = _now()
            for plant_id in dict.fromkeys(plant_ids):
                if not plant_id:
                    raise WorkflowError("PLANT_REQUIRED", "必须选择工厂。")
                existing = session.scalar(
                    select(WorkflowPlantActivationRow).where(
                        WorkflowPlantActivationRow.workflow_version_id == version_id,
                        WorkflowPlantActivationRow.plant_id == plant_id,
                    )
                )
                if existing:
                    existing.status = "ACTIVE"
                    existing.activated_by = actor_id
                    existing.activated_at = now
                else:
                    session.add(
                        WorkflowPlantActivationRow(
                            activation_id=_id("workflow-activation"),
                            workflow_version_id=version_id,
                            plant_id=plant_id,
                            status="ACTIVE",
                            activated_by=actor_id,
                            activated_at=now,
                        )
                    )
            return {
                "version_id": version_id,
                "status": "ACTIVE",
                "plant_ids": list(dict.fromkeys(plant_ids)),
            }

    @staticmethod
    def _load(
        session: Session,
        version_id: str,
    ) -> tuple[WorkflowDefinitionRow, WorkflowVersionRow]:
        row = session.execute(
            select(WorkflowDefinitionRow, WorkflowVersionRow)
            .join(
                WorkflowVersionRow,
                WorkflowVersionRow.definition_id == WorkflowDefinitionRow.definition_id,
            )
            .where(WorkflowVersionRow.version_id == version_id)
        ).one_or_none()
        if row is None:
            raise WorkflowError("WORKFLOW_NOT_FOUND", "流程版本不存在。")
        return row[0], row[1]

    @staticmethod
    def _preflight(session: Session, version: WorkflowVersionRow) -> PreflightReport:
        active_forms = set(
            session.scalars(
                select(FormPlantActivationRow.form_version_id).where(
                    FormPlantActivationRow.status == "ACTIVE"
                )
            )
        )
        confirmed_rules = set(
            session.scalars(
                select(BusinessRuleConfirmationRow.rule_id).where(
                    BusinessRuleConfirmationRow.status == "CONFIRMED"
                )
            )
        )
        return preflight_workflow(
            version.graph_json,
            active_form_version_ids=active_forms,
            confirmed_rule_ids=confirmed_rules,
        )

    @staticmethod
    def _report_payload(report: PreflightReport) -> dict[str, Any]:
        return {
            "valid": report.valid,
            "errors": [
                {"code": error.code, "detail": error.detail, "node_id": error.node_id}
                for error in report.errors
            ],
        }

    @staticmethod
    def _payload(
        definition: WorkflowDefinitionRow,
        version: WorkflowVersionRow,
    ) -> dict[str, Any]:
        return {
            "definition_id": definition.definition_id,
            "workflow_key": definition.workflow_key,
            "name": definition.name,
            "version_id": version.version_id,
            "version": version.version,
            "graph_json": version.graph_json,
            "canvas_json": version.canvas_json,
            "content_hash": version.content_hash,
            "status": version.status,
            "revision": version.revision,
            "validation": version.validation_json,
            "created_by": version.created_by,
            "created_at": version.created_at,
            "reviewed_by": version.reviewed_by,
            "reviewed_at": version.reviewed_at,
        }
