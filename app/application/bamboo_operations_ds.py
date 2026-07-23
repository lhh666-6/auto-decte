"""Operational services layered on the signed bamboo workflow."""

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Engine, func, select, update
from sqlalchemy.engine import CursorResult
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
    BambooInspectionWindowRow,
    BambooPayrollFactRow,
    BambooPayrollRuleVersionRow,
    BambooPersonnelTransferRow,
    BambooRecordRow,
    BambooReturnRow,
    BambooRoleChangeRequestRow,
    BambooRoleDefinitionRow,
    BambooStageSubmissionRow,
    EmployeeBambooAssignmentRow,
    MasterDataRecordRow,
    MobileAccessProfileRow,
    MobileCredentialRow,
    MobileNotificationRow,
)
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.mobile_identity_ds import hash_pin
from app.modules.bamboo_process.models_ds import (
    BambooActor,
    BambooFormType,
    BambooRole,
    BambooStage,
)

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
DEFAULT_SPECIAL_CLASSES = ["直装", "防霉"]
DEFAULT_LENGTHS = ["2.1", "2.3", "2.5"]
DEFAULT_SHADES = ["深", "浅"]
DEFAULT_GRADES = ["A", "B"]
DEFAULT_WEIGHT_FACTORS = {"2.1": "5", "2.3": "6", "2.5": "7"}
DEFAULT_ROLE_DEFINITIONS = {
    "SORT_OPERATOR": ("分选工", "PRODUCTION", True),
    "DIPPING_OPERATOR": ("浸胶工", "PRODUCTION", True),
    "DRYING_RACK_OPERATOR": ("干燥工", "PRODUCTION", True),
    "INSPECTOR": ("检测人", "QUALITY", True),
    "SUPERVISOR": ("主管", "MANAGEMENT", True),
    "PLANT_MANAGER": ("厂长", "MANAGEMENT", False),
    "FINANCE_APPROVER": ("财务审批", "FINANCE", False),
    "SYSTEM_ADMIN": ("系统管理员", "ADMIN", False),
}


class BambooOperationError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


def _string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _option_list(configuration: dict[str, Any], key: str, fallback: list[str]) -> list[str]:
    value = configuration.get(key)
    if isinstance(value, list):
        options = [str(item).strip() for item in value if str(item).strip()]
        if options:
            return options
    return fallback


def _record_options_from_rule(configuration: dict[str, Any]) -> dict[str, Any]:
    length_multipliers = configuration.get("length_multipliers")
    configured_lengths = (
        [str(key) for key in length_multipliers]
        if isinstance(length_multipliers, dict)
        else []
    )
    lengths = _option_list(configuration, "lengths", configured_lengths or DEFAULT_LENGTHS)
    weight_factors = configuration.get("weight_factors")
    if not isinstance(weight_factors, dict):
        weight_factors = (
            length_multipliers
            if isinstance(length_multipliers, dict)
            else DEFAULT_WEIGHT_FACTORS
        )
    return {
        "special_classes": _option_list(
            configuration,
            "special_classes",
            DEFAULT_SPECIAL_CLASSES,
        ),
        "lengths": lengths,
        "shades": _option_list(configuration, "shades", DEFAULT_SHADES),
        "grades": _option_list(configuration, "grades", DEFAULT_GRADES),
        "weight_factors": {str(key): str(value) for key, value in weight_factors.items()},
    }


def _require_member(value: str, options: list[str], detail: str) -> None:
    if value not in options:
        raise BambooOperationError("INVALID_BAMBOO_BASE_INFO", detail)


def _optional_decimal(
    values: dict[str, Any],
    keys: tuple[str, ...],
    label: str,
) -> Decimal | None:
    raw = next(
        (
            values[key]
            for key in keys
            if values.get(key) is not None and values.get(key) != ""
        ),
        None,
    )
    if raw is None:
        return None
    try:
        value = Decimal(str(raw))
    except (ArithmeticError, ValueError) as error:
        raise BambooOperationError(
            "INVALID_BAMBOO_STAGE_VALUES",
            f"{label}必须是有效数值",
        ) from error
    if not value.is_finite() or value < 0:
        raise BambooOperationError(
            "INVALID_BAMBOO_STAGE_VALUES",
            f"{label}必须是非负数",
        )
    return value


class BambooOperationsService:
    def __init__(self, engine: Engine, storage: LocalEvidenceStorage) -> None:
        self._engine = engine
        self._storage = storage
        self._install_default_roles()

    def _install_default_roles(self) -> None:
        with Session(self._engine) as session, session.begin():
            for code, (name, category, requestable) in DEFAULT_ROLE_DEFINITIONS.items():
                row = session.get(BambooRoleDefinitionRow, code)
                if row is None:
                    session.add(BambooRoleDefinitionRow(
                        role_code=code,
                        display_name=name,
                        category=category,
                        self_requestable=requestable,
                        active=True,
                        revision=1,
                    ))
                    continue
                if row.display_name == code:
                    row.display_name = name
                row.category = category
                row.self_requestable = requestable

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

    def record_options(self, actor: BambooActor) -> dict[str, Any]:
        with Session(self._engine) as session:
            row = self._active_rule(session, "SORT", actor.factory_id)
            options = _record_options_from_rule(row.configuration if row else {})
            version = row.rule_version_id if row else "system-sort-v1"
            return {"options_version": version, **options}

    def validate_record_base_info(
        self,
        actor: BambooActor,
        base_info: dict[str, Any],
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.SORT_OPERATOR:
            raise BambooOperationError("BAMBOO_ROLE_REQUIRED", "只有分选/装笼岗位可以新建竹丝记录")
        options = self.record_options(actor)
        cage_no = str(base_info.get("cage_no") or "").strip()
        length = str(base_info.get("length") or "").strip()
        shade = str(base_info.get("shade") or "").strip()
        grade = str(base_info.get("grade") or "").strip()
        mode = str(base_info.get("mode") or "分选").strip()
        supplier = str(base_info.get("supplier") or "").strip()
        special_classes = _string_list(base_info.get("special_classes"))
        if not special_classes and base_info.get("special_class"):
            special_classes = _string_list(base_info.get("special_class"))
        bundle_count_raw = base_info.get("bundle_count")
        try:
            bundle_count = int(str(bundle_count_raw).strip())
        except (TypeError, ValueError) as error:
            raise BambooOperationError("INVALID_BAMBOO_BASE_INFO", "把数需填写正整数") from error
        if not cage_no:
            raise BambooOperationError("INVALID_BAMBOO_BASE_INFO", "请填写笼号")
        if bundle_count <= 0:
            raise BambooOperationError("INVALID_BAMBOO_BASE_INFO", "把数需填写正整数")
        _require_member(length, options["lengths"], "请选择后台发布的长度")
        _require_member(shade, options["shades"], "请选择后台发布的深浅")
        _require_member(grade, options["grades"], "请选择后台发布的品级")
        if mode not in {"分选", "分选+装笼"}:
            raise BambooOperationError(
                "INVALID_BAMBOO_BASE_INFO",
                "作业模式只能选择分选或分选+装笼",
            )
        invalid_special = [
            item for item in special_classes if item not in options["special_classes"]
        ]
        if invalid_special:
            raise BambooOperationError("INVALID_BAMBOO_BASE_INFO", "特殊类包含未发布选项")
        normalized: dict[str, Any] = {
            "mode": mode,
            "special_classes": special_classes,
            "length": length,
            "shade": shade,
            "grade": grade,
            "supplier": supplier,
            "cage_no": cage_no,
            "bundle_count": bundle_count,
            "options_version": options["options_version"],
        }
        factor = options["weight_factors"].get(length)
        if factor is not None:
            normalized["net_weight"] = str(Decimal(bundle_count) * Decimal(str(factor)))
        return normalized

    def validate_stage_values(
        self,
        stage: BambooStage,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(values)
        if stage not in {BambooStage.SORT, BambooStage.DIPPING, BambooStage.DRYING}:
            return normalized
        moisture = values.get("moisture")
        if not isinstance(moisture, list) or not moisture:
            raise BambooOperationError(
                "INVALID_BAMBOO_STAGE_VALUES",
                "至少填写一个含水率检测点",
            )
        if len(moisture) > 20:
            raise BambooOperationError(
                "INVALID_BAMBOO_STAGE_VALUES",
                "含水率检测点不能超过 20 个",
            )
        normalized_moisture: list[int] = []
        for raw in moisture:
            if isinstance(raw, bool):
                raise BambooOperationError(
                    "INVALID_BAMBOO_STAGE_VALUES",
                    "含水率必须是 1 至 100 的正整数",
                )
            try:
                point = Decimal(str(raw))
            except (ArithmeticError, ValueError) as error:
                raise BambooOperationError(
                    "INVALID_BAMBOO_STAGE_VALUES",
                    "含水率必须是 1 至 100 的正整数",
                ) from error
            if (
                not point.is_finite()
                or point != point.to_integral_value()
                or not 1 <= point <= 100
            ):
                raise BambooOperationError(
                    "INVALID_BAMBOO_STAGE_VALUES",
                    "含水率必须是 1 至 100 的正整数",
                )
            normalized_moisture.append(int(point))
        normalized["moisture"] = normalized_moisture

        if stage is BambooStage.DIPPING:
            before = _optional_decimal(
                values,
                (
                    "glue_before_weight",
                    "pre_glue_weight",
                    "before_glue_weight",
                    "weight_before",
                ),
                "胶前重",
            )
            after = _optional_decimal(
                values,
                (
                    "glue_after_weight",
                    "post_glue_weight",
                    "after_glue_weight",
                    "weight_after",
                ),
                "胶后重",
            )
            glue_gain = _optional_decimal(
                values,
                ("glue_gain", "glue_amount"),
                "上胶量",
            )
            if before is not None:
                normalized["glue_before_weight"] = str(before)
            else:
                normalized.pop("glue_before_weight", None)
            if after is not None:
                normalized["glue_after_weight"] = str(after)
            else:
                normalized.pop("glue_after_weight", None)
            if glue_gain is not None:
                normalized["glue_gain"] = str(glue_gain)
            else:
                normalized.pop("glue_gain", None)
            if values.get("wage_amount") is not None and values.get("wage_amount") != "":
                wage_amount = _optional_decimal(values, ("wage_amount",), "工资金额")
                if wage_amount is not None:
                    normalized["wage_amount"] = str(wage_amount)
            if before is not None and after is not None and after < before:
                raise BambooOperationError(
                    "INVALID_BAMBOO_STAGE_VALUES",
                    "胶后重不能小于胶前重",
                )

        if stage is BambooStage.DRYING:
            raw_racks = values.get("rack_numbers", values.get("rack_nos"))
            if raw_racks is None:
                raw_racks = values.get("rack_no")
            if isinstance(raw_racks, str):
                rack_numbers = [
                    item.strip()
                    for item in raw_racks.replace("，", ",").split(",")
                    if item.strip()
                ]
            elif isinstance(raw_racks, list):
                rack_numbers = [str(item).strip() for item in raw_racks if str(item).strip()]
            else:
                rack_numbers = []
            if not rack_numbers:
                raise BambooOperationError(
                    "INVALID_BAMBOO_STAGE_VALUES",
                    "至少填写一个干燥架号",
                )
            if len(set(rack_numbers)) != len(rack_numbers):
                raise BambooOperationError(
                    "INVALID_BAMBOO_STAGE_VALUES",
                    "干燥架号不能重复",
                )
            normalized["rack_numbers"] = rack_numbers
            normalized["rack_count"] = len(rack_numbers)
        return normalized

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
            if role is None or not role.active:
                raise BambooOperationError(
                    "ROLE_NOT_PUBLISHED",
                    "该职位尚未由管理员发布或已经停用",
                )
            active_assignment = session.scalar(
                select(EmployeeBambooAssignmentRow).where(
                    EmployeeBambooAssignmentRow.employee_catalog == "employees",
                    EmployeeBambooAssignmentRow.employee_code == employee_code,
                    EmployeeBambooAssignmentRow.status == "ACTIVE",
                )
            )
            if active_assignment is not None:
                raise BambooOperationError(
                    "TRANSFER_REQUEST_REQUIRED",
                    "已有在岗员工必须通过人员调动流程变更职务或工厂",
                )
            if (
                actor.role is BambooRole.PLANT_MANAGER
                and active_assignment is not None
                and active_assignment.factory_id != actor.factory_id
            ):
                raise BambooOperationError(
                    "EMPLOYEE_OUTSIDE_FACTORY",
                    "厂长只能调整本厂人员",
                )
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
                        position=role.display_name,
                        roles=["WORKER"],
                        allowed_form_types=[],
                        allowed_processes=["BAMBOO_PROCESS"],
                        active=True,
                    )
                )
            else:
                profile.team_id = f"TEAM-{selected_factory}"
                profile.team_name = factory.name
                profile.position = role.display_name
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

    def list_inspection_queue(
        self,
        actor: BambooActor,
        *,
        bucket: str = "active",
        query: str = "",
    ) -> dict[str, Any]:
        if actor.role not in {
            BambooRole.INSPECTOR,
            BambooRole.SUPERVISOR,
            BambooRole.PLANT_MANAGER,
        }:
            raise BambooOperationError("INSPECTION_QUEUE_FORBIDDEN", "当前职务不能查看检测队列")
        if bucket not in {"active", "history"}:
            raise BambooOperationError("INVALID_INSPECTION_BUCKET", "检测队列分组无效")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            rows = session.execute(
                select(BambooInspectionWindowRow, BambooRecordRow)
                .join(
                    BambooRecordRow,
                    BambooRecordRow.record_id == BambooInspectionWindowRow.record_id,
                )
                .where(BambooInspectionWindowRow.factory_id == actor.factory_id)
                .order_by(BambooInspectionWindowRow.deadline_at, BambooRecordRow.display_no)
            ).all()
            items: list[dict[str, Any]] = []
            for window, record in rows:
                if window.status in {"OPEN", "CLAIMED"} and now >= _utc(window.deadline_at):
                    window.status = "EXPIRED"
                    window.appeal_deadline_at = _utc(window.deadline_at) + timedelta(hours=24)
                    window.revision += 1
                is_active = window.status in {"OPEN", "CLAIMED"}
                if (bucket == "active") != is_active:
                    continue
                search = query.strip().casefold()
                cage_no = str((record.base_info or {}).get("cage_no", ""))
                if (
                    search
                    and search not in record.display_no.casefold()
                    and search not in cage_no.casefold()
                ):
                    continue
                items.append(self._inspection_window(window, record, now))
            return {"bucket": bucket, "items": items}

    def claim_inspection(self, record_id: str, *, actor: BambooActor) -> dict[str, Any]:
        if actor.role is not BambooRole.INSPECTOR:
            raise BambooOperationError("INSPECTOR_REQUIRED", "仅检测人可以领取检测任务")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            window = session.get(BambooInspectionWindowRow, record_id)
            if window is None or window.factory_id != actor.factory_id:
                raise BambooOperationError("INSPECTION_WINDOW_NOT_FOUND", "检测任务不存在")
            if now >= _utc(window.deadline_at):
                if window.status in {"OPEN", "CLAIMED"}:
                    window.status = "EXPIRED"
                    window.appeal_deadline_at = _utc(window.deadline_at) + timedelta(hours=24)
                    window.revision += 1
                raise BambooOperationError("INSPECTION_WINDOW_EXPIRED", "两小时检测窗口已结束")
            if window.claimed_by == actor.actor_id and window.status == "CLAIMED":
                record = session.get(BambooRecordRow, record_id)
                if record is None:  # pragma: no cover
                    raise BambooOperationError("INSPECTION_WINDOW_NOT_FOUND", "检测任务不存在")
                return self._inspection_window(window, record, now)
            result = cast(
                CursorResult[Any],
                session.execute(
                    update(BambooInspectionWindowRow)
                    .where(
                        BambooInspectionWindowRow.record_id == record_id,
                        BambooInspectionWindowRow.status == "OPEN",
                        BambooInspectionWindowRow.claimed_by.is_(None),
                    )
                    .values(
                        status="CLAIMED",
                        claimed_by=actor.actor_id,
                        claimed_at=now,
                        revision=BambooInspectionWindowRow.revision + 1,
                    )
                )
            )
            if result.rowcount != 1:
                raise BambooOperationError(
                    "INSPECTION_ALREADY_CLAIMED",
                    "该表单已由另一名检测员领取",
                )
            session.flush()
            window = session.get(BambooInspectionWindowRow, record_id)
            record = session.get(BambooRecordRow, record_id)
            if window is None or record is None:  # pragma: no cover
                raise BambooOperationError("INSPECTION_WINDOW_NOT_FOUND", "检测任务不存在")
            return self._inspection_window(window, record, now)

    def terminate_inspection(
        self,
        record_id: str,
        *,
        actor: BambooActor,
        confirm: bool,
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.PLANT_MANAGER:
            raise BambooOperationError("MANAGER_REQUIRED", "仅厂长可以提前终止检测")
        if not confirm:
            raise BambooOperationError("TERMINATION_CONFIRMATION_REQUIRED", "请二次确认提前签字")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            window = session.get(BambooInspectionWindowRow, record_id)
            if window is None or window.factory_id != actor.factory_id:
                raise BambooOperationError("INSPECTION_WINDOW_NOT_FOUND", "检测任务不存在")
            record = session.get(BambooRecordRow, record_id)
            if record is None:  # pragma: no cover
                raise BambooOperationError("INSPECTION_WINDOW_NOT_FOUND", "检测任务不存在")
            if window.status == "EARLY_TERMINATED" and window.terminated_by == actor.actor_id:
                return self._inspection_window(window, record, now)
            if window.status not in {"OPEN", "CLAIMED"}:
                raise BambooOperationError("INSPECTION_WINDOW_CLOSED", "当前检测已结束")
            if now >= _utc(window.deadline_at):
                window.status = "EXPIRED"
                window.appeal_deadline_at = _utc(window.deadline_at) + timedelta(hours=24)
                window.revision += 1
                raise BambooOperationError("INSPECTION_WINDOW_EXPIRED", "两小时检测窗口已结束")
            window.status = "EARLY_TERMINATED"
            window.terminated_by = actor.actor_id
            window.terminated_at = now
            window.appeal_deadline_at = now + timedelta(hours=24)
            window.revision += 1
            self._notify_factory_role(
                session,
                factory_id=actor.factory_id,
                role=BambooRole.INSPECTOR,
                category="INSPECTION_TERMINATED",
                title="检测已由厂长提前终止",
                body=f"表单 {record.display_no} 的检测权限已停止，可在24小时内申诉。",
                link=f"/mobile/bamboo/{record_id}",
                payload={"record_id": record_id},
                now=now,
            )
            return self._inspection_window(window, record, now)

    def claim_inspection_appeal(
        self,
        record_id: str,
        *,
        actor: BambooActor,
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.INSPECTOR:
            raise BambooOperationError("INSPECTOR_REQUIRED", "仅检测人可以领取申诉")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            window = session.get(BambooInspectionWindowRow, record_id)
            if window is None or window.factory_id != actor.factory_id:
                raise BambooOperationError("INSPECTION_WINDOW_NOT_FOUND", "检测任务不存在")
            record = session.get(BambooRecordRow, record_id)
            if record is None:  # pragma: no cover
                raise BambooOperationError("INSPECTION_WINDOW_NOT_FOUND", "检测任务不存在")
            if window.appeal_deadline_at is None or now >= _utc(window.appeal_deadline_at):
                raise BambooOperationError("APPEAL_WINDOW_EXPIRED", "24小时申诉窗口已结束")
            if window.status not in {
                "EARLY_TERMINATED",
                "EXPIRED",
                "APPEAL_CLAIMED",
            }:
                raise BambooOperationError("APPEAL_NOT_AVAILABLE", "当前表单不能发起申诉")
            if window.claimed_by and window.claimed_by != actor.actor_id:
                raise BambooOperationError(
                    "APPEAL_RESERVED_FOR_ORIGINAL_INSPECTOR",
                    "申诉权保留给最初领取检测的检测员",
                )
            if window.appeal_claimed_by == actor.actor_id:
                return self._inspection_window(window, record, now)
            if window.appeal_claimed_by is not None:
                raise BambooOperationError("APPEAL_ALREADY_CLAIMED", "申诉已由另一名检测员领取")
            window.status = "APPEAL_CLAIMED"
            window.appeal_claimed_by = actor.actor_id
            window.appeal_claimed_at = now
            window.revision += 1
            return self._inspection_window(window, record, now)

    def submit_inspection_appeal(
        self,
        record_id: str,
        *,
        actor: BambooActor,
        target_stage: BambooStage,
        text_evidence: str,
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.INSPECTOR:
            raise BambooOperationError("INSPECTOR_REQUIRED", "仅检测人可以提交申诉")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            window = session.get(BambooInspectionWindowRow, record_id)
            if window is None or window.factory_id != actor.factory_id:
                raise BambooOperationError("INSPECTION_WINDOW_NOT_FOUND", "检测任务不存在")
            record = session.get(BambooRecordRow, record_id)
            if record is None:  # pragma: no cover
                raise BambooOperationError("INSPECTION_WINDOW_NOT_FOUND", "检测任务不存在")
            if window.appeal_deadline_at is None or now >= _utc(window.appeal_deadline_at):
                raise BambooOperationError("APPEAL_WINDOW_EXPIRED", "24小时申诉窗口已结束")
            if window.status != "APPEAL_CLAIMED" or window.appeal_claimed_by != actor.actor_id:
                raise BambooOperationError("APPEAL_CLAIM_REQUIRED", "请先领取申诉权")
            allowed = (
                {BambooStage.SORT}
                if record.form_type == BambooFormType.SORTING.value
                else {BambooStage.DIPPING, BambooStage.DRYING}
            )
            if target_stage not in allowed:
                raise BambooOperationError("INVALID_INSPECTION_STAGE", "申诉环节不属于当前表单")
            text = text_evidence.strip()
            if not text:
                raise BambooOperationError("INSPECTION_EVIDENCE_REQUIRED", "请填写申诉检测结果")
            window.status = "APPEAL_SUBMITTED"
            window.appeal_payload = {
                "target_stage": target_stage.value,
                "conclusion": "NONCONFORMING",
                "text_evidence": text,
            }
            window.appeal_submitted_at = now
            window.revision += 1
            self._notify_factory_role(
                session,
                factory_id=actor.factory_id,
                role=BambooRole.PLANT_MANAGER,
                category="APPEAL_SUBMITTED",
                title="收到检测申诉",
                body=f"表单 {record.display_no} 有新的检测申诉待审批。",
                link=f"/mobile/bamboo/{record_id}",
                payload={"record_id": record_id},
                now=now,
            )
            return self._inspection_window(window, record, now)

    def decide_inspection_appeal(
        self,
        record_id: str,
        *,
        actor: BambooActor,
        approve: bool,
        note: str,
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.PLANT_MANAGER:
            raise BambooOperationError("MANAGER_REQUIRED", "仅厂长可以审批检测申诉")
        now = datetime.now(UTC)
        target_stage: BambooStage | None = None
        appeal_text = ""
        recipient = ""
        with Session(self._engine) as session, session.begin():
            window = session.get(BambooInspectionWindowRow, record_id)
            if window is None or window.factory_id != actor.factory_id:
                raise BambooOperationError("INSPECTION_WINDOW_NOT_FOUND", "检测任务不存在")
            record = session.get(BambooRecordRow, record_id)
            if record is None:  # pragma: no cover
                raise BambooOperationError("INSPECTION_WINDOW_NOT_FOUND", "检测任务不存在")
            if window.status != "APPEAL_SUBMITTED" or not window.appeal_payload:
                raise BambooOperationError("APPEAL_NOT_PENDING", "当前没有待审批申诉")
            window.appeal_decision = "APPROVED" if approve else "REJECTED"
            window.appeal_decision_note = note
            window.appeal_decided_by = actor.actor_id
            window.appeal_decided_at = now
            window.status = "APPEAL_APPROVED" if approve else "APPEAL_REJECTED"
            window.revision += 1
            recipient = str(window.appeal_claimed_by or "")
            target_stage = BambooStage(str(window.appeal_payload["target_stage"]))
            appeal_text = str(window.appeal_payload["text_evidence"])
            if recipient:
                self._notify(
                    session,
                    recipient_actor_id=recipient,
                    category="APPEAL_DECIDED",
                    title="检测申诉已审批",
                    body=f"表单 {record.display_no} 的申诉已{'通过' if approve else '驳回'}。",
                    link=f"/mobile/bamboo/{record_id}",
                    payload={"record_id": record_id, "approved": approve},
                    now=now,
                )
            result = self._inspection_window(window, record, now)
            result["appeal_decision"] = window.appeal_decision
        if approve and target_stage is not None:
            return_result = self.selective_return(
                record_id,
                actor=actor,
                target_stages=[target_stage],
                reason=appeal_text,
                source="INSPECTION_APPEAL",
            )
            result["return"] = return_result
        return result

    def list_notifications(self, actor: BambooActor) -> dict[str, Any]:
        with Session(self._engine) as session:
            rows = session.scalars(
                select(MobileNotificationRow)
                .where(MobileNotificationRow.recipient_actor_id == actor.actor_id)
                .order_by(MobileNotificationRow.created_at.desc())
            ).all()
            return {"items": [self._notification(row) for row in rows]}

    def read_notification(self, notification_id: str, *, actor: BambooActor) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            row = session.get(MobileNotificationRow, notification_id)
            if row is None or row.recipient_actor_id != actor.actor_id:
                raise BambooOperationError("NOTIFICATION_NOT_FOUND", "消息不存在")
            if row.read_at is None:
                row.read_at = datetime.now(UTC)
            return self._notification(row)

    def list_role_options(self, actor: BambooActor) -> list[dict[str, Any]]:
        manager_roles = PRODUCTION_ROLES | {
            BambooRole.INSPECTOR.value,
            BambooRole.SUPERVISOR.value,
        }
        with Session(self._engine) as session:
            rows = session.scalars(
                select(BambooRoleDefinitionRow)
                .where(BambooRoleDefinitionRow.active.is_(True))
                .order_by(
                    BambooRoleDefinitionRow.category,
                    BambooRoleDefinitionRow.display_name,
                )
            ).all()
            if actor.role.value in manager_roles and actor.role is not BambooRole.PLANT_MANAGER:
                rows = [row for row in rows if row.self_requestable]
            elif actor.role is BambooRole.PLANT_MANAGER:
                rows = [row for row in rows if row.role_code in manager_roles]
            elif actor.role is not BambooRole.SYSTEM_ADMIN:
                rows = []
            return [
                {
                    "role_code": row.role_code,
                    "display_name": row.display_name,
                    "category": row.category,
                    "self_requestable": row.self_requestable,
                }
                for row in rows
            ]

    def list_factory_employees(self, actor: BambooActor) -> list[dict[str, Any]]:
        if actor.role not in {BambooRole.PLANT_MANAGER, BambooRole.SYSTEM_ADMIN}:
            raise BambooOperationError("MANAGER_REQUIRED", "仅厂长或管理员可查看人员")
        with Session(self._engine) as session:
            assignments = session.scalars(
                select(EmployeeBambooAssignmentRow)
                .where(
                    EmployeeBambooAssignmentRow.factory_id == actor.factory_id,
                    EmployeeBambooAssignmentRow.status == "ACTIVE",
                )
                .order_by(EmployeeBambooAssignmentRow.effective_at.desc())
            ).all()
            people: list[dict[str, Any]] = []
            for assignment in assignments:
                employee = session.get(
                    MasterDataRecordRow,
                    (assignment.employee_catalog, assignment.employee_code),
                )
                role = session.get(BambooRoleDefinitionRow, assignment.role_code)
                if employee is None or not employee.active:
                    continue
                people.append(
                    {
                        "employee_code": employee.code,
                        "employee_name": employee.display_name,
                        "role_code": assignment.role_code,
                        "role_name": (
                            role.display_name if role is not None else assignment.role_code
                        ),
                    }
                )
            return sorted(
                people,
                key=lambda item: (item["employee_name"], item["employee_code"]),
            )

    def create_factory_employee(
        self,
        *,
        actor: BambooActor,
        employee_name: str,
        initial_pin: str,
        role_code: str,
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.PLANT_MANAGER:
            raise BambooOperationError("MANAGER_REQUIRED", "仅厂长可新增本厂人员")
        manager_roles = PRODUCTION_ROLES | {
            BambooRole.INSPECTOR.value,
            BambooRole.SUPERVISOR.value,
        }
        if role_code not in manager_roles:
            raise BambooOperationError("ASSIGNMENT_FORBIDDEN", "厂长不能分配该职位")
        name = employee_name.strip()
        if not name:
            raise BambooOperationError("EMPLOYEE_NAME_REQUIRED", "请填写员工姓名")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            factory = session.get(BambooFactoryRow, actor.factory_id)
            role = session.get(BambooRoleDefinitionRow, role_code)
            if factory is None or not factory.active:
                raise BambooOperationError("FACTORY_NOT_FOUND", "当前工厂不存在或已停用")
            if role is None or not role.active:
                raise BambooOperationError(
                    "ROLE_NOT_PUBLISHED",
                    "该职位尚未由管理员发布或已经停用",
                )
            codes = session.scalars(
                select(MasterDataRecordRow.code).where(
                    MasterDataRecordRow.catalog == "employees",
                    MasterDataRecordRow.code.like("YG%"),
                )
            ).all()
            sequence = max(
                (int(code[2:]) for code in codes if code[2:].isdigit()),
                default=0,
            ) + 1
            employee_code = f"YG{sequence:04d}"
            session.add(
                MasterDataRecordRow(
                    catalog="employees",
                    code=employee_code,
                    display_name=name,
                    attributes={"factory_id": actor.factory_id},
                    active=True,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.actor_id,
                    updated_by=actor.actor_id,
                )
            )
            session.flush()
            salt, digest = hash_pin(initial_pin)
            session.add(
                MobileCredentialRow(
                    employee_catalog="employees",
                    employee_code=employee_code,
                    pin_salt=salt,
                    pin_hash=digest,
                    failed_attempts=0,
                    locked_until=None,
                    revision=1,
                    updated_at=now,
                )
            )
            session.add(
                MobileAccessProfileRow(
                    employee_catalog="employees",
                    employee_code=employee_code,
                    team_id=f"TEAM-{actor.factory_id}",
                    team_name=factory.name,
                    position=role.display_name,
                    roles=["WORKER"],
                    allowed_form_types=[],
                    allowed_processes=["BAMBOO_PROCESS"],
                    active=True,
                )
            )
            session.flush()
            assignment = EmployeeBambooAssignmentRow(
                assignment_id=f"MBA-{uuid4().hex}",
                employee_catalog="employees",
                employee_code=employee_code,
                factory_id=actor.factory_id,
                role_code=role_code,
                status="ACTIVE",
                effective_at=now,
                ended_at=None,
                created_by=actor.actor_id,
                created_at=now,
            )
            session.add(assignment)
            return {
                "employee_code": employee_code,
                "employee_name": name,
                "role_code": role_code,
                "role_name": role.display_name,
            }

    def list_actor_history(self, actor: BambooActor) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            rows = session.execute(
                select(BambooStageSubmissionRow, BambooRecordRow)
                .join(
                    BambooRecordRow,
                    BambooRecordRow.record_id == BambooStageSubmissionRow.record_id,
                )
                .where(
                    BambooStageSubmissionRow.actor_id == actor.actor_id,
                    BambooStageSubmissionRow.factory_id == actor.factory_id,
                )
                .order_by(BambooStageSubmissionRow.submitted_at.desc())
            ).all()
            history = [
                {
                    "activity_id": submission.submission_id,
                    "record_id": record.record_id,
                    "display_no": record.display_no,
                    "form_type": record.form_type,
                    "cage_no": str((record.base_info or {}).get("cage_no", "")),
                    "action": submission.stage_key,
                    "submitted_at": submission.submitted_at,
                    "current_stage": record.current_stage,
                    "status": record.status,
                }
                for submission, record in rows
            ]
            inspections = session.execute(
                select(BambooInspectionRow, BambooRecordRow)
                .join(
                    BambooRecordRow,
                    BambooRecordRow.record_id == BambooInspectionRow.record_id,
                )
                .where(
                    BambooInspectionRow.actor_id == actor.actor_id,
                    BambooInspectionRow.factory_id == actor.factory_id,
                )
                .order_by(BambooInspectionRow.signed_at.desc())
            ).all()
            history.extend(
                {
                    "activity_id": inspection.inspection_id,
                    "record_id": record.record_id,
                    "display_no": record.display_no,
                    "form_type": record.form_type,
                    "cage_no": str((record.base_info or {}).get("cage_no", "")),
                    "action": "INSPECTION",
                    "submitted_at": inspection.signed_at,
                    "current_stage": record.current_stage,
                    "status": record.status,
                }
                for inspection, record in inspections
            )
            return sorted(
                history,
                key=lambda item: item["submitted_at"],
                reverse=True,
            )

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
        serial_no: str | None,
        target_stage: BambooStage | None,
        moisture_points: list[Decimal],
        conclusion: str,
        note: str | None,
        text_evidence: str | None,
        device_id: str,
        request_id: str,
        idempotency_key: str,
        has_file_evidence: bool = False,
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.INSPECTOR:
            raise BambooOperationError("INSPECTOR_REQUIRED", "仅检测人可以登记检测记录")
        if target_stage is not None and target_stage not in {
            BambooStage.SORT,
            BambooStage.DIPPING,
            BambooStage.DRYING,
        }:
            raise BambooOperationError("INVALID_INSPECTION_STAGE", "检测流程只能选择前三个生产环节")
        now = datetime.now(UTC)
        canonical = json.dumps(
            {
                "record_id": record_id,
                "serial_no": serial_no,
                "target_stage": target_stage.value if target_stage else None,
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
            window = session.get(BambooInspectionWindowRow, record_id)
            if window is None:
                raise BambooOperationError("INSPECTION_WINDOW_NOT_OPEN", "主管审核后才开放检测")
            submitted = session.scalar(
                select(BambooInspectionRow).where(
                    BambooInspectionRow.record_id == record_id,
                    BambooInspectionRow.inspection_kind == "FORMAL",
                )
            )
            if submitted is not None:
                raise BambooOperationError(
                    "INSPECTION_ALREADY_SUBMITTED",
                    "该表单已完成一次正式检测",
                )
            if now >= _utc(window.deadline_at):
                if window.status in {"OPEN", "CLAIMED"}:
                    window.status = "EXPIRED"
                    window.appeal_deadline_at = _utc(window.deadline_at) + timedelta(hours=24)
                    window.revision += 1
                raise BambooOperationError("INSPECTION_WINDOW_EXPIRED", "两小时检测窗口已结束")
            if window.status != "CLAIMED" or window.claimed_by != actor.actor_id:
                raise BambooOperationError("INSPECTION_CLAIM_REQUIRED", "请先领取该检测任务")
            form_type = BambooFormType(record.form_type)
            allowed_targets = (
                {BambooStage.SORT}
                if form_type is BambooFormType.SORTING
                else {BambooStage.DIPPING, BambooStage.DRYING}
            )
            if target_stage is None:
                target_stage = (
                    BambooStage.SORT
                    if form_type is BambooFormType.SORTING
                    else BambooStage.DRYING
                )
            if target_stage not in allowed_targets:
                raise BambooOperationError(
                    "INVALID_INSPECTION_STAGE",
                    "检测目标必须属于当前独立表单",
                )
            if conclusion not in {"CONFORMING", "NONCONFORMING"}:
                raise BambooOperationError("INVALID_INSPECTION_CONCLUSION", "检测结论无效")
            text = (text_evidence or note or "").strip()
            if conclusion == "NONCONFORMING" and not text and not has_file_evidence:
                raise BambooOperationError(
                    "INSPECTION_EVIDENCE_REQUIRED",
                    "不合格检测至少填写文字或提交照片、录音",
                )
            average = (
                sum(moisture_points, Decimal("0")) / len(moisture_points)
                if moisture_points
                else None
            )
            row = BambooInspectionRow(
                inspection_id=str(uuid4()),
                record_id=record_id,
                serial_no=(serial_no or record.display_no).strip(),
                target_stage=target_stage.value,
                moisture_points=[str(value) for value in moisture_points],
                average_value=(str(average.quantize(Decimal("0.01"))) if average else ""),
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
                inspection_kind="FORMAL",
            )
            session.add(row)
            session.flush()
            if text:
                session.add(
                    BambooEvidenceAssetRow(
                        asset_id=str(uuid4()),
                        inspection_id=row.inspection_id,
                        evidence_type="TEXT",
                        file_id=None,
                        uri=None,
                        mime_type="text/plain",
                        size_bytes=len(text.encode()),
                        sha256=hashlib.sha256(text.encode()).hexdigest(),
                        text_content=text,
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
            window.status = "COMPLETED"
            window.inspection_id = row.inspection_id
            window.completed_at = now
            window.revision += 1
            session.flush()
            result = self._inspection(session, row)
            result["display_text"] = "检测合格" if conclusion == "CONFORMING" else "检测不合格"
            return result

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
        if actor.role is not BambooRole.SUPERVISOR and not (
            actor.role is BambooRole.PLANT_MANAGER and source == "INSPECTION_APPEAL"
        ):
            raise BambooOperationError("RETURN_FORBIDDEN", "由主管选择需要重写的流程")
        selected = set(target_stages)
        if not selected:
            raise BambooOperationError("INVALID_RETURN_STAGES", "请选择需要重写的生产环节")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            record = self._record(session, record_id, actor)
            form_type = BambooFormType(record.form_type)
            allowed_stages = (
                {BambooStage.SORT}
                if form_type is BambooFormType.SORTING
                else {BambooStage.DIPPING, BambooStage.DRYING}
            )
            if not selected <= allowed_stages:
                raise BambooOperationError(
                    "INVALID_RETURN_STAGES",
                    "退回环节必须属于当前独立表单",
                )
            invalidated_stages = {
                stage
                for selected_stage in selected
                for stage in REWORK_DEPENDENCIES[selected_stage]
                if stage
                in (
                    {
                        BambooStage.SORT,
                        BambooStage.SUPERVISOR,
                        BambooStage.PLANT_AUDIT,
                    }
                    if form_type is BambooFormType.SORTING
                    else {
                        BambooStage.DIPPING,
                        BambooStage.DRYING,
                        BambooStage.SUPERVISOR,
                        BambooStage.PLANT_AUDIT,
                    }
                )
            }
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
            if form_type is BambooFormType.SORTING:
                linked_records = session.scalars(
                    select(BambooRecordRow).where(
                        BambooRecordRow.source_record_id == record_id,
                        BambooRecordRow.form_type
                        == BambooFormType.DIPPING_DRYING.value,
                    )
                ).all()
                for linked_record in linked_records:
                    source_snapshot = dict(linked_record.source_snapshot or {})
                    source_snapshot.setdefault(
                        "original_revision",
                        source_snapshot.get("revision") or record.revision - 1,
                    )
                    source_snapshot.update(
                        {
                            "source_status": "UPSTREAM_CHANGED",
                            "latest_revision": record.revision,
                            "changed_at": now.isoformat(),
                        }
                    )
                    linked_record.source_snapshot = source_snapshot
                    linked_record.revision += 1
                    linked_record.updated_at = now
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
        del actor, to_role, reason
        raise BambooOperationError(
            "WORKER_TRANSFER_FORBIDDEN",
            "员工不能在线自行申请换岗，请线下联系厂长",
        )

    def create_personnel_transfer(
        self,
        *,
        actor: BambooActor,
        employee_code: str,
        to_role: str,
        target_factory_id: str,
        reason: str,
    ) -> dict[str, Any]:
        if actor.role not in {BambooRole.PLANT_MANAGER, BambooRole.SYSTEM_ADMIN}:
            raise BambooOperationError(
                "WORKER_TRANSFER_FORBIDDEN",
                "员工不能在线自行申请换岗，请线下联系厂长",
            )
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            assignment = session.scalar(
                select(EmployeeBambooAssignmentRow).where(
                    EmployeeBambooAssignmentRow.employee_catalog == "employees",
                    EmployeeBambooAssignmentRow.employee_code == employee_code,
                    EmployeeBambooAssignmentRow.status == "ACTIVE",
                )
            )
            if assignment is None:
                raise BambooOperationError("EMPLOYEE_NOT_FOUND", "员工没有有效在岗信息")
            target_factory = session.get(BambooFactoryRow, target_factory_id)
            target = session.get(BambooRoleDefinitionRow, to_role)
            if target_factory is None or not target_factory.active:
                raise BambooOperationError("FACTORY_NOT_FOUND", "目标工厂不存在或已停用")
            if target is None or not target.active:
                raise BambooOperationError("ROLE_NOT_PUBLISHED", "目标职位不存在或已停用")
            pending = session.scalar(
                select(BambooPersonnelTransferRow).where(
                    BambooPersonnelTransferRow.employee_code == employee_code,
                    BambooPersonnelTransferRow.status.in_(
                        ["TARGET_MANAGER_PENDING", "ADMIN_PENDING"]
                    ),
                )
            )
            if pending is not None:
                raise BambooOperationError("TRANSFER_ALREADY_PENDING", "员工已有待处理调动")
            if actor.role is BambooRole.SYSTEM_ADMIN:
                if to_role != BambooRole.PLANT_MANAGER.value:
                    raise BambooOperationError(
                        "MANAGER_REQUEST_REQUIRED",
                        "普通人员调动必须由原工厂厂长发起",
                    )
                transfer_type = "MANAGER_REPLACEMENT"
                status = "ADMIN_PENDING"
                source_decision = None
                source_manager_id = None
                source_decided_at = None
            else:
                if assignment.factory_id != actor.factory_id:
                    raise BambooOperationError(
                        "EMPLOYEE_OUTSIDE_FACTORY",
                        "厂长只能发起本厂员工调动",
                    )
                if to_role in {
                    BambooRole.PLANT_MANAGER.value,
                    BambooRole.FINANCE_APPROVER.value,
                    BambooRole.SYSTEM_ADMIN.value,
                }:
                    raise BambooOperationError(
                        "ADMIN_ONLY_ROLE",
                        "厂长、财务和管理员职位只能由管理员管理",
                    )
                transfer_type = (
                    "INTERNAL"
                    if assignment.factory_id == target_factory_id
                    else "CROSS_FACTORY"
                )
                status = (
                    "ADMIN_PENDING"
                    if transfer_type == "INTERNAL"
                    else "TARGET_MANAGER_PENDING"
                )
                source_decision = "APPROVED"
                source_manager_id = actor.actor_id
                source_decided_at = now
            if assignment.factory_id == target_factory_id and assignment.role_code == to_role:
                raise BambooOperationError("ROLE_UNCHANGED", "目标工厂和职位均未变化")
            row = BambooPersonnelTransferRow(
                transfer_id=str(uuid4()),
                employee_code=employee_code,
                transfer_type=transfer_type,
                source_factory_id=assignment.factory_id,
                target_factory_id=target_factory_id,
                from_role=assignment.role_code,
                to_role=to_role,
                reason=reason.strip(),
                status=status,
                requested_by=actor.actor_id,
                requested_at=now,
                source_manager_id=source_manager_id,
                source_manager_decision=source_decision,
                source_manager_decided_at=source_decided_at,
                target_manager_id=None,
                target_manager_decision=None,
                target_manager_decided_at=None,
                admin_id=None,
                admin_decision=None,
                admin_note=None,
                admin_decided_at=None,
                executed_at=None,
                revision=1,
            )
            session.add(row)
            session.flush()
            return self._personnel_transfer(row)

    def list_personnel_transfers(self, actor: BambooActor) -> list[dict[str, Any]]:
        if actor.role not in {BambooRole.PLANT_MANAGER, BambooRole.SYSTEM_ADMIN}:
            raise BambooOperationError("TRANSFER_VIEW_FORBIDDEN", "当前职务不能查看人员调动")
        with Session(self._engine) as session:
            query = select(BambooPersonnelTransferRow)
            if actor.role is BambooRole.PLANT_MANAGER:
                query = query.where(
                    (BambooPersonnelTransferRow.source_factory_id == actor.factory_id)
                    | (BambooPersonnelTransferRow.target_factory_id == actor.factory_id)
                )
            rows = session.scalars(
                query.order_by(BambooPersonnelTransferRow.requested_at.desc())
            ).all()
            return [self._personnel_transfer(row) for row in rows]

    def decide_personnel_transfer_as_manager(
        self,
        transfer_id: str,
        *,
        actor: BambooActor,
        approve: bool,
        note: str,
    ) -> dict[str, Any]:
        del note
        if actor.role is not BambooRole.PLANT_MANAGER:
            raise BambooOperationError("MANAGER_REQUIRED", "仅目标工厂厂长可以审批跨厂调动")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            row = session.get(BambooPersonnelTransferRow, transfer_id)
            if (
                row is None
                or row.transfer_type != "CROSS_FACTORY"
                or row.target_factory_id != actor.factory_id
            ):
                raise BambooOperationError("TRANSFER_NOT_FOUND", "跨厂调动不存在")
            if row.status != "TARGET_MANAGER_PENDING":
                raise BambooOperationError("TRANSFER_ALREADY_DECIDED", "调动已处理")
            row.target_manager_id = actor.actor_id
            row.target_manager_decision = "APPROVED" if approve else "REJECTED"
            row.target_manager_decided_at = now
            row.status = "ADMIN_PENDING" if approve else "REJECTED"
            row.revision += 1
            return self._personnel_transfer(row)

    def execute_personnel_transfer(
        self,
        transfer_id: str,
        *,
        actor: BambooActor,
        approve: bool,
        note: str,
    ) -> dict[str, Any]:
        if actor.role is not BambooRole.SYSTEM_ADMIN:
            raise BambooOperationError("ADMIN_REQUIRED", "仅管理员可以最终执行人员调动")
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            row = session.get(BambooPersonnelTransferRow, transfer_id)
            if row is None:
                raise BambooOperationError("TRANSFER_NOT_FOUND", "人员调动不存在")
            if row.transfer_type == "CROSS_FACTORY" and not (
                row.source_manager_decision == "APPROVED"
                and row.target_manager_decision == "APPROVED"
            ):
                raise BambooOperationError(
                    "BOTH_MANAGERS_REQUIRED",
                    "跨厂调动必须由两厂厂长同时同意",
                )
            if row.status != "ADMIN_PENDING":
                raise BambooOperationError("TRANSFER_NOT_READY", "人员调动尚未满足执行条件")
            row.admin_id = actor.actor_id
            row.admin_decision = "APPROVED" if approve else "REJECTED"
            row.admin_note = note
            row.admin_decided_at = now
            row.revision += 1
            if not approve:
                row.status = "REJECTED"
                return self._personnel_transfer(row)
            target_role = session.get(BambooRoleDefinitionRow, row.to_role)
            target_factory = session.get(BambooFactoryRow, row.target_factory_id)
            if target_role is None or not target_role.active:
                raise BambooOperationError("ROLE_NOT_PUBLISHED", "目标职位不存在或已停用")
            if target_factory is None or not target_factory.active:
                raise BambooOperationError("FACTORY_NOT_FOUND", "目标工厂不存在或已停用")
            if row.transfer_type == "MANAGER_REPLACEMENT":
                session.execute(
                    update(EmployeeBambooAssignmentRow)
                    .where(
                        EmployeeBambooAssignmentRow.factory_id == row.target_factory_id,
                        EmployeeBambooAssignmentRow.role_code == BambooRole.PLANT_MANAGER.value,
                        EmployeeBambooAssignmentRow.status == "ACTIVE",
                    )
                    .values(status="INACTIVE", ended_at=now)
                )
            session.execute(
                update(EmployeeBambooAssignmentRow)
                .where(
                    EmployeeBambooAssignmentRow.employee_code == row.employee_code,
                    EmployeeBambooAssignmentRow.status == "ACTIVE",
                )
                .values(status="INACTIVE", ended_at=now)
            )
            session.add(
                EmployeeBambooAssignmentRow(
                    assignment_id=f"MBA-{uuid4().hex}",
                    employee_catalog="employees",
                    employee_code=row.employee_code,
                    factory_id=row.target_factory_id,
                    role_code=row.to_role,
                    status="ACTIVE",
                    effective_at=now,
                    ended_at=None,
                    created_by=actor.actor_id,
                    created_at=now,
                )
            )
            profile = session.get(
                MobileAccessProfileRow,
                ("employees", row.employee_code),
            )
            if profile is not None:
                profile.team_id = f"TEAM-{row.target_factory_id}"
                profile.team_name = target_factory.name
                profile.position = target_role.display_name
            row.status = "EXECUTED"
            row.executed_at = now
            self._notify(
                session,
                recipient_actor_id=row.employee_code,
                category="PERSONNEL_TRANSFER_COMPLETED",
                title="人员调动已完成",
                body=f"你的工厂/职位已调整为 {target_factory.name} · {target_role.display_name}。",
                link="/mobile/profile",
                payload={"transfer_id": row.transfer_id},
                now=now,
            )
            session.flush()
            return self._personnel_transfer(row)
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
                target = session.get(BambooRoleDefinitionRow, row.to_role)
                if target is None or not target.active or not target.self_requestable:
                    raise BambooOperationError(
                        "ROLE_NOT_REQUESTABLE",
                        "目标职位已停用，请驳回申请并让员工重新选择",
                    )
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
                profile = session.get(
                    MobileAccessProfileRow,
                    ("employees", row.employee_code),
                )
                if profile is not None:
                    profile.position = target.display_name
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

    @staticmethod
    def _active_rule(
        session: Session,
        rule_key: str,
        factory_id: str,
    ) -> BambooPayrollRuleVersionRow | None:
        for scoped_factory in (factory_id, None):
            row = session.scalar(
                select(BambooPayrollRuleVersionRow)
                .where(
                    BambooPayrollRuleVersionRow.rule_key == rule_key,
                    BambooPayrollRuleVersionRow.factory_id == scoped_factory,
                    BambooPayrollRuleVersionRow.active.is_(True),
                )
                .order_by(
                    BambooPayrollRuleVersionRow.effective_at.desc(),
                    BambooPayrollRuleVersionRow.version.desc(),
                )
            )
            if row is not None:
                return row
        return None

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
    def _inspection_window(
        window: BambooInspectionWindowRow,
        record: BambooRecordRow,
        now: datetime,
    ) -> dict[str, Any]:
        return {
            "record_id": record.record_id,
            "display_no": record.display_no,
            "form_type": record.form_type,
            "cage_no": str((record.base_info or {}).get("cage_no", "")),
            "status": window.status,
            "opened_at": window.opened_at,
            "deadline_at": window.deadline_at,
            "inside_window": now < _utc(window.deadline_at),
            "claimed_by": window.claimed_by,
            "claimed_at": window.claimed_at,
            "completed_at": window.completed_at,
            "appeal_deadline_at": window.appeal_deadline_at,
            "appeal_claimed_by": window.appeal_claimed_by,
            "appeal_submitted_at": window.appeal_submitted_at,
            "appeal_decision": window.appeal_decision,
            "revision": window.revision,
        }

    @staticmethod
    def _notify(
        session: Session,
        *,
        recipient_actor_id: str,
        category: str,
        title: str,
        body: str,
        link: str | None,
        payload: dict[str, Any],
        now: datetime,
    ) -> None:
        session.add(
            MobileNotificationRow(
                notification_id=str(uuid4()),
                recipient_actor_id=recipient_actor_id,
                category=category,
                title=title,
                body=body,
                link=link,
                payload=payload,
                read_at=None,
                created_at=now,
            )
        )

    def _notify_factory_role(
        self,
        session: Session,
        *,
        factory_id: str,
        role: BambooRole,
        category: str,
        title: str,
        body: str,
        link: str | None,
        payload: dict[str, Any],
        now: datetime,
    ) -> None:
        recipients = session.scalars(
            select(EmployeeBambooAssignmentRow.employee_code).where(
                EmployeeBambooAssignmentRow.factory_id == factory_id,
                EmployeeBambooAssignmentRow.role_code == role.value,
                EmployeeBambooAssignmentRow.status == "ACTIVE",
            )
        ).all()
        for recipient in set(recipients):
            self._notify(
                session,
                recipient_actor_id=recipient,
                category=category,
                title=title,
                body=body,
                link=link,
                payload=payload,
                now=now,
            )

    @staticmethod
    def _notification(row: MobileNotificationRow) -> dict[str, Any]:
        return {
            "notification_id": row.notification_id,
            "category": row.category,
            "title": row.title,
            "body": row.body,
            "link": row.link,
            "payload": row.payload,
            "read_at": row.read_at,
            "created_at": row.created_at,
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

    @staticmethod
    def _personnel_transfer(row: BambooPersonnelTransferRow) -> dict[str, Any]:
        return {
            "transfer_id": row.transfer_id,
            "employee_code": row.employee_code,
            "transfer_type": row.transfer_type,
            "source_factory_id": row.source_factory_id,
            "target_factory_id": row.target_factory_id,
            "from_role": row.from_role,
            "to_role": row.to_role,
            "reason": row.reason,
            "status": row.status,
            "requested_by": row.requested_by,
            "requested_at": row.requested_at,
            "source_manager_decision": row.source_manager_decision,
            "target_manager_decision": row.target_manager_decision,
            "admin_decision": row.admin_decision,
            "admin_note": row.admin_note,
            "executed_at": row.executed_at,
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
