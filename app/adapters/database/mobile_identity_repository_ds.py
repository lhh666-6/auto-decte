"""SQLAlchemy persistence for mobile credentials, profiles, and sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BambooFactoryRow,
    BambooRoleDefinitionRow,
    EmployeeBambooAssignmentRow,
    MasterDataRecordRow,
    MobileAccessProfileRow,
    MobileCredentialRow,
    MobileSessionRow,
)
from app.application.mobile_identity_ds import (
    MobileAccessProfile,
    MobileCredential,
    MobileSessionRecord,
    hash_pin,
)

EMPLOYEE_CATALOG = "employees"


class SqlAlchemyMobileIdentityRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_employee(self, employee_code: str) -> tuple[str, bool] | None:
        with Session(self._engine) as session:
            row = session.get(
                MasterDataRecordRow,
                (EMPLOYEE_CATALOG, employee_code),
            )
            if row is None:
                return None
            return row.display_name, row.active

    def get_credential(self, employee_code: str) -> MobileCredential | None:
        with Session(self._engine) as session:
            row = session.get(
                MobileCredentialRow,
                (EMPLOYEE_CATALOG, employee_code),
            )
            return _credential(row) if row is not None else None

    def save_credential(self, credential: MobileCredential) -> None:
        updated_at = credential.updated_at or datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            session.merge(
                MobileCredentialRow(
                    employee_catalog=EMPLOYEE_CATALOG,
                    employee_code=credential.employee_code,
                    pin_salt=credential.pin_salt,
                    pin_hash=credential.pin_hash,
                    failed_attempts=credential.failed_attempts,
                    locked_until=credential.locked_until,
                    revision=credential.revision,
                    updated_at=updated_at,
                )
            )

    def set_credential(
        self,
        employee_code: str,
        pin: str,
        *,
        updated_at: datetime | None = None,
    ) -> None:
        salt, digest = hash_pin(pin)
        current = self.get_credential(employee_code)
        self.save_credential(
            MobileCredential(
                employee_code=employee_code,
                pin_salt=salt,
                pin_hash=digest,
                revision=(current.revision + 1 if current else 1),
                updated_at=updated_at or datetime.now(UTC),
            )
        )

    def get_access_profile(self, employee_code: str) -> MobileAccessProfile | None:
        with Session(self._engine) as session:
            row = session.get(
                MobileAccessProfileRow,
                (EMPLOYEE_CATALOG, employee_code),
            )
            if row is None:
                return None
            assignment = session.scalar(
                select(EmployeeBambooAssignmentRow)
                .where(
                    EmployeeBambooAssignmentRow.employee_catalog == EMPLOYEE_CATALOG,
                    EmployeeBambooAssignmentRow.employee_code == employee_code,
                    EmployeeBambooAssignmentRow.status == "ACTIVE",
                    EmployeeBambooAssignmentRow.ended_at.is_(None),
                )
                .order_by(EmployeeBambooAssignmentRow.effective_at.desc())
                .limit(1)
            )
            factory_name = ""
            if assignment is not None:
                factory = session.get(BambooFactoryRow, assignment.factory_id)
                factory_name = factory.name if factory is not None else ""
            return _profile(row, assignment, factory_name)

    def list_team_members(self, team_id: str) -> list[tuple[str, str]]:
        statement = (
            select(MobileAccessProfileRow, MasterDataRecordRow.display_name)
            .join(
                MasterDataRecordRow,
                (MasterDataRecordRow.catalog == MobileAccessProfileRow.employee_catalog)
                & (MasterDataRecordRow.code == MobileAccessProfileRow.employee_code),
            )
            .where(
                MobileAccessProfileRow.team_id == team_id,
                MobileAccessProfileRow.active.is_(True),
                MasterDataRecordRow.active.is_(True),
            )
            .order_by(MasterDataRecordRow.display_name, MobileAccessProfileRow.employee_code)
        )
        with Session(self._engine) as session:
            return [
                (profile.employee_code, display_name)
                for profile, display_name in session.execute(statement).all()
            ]

    def set_access_profile(
        self,
        employee_code: str,
        *,
        team_id: str,
        team_name: str,
        position: str,
        roles: list[str],
        allowed_form_types: list[str],
        allowed_processes: list[str],
        active: bool = True,
        factory_id: str = "",
        factory_name: str = "",
        bamboo_role: str = "",
    ) -> None:
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            session.merge(
                MobileAccessProfileRow(
                    employee_catalog=EMPLOYEE_CATALOG,
                    employee_code=employee_code,
                    team_id=team_id,
                    team_name=team_name,
                    position=position,
                    roles=list(roles),
                    allowed_form_types=list(allowed_form_types),
                    allowed_processes=list(allowed_processes),
                    active=active,
                )
            )
            if factory_id and bamboo_role:
                session.merge(
                    BambooFactoryRow(
                        factory_id=factory_id,
                        code=factory_id,
                        name=factory_name or factory_id,
                        active=True,
                        revision=1,
                        created_at=now,
                        updated_at=now,
                    )
                )
                session.merge(
                    BambooRoleDefinitionRow(
                        role_code=bamboo_role,
                        display_name=bamboo_role,
                        category="PRODUCTION",
                        self_requestable=False,
                        active=True,
                        revision=1,
                    )
                )
                session.execute(
                    update(EmployeeBambooAssignmentRow)
                    .where(
                        EmployeeBambooAssignmentRow.employee_catalog == EMPLOYEE_CATALOG,
                        EmployeeBambooAssignmentRow.employee_code == employee_code,
                        EmployeeBambooAssignmentRow.status == "ACTIVE",
                        EmployeeBambooAssignmentRow.ended_at.is_(None),
                    )
                    .values(status="INACTIVE", ended_at=now)
                )
                session.add(
                    EmployeeBambooAssignmentRow(
                        assignment_id=f"MBA-{uuid4().hex}",
                        employee_catalog=EMPLOYEE_CATALOG,
                        employee_code=employee_code,
                        factory_id=factory_id,
                        role_code=bamboo_role,
                        status="ACTIVE",
                        effective_at=now,
                        ended_at=None,
                        created_by="system",
                        created_at=now,
                    )
                )

    def create_session(self, session_record: MobileSessionRecord) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(
                MobileSessionRow(
                    session_id=session_record.session_id,
                    employee_catalog=EMPLOYEE_CATALOG,
                    employee_code=session_record.employee_code,
                    device_id=session_record.device_id,
                    token_hash=session_record.token_hash,
                    expires_at=session_record.expires_at,
                    revoked_at=session_record.revoked_at,
                    created_at=session_record.created_at,
                )
            )

    def get_session(self, token_hash: str) -> MobileSessionRecord | None:
        statement = select(MobileSessionRow).where(
            MobileSessionRow.token_hash == token_hash,
        )
        with Session(self._engine) as session:
            row = session.scalar(statement)
            return _session(row) if row is not None else None

    def revoke_session(self, token_hash: str, revoked_at: datetime) -> None:
        with Session(self._engine) as session, session.begin():
            session.execute(
                update(MobileSessionRow)
                .where(MobileSessionRow.token_hash == token_hash)
                .values(revoked_at=revoked_at)
            )


def _credential(row: MobileCredentialRow) -> MobileCredential:
    return MobileCredential(
        employee_code=row.employee_code,
        pin_salt=row.pin_salt,
        pin_hash=row.pin_hash,
        failed_attempts=row.failed_attempts,
        locked_until=row.locked_until,
        revision=row.revision,
        updated_at=row.updated_at,
    )


def _profile(
    row: MobileAccessProfileRow,
    assignment: EmployeeBambooAssignmentRow | None,
    factory_name: str,
) -> MobileAccessProfile:
    return MobileAccessProfile(
        employee_code=row.employee_code,
        team_id=row.team_id,
        team_name=row.team_name,
        position=row.position,
        roles=list(row.roles),
        allowed_form_types=list(row.allowed_form_types),
        allowed_processes=list(row.allowed_processes),
        active=row.active,
        factory_id=assignment.factory_id if assignment is not None else "",
        factory_name=factory_name,
        bamboo_role=assignment.role_code if assignment is not None else "",
    )


def _session(row: MobileSessionRow) -> MobileSessionRecord:
    return MobileSessionRecord(
        session_id=row.session_id,
        employee_code=row.employee_code,
        device_id=row.device_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )
