"""Operational services layered on the signed bamboo workflow."""

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BambooCorrectionCaseRow,
    BambooDailyExportBatchRow,
    BambooDailyExportItemRow,
    BambooEvidenceAssetRow,
    BambooFactoryRow,
    BambooFinanceInquiryMessageRow,
    BambooFinanceInquiryRow,
    BambooInspectionExceptionRow,
    BambooInspectionRow,
    BambooPayrollFactRow,
    BambooPayrollRuleVersionRow,
    BambooRecordRow,
    BambooReturnRow,
    BambooRoleChangeRequestRow,
    BambooRoleDefinitionRow,
    BambooStageSubmissionRow,
    EmployeeBambooAssignmentRow,
    MasterDataRecordRow,
    MobileAccessProfileRow,
)
from app.adapters.storage.local import LocalEvidenceStorage
from app.modules.bamboo_process.models_ds import BambooActor, BambooRole, BambooStage

PRODUCTION_ROLES = {
    BambooRole.SORT_OPERATOR.value,
    BambooRole.DIPPING_OPERATOR.value,
    BambooRole.DRYING_RACK_OPERATOR.value,
}
REWORK_DEPENDENCIES = {
    BambooStage.SORT: tuple(BambooStage),
    BambooStage.DIPPING: (
        BambooStage.DIPPING,
        BambooStage.DRYING,
        BambooStage.SUPERVISOR,
        BambooStage.PLANT_AUDIT,
    ),
    BambooStage.DRYING: (
        BambooStage.DRYING,
        BambooStage.SUPERVISOR,
        BambooStage.PLANT_AUDIT,
    ),
}


class BambooOperationError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


class BambooOperationsService:
    def __init__(self, engine: Engine, storage: LocalEvidenceStorage) -> None:
        self._engine = engine
        self._storage = storage

    def record_summary(self, record_id: str, actor: BambooActor) -> dict[str, Any]:
        with Session(self._engine) as session:
            record = self._record(session, record_id, actor)
            facts = session.scalars(
                select(BambooPayrollFactRow)
                .where(BambooPayrollFactRow.record_id == record.record_id)
                .order_by(BambooPayrollFactRow.fact_type, BambooPayrollFactRow.version)
            ).all()
            inspections = session.scalars(
                select(BambooInspectionRow)
                .where(BambooInspectionRow.record_id == record.record_id)
                .order_by(BambooInspectionRow.signed_at)
            ).all()
            corrections = session.scalars(
                select(BambooCorrectionCaseRow)
                .where(BambooCorrectionCaseRow.record_id == record.record_id)
                .order_by(BambooCorrectionCaseRow.created_at.desc())
            ).all()
            return {
                "payroll_facts": [self._fact(row) for row in facts],
                "inspections": [self._inspection(session, row) for row in inspections],
                "corrections": [
                    {
                        "case_id": row.case_id,
                        "status": row.status,
                        "reason": row.reason,
                        "created_at": row.created_at,
                    }
                    for row in corrections
                ],
            }

    def list_payroll_rules(self, actor: BambooActor) -> list[dict[str, Any]]:
        if actor.role not in {BambooRole.PLANT_MANAGER, BambooRole.SYSTEM_ADMIN}:
            raise BambooOperationError("PAYROLL_RULE_FORBIDDEN", "仅厂长或管理员可查看工资规则")
        with Session(self._engine) as session:
            rows = session.scalars(
                select(BambooPayrollRuleVersionRow)
                .where(
                    (BambooPayrollRuleVersionRow.factory_id == actor.factory_id)
                    | (BambooPayrollRuleVersionRow.factory_id.is_(None))
                )
                .order_by(
                    BambooPayrollRuleVersionRow.rule_key,
                    BambooPayrollRuleVersionRow.factory_id,
                    BambooPayrollRuleVersionRow.version.desc(),
                )
            ).all()
            return [self._rule(row) for row in rows]

    def create_payroll_rule(
        self,
        *,
        actor: BambooActor,
        rule_key: str,
        configuration: dict[str, Any],
        system_default: bool,
    ) -> dict[str, Any]:
        if actor.role not in {BambooRole.PLANT_MANAGER, BambooRole.SYSTEM_ADMIN}:
            raise BambooOperationError("PAYROLL_RULE_FORBIDDEN", "仅厂长或管理员可配置工资规则")
        if system_default and actor.role is not BambooRole.SYSTEM_ADMIN:
            raise BambooOperationError("ADMIN_REQUIRED", "只有管理员可以修改系统默认规则")
        if rule_key not in {"SORT", "DIPPING_DRYING_JOINT"}:
            raise BambooOperationError("INVALID_PAYROLL_RULE", "不支持的工资规则类型")
        factory_id = None if system_default else actor.factory_id
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            session.execute(
                update(BambooPayrollRuleVersionRow)
                .where(
                    BambooPayrollRuleVersionRow.rule_key == rule_key,
                    BambooPayrollRuleVersionRow.factory_id == factory_id,
                    BambooPayrollRuleVersionRow.active.is_(True),
                )
                .values(active=False)
            )
            latest = session.scalar(
                select(func.max(BambooPayrollRuleVersionRow.version)).where(
                    BambooPayrollRuleVersionRow.rule_key == rule_key,
                    BambooPayrollRuleVersionRow.factory_id == factory_id,
                )
            )
            row = BambooPayrollRuleVersionRow(
                rule_version_id=str(uuid4()),
                rule_key=rule_key,
                factory_id=factory_id,
                version=int(latest or 0) + 1,
                configuration=configuration,
                active=True,
                effective_at=now,
                created_by=actor.actor_id,
                created_at=now,
            )
            session.add(row)
            session.flush()
            return self._rule(row)

    def assign_employee_role(
        self,
        *,
        actor: BambooActor,
        employee_code: str,
        role_code: str,
        factory_id: str | None,
    ) -> dict[str, Any]:
        manager_roles = PRODUCTION_ROLES | {BambooRole.INSPECTOR.value, BambooRole.SUPERVISOR.value}
        if actor.role is BambooRole.PLANT_MANAGER:
            if role_code not in manager_roles:
                raise BambooOperationError(
                    "ASSIGNMENT_FORBIDDEN", "厂长只能分配本厂工人、检测人和主管职务"
                )
            selected_factory = actor.factory_id
        elif actor.role is BambooRole.SYSTEM_ADMIN:
            selected_factory = factory_id or actor.factory_id
        else:
            raise BambooOperationError("ASSIGNMENT_FORBIDDEN", "当前职务不能分配人员职务")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            employee = session.get(MasterDataRecordRow, ("employees", employee_code))
            if employee is None or not employee.active:
                raise BambooOperationError("EMPLOYEE_NOT_FOUND", "员工不存在，请先建立员工档案")
            factory = session.get(BambooFactoryRow, selected_factory)
            if factory is None or not factory.active:
                raise BambooOperationError("FACTORY_NOT_FOUND", "目标工厂不存在或已停用")
            role = session.get(BambooRoleDefinitionRow, role_code)
            if role is None:
                category = "PRODUCTION" if role_code in PRODUCTION_ROLES else "MANAGEMENT"
                role = BambooRoleDefinitionRow(
                    role_code=role_code,
                    display_name=role_code,
                    category=category,
                    self_requestable=role_code in PRODUCTION_ROLES,
                    active=True,
                    revision=1,
                )
                session.add(role)
                session.flush()
            session.execute(
                update(EmployeeBambooAssignmentRow)
                .where(
                    EmployeeBambooAssignmentRow.employee_catalog == "employees",
                    EmployeeBambooAssignmentRow.employee_code == employee_code,
                    EmployeeBambooAssignmentRow.status == "ACTIVE",
                )
                .values(status="INACTIVE", ended_at=now)
            )
            row = EmployeeBambooAssignmentRow(
                assignment_id=f"MBA-{uuid4().hex}",
                employee_catalog="employees",
                employee_code=employee_code,
                factory_id=selected_factory,
                role_code=role_code,
                status="ACTIVE",
                effective_at=now,
                ended_at=None,
                created_by=actor.actor_id,
                created_at=now,
            )
            session.add(row)
            profile = session.get(MobileAccessProfileRow, ("employees", employee_code))
            if profile is None:
                session.add(
                    MobileAccessProfileRow(
                        employee_catalog="employees",
                        employee_code=employee_code,
                        team_id=f"TEAM-{selected_factory}",
                        team_name=factory.name,
                        position=role_code,
                        roles=["WORKER"],
                        allowed_form_types=[],
                        allowed_processes=["BAMBOO_PROCESS"],
                        active=True,
                    )
                )
            else:
                profile.position = role_code
                profile.allowed_processes = sorted(
                    set(profile.allowed_processes) | {"BAMBOO_PROCESS"}
                )
                profile.active = True
            return {
                "assignment_id": row.assignment_id,
                "employee_code": employee_code,
                "factory_id": selected_factory,
                "role_code": role_code,
                "status": "ACTIVE",
            }

    def create_factory(self, *, actor: BambooActor, code: str, name: str) -> dict[str, Any]:
        if actor.role is not BambooRole.SYSTEM_ADMIN:
            raise BambooOperationError("ADMIN_REQUIRED", "只有管理员可以新增工厂")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            if session.scalar(select(BambooFactoryRow).where(BambooFactoryRow.code == code)):
                raise BambooOperationError("FACTORY_EXISTS", "工厂编码已存在")
            row = BambooFactoryRow(
                factory_id=str(uuid4()),
                code=code,
                name=name,
                active=True,
                revision=1,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            return {"factory_id": row.factory_id, "code": code, "name": name, "active": True}

    def create_inspection(
        self,
        record_id: str,
        *,
        actor: BambooActor,
        serial_no: str,
        target_stage: BambooStage,
        moisture_points: list[Decimal],
        conclusion: str,
        note: str | None,
        text_evidence: str | None,
        device_id: str,
        request_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.INSPECTOR:
            raise BambooOperationError("INSPECTOR_REQUIRED", "仅检测人可以登记检测记录")
        if target_stage not in {BambooStage.SORT, BambooStage.DIPPING, BambooStage.DRYING}:
            raise BambooOperationError("INVALID_INSPECTION_STAGE", "检测流程只能选择前三个生产环节")
        now = datetime.now(UTC)
        canonical = json.dumps(
            {
                "record_id": record_id,
                "serial_no": serial_no,
                "target_stage": target_stage.value,
                "moisture_points": [str(value) for value in moisture_points],
                "conclusion": conclusion,
                "note": note,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        with Session(self._engine) as session, session.begin():
            existing = session.scalar(
                select(BambooInspectionRow).where(
                    BambooInspectionRow.actor_id == actor.actor_id,
                    BambooInspectionRow.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return self._inspection(session, existing)
            record = self._record(session, record_id, actor)
            signed = set(
                session.scalars(
                    select(BambooStageSubmissionRow.stage_key).where(
                        BambooStageSubmissionRow.record_id == record_id,
                        BambooStageSubmissionRow.invalidated.is_(False),
                    )
                ).all()
            )
            if not {"SORT", "DIPPING", "DRYING"} <= signed:
                raise BambooOperationError(
                    "INSPECTION_WINDOW_NOT_OPEN", "前三个流程完成后才开放检测"
                )
            if "SUPERVISOR" in signed:
                raise BambooOperationError("INSPECTION_WINDOW_CLOSED", "主管签字后检测窗口已关闭")
            if not moisture_points:
                raise BambooOperationError("MOISTURE_REQUIRED", "至少填写一个检测数值")
            average = sum(moisture_points, Decimal("0")) / len(moisture_points)
            row = BambooInspectionRow(
                inspection_id=str(uuid4()),
                record_id=record_id,
                serial_no=serial_no.strip(),
                target_stage=target_stage.value,
                moisture_points=[str(value) for value in moisture_points],
                average_value=str(average.quantize(Decimal("0.01"))),
                conclusion=conclusion,
                note=note,
                actor_id=actor.actor_id,
                actor_name=actor.employee_name,
                factory_id=actor.factory_id,
                role_code=actor.role.value,
                signed_at=now,
                payload_hash=hashlib.sha256(canonical).hexdigest(),
                device_id=device_id,
                request_id=request_id,
                idempotency_key=idempotency_key,
                window_revision=record.revision,
            )
            session.add(row)
            session.flush()
            if text_evidence:
                session.add(
                    BambooEvidenceAssetRow(
                        asset_id=str(uuid4()),
                        inspection_id=row.inspection_id,
                        evidence_type="TEXT",
                        file_id=None,
                        uri=None,
                        mime_type="text/plain",
                        size_bytes=len(text_evidence.encode()),
                        sha256=hashlib.sha256(text_evidence.encode()).hexdigest(),
                        text_content=text_evidence,
                        actor_id=actor.actor_id,
                        created_at=now,
                    )
                )
            if conclusion != "CONFORMING":
                session.add(
                    BambooInspectionExceptionRow(
                        exception_id=str(uuid4()),
                        inspection_id=row.inspection_id,
                        record_id=record_id,
                        status="OPEN",
                        resolution=None,
                        closed_by=None,
                        closed_at=None,
                        revision=1,
                    )
                )
            session.flush()
            return self._inspection(session, row)

    def add_file_evidence(
        self,
        inspection_id: str,
        *,
        actor: BambooActor,
        evidence_type: str,
        content: bytes,
        filename: str,
        mime_type: str,
    ) -> dict[str, Any]:
        kind = evidence_type.upper()
        if kind not in {"PHOTO", "AUDIO"}:
            raise BambooOperationError("INVALID_EVIDENCE_TYPE", "文件留痕只支持照片或录音")
        if not content or len(content) > 20 * 1024 * 1024:
            raise BambooOperationError("INVALID_EVIDENCE_SIZE", "留痕文件必须小于 20MB")
        with Session(self._engine) as session, session.begin():
            inspection = session.get(BambooInspectionRow, inspection_id)
            if inspection is None or inspection.factory_id != actor.factory_id:
                raise BambooOperationError("INSPECTION_NOT_FOUND", "检测记录不存在")
            if kind == "PHOTO":
                count = session.scalar(
                    select(func.count())
                    .select_from(BambooEvidenceAssetRow)
                    .where(
                        BambooEvidenceAssetRow.inspection_id == inspection_id,
                        BambooEvidenceAssetRow.evidence_type == "PHOTO",
                    )
                )
                if int(count or 0) >= 6:
                    raise BambooOperationError("PHOTO_LIMIT", "每次检测最多上传 6 张照片")
            suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            stored = self._storage.store_bytes(content, suffix, f"bamboo/{inspection_id}")
            row = BambooEvidenceAssetRow(
                asset_id=str(uuid4()),
                inspection_id=inspection_id,
                evidence_type=kind,
                file_id=stored.file_id,
                uri=stored.uri,
                mime_type=mime_type,
                size_bytes=len(content),
                sha256=stored.sha256,
                text_content=None,
                actor_id=actor.actor_id,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            session.flush()
            return self._evidence(row)

    def close_exception(
        self, exception_id: str, *, actor: BambooActor, resolution: str
    ) -> dict[str, Any]:
        if actor.role not in {
            BambooRole.INSPECTOR,
            BambooRole.SUPERVISOR,
            BambooRole.PLANT_MANAGER,
        }:
            raise BambooOperationError("EXCEPTION_CLOSE_FORBIDDEN", "当前职务不能关闭检测异常")
        with Session(self._engine) as session, session.begin():
            row = session.get(BambooInspectionExceptionRow, exception_id)
            if row is None:
                raise BambooOperationError("EXCEPTION_NOT_FOUND", "检测异常不存在")
            record = self._record(session, row.record_id, actor)
            del record
            row.status = "CLOSED"
            row.resolution = resolution
            row.closed_by = actor.actor_id
            row.closed_at = datetime.now(UTC)
            row.revision += 1
            session.flush()
            return self._exception(row)

    def selective_return(
        self,
        record_id: str,
        *,
        actor: BambooActor,
        target_stages: list[BambooStage],
        reason: str,
        source: str,
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.SUPERVISOR:
            raise BambooOperationError("RETURN_FORBIDDEN", "由主管选择需要重写的流程")
        selected = set(target_stages)
        if not selected or not selected <= set(REWORK_DEPENDENCIES):
            raise BambooOperationError("INVALID_RETURN_STAGES", "请选择需要重写的生产环节")
        invalidated_stages = {
            stage for selected_stage in selected for stage in REWORK_DEPENDENCIES[selected_stage]
        }
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            record = self._record(session, record_id, actor)
            submissions = session.scalars(
                select(BambooStageSubmissionRow).where(
                    BambooStageSubmissionRow.record_id == record_id,
                    BambooStageSubmissionRow.invalidated.is_(False),
                    BambooStageSubmissionRow.stage_key.in_(
                        [stage.value for stage in invalidated_stages]
                    ),
                )
            ).all()
            submission_ids = {row.submission_id for row in submissions}
            for submission in submissions:
                submission.invalidated = True
            facts = session.scalars(
                select(BambooPayrollFactRow).where(
                    BambooPayrollFactRow.record_id == record_id,
                    BambooPayrollFactRow.status != "INVALIDATED",
                )
            ).all()
            for fact in facts:
                if submission_ids.intersection(fact.source_submission_ids):
                    fact.status = "INVALIDATED"
                    fact.invalidated_at = now
                    session.execute(
                        update(BambooDailyExportItemRow)
                        .where(BambooDailyExportItemRow.payroll_fact_id == fact.fact_id)
                        .values(status="SUPERSEDED", revision=BambooDailyExportItemRow.revision + 1)
                    )
            earliest = min(selected, key=lambda stage: list(BambooStage).index(stage))
            record.current_stage = earliest.value
            record.status = "ACTIVE"
            record.revision += 1
            record.updated_at = now
            return_row = BambooReturnRow(
                return_id=str(uuid4()),
                record_id=record_id,
                requested_by=actor.actor_id,
                requested_role=actor.role.value,
                target_stages=[
                    stage.value
                    for stage in sorted(selected, key=lambda stage: list(BambooStage).index(stage))
                ],
                reason=reason,
                source=source,
                created_at=now,
                record_revision=record.revision,
            )
            session.add(return_row)
            return {
                "return_id": return_row.return_id,
                "record_id": record_id,
                "current_stage": earliest.value,
                "revision": record.revision,
            }

    def request_role_change(
        self, *, actor: BambooActor, to_role: str, reason: str
    ) -> dict[str, Any]:
        if actor.role.value not in PRODUCTION_ROLES or to_role not in PRODUCTION_ROLES:
            raise BambooOperationError("ROLE_CHANGE_FORBIDDEN", "仅生产工人可申请切换生产职务")
        if to_role == actor.role.value:
            raise BambooOperationError("ROLE_UNCHANGED", "目标职务与当前职务相同")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            duplicate = session.scalar(
                select(BambooRoleChangeRequestRow).where(
                    BambooRoleChangeRequestRow.employee_code == actor.employee_code,
                    BambooRoleChangeRequestRow.status == "PENDING",
                )
            )
            if duplicate is not None:
                raise BambooOperationError("ROLE_CHANGE_PENDING", "已有待厂长处理的职务申请")
            row = BambooRoleChangeRequestRow(
                request_id=str(uuid4()),
                employee_code=actor.employee_code,
                factory_id=actor.factory_id,
                from_role=actor.role.value,
                to_role=to_role,
                reason=reason,
                status="PENDING",
                requested_by=actor.actor_id,
                requested_at=now,
                decided_by=None,
                decided_at=None,
                decision_note=None,
                revision=1,
            )
            session.add(row)
            return self._role_request(row)

    def list_role_changes(self, actor: BambooActor) -> list[dict[str, Any]]:
        if actor.role is not BambooRole.PLANT_MANAGER:
            raise BambooOperationError("MANAGER_REQUIRED", "仅厂长可以处理职务申请")
        with Session(self._engine) as session:
            rows = session.scalars(
                select(BambooRoleChangeRequestRow)
                .where(BambooRoleChangeRequestRow.factory_id == actor.factory_id)
                .order_by(BambooRoleChangeRequestRow.requested_at.desc())
            ).all()
            return [self._role_request(row) for row in rows]

    def decide_role_change(
        self, request_id: str, *, actor: BambooActor, approve: bool, note: str
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.PLANT_MANAGER:
            raise BambooOperationError("MANAGER_REQUIRED", "仅厂长可以处理职务申请")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            row = session.get(BambooRoleChangeRequestRow, request_id)
            if row is None or row.factory_id != actor.factory_id:
                raise BambooOperationError("ROLE_CHANGE_NOT_FOUND", "职务申请不存在")
            if row.status != "PENDING":
                raise BambooOperationError("ROLE_CHANGE_DECIDED", "职务申请已处理")
            row.status = "APPROVED" if approve else "REJECTED"
            row.decided_by = actor.actor_id
            row.decided_at = now
            row.decision_note = note
            row.revision += 1
            if approve:
                if session.get(BambooRoleDefinitionRow, row.to_role) is None:
                    session.add(
                        BambooRoleDefinitionRow(
                            role_code=row.to_role,
                            display_name=row.to_role,
                            category="PRODUCTION",
                            self_requestable=True,
                            active=True,
                            revision=1,
                        )
                    )
                    session.flush()
                active = session.scalar(
                    select(EmployeeBambooAssignmentRow).where(
                        EmployeeBambooAssignmentRow.employee_code == row.employee_code,
                        EmployeeBambooAssignmentRow.factory_id == actor.factory_id,
                        EmployeeBambooAssignmentRow.status == "ACTIVE",
                    )
                )
                if active is not None:
                    active.status = "INACTIVE"
                    active.ended_at = now
                session.add(
                    EmployeeBambooAssignmentRow(
                        assignment_id=f"MBA-{uuid4().hex}",
                        employee_catalog="employees",
                        employee_code=row.employee_code,
                        factory_id=row.factory_id,
                        role_code=row.to_role,
                        status="ACTIVE",
                        effective_at=now,
                        ended_at=None,
                        created_by=actor.actor_id,
                        created_at=now,
                    )
                )
            session.flush()
            return self._role_request(row)

    def list_daily_batches(self, actor: BambooActor) -> list[dict[str, Any]]:
        if actor.role not in {BambooRole.FINANCE_APPROVER, BambooRole.PLANT_MANAGER}:
            raise BambooOperationError("FINANCE_REQUIRED", "当前职务无权查看财务批次")
        with Session(self._engine) as session:
            rows = session.scalars(
                select(BambooDailyExportBatchRow)
                .where(BambooDailyExportBatchRow.factory_id == actor.factory_id)
                .order_by(
                    BambooDailyExportBatchRow.business_date.desc(),
                    BambooDailyExportBatchRow.version.desc(),
                )
            ).all()
            return [self._batch(session, row) for row in rows]

    def decide_daily_item(
        self, item_id: str, *, actor: BambooActor, decision: str, note: str
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.FINANCE_APPROVER:
            raise BambooOperationError("FINANCE_REQUIRED", "仅财务可以审批工资条目")
        if decision not in {"APPROVED", "HELD", "CORRECTION_REQUIRED"}:
            raise BambooOperationError("INVALID_FINANCE_DECISION", "无效的财务审批结果")
        with Session(self._engine) as session, session.begin():
            row = session.get(BambooDailyExportItemRow, item_id)
            if row is None:
                raise BambooOperationError("FINANCE_ITEM_NOT_FOUND", "财务条目不存在")
            batch = session.get(BambooDailyExportBatchRow, row.batch_id)
            if batch is None or batch.factory_id != actor.factory_id:
                raise BambooOperationError("FINANCE_ITEM_NOT_FOUND", "财务条目不存在")
            row.status = decision
            row.decision_by = actor.actor_id
            row.decision_at = datetime.now(UTC)
            row.decision_note = note
            row.revision += 1
            if decision == "CORRECTION_REQUIRED":
                session.add(
                    BambooCorrectionCaseRow(
                        case_id=str(uuid4()),
                        item_id=row.item_id,
                        record_id=row.record_id,
                        status="OPEN",
                        reason=note,
                        created_by=actor.actor_id,
                        created_at=datetime.now(UTC),
                        resolved_at=None,
                        supplement_batch_id=None,
                    )
                )
            session.flush()
            return self._item(row)

    def create_inquiry(
        self, item_id: str, *, actor: BambooActor, subject: str, body: str
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.FINANCE_APPROVER:
            raise BambooOperationError("FINANCE_REQUIRED", "仅财务可以发起询问")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            item = session.get(BambooDailyExportItemRow, item_id)
            if item is None:
                raise BambooOperationError("FINANCE_ITEM_NOT_FOUND", "财务条目不存在")
            batch = session.get(BambooDailyExportBatchRow, item.batch_id)
            if batch is None or batch.factory_id != actor.factory_id:
                raise BambooOperationError("FINANCE_ITEM_NOT_FOUND", "财务条目不存在")
            inquiry = BambooFinanceInquiryRow(
                inquiry_id=str(uuid4()),
                item_id=item_id,
                factory_id=actor.factory_id,
                subject=subject,
                status="OPEN",
                created_by=actor.actor_id,
                created_at=now,
            )
            session.add(inquiry)
            session.flush()
            session.add(self._message(inquiry.inquiry_id, actor, body, now))
            return {"inquiry_id": inquiry.inquiry_id, "status": inquiry.status, "subject": subject}

    def reply_inquiry(
        self, inquiry_id: str, *, actor: BambooActor, body: str, close: bool
    ) -> dict[str, Any]:
        if actor.role not in {BambooRole.PLANT_MANAGER, BambooRole.FINANCE_APPROVER}:
            raise BambooOperationError("INQUIRY_REPLY_FORBIDDEN", "当前职务不能回复询问")
        with Session(self._engine) as session, session.begin():
            inquiry = session.get(BambooFinanceInquiryRow, inquiry_id)
            if inquiry is None or inquiry.factory_id != actor.factory_id:
                raise BambooOperationError("INQUIRY_NOT_FOUND", "询问不存在")
            session.add(self._message(inquiry_id, actor, body, datetime.now(UTC)))
            inquiry.status = "CLOSED" if close else "ANSWERED"
            return {"inquiry_id": inquiry.inquiry_id, "status": inquiry.status}

    def list_inquiries(self, actor: BambooActor) -> list[dict[str, Any]]:
        if actor.role not in {BambooRole.PLANT_MANAGER, BambooRole.FINANCE_APPROVER}:
            raise BambooOperationError("INQUIRY_VIEW_FORBIDDEN", "当前职务不能查看财务询问")
        with Session(self._engine) as session:
            rows = session.scalars(
                select(BambooFinanceInquiryRow)
                .where(BambooFinanceInquiryRow.factory_id == actor.factory_id)
                .order_by(BambooFinanceInquiryRow.created_at.desc())
            ).all()
            return [self._inquiry(session, row) for row in rows]

    def monthly_summary(self, actor: BambooActor, month: str) -> dict[str, Any]:
        if actor.role not in {BambooRole.FINANCE_APPROVER, BambooRole.PLANT_MANAGER}:
            raise BambooOperationError("FINANCE_REQUIRED", "当前职务无权查看月汇总")
        totals: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        with Session(self._engine) as session:
            rows = session.execute(
                select(BambooDailyExportItemRow, BambooDailyExportBatchRow)
                .join(
                    BambooDailyExportBatchRow,
                    BambooDailyExportBatchRow.batch_id == BambooDailyExportItemRow.batch_id,
                )
                .where(
                    BambooDailyExportBatchRow.factory_id == actor.factory_id,
                    BambooDailyExportBatchRow.business_date.like(f"{month}%"),
                    BambooDailyExportItemRow.status == "APPROVED",
                )
            ).all()
            for item, _batch in rows:
                totals[item.employee_code] += Decimal(item.amount)
        items = [
            {"employee_code": code, "amount": str(amount.quantize(Decimal("0.01")))}
            for code, amount in sorted(totals.items())
        ]
        return {
            "factory_id": actor.factory_id,
            "month": month,
            "items": items,
            "total_amount": str(sum(totals.values(), Decimal("0")).quantize(Decimal("0.01"))),
        }

    @staticmethod
    def _message(
        inquiry_id: str, actor: BambooActor, body: str, now: datetime
    ) -> BambooFinanceInquiryMessageRow:
        return BambooFinanceInquiryMessageRow(
            message_id=str(uuid4()),
            inquiry_id=inquiry_id,
            actor_id=actor.actor_id,
            actor_name=actor.employee_name,
            role_code=actor.role.value,
            body=body,
            created_at=now,
        )

    @staticmethod
    def _record(session: Session, record_id: str, actor: BambooActor) -> BambooRecordRow:
        row = session.get(BambooRecordRow, record_id)
        if row is None or row.factory_id != actor.factory_id:
            raise BambooOperationError("RECORD_NOT_VISIBLE", "记录不存在或不属于当前工厂")
        return row

    def _inspection(self, session: Session, row: BambooInspectionRow) -> dict[str, Any]:
        evidence = session.scalars(
            select(BambooEvidenceAssetRow).where(
                BambooEvidenceAssetRow.inspection_id == row.inspection_id
            )
        ).all()
        exception = session.scalar(
            select(BambooInspectionExceptionRow).where(
                BambooInspectionExceptionRow.inspection_id == row.inspection_id
            )
        )
        return {
            "inspection_id": row.inspection_id,
            "record_id": row.record_id,
            "serial_no": row.serial_no,
            "target_stage": row.target_stage,
            "moisture_points": row.moisture_points,
            "average_value": row.average_value,
            "conclusion": row.conclusion,
            "note": row.note,
            "actor_name": row.actor_name,
            "signed_at": row.signed_at,
            "payload_hash": row.payload_hash,
            "evidence": [self._evidence(item) for item in evidence],
            "exception": self._exception(exception) if exception else None,
        }

    @staticmethod
    def _evidence(row: BambooEvidenceAssetRow) -> dict[str, Any]:
        return {
            "asset_id": row.asset_id,
            "evidence_type": row.evidence_type,
            "file_id": row.file_id,
            "uri": row.uri,
            "mime_type": row.mime_type,
            "size_bytes": row.size_bytes,
            "sha256": row.sha256,
            "text_content": row.text_content,
        }

    @staticmethod
    def _exception(row: BambooInspectionExceptionRow) -> dict[str, Any]:
        return {
            "exception_id": row.exception_id,
            "status": row.status,
            "resolution": row.resolution,
            "closed_by": row.closed_by,
            "closed_at": row.closed_at,
            "revision": row.revision,
        }

    @staticmethod
    def _fact(row: BambooPayrollFactRow) -> dict[str, Any]:
        return {
            "fact_id": row.fact_id,
            "fact_type": row.fact_type,
            "version": row.version,
            "status": row.status,
            "rule_version_id": row.rule_version_id,
            "input_snapshot": row.input_snapshot,
            "allocations": row.allocations,
            "total_amount": row.total_amount,
            "created_at": row.created_at,
            "effective_at": row.effective_at,
        }

    @staticmethod
    def _rule(row: BambooPayrollRuleVersionRow) -> dict[str, Any]:
        return {
            "rule_version_id": row.rule_version_id,
            "rule_key": row.rule_key,
            "factory_id": row.factory_id,
            "version": row.version,
            "configuration": row.configuration,
            "active": row.active,
            "effective_at": row.effective_at,
        }

    @staticmethod
    def _role_request(row: BambooRoleChangeRequestRow) -> dict[str, Any]:
        return {
            "request_id": row.request_id,
            "employee_code": row.employee_code,
            "factory_id": row.factory_id,
            "from_role": row.from_role,
            "to_role": row.to_role,
            "reason": row.reason,
            "status": row.status,
            "requested_at": row.requested_at,
            "decided_at": row.decided_at,
            "decision_note": row.decision_note,
            "revision": row.revision,
        }

    def _batch(self, session: Session, row: BambooDailyExportBatchRow) -> dict[str, Any]:
        items = session.scalars(
            select(BambooDailyExportItemRow)
            .where(BambooDailyExportItemRow.batch_id == row.batch_id)
            .order_by(BambooDailyExportItemRow.employee_code)
        ).all()
        return {
            "batch_id": row.batch_id,
            "factory_id": row.factory_id,
            "business_date": row.business_date,
            "version": row.version,
            "status": row.status,
            "supplemental": row.supplemental,
            "items": [self._item(item) for item in items],
        }

    @staticmethod
    def _item(row: BambooDailyExportItemRow) -> dict[str, Any]:
        return {
            "item_id": row.item_id,
            "batch_id": row.batch_id,
            "payroll_fact_id": row.payroll_fact_id,
            "record_id": row.record_id,
            "employee_code": row.employee_code,
            "amount": row.amount,
            "status": row.status,
            "decision_note": row.decision_note,
            "source_snapshot": row.source_snapshot,
            "revision": row.revision,
        }

    @staticmethod
    def _inquiry(session: Session, row: BambooFinanceInquiryRow) -> dict[str, Any]:
        messages = session.scalars(
            select(BambooFinanceInquiryMessageRow)
            .where(BambooFinanceInquiryMessageRow.inquiry_id == row.inquiry_id)
            .order_by(BambooFinanceInquiryMessageRow.created_at)
        ).all()
        return {
            "inquiry_id": row.inquiry_id,
            "item_id": row.item_id,
            "subject": row.subject,
            "status": row.status,
            "created_at": row.created_at,
            "messages": [
                {
                    "actor_name": message.actor_name,
                    "role_code": message.role_code,
                    "body": message.body,
                    "created_at": message.created_at,
                }
                for message in messages
            ],
        }
