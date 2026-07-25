"""Management Salary Service — Admin-managed fixed salaries.

Admin creates/edits; Finance has read-only access.
Each new version supersedes the previous; history is preserved.

V1 Final Verification §7: effective_from is authoritative.
- Future-dated salaries do NOT prematurely supersede current.
- get_current filters by effective_from <= today.
- effective_until is populated when a version is superseded.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import ManagementSalaryVersionRow


class ManagementSalaryError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _now() -> datetime:
    return datetime.now(UTC)


def _today_str() -> str:
    """Return today's date as YYYY-MM-DD for string comparison with effective_from."""
    return _now().strftime("%Y-%m-%d")


def _id() -> str:
    return str(uuid4())


class ManagementSalaryService:
    """Admin-managed fixed salaries for management positions."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_salary(
        self,
        *,
        employee_code: str,
        factory_id: str,
        position_snapshot: str,
        role_code_snapshot: str,
        salary_type: str,
        amount: str,
        effective_from: str,
        created_by: str,
    ) -> dict[str, Any]:
        # Validate effective_from format
        if not _is_valid_date_str(effective_from):
            raise ManagementSalaryError(
                "INVALID_EFFECTIVE_DATE",
                f"生效日期格式无效: {effective_from!r}，请使用 YYYY-MM-DD 格式",
            )

        today = _today_str()
        with Session(self._engine) as session, session.begin():
            latest = session.scalar(
                select(ManagementSalaryVersionRow)
                .where(ManagementSalaryVersionRow.employee_code == employee_code)
                .order_by(ManagementSalaryVersionRow.version.desc())
                .limit(1)
            )
            next_version = (latest.version + 1) if latest else 1
            row = ManagementSalaryVersionRow(
                salary_version_id=_id(),
                employee_code=employee_code,
                factory_id=factory_id,
                position_snapshot=position_snapshot,
                role_code_snapshot=role_code_snapshot,
                salary_type=salary_type,
                amount=amount,
                effective_from=effective_from,
                version=next_version,
                status="PUBLISHED",
                created_by=created_by,
                created_at=_now(),
                supersedes_version_id=latest.salary_version_id if latest else None,
            )

            # §7 Bug A fix: Only supersede previous version if the new one
            # is already effective (effective_from <= today). Future-dated
            # salaries coexist as PUBLISHED with the current one.
            if latest and latest.status == "PUBLISHED":
                if effective_from <= today:
                    # New version takes effect immediately — retire the old one
                    latest.status = "SUPERSEDED"
                    # §7 Bug E fix: Record when the old version stopped being effective
                    latest.effective_until = effective_from
                # else: future-dated — leave previous version as PUBLISHED
                # Both versions coexist until the future date arrives

            session.add(row)
            return self._to_dict(row)

    def get_current(self, employee_code: str) -> dict[str, Any] | None:
        """Return the currently-effective salary (effective_from <= today)."""
        today = _today_str()
        with Session(self._engine) as session:
            row = session.scalar(
                select(ManagementSalaryVersionRow)
                .where(
                    ManagementSalaryVersionRow.employee_code == employee_code,
                    ManagementSalaryVersionRow.status == "PUBLISHED",
                    ManagementSalaryVersionRow.effective_from <= today,
                )
                .order_by(ManagementSalaryVersionRow.effective_from.desc())
                .limit(1)
            )
            return self._to_dict(row) if row else None

    def list_salaries(
        self, factory_id: str | None = None
    ) -> list[dict[str, Any]]:
        """List currently-effective salaries (effective_from <= today)."""
        today = _today_str()
        with Session(self._engine) as session:
            query = select(ManagementSalaryVersionRow).where(
                ManagementSalaryVersionRow.status == "PUBLISHED",
                ManagementSalaryVersionRow.effective_from <= today,
            )
            if factory_id:
                query = query.where(
                    ManagementSalaryVersionRow.factory_id == factory_id
                )
            rows = session.scalars(
                query.order_by(
                    ManagementSalaryVersionRow.employee_code,
                    ManagementSalaryVersionRow.effective_from.desc(),
                )
            ).all()
            # Deduplicate: latest effective version per employee
            seen: set[str] = set()
            result: list[dict[str, Any]] = []
            for row in rows:
                if row.employee_code not in seen:
                    seen.add(row.employee_code)
                    result.append(self._to_dict(row))
            return result

    @staticmethod
    def _to_dict(row: ManagementSalaryVersionRow) -> dict[str, Any]:
        return {
            "salary_version_id": row.salary_version_id,
            "employee_code": row.employee_code,
            "factory_id": row.factory_id,
            "position_snapshot": row.position_snapshot,
            "role_code_snapshot": row.role_code_snapshot,
            "salary_type": row.salary_type,
            "amount": row.amount,
            "effective_from": row.effective_from,
            "effective_until": row.effective_until,
            "version": row.version,
            "status": row.status,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "supersedes_version_id": row.supersedes_version_id,
        }


def _is_valid_date_str(value: str) -> bool:
    """Validate YYYY-MM-DD format."""
    if len(value) != 10:
        return False
    if value[4] != "-" or value[7] != "-":
        return False
    try:
        _year, month, day = int(value[:4]), int(value[5:7]), int(value[8:10])
        if not (1 <= month <= 12):
            return False
        if not (1 <= day <= 31):
            return False
        return True
    except (ValueError, IndexError):
        return False
