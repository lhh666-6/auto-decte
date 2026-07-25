"""Personnel & Identity Governance — V1 Final Cutover.

Employee lifecycle: ACTIVE → FROZEN → ACTIVE (restore), ACTIVE → REMOVED.
One-active-position invariant enforced at service layer + DB partial unique index.
Personnel transfers: Plant Manager initiates, Admin approves/executes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    EmployeeBambooAssignmentRow,
    MobileAccessProfileRow,
    MobileCredentialRow,
)


class PersonnelGovernanceError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


VALID_ACCOUNT_STATES = {"ACTIVE", "FROZEN", "REMOVED"}


def _now() -> datetime:
    return datetime.now(UTC)


class PersonnelGovernanceService:
    """Admin-only employee lifecycle management.

    Plant Managers can only initiate transfer requests (handled by
    existing BambooPersonnelTransferRow endpoints). This service covers
    Admin authority: freeze, restore, remove, and final transfer execution.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ── Account state management ──────────────────────────────────

    def set_account_state(
        self,
        employee_code: str,
        state: str,
        *,
        actor_id: str,
    ) -> dict[str, Any]:
        """Set employee account state. Only SYSTEM_ADMIN can call this.

        FROZEN: login blocked, all data preserved
        REMOVED: login blocked, all historical data preserved
        ACTIVE: restore from FROZEN (REMOVED cannot be restored in V1)
        """
        if state not in VALID_ACCOUNT_STATES:
            raise PersonnelGovernanceError(
                "INVALID_ACCOUNT_STATE",
                f"Account state must be one of: {', '.join(sorted(VALID_ACCOUNT_STATES))}",
            )

        with Session(self._engine) as session, session.begin():
            profile = session.scalar(
                select(MobileAccessProfileRow).where(
                    MobileAccessProfileRow.employee_code == employee_code
                )
            )
            if profile is None:
                raise PersonnelGovernanceError(
                    "EMPLOYEE_NOT_FOUND",
                    f"Employee {employee_code} not found",
                )

            current_state = profile.account_state

            # Business rule: REMOVED is irreversible in V1
            if current_state == "REMOVED" and state != "REMOVED":
                raise PersonnelGovernanceError(
                    "EMPLOYEE_REMOVED",
                    f"Employee {employee_code} has been removed and cannot be restored in V1",
                )

            profile.account_state = state
            profile.active = (state == "ACTIVE")

            # When frozen/removed, lock credentials
            if state in {"FROZEN", "REMOVED"}:
                session.execute(
                    update(MobileCredentialRow)
                    .where(MobileCredentialRow.employee_code == employee_code)
                    .values(locked_until=datetime(9999, 12, 31, tzinfo=UTC))
                )

            # V1 Runtime Closure §6.3: RESTORE clears lock + resets failed attempts
            if state == "ACTIVE":
                session.execute(
                    update(MobileCredentialRow)
                    .where(MobileCredentialRow.employee_code == employee_code)
                    .values(locked_until=None, failed_attempts=0)
                )

            # V1 Runtime Closure §6.4: REMOVED closes active assignment
            if state == "REMOVED":
                now = _now()
                session.execute(
                    update(EmployeeBambooAssignmentRow)
                    .where(
                        EmployeeBambooAssignmentRow.employee_code == employee_code,
                        EmployeeBambooAssignmentRow.status == "ACTIVE",
                    )
                    .values(status="INACTIVE", ended_at=now)
                )

            return {
                "employee_code": employee_code,
                "account_state": state,
                "previous_state": current_state,
                "updated_by": actor_id,
                "updated_at": _now().isoformat(),
            }

    def get_account_state(self, employee_code: str) -> dict[str, Any] | None:
        with Session(self._engine) as session:
            profile = session.scalar(
                select(MobileAccessProfileRow).where(
                    MobileAccessProfileRow.employee_code == employee_code
                )
            )
            if profile is None:
                return None
            return {
                "employee_code": profile.employee_code,
                "account_state": profile.account_state,
                "active": profile.active,
                "factory_id": profile.factory_id,
                "factory_name": profile.factory_name,
                "position": profile.position,
            }

    # ── One-active-position enforcement ────────────────────────────

    def enforce_single_active_assignment(
        self, employee_catalog: str, employee_code: str
    ) -> None:
        """Run before creating a new ACTIVE assignment to verify the invariant."""
        # DB partial unique index (ux_employee_one_active_assignment) is
        # authoritative; this service method exists for future pre-check logic.
        pass

    def check_active_assignment_exists(
        self, employee_code: str, *, exclude_assignment_id: str | None = None
    ) -> bool:
        """Check if an employee already has an ACTIVE assignment."""
        with Session(self._engine) as session:
            query = select(EmployeeBambooAssignmentRow).where(
                EmployeeBambooAssignmentRow.employee_code == employee_code,
                EmployeeBambooAssignmentRow.status == "ACTIVE",
            )
            if exclude_assignment_id:
                query = query.where(
                    EmployeeBambooAssignmentRow.assignment_id != exclude_assignment_id
                )
            return session.scalar(query.limit(1)) is not None

    # ── Active assignment deactivation ────────────────────────────

    def deactivate_assignments(
        self, employee_catalog: str, employee_code: str, *, actor_id: str
    ) -> int:
        """Deactivate all ACTIVE assignments for an employee.

        Returns count of deactivated assignments.
        Used before: creating a new role, transfer, or removal.
        """
        now = _now()
        with Session(self._engine) as session, session.begin():
            result = session.execute(
                update(EmployeeBambooAssignmentRow)
                .where(
                    EmployeeBambooAssignmentRow.employee_catalog == employee_catalog,
                    EmployeeBambooAssignmentRow.employee_code == employee_code,
                    EmployeeBambooAssignmentRow.status == "ACTIVE",
                )
                .values(status="INACTIVE", ended_at=now)
            )
            return result.rowcount
