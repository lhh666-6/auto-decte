"""Safe multi-round business discovery; proposals never execute automatically."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BusinessDiscoveryMessageRow,
    BusinessDiscoverySessionRow,
    BusinessLogicBaselineRow,
    BusinessRuleConfirmationRow,
)


class BusinessDiscoveryError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _now() -> datetime:
    return datetime.now(UTC)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:16]}"


class BusinessDiscoveryService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_session(
        self,
        *,
        title: str,
        source_refs: list[str],
        actor_id: str,
    ) -> dict[str, Any]:
        now = _now()
        row = BusinessDiscoverySessionRow(
            session_id=_id("discovery"),
            title=title,
            status="OPEN",
            source_refs=source_refs,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        with Session(self._engine) as session, session.begin():
            session.add(row)
            session.flush()
            return self._session_payload(row)

    def add_message(
        self,
        session_id: str,
        *,
        content: str,
    ) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            discovery = session.get(BusinessDiscoverySessionRow, session_id)
            if discovery is None:
                raise BusinessDiscoveryError("DISCOVERY_NOT_FOUND", "业务梳理会话不存在。")
            if discovery.status != "OPEN":
                raise BusinessDiscoveryError("DISCOVERY_CLOSED", "业务梳理会话已确认关闭。")
            now = _now()
            session.add(
                BusinessDiscoveryMessageRow(
                    message_id=_id("message"),
                    session_id=session_id,
                    role="FINANCE",
                    content=content,
                    created_at=now,
                )
            )
            # The proposal is deliberately non-executable. A configured DS provider may
            # later enrich the structured content, but cannot change this state.
            rule = BusinessRuleConfirmationRow(
                rule_id=_id("rule"),
                session_id=session_id,
                version=1,
                content_json={
                    "statement": content,
                    "kind": "BUSINESS_RULE_DRAFT",
                    "questions": ["适用工厂和岗位是否已完整确认？"],
                },
                source_refs=discovery.source_refs,
                confidence=50,
                status="PROPOSED",
                confirmed_by=None,
                confirmed_at=None,
                finance_note="",
            )
            session.add(rule)
            discovery.updated_at = now
            session.flush()
            return {
                "session": self._session_payload(discovery),
                "proposed_rules": [self._rule_payload(rule)],
                "assistant_message": "已生成待确认规则草稿；确认前不会进入执行流程。",
            }

    def confirm(
        self,
        session_id: str,
        *,
        rule_ids: list[str],
        note: str,
        actor_id: str,
    ) -> dict[str, Any]:
        with Session(self._engine) as session, session.begin():
            discovery = session.get(BusinessDiscoverySessionRow, session_id)
            if discovery is None:
                raise BusinessDiscoveryError("DISCOVERY_NOT_FOUND", "业务梳理会话不存在。")
            rules = list(
                session.scalars(
                    select(BusinessRuleConfirmationRow).where(
                        BusinessRuleConfirmationRow.session_id == session_id,
                        BusinessRuleConfirmationRow.rule_id.in_(rule_ids),
                    )
                )
            )
            if len(rules) != len(set(rule_ids)) or not rules:
                raise BusinessDiscoveryError("RULE_NOT_FOUND", "待确认规则不存在。")
            now = _now()
            for rule in rules:
                if rule.status not in {"PROPOSED", "PENDING_CONFIRMATION"}:
                    raise BusinessDiscoveryError("RULE_ALREADY_DECIDED", "规则已经处理。")
                rule.status = "CONFIRMED"
                rule.confirmed_by = actor_id
                rule.confirmed_at = now
                rule.finance_note = note
            latest = session.scalar(select(func.max(BusinessLogicBaselineRow.version))) or 0
            baseline = BusinessLogicBaselineRow(
                baseline_id=_id("baseline"),
                version=int(latest) + 1,
                content_json={
                    "session_id": session_id,
                    "rules": [rule.content_json for rule in rules],
                    "source_refs": discovery.source_refs,
                    "unresolved_questions": [],
                },
                status="CONFIRMED",
                confirmed_by=actor_id,
                confirmed_at=now,
            )
            session.add(baseline)
            discovery.status = "CONFIRMED"
            discovery.updated_at = now
            session.flush()
            return {
                "rules": [self._rule_payload(rule) for rule in rules],
                "baseline": {
                    "baseline_id": baseline.baseline_id,
                    "version": baseline.version,
                    "status": baseline.status,
                    "content_json": baseline.content_json,
                    "confirmed_by": baseline.confirmed_by,
                    "confirmed_at": baseline.confirmed_at,
                },
            }

    @staticmethod
    def _session_payload(row: BusinessDiscoverySessionRow) -> dict[str, Any]:
        return {
            "session_id": row.session_id,
            "title": row.title,
            "status": row.status,
            "source_refs": row.source_refs,
            "created_by": row.created_by,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _rule_payload(row: BusinessRuleConfirmationRow) -> dict[str, Any]:
        return {
            "rule_id": row.rule_id,
            "session_id": row.session_id,
            "version": row.version,
            "content_json": row.content_json,
            "source_refs": row.source_refs,
            "confidence": row.confidence,
            "status": row.status,
            "executable": row.status == "CONFIRMED",
            "confirmed_by": row.confirmed_by,
            "confirmed_at": row.confirmed_at,
            "finance_note": row.finance_note,
        }
