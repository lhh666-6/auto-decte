"""Persistent mobile credential and session application service."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class MobileActor:
    user_id: str
    employee_code: str
    employee_name: str
    team_id: str
    team_name: str
    position: str
    roles: list[str]
    allowed_form_types: list[str]
    allowed_processes: list[str]


@dataclass(frozen=True, slots=True)
class MobileCredential:
    employee_code: str
    pin_salt: str
    pin_hash: str
    failed_attempts: int = 0
    locked_until: datetime | None = None
    revision: int = 1
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MobileAccessProfile:
    employee_code: str
    team_id: str
    team_name: str
    position: str
    roles: list[str]
    allowed_form_types: list[str]
    allowed_processes: list[str]
    active: bool = True


@dataclass(slots=True)
class MobileSessionRecord:
    session_id: str
    employee_code: str
    device_id: str
    token_hash: str
    expires_at: datetime
    created_at: datetime
    revoked_at: datetime | None = None


class MobileIdentityRepository(Protocol):
    def get_employee(self, employee_code: str) -> tuple[str, bool] | None: ...

    def get_credential(self, employee_code: str) -> MobileCredential | None: ...

    def save_credential(self, credential: MobileCredential) -> None: ...

    def get_access_profile(self, employee_code: str) -> MobileAccessProfile | None: ...

    def create_session(self, session: MobileSessionRecord) -> None: ...

    def get_session(self, token_hash: str) -> MobileSessionRecord | None: ...

    def revoke_session(self, token_hash: str, revoked_at: datetime) -> None: ...


class AuthenticationError(ValueError):
    pass


class RateLimitExceeded(AuthenticationError):
    pass


class AccountLocked(AuthenticationError):
    pass


def hash_pin(pin: str, *, salt: bytes | None = None) -> tuple[str, str]:
    """Return hex salt and scrypt digest; never persist the plaintext PIN."""
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        pin.encode("utf-8"),
        salt=actual_salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return actual_salt.hex(), digest.hex()


def _verify_pin(pin: str, salt_hex: str, digest_hex: str) -> bool:
    _, candidate = hash_pin(pin, salt=bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate, digest_hex)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class MobileIdentityService:
    def __init__(
        self,
        repository: MobileIdentityRepository,
        clock: Callable[[], datetime] | None = None,
        max_failed_attempts: int = 5,
        lockout_minutes: int = 15,
        session_hours: int = 12,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._max_failed = max_failed_attempts
        self._lockout = timedelta(minutes=lockout_minutes)
        self._session_ttl = timedelta(hours=session_hours)

    def authenticate(
        self,
        employee_code: str,
        pin: str,
        device_id: str = "unknown",
    ) -> tuple[MobileActor, str]:
        now = _as_utc(self._clock())
        employee = self._repository.get_employee(employee_code)
        credential = self._repository.get_credential(employee_code)
        profile = self._repository.get_access_profile(employee_code)
        if employee is None or credential is None or profile is None:
            raise AuthenticationError("工号不存在或未授权移动填报。")
        employee_name, employee_active = employee
        if not employee_active or not profile.active:
            raise AuthenticationError("员工或移动访问权限已停用。")
        if credential.locked_until is not None and _as_utc(credential.locked_until) > now:
            raise AccountLocked("账户已临时锁定，请稍后重试。")

        if not _verify_pin(pin, credential.pin_salt, credential.pin_hash):
            failed_attempts = credential.failed_attempts + 1
            locked_until = (
                now + self._lockout
                if failed_attempts >= self._max_failed
                else None
            )
            self._repository.save_credential(
                replace(
                    credential,
                    failed_attempts=failed_attempts,
                    locked_until=locked_until,
                    revision=credential.revision + 1,
                    updated_at=now,
                )
            )
            if locked_until is not None:
                raise AccountLocked("PIN 连续错误，账户已临时锁定。")
            raise AuthenticationError("PIN 错误。")

        if credential.failed_attempts or credential.locked_until is not None:
            self._repository.save_credential(
                replace(
                    credential,
                    failed_attempts=0,
                    locked_until=None,
                    revision=credential.revision + 1,
                    updated_at=now,
                )
            )

        actor = self._actor(employee_code, employee_name, profile)
        token = f"mob-{secrets.token_urlsafe(32)}"
        self._repository.create_session(
            MobileSessionRecord(
                session_id=f"MS-{uuid4().hex}",
                employee_code=employee_code,
                device_id=device_id,
                token_hash=_token_hash(token),
                expires_at=now + self._session_ttl,
                created_at=now,
            )
        )
        return actor, token

    def verify_session(self, token: str) -> MobileActor | None:
        now = _as_utc(self._clock())
        session = self._repository.get_session(_token_hash(token))
        if session is None or session.revoked_at is not None:
            return None
        if _as_utc(session.expires_at) <= now:
            return None
        employee = self._repository.get_employee(session.employee_code)
        profile = self._repository.get_access_profile(session.employee_code)
        if employee is None or profile is None:
            return None
        employee_name, employee_active = employee
        if not employee_active or not profile.active:
            return None
        return self._actor(session.employee_code, employee_name, profile)

    def revoke_session(self, token: str) -> None:
        token_hash = _token_hash(token)
        if self._repository.get_session(token_hash) is not None:
            self._repository.revoke_session(token_hash, _as_utc(self._clock()))

    @staticmethod
    def _actor(
        employee_code: str,
        employee_name: str,
        profile: MobileAccessProfile,
    ) -> MobileActor:
        return MobileActor(
            user_id=employee_code,
            employee_code=employee_code,
            employee_name=employee_name,
            team_id=profile.team_id,
            team_name=profile.team_name,
            position=profile.position,
            roles=list(profile.roles),
            allowed_form_types=list(profile.allowed_form_types),
            allowed_processes=list(profile.allowed_processes),
        )
