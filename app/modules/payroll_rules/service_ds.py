"""Governed payroll rules, immutable calculations and historical recalculation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    FinanceEffectiveRecordRow,
    FinanceLedgerEventRow,
    GovernedPayrollRuleVersionRow,
    PayrollAccessAuditRow,
    PayrollCalculationBatchRow,
    PayrollCalculationResultRow,
)


class PayrollError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class PayrollService:
    def __init__(
        self,
        engine: Engine,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(UTC))

    def create_rule(
        self,
        *,
        rule_key: str,
        name: str,
        factory_id: str,
        position: str,
        dsl: dict[str, Any],
        actor_id: str,
    ) -> dict[str, object]:
        # V1 Runtime Closure §9.1: factory_id must be real
        if not factory_id or not factory_id.strip():
            raise PayrollError("FACTORY_REQUIRED", "工资规则必须指定工厂。")
        # V1 Runtime Closure §9.2: validate metric against field registry
        self._validate_metric_for_position(dsl.get("metric", ""), position)
        normalized = self._validate_dsl(dsl)
        # V1 Runtime Closure §9.4: stable logical rule_key = factory + position
        stable_key = f"PAYROLL_{factory_id.strip().upper()}_{position.strip().upper()}"
        now = self._clock()
        with Session(self._engine) as session, session.begin():
            version = int(
                session.scalar(
                    select(func.max(GovernedPayrollRuleVersionRow.version)).where(
                        GovernedPayrollRuleVersionRow.rule_key == stable_key,
                        GovernedPayrollRuleVersionRow.factory_id == factory_id.strip(),
                    )
                )
                or 0
            ) + 1
            row = GovernedPayrollRuleVersionRow(
                rule_version_id=self._id("PRV"),
                rule_key=stable_key,
                name=name.strip(),
                factory_id=factory_id.strip(),
                position=position.strip().upper(),
                version=version,
                dsl=normalized,
                content_hash=self._hash(normalized),
                status="DRAFT",
                created_by=actor_id,
                created_at=now,
                review_note="",
            )
            session.add(row)
            payload = self._rule(row)
        return payload

    def submit_rule(self, rule_version_id: str) -> dict[str, object]:
        with Session(self._engine) as session, session.begin():
            row = self._rule_required(session, rule_version_id)
            if row.status != "DRAFT":
                raise PayrollError("RULE_STATE_INVALID", "只有草稿可提交审批。")
            row.status = "PENDING_APPROVAL"
            payload = self._rule(row)
        return payload

    def decide_rule(
        self,
        rule_version_id: str,
        *,
        approved: bool,
        actor_id: str,
        note: str,
    ) -> dict[str, object]:
        now = self._clock()
        with Session(self._engine) as session, session.begin():
            row = self._rule_required(session, rule_version_id)
            if row.status != "PENDING_APPROVAL":
                raise PayrollError("RULE_STATE_INVALID", "规则当前不可审批。")
            row.status = "APPROVED" if approved else "REJECTED"
            row.reviewed_by = actor_id
            row.reviewed_at = now
            row.review_note = note.strip()
            if approved:
                previous = session.scalars(
                    select(GovernedPayrollRuleVersionRow).where(
                        GovernedPayrollRuleVersionRow.rule_key == row.rule_key,
                        GovernedPayrollRuleVersionRow.factory_id == row.factory_id,
                        GovernedPayrollRuleVersionRow.status == "APPROVED",
                        GovernedPayrollRuleVersionRow.rule_version_id != row.rule_version_id,
                    )
                ).all()
                for item in previous:
                    item.status = "RETIRED"
            payload = self._rule(row)
        return payload

    def list_rules(self, *, approvals_only: bool = False) -> dict[str, object]:
        with Session(self._engine) as session:
            statement = select(GovernedPayrollRuleVersionRow).order_by(
                GovernedPayrollRuleVersionRow.created_at.desc()
            )
            if approvals_only:
                statement = statement.where(
                    GovernedPayrollRuleVersionRow.status == "PENDING_APPROVAL"
                )
            return {"items": [self._rule(row) for row in session.scalars(statement)]}

    def calculate(
        self,
        *,
        rule_version_id: str,
        period_start: str,
        period_end: str,
        actor_id: str,
        dry_run: bool = False,
    ) -> dict[str, object]:
        if dry_run:
            return self._trial_calculate(
                rule_version_id=rule_version_id,
                period_start=period_start,
                period_end=period_end,
            )
        return self._calculate(
            rule_version_id=rule_version_id,
            period_start=period_start,
            period_end=period_end,
            actor_id=actor_id,
            batch_type="NORMAL",
            source_batch_id=None,
        )

    def recalculate(
        self,
        *,
        source_batch_id: str,
        new_rule_version_id: str,
        actor_id: str,
    ) -> dict[str, object]:
        with Session(self._engine) as session:
            source = session.get(PayrollCalculationBatchRow, source_batch_id)
            if source is None or source.status != "CONFIRMED":
                raise PayrollError("SOURCE_BATCH_INVALID", "历史重算必须基于已确认批次。")
            period_start = source.period_start
            period_end = source.period_end
        return self._calculate(
            rule_version_id=new_rule_version_id,
            period_start=period_start,
            period_end=period_end,
            actor_id=actor_id,
            batch_type="RECALCULATION",
            source_batch_id=source_batch_id,
        )

    def _calculate(
        self,
        *,
        rule_version_id: str,
        period_start: str,
        period_end: str,
        actor_id: str,
        batch_type: str,
        source_batch_id: str | None,
    ) -> dict[str, object]:
        now = self._clock()
        with Session(self._engine) as session, session.begin():
            rule = self._rule_required(session, rule_version_id)
            if rule.status != "APPROVED":
                raise PayrollError("RULE_NOT_APPROVED", "未批准工资规则不能执行。")
            watermark = session.scalar(select(func.max(FinanceLedgerEventRow.occurred_at)))
            batch = PayrollCalculationBatchRow(
                batch_id=self._id("PCB"),
                batch_type=batch_type,
                factory_id=rule.factory_id,
                period_start=period_start,
                period_end=period_end,
                data_watermark=watermark.isoformat() if watermark else now.isoformat(),
                rule_version_id=rule_version_id,
                source_batch_id=source_batch_id,
                status="PENDING_FINANCE",
                created_by=actor_id,
                created_at=now,
            )
            session.add(batch)
            records = session.scalars(
                select(FinanceEffectiveRecordRow).where(
                    FinanceEffectiveRecordRow.factory_id == rule.factory_id,
                    FinanceEffectiveRecordRow.status == "ACTIVE",
                    FinanceEffectiveRecordRow.business_date >= period_start,
                    FinanceEffectiveRecordRow.business_date <= period_end,
                )
            ).all()
            originals: dict[str, str] = {}
            if source_batch_id:
                originals = {
                    row.root_submission_id: row.amount
                    for row in session.scalars(
                        select(PayrollCalculationResultRow).where(
                            PayrollCalculationResultRow.batch_id == source_batch_id
                        )
                    )
                }
            for record in records:
                amount = self._amount(rule.dsl, record.values)
                original = originals.get(record.root_submission_id)
                delta = (
                    self._money(amount - Decimal(original))
                    if original is not None
                    else None
                )
                session.add(
                    PayrollCalculationResultRow(
                        result_id=self._id("PCR"),
                        batch_id=batch.batch_id,
                        root_submission_id=record.root_submission_id,
                        employee_code=record.subject_employee_code,
                        factory_id=record.factory_id,
                        business_date=record.business_date,
                        rule_version_id=rule_version_id,
                        input_snapshot={
                            "effective_submission_id": record.effective_submission_id,
                            "values": record.values,
                            "data_watermark": batch.data_watermark,
                        },
                        amount=self._money(amount),
                        original_amount=original,
                        delta_amount=delta,
                        created_at=now,
                    )
                )
            payload = self._batch(batch)
            payload["result_count"] = len(records)
        return payload

    def _trial_calculate(
        self,
        *,
        rule_version_id: str,
        period_start: str,
        period_end: str,
    ) -> dict[str, object]:
        """Dry-run calculation: returns results without creating any persistent records.

        V1 Runtime Closure §9.3: DRAFT and PENDING_APPROVAL rules can be trialed.
        Only APPROVED rules can execute official (non-dry-run) calculations.
        """
        with Session(self._engine) as session:
            rule = self._rule_required(session, rule_version_id)
            # V1 §9.3: Allow dry_run for DRAFT and PENDING_APPROVAL (not just APPROVED)
            if rule.status not in {"DRAFT", "PENDING_APPROVAL", "APPROVED"}:
                raise PayrollError(
                    "RULE_NOT_TRIALABLE",
                    f"状态为 {rule.status} 的规则不能试算。仅草稿、待审批和已生效规则可试算。",
                )
            records = session.scalars(
                select(FinanceEffectiveRecordRow).where(
                    FinanceEffectiveRecordRow.factory_id == rule.factory_id,
                    FinanceEffectiveRecordRow.status == "ACTIVE",
                    FinanceEffectiveRecordRow.business_date >= period_start,
                    FinanceEffectiveRecordRow.business_date <= period_end,
                )
            ).all()
            # Fetch existing confirmed results for comparison
            confirmed = session.scalars(
                select(PayrollCalculationResultRow)
                .join(
                    PayrollCalculationBatchRow,
                    PayrollCalculationBatchRow.batch_id
                    == PayrollCalculationResultRow.batch_id,
                )
                .where(
                    PayrollCalculationBatchRow.status == "CONFIRMED",
                    PayrollCalculationResultRow.rule_version_id == rule_version_id,
                )
            ).all()
            confirmed_map: dict[str, str] = {
                row.root_submission_id: row.amount for row in confirmed
            }
            trial_items: list[dict[str, object]] = []
            for record in records:
                amount = self._amount(rule.dsl, record.values)
                original = confirmed_map.get(record.root_submission_id)
                delta = (
                    self._money(amount - Decimal(original))
                    if original is not None
                    else None
                )
                trial_items.append({
                    "employee_code": record.subject_employee_code,
                    "factory_id": record.factory_id,
                    "business_date": record.business_date,
                    "amount": self._money(amount),
                    "original_amount": original,
                    "delta_amount": delta,
                })
            return {
                "items": trial_items,
                "result_count": len(records),
                "rule": {
                    "rule_version_id": rule.rule_version_id,
                    "name": rule.name,
                    "factory_id": rule.factory_id,
                    "version": rule.version,
                    "dsl": rule.dsl,
                    "status": rule.status,
                },
                "dry_run": True,
            }

    def confirm_batch(self, batch_id: str, *, actor_id: str) -> dict[str, object]:
        now = self._clock()
        with Session(self._engine) as session, session.begin():
            batch = session.get(PayrollCalculationBatchRow, batch_id)
            if batch is None or batch.status != "PENDING_FINANCE":
                raise PayrollError("BATCH_STATE_INVALID", "批次当前不可确认。")
            batch.status = "CONFIRMED"
            batch.confirmed_by = actor_id
            batch.confirmed_at = now
            if batch.source_batch_id:
                source = session.get(
                    PayrollCalculationBatchRow, batch.source_batch_id
                )
                if source is not None:
                    source.status = "SUPERSEDED"
            payload = self._batch(batch)
        return payload

    def list_batches(self) -> dict[str, object]:
        with Session(self._engine) as session:
            rows = session.scalars(
                select(PayrollCalculationBatchRow).order_by(
                    PayrollCalculationBatchRow.created_at.desc()
                )
            )
            return {"items": [self._batch(row) for row in rows]}

    def list_official(
        self,
        *,
        factory_id: str | None = None,
        employee_code: str | None = None,
        actor_id: str = "",
        actor_role: str = "",
    ) -> dict[str, object]:
        now = self._clock()
        with Session(self._engine) as session, session.begin():
            statement = (
                select(PayrollCalculationResultRow)
                .join(
                    PayrollCalculationBatchRow,
                    PayrollCalculationBatchRow.batch_id
                    == PayrollCalculationResultRow.batch_id,
                )
                .where(PayrollCalculationBatchRow.status == "CONFIRMED")
                .order_by(PayrollCalculationResultRow.business_date.desc())
            )
            if factory_id:
                statement = statement.where(
                    PayrollCalculationResultRow.factory_id == factory_id
                )
            if employee_code:
                statement = statement.where(
                    PayrollCalculationResultRow.employee_code == employee_code
                )
            rows = session.scalars(statement).all()
            if actor_id:
                session.add(
                    PayrollAccessAuditRow(
                        audit_id=self._id("PAA"),
                        actor_id=actor_id,
                        actor_role=actor_role,
                        requested_factory_id=factory_id or "*",
                        requested_employee_code=employee_code or "*",
                        result_count=len(rows),
                        viewed_at=now,
                    )
                )
            return {
                "items": [
                    {
                        "result_id": row.result_id,
                        "batch_id": row.batch_id,
                        "employee_code": row.employee_code,
                        "factory_id": row.factory_id,
                        "business_date": row.business_date,
                        "rule_version_id": row.rule_version_id,
                        "amount": row.amount,
                        "original_amount": row.original_amount,
                        "delta_amount": row.delta_amount,
                    }
                    for row in rows
                ]
            }

    # ── V1 Runtime Closure §9.2: Field Registry backend authority ──

    def _validate_metric_for_position(
        self, metric: str, position: str
    ) -> None:
        """Validate that the metric is registered and numeric for this position.

        V1 Final Verification §6.2: FAIL CLOSED.
        - Registry not seeded for position → reject
        - Field not in registry → reject
        - Field is non-numeric (STRING/JSON) → reject
        - Only INTEGER/DECIMAL fields are allowed in payroll formulas
        """
        from app.adapters.database.models import PayrollFieldRegistryRow

        metric_key = str(metric).strip()
        position_key = str(position).strip().upper()
        if not metric_key:
            raise PayrollError("DSL_INVALID", "工资指标字段不能为空。")

        with Session(self._engine) as session:
            registered = session.scalar(
                select(PayrollFieldRegistryRow).where(
                    PayrollFieldRegistryRow.position_role == position_key,
                    PayrollFieldRegistryRow.field_key == metric_key,
                    PayrollFieldRegistryRow.active.is_(True),
                )
            )
            if registered is None:
                # Check if any fields exist for this position at all
                any_fields = session.scalar(
                    select(PayrollFieldRegistryRow).where(
                        PayrollFieldRegistryRow.position_role == position_key,
                        PayrollFieldRegistryRow.active.is_(True),
                    ).limit(1)
                )
                if any_fields is None:
                    raise PayrollError(
                        "PAYROLL_FIELD_REGISTRY_NOT_CONFIGURED",
                        f"职位 {position_key} 的工资字段注册表尚未配置。"
                        f"请联系管理员完成系统初始化。",
                    )
                allowed = session.scalars(
                    select(PayrollFieldRegistryRow.field_key).where(
                        PayrollFieldRegistryRow.position_role == position_key,
                        PayrollFieldRegistryRow.active.is_(True),
                    )
                ).all()
                raise PayrollError(
                    "PAYROLL_FIELD_NOT_ALLOWED",
                    f"字段 {metric_key!r} 未在 {position_key} 的工资字段注册表中。"
                    f"允许的字段: {sorted(allowed)}",
                )

            # §6.2: Only numeric fields can be used in formulas
            if registered.data_type not in {"INTEGER", "DECIMAL"}:
                raise PayrollError(
                    "PAYROLL_FIELD_NOT_NUMERIC",
                    f"字段 {metric_key!r}（{registered.display_name}）"
                    f"的数据类型为 {registered.data_type}，不能用于工资公式计算。"
                    f"仅 INTEGER 和 DECIMAL 类型的字段可作为计薪依据。",
                )

    def _validate_dsl(self, dsl: dict[str, Any]) -> dict[str, str]:
        metric = str(dsl.get("metric", "")).strip()
        if not metric.replace("_", "").isalnum():
            raise PayrollError("DSL_INVALID", "工资指标字段无效。")
        try:
            rate = Decimal(str(dsl.get("rate", "")))
            base = Decimal(str(dsl.get("base", "0")))
        except InvalidOperation as error:
            raise PayrollError("DSL_INVALID", "工资倍率和基础金额必须是数字。") from error
        if rate < 0:
            raise PayrollError("DSL_INVALID", "工资倍率不能为负数。")
        normalized: dict[str, str] = {"metric": metric, "rate": str(rate), "base": str(base)}
        # V1 Runtime Closure §9.5: optional grade/rank lookup
        lookup = dsl.get("lookup")
        if lookup is not None:
            if not isinstance(lookup, dict):
                raise PayrollError("DSL_INVALID", "lookup 必须是字典。")
            lookup_field = str(lookup.get("field", "")).strip()
            if not lookup_field:
                raise PayrollError("DSL_INVALID", "lookup.field 不能为空。")
            lookup_values = lookup.get("values")
            if not isinstance(lookup_values, dict) or not lookup_values:
                raise PayrollError("DSL_INVALID", "lookup.values 必须是非空字典。")
            norm_values: dict[str, str] = {}
            for k, v in lookup_values.items():
                if not isinstance(k, str) or not isinstance(v, (str, int, float)):
                    raise PayrollError(
                        "DSL_INVALID",
                        "lookup.values 键必须是字符串，值必须是数字。",
                    )
                try:
                    dec = Decimal(str(v))
                except InvalidOperation as error:
                    raise PayrollError(
                        "DSL_INVALID",
                        f"lookup.values[{k!r}] 不是有效数字。",
                    ) from error
                norm_values[k] = str(dec)
            # Validate lookup.field against PayrollFieldRegistry (must be STRING)
            self._validate_lookup_field_for_registry(lookup_field)
            normalized["lookup.field"] = lookup_field
            normalized["lookup.values"] = json.dumps(
                norm_values, sort_keys=True, ensure_ascii=False,
            )
        return normalized

    def _validate_lookup_field_for_registry(self, field_key: str) -> None:
        """Validate that a lookup field is registered and of STRING type."""
        from app.adapters.database.models import PayrollFieldRegistryRow

        with Session(self._engine) as session:
            registered = session.scalar(
                select(PayrollFieldRegistryRow).where(
                    PayrollFieldRegistryRow.field_key == field_key,
                    PayrollFieldRegistryRow.active.is_(True),
                )
            )
            if registered is None:
                raise PayrollError(
                    "PAYROLL_LOOKUP_FIELD_NOT_REGISTERED",
                    f"评级字段 {field_key!r} 未在工资字段注册表中。"
                    f"仅注册的 STRING 类型字段可作为评级依据。",
                )
            if registered.data_type != "STRING":
                raise PayrollError(
                    "PAYROLL_LOOKUP_FIELD_NOT_STRING",
                    f"评级字段 {field_key!r}（{registered.display_name}）"
                    f"的数据类型为 {registered.data_type}，评级字段必须是 STRING 类型。",
                )

    @classmethod
    def _amount(cls, dsl: dict[str, Any], values: dict[str, Any]) -> Decimal:
        try:
            metric = Decimal(str(values.get(str(dsl["metric"]), "0")))
            result = metric * Decimal(str(dsl["rate"])) + Decimal(str(dsl["base"]))
            # V1 Runtime Closure §9.5: optional grade/rank lookup multiplier
            lookup_field = dsl.get("lookup.field")
            if lookup_field:
                lookup_values: dict[str, str] = json.loads(str(dsl["lookup.values"]))
                actual_grade = str(values.get(str(lookup_field), "")).strip()
                multiplier_str = lookup_values.get(actual_grade)
                if multiplier_str is None:
                    raise PayrollError(
                        "PAYROLL_LOOKUP_MISSING",
                        f"员工评级 {actual_grade!r} 不在工资规则配置的评级表中。"
                        f"可用评级: {sorted(lookup_values.keys())}",
                    )
                result *= Decimal(multiplier_str)
            return result
        except InvalidOperation as error:
            raise PayrollError("PAYROLL_INPUT_INVALID", "工资计算输入不是数字。") from error

    @staticmethod
    def _money(value: Decimal) -> str:
        return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:16].upper()}"

    @staticmethod
    def _rule(row: GovernedPayrollRuleVersionRow) -> dict[str, object]:
        return {
            "rule_version_id": row.rule_version_id,
            "rule_key": row.rule_key,
            "name": row.name,
            "factory_id": row.factory_id,
            "position": row.position,
            "version": row.version,
            "dsl": row.dsl,
            "content_hash": row.content_hash,
            "status": row.status,
            "created_by": row.created_by,
            "reviewed_by": row.reviewed_by,
            "review_note": row.review_note,
        }

    @staticmethod
    def _batch(row: PayrollCalculationBatchRow) -> dict[str, object]:
        return {
            "batch_id": row.batch_id,
            "batch_type": row.batch_type,
            "factory_id": row.factory_id,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "data_watermark": row.data_watermark,
            "rule_version_id": row.rule_version_id,
            "source_batch_id": row.source_batch_id,
            "status": row.status,
            "created_by": row.created_by,
            "confirmed_by": row.confirmed_by,
        }

    @staticmethod
    def _rule_required(
        session: Session, rule_version_id: str
    ) -> GovernedPayrollRuleVersionRow:
        row = session.get(GovernedPayrollRuleVersionRow, rule_version_id)
        if row is None:
            raise PayrollError("RULE_NOT_FOUND", "工资规则版本不存在。")
        return row
