"""Application tests for persistent mobile identity."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.mobile_identity_ds import (
    AccountLocked,
    AuthenticationError,
    MobileAccessProfile,
    MobileCredential,
    MobileIdentityService,
    MobileSessionRecord,
    hash_pin,
)


class _MemoryIdentityRepository:
    def __init__(self) -> None:
        self.employees: dict[str, tuple[str, bool]] = {}
        self.credentials: dict[str, MobileCredential] = {}
        self.profiles: dict[str, MobileAccessProfile] = {}
        self.sessions: dict[str, MobileSessionRecord] = {}

    def get_employee(self, employee_code: str):  # type: ignore[no-untyped-def]
        return self.employees.get(employee_code)

    def get_credential(self, employee_code: str) -> MobileCredential | None:
        return self.credentials.get(employee_code)

    def save_credential(self, credential: MobileCredential) -> None:
        self.credentials[credential.employee_code] = credential

    def get_access_profile(self, employee_code: str) -> MobileAccessProfile | None:
        return self.profiles.get(employee_code)

    def create_session(self, session: MobileSessionRecord) -> None:
        self.sessions[session.token_hash] = session

    def get_session(self, token_hash: str) -> MobileSessionRecord | None:
        return self.sessions.get(token_hash)

    def revoke_session(self, token_hash: str, revoked_at: datetime) -> None:
        session = self.sessions[token_hash]
        session.revoked_at = revoked_at


def _identity_fixture(
    *,
    active: bool = True,
    max_failed_attempts: int = 3,
) -> tuple[MobileIdentityService, _MemoryIdentityRepository, list[datetime]]:
    now = [datetime(2026, 7, 21, 8, 0, tzinfo=UTC)]
    repository = _MemoryIdentityRepository()
    repository.employees["E10001"] = ("测试员工", active)
    salt, digest = hash_pin("2468", salt=b"0123456789abcdef")
    repository.credentials["E10001"] = MobileCredential(
        employee_code="E10001",
        pin_salt=salt,
        pin_hash=digest,
    )
    repository.profiles["E10001"] = MobileAccessProfile(
        employee_code="E10001",
        team_id="TEAM-A",
        team_name="测试班组",
        position="操作工",
        roles=["WORKER"],
        allowed_form_types=["SHEET_PIECE_MEASUREMENT"],
        allowed_processes=["CUTTING"],
        factory_id="FACTORY-A",
        factory_name="竹丝一厂",
        bamboo_role="SORT_OPERATOR",
    )
    service = MobileIdentityService(
        repository=repository,
        clock=lambda: now[0],
        max_failed_attempts=max_failed_attempts,
        lockout_minutes=15,
        session_hours=12,
    )
    return service, repository, now


def test_authentication_uses_active_employee_and_persistent_credential() -> None:
    service, _, _ = _identity_fixture()

    actor, token = service.authenticate("E10001", "2468", "device-a")

    assert actor.employee_code == "E10001"
    assert actor.employee_name == "测试员工"
    assert actor.factory_id == "FACTORY-A"
    assert actor.factory_name == "竹丝一厂"
    assert actor.bamboo_role == "SORT_OPERATOR"
    assert service.verify_session(token).employee_code == "E10001"  # type: ignore[union-attr]


def test_inactive_employee_cannot_authenticate() -> None:
    service, _, _ = _identity_fixture(active=False)

    with pytest.raises(AuthenticationError, match="停用"):
        service.authenticate("E10001", "2468", "device-a")


def test_consecutive_wrong_pins_lock_account() -> None:
    service, repository, _ = _identity_fixture(max_failed_attempts=3)

    for _ in range(2):
        with pytest.raises(AuthenticationError, match="PIN"):
            service.authenticate("E10001", "0000", "device-a")
    with pytest.raises(AccountLocked):
        service.authenticate("E10001", "0000", "device-a")
    assert repository.credentials["E10001"].failed_attempts == 3

    with pytest.raises(AccountLocked):
        service.authenticate("E10001", "2468", "device-a")


def test_expired_and_revoked_sessions_are_rejected() -> None:
    service, _, now = _identity_fixture()
    _, expired_token = service.authenticate("E10001", "2468", "device-a")
    now[0] += timedelta(hours=13)
    assert service.verify_session(expired_token) is None

    now[0] -= timedelta(hours=13)
    _, revoked_token = service.authenticate("E10001", "2468", "device-a")
    service.revoke_session(revoked_token)
    assert service.verify_session(revoked_token) is None
