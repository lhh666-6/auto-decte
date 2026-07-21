"""Database persistence tests for mobile identity and sessions."""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.adapters.database.mobile_identity_repository_ds import (
    SqlAlchemyMobileIdentityRepository,
)
from app.adapters.database.models import Base, MasterDataRecordRow
from app.application.mobile_identity_ds import MobileIdentityService


def test_session_survives_service_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "identity.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 21, 8, 0, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        session.add(
            MasterDataRecordRow(
                catalog="employees",
                code="E10001",
                display_name="测试员工",
                attributes={},
                active=True,
                revision=1,
                created_at=now,
                updated_at=now,
                created_by="test",
                updated_by="test",
            )
        )

    repository = SqlAlchemyMobileIdentityRepository(engine)
    repository.set_credential("E10001", "2468", updated_at=now)
    repository.set_access_profile(
        "E10001",
        team_id="TEAM-A",
        team_name="测试班组",
        position="操作工",
        roles=["WORKER"],
        allowed_form_types=["SHEET_PIECE_MEASUREMENT"],
        allowed_processes=["CUTTING"],
    )
    first_service = MobileIdentityService(repository=repository, clock=lambda: now)
    _, token = first_service.authenticate("E10001", "2468", "device-a")

    restarted_service = MobileIdentityService(
        repository=SqlAlchemyMobileIdentityRepository(engine),
        clock=lambda: now,
    )

    actor = restarted_service.verify_session(token)
    assert actor is not None
    assert actor.employee_code == "E10001"
