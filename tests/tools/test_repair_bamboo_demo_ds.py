from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BambooFactoryRow,
    BambooRoleDefinitionRow,
    Base,
    EmployeeBambooAssignmentRow,
    MasterDataRecordRow,
    MobileAccessProfileRow,
    MobileCredentialRow,
)
from app.tools.repair_bamboo_demo_ds import main, repair_bamboo_demo_data

DEMO_IDENTITIES = {
    "ZS001": ("王分选", "分选工", "SORT_OPERATOR"),
    "JZ001": ("李浸胶", "浸胶工", "DIPPING_OPERATOR"),
    "GZ001": ("陈干燥", "干燥工", "DRYING_RACK_OPERATOR"),
    "JC001": ("周检测", "检测人", "INSPECTOR"),
    "ZG001": ("赵主管", "主管", "SUPERVISOR"),
    "CZ001": ("钱厂长", "厂长", "PLANT_MANAGER"),
    "CW001": ("孙财务", "财务审批", "FINANCE_APPROVER"),
}
DEMO_TEAM_ID = "BAMBOO-DEMO-TEAM"
DEMO_TEAM_NAME = "竹丝示范一厂生产组"


def _engine():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _seed_corrupted_demo(engine) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 7, 22, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                BambooFactoryRow(
                    factory_id="BAMBOO-DEMO-FACTORY",
                    code="BAMBOO-DEMO-FACTORY",
                    name="???",
                    active=True,
                    revision=7,
                    created_at=now,
                    updated_at=now,
                ),
                BambooFactoryRow(
                    factory_id="FACTORY-QA",
                    code="QA-FACTORY",
                    name="QA工厂",
                    active=True,
                    revision=3,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.add_all(
            BambooRoleDefinitionRow(
                role_code=role_code,
                display_name=role_code,
                category="PRODUCTION",
                self_requestable=False,
                active=True,
                revision=1,
            )
            for role_code in {identity[2] for identity in DEMO_IDENTITIES.values()}
        )
        for index, (code, identity) in enumerate(DEMO_IDENTITIES.items()):
            session.add(
                MasterDataRecordRow(
                    catalog="employees",
                    code=code,
                    display_name="???",
                    attributes={"legacy": index},
                    active=True,
                    revision=4,
                    created_at=now,
                    updated_at=now,
                    created_by="seed",
                    updated_by="seed",
                )
            )
            session.add(
                MobileAccessProfileRow(
                    employee_catalog="employees",
                    employee_code=code,
                    team_id=DEMO_TEAM_ID,
                    team_name="???",
                    position="???",
                    roles=["WORKER"],
                    allowed_form_types=["BAMBOO_PROCESS"],
                    allowed_processes=["BAMBOO_PROCESS"],
                    active=True,
                )
            )
            session.add(
                EmployeeBambooAssignmentRow(
                    assignment_id=f"ASSIGN-{code}",
                    employee_catalog="employees",
                    employee_code=code,
                    factory_id="BAMBOO-DEMO-FACTORY",
                    role_code=identity[2],
                    status="ACTIVE",
                    effective_at=now,
                    ended_at=None,
                    created_by="seed",
                    created_at=now,
                )
            )
        session.add(
            MobileCredentialRow(
                employee_catalog="employees",
                employee_code="ZS001",
                pin_salt="demo-salt",
                pin_hash="demo-hash",
                failed_attempts=2,
                locked_until=None,
                revision=5,
                updated_at=now,
            )
        )
        session.add(
            MasterDataRecordRow(
                catalog="employees",
                code="QA001",
                display_name="质量测试员",
                attributes={"scope": "qa"},
                active=False,
                revision=9,
                created_at=now,
                updated_at=now,
                created_by="qa",
                updated_by="qa",
            )
        )
        session.add(
            MobileAccessProfileRow(
                employee_catalog="employees",
                employee_code="QA001",
                team_id="TEAM-QA",
                team_name="质量组",
                position="测试员",
                roles=["QA"],
                allowed_form_types=["QA_FORM"],
                allowed_processes=["QA_PROCESS"],
                active=False,
            )
        )


def _assignment_snapshot(session: Session) -> list[tuple[object, ...]]:
    rows = session.scalars(
        select(EmployeeBambooAssignmentRow).order_by(
            EmployeeBambooAssignmentRow.assignment_id
        )
    )
    return [
        (
            row.assignment_id,
            row.employee_code,
            row.factory_id,
            row.role_code,
            row.status,
            row.effective_at,
            row.ended_at,
            row.created_by,
            row.created_at,
        )
        for row in rows
    ]


def test_repair_restores_known_chinese_identities_without_changing_links_or_credentials() -> None:
    engine = _engine()
    _seed_corrupted_demo(engine)
    with Session(engine) as session:
        assignments_before = _assignment_snapshot(session)
        credential_before = session.get(MobileCredentialRow, ("employees", "ZS001"))
        assert credential_before is not None
        credential_values = (
            credential_before.pin_salt,
            credential_before.pin_hash,
            credential_before.failed_attempts,
            credential_before.revision,
        )

    repair_bamboo_demo_data(engine)

    with Session(engine) as session:
        factory = session.get(BambooFactoryRow, "BAMBOO-DEMO-FACTORY")
        assert factory is not None
        assert factory.name == "竹丝示范一厂"
        assert factory.code == "BAMBOO-DEMO-FACTORY"
        assert factory.revision == 7
        for code, (name, position, _role) in DEMO_IDENTITIES.items():
            employee = session.get(MasterDataRecordRow, ("employees", code))
            profile = session.get(MobileAccessProfileRow, ("employees", code))
            assert employee is not None
            assert profile is not None
            assert employee.display_name == name
            assert employee.attributes == {"legacy": list(DEMO_IDENTITIES).index(code)}
            assert employee.revision == 4
            assert profile.position == position
            assert (profile.team_id, profile.team_name) == (DEMO_TEAM_ID, DEMO_TEAM_NAME)
            assert profile.roles == ["WORKER"]
            assert profile.allowed_processes == ["BAMBOO_PROCESS"]
        assert _assignment_snapshot(session) == assignments_before
        credential = session.get(MobileCredentialRow, ("employees", "ZS001"))
        assert credential is not None
        assert (
            credential.pin_salt,
            credential.pin_hash,
            credential.failed_attempts,
            credential.revision,
        ) == credential_values


def test_repair_is_idempotent_and_does_not_touch_qa_or_create_missing_demo_rows() -> None:
    engine = _engine()
    _seed_corrupted_demo(engine)
    with Session(engine) as session, session.begin():
        missing = session.get(MasterDataRecordRow, ("employees", "CW001"))
        assert missing is not None
        session.delete(missing)
        qa_before = session.get(MasterDataRecordRow, ("employees", "QA001"))
        qa_profile_before = session.get(MobileAccessProfileRow, ("employees", "QA001"))
        assert qa_before is not None and qa_profile_before is not None
        qa_values = (
            qa_before.display_name,
            dict(qa_before.attributes),
            qa_before.active,
            qa_before.revision,
            qa_profile_before.team_id,
            qa_profile_before.team_name,
            qa_profile_before.position,
            list(qa_profile_before.roles),
            qa_profile_before.active,
        )
        credential_count = len(session.scalars(select(MobileCredentialRow)).all())

    repair_bamboo_demo_data(engine)
    repair_bamboo_demo_data(engine)

    with Session(engine) as session:
        assert session.get(MasterDataRecordRow, ("employees", "CW001")) is None
        assert session.get(MobileCredentialRow, ("employees", "CW001")) is None
        qa = session.get(MasterDataRecordRow, ("employees", "QA001"))
        qa_profile = session.get(MobileAccessProfileRow, ("employees", "QA001"))
        assert qa is not None and qa_profile is not None
        assert (
            qa.display_name,
            qa.attributes,
            qa.active,
            qa.revision,
            qa_profile.team_id,
            qa_profile.team_name,
            qa_profile.position,
            qa_profile.roles,
            qa_profile.active,
        ) == qa_values
        assert len(session.scalars(select(MobileCredentialRow)).all()) == credential_count


def test_cli_repairs_the_selected_database(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "demo.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    Base.metadata.create_all(engine)
    _seed_corrupted_demo(engine)
    engine.dispose()

    assert main(["--db", str(database_path)]) == 0

    output = capsys.readouterr().out
    assert "Bamboo demo data repaired" in output
    with Session(create_engine(f"sqlite+pysqlite:///{database_path}")) as session:
        employee = session.get(MasterDataRecordRow, ("employees", "ZS001"))
        assert employee is not None
        assert employee.display_name == "王分选"
