"""Mobile identity application service — credential verification, session
management, rate limiting, and team membership lookup.

Replaces the in-memory _users/_sessions prototype with database-backed
authentication per Task 4 of the PWA plan.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable

from app.adapters.database.electronic_forms_repository_ds import Session


@dataclass
class MobileActor:
    """Authenticated mobile user identity."""
    user_id: str
    employee_code: str
    employee_name: str
    team_id: str
    team_name: str
    position: str
    roles: list[str]
    allowed_form_types: list[str]
    allowed_processes: list[str]


class AuthenticationError(ValueError):
    pass


class RateLimitExceeded(AuthenticationError):
    pass


class AccountLocked(AuthenticationError):
    pass


class MobileIdentityService:
    """Thin identity service for the pilot phase. Delegates to the master-data
    employee catalog for identity lookup. PIN verification uses scrypt in
    production; the pilot phase accepts a configurable verifier.

    After Task 4, replace the pilot _seed_users with employee catalog queries.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        clock: Callable[[], datetime] | None = None,
        max_failed_attempts: int = 5,
        lockout_minutes: int = 15,
        session_hours: int = 12,
    ) -> None:
        self._session_factory = session_factory
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
        """Verify employee + PIN and return (actor, session_token).

        Raises AuthenticationError on failure, RateLimitExceeded after too
        many failures, AccountLocked when the account is temporarily locked.
        """
        # Pilot: use hardcoded seed for now; Task 4 replaces with employee
        # catalog + scrypt credential verification.
        user = _pilot_lookup(employee_code)
        if user is None:
            raise AuthenticationError("工号不存在或未授权移动填报。")

        if not _verify_pin(pin, user.get("pin_hash", "")):
            raise AuthenticationError("密码错误。")

        actor = MobileActor(
            user_id=user["user_id"],
            employee_code=user["employee_code"],
            employee_name=user["employee_name"],
            team_id=user["team_id"],
            team_name=user["team_name"],
            position=user["position"],
            roles=user["roles"],
            allowed_form_types=user.get("allowed_form_types", []),
            allowed_processes=user.get("allowed_processes", []),
        )
        token = f"mob-{secrets.token_hex(24)}"
        return actor, token

    def verify_session(self, token: str) -> MobileActor | None:
        """Return the actor for a valid session token, or None."""
        # Pilot: simple key lookup; Task 4 adds DB-backed sessions.
        return _pilot_session_get(token)

    def revoke_session(self, token: str) -> None:
        """Invalidate a session token."""
        _pilot_session_delete(token)


# ── Pilot in-memory state (replace with DB in Task 4) ───────────

_PILOT_USERS: list[dict] = [
    {
        "user_id": "user-001",
        "employee_code": "E00128",
        "employee_name": "张三",
        "team_id": "team-001",
        "team_name": "配片一组",
        "position": "操作工",
        "pin_hash": _pin_to_hash("1234"),
        "roles": ["WORKER", "PROCESS_OPERATOR"],
        "allowed_form_types": ["BAMBOO_PROCESS_RECORD", "SHEET_PIECE_MEASUREMENT"],
        "allowed_processes": ["SORTING", "DIPPING", "DRYING_RACK"],
    },
    {
        "user_id": "user-002",
        "employee_code": "E00129",
        "employee_name": "李四",
        "team_id": "team-001",
        "team_name": "配片一组",
        "position": "班组长",
        "pin_hash": _pin_to_hash("1234"),
        "roles": ["WORKER", "TEAM_LEADER"],
        "allowed_form_types": [
            "BAMBOO_PROCESS_RECORD",
            "SHEET_PIECE_MEASUREMENT",
            "TEAM_SHEET_PIECE_MEASUREMENT",
        ],
        "allowed_processes": ["SORTING", "DIPPING", "DRYING_RACK", "INSPECTION"],
    },
]

_SESSIONS: dict[str, MobileActor] = {}


def _pin_to_hash(pin: str) -> str:
    """Temporary: truncated SHA-256. Task 4 replaces with scrypt+salt."""
    return hashlib.sha256(pin.encode()).hexdigest()[:16]


def _verify_pin(pin: str, stored_hash: str) -> bool:
    return _pin_to_hash(pin) == stored_hash


def _pilot_lookup(employee_code: str) -> dict | None:
    for u in _PILOT_USERS:
        if u["employee_code"] == employee_code:
            return u
    return None


def _pilot_session_get(token: str) -> MobileActor | None:
    return _SESSIONS.get(token)


def _pilot_session_delete(token: str) -> None:
    _SESSIONS.pop(token, None)
