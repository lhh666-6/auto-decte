from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.adapters.database.bamboo_process_repository_ds import (
    SqlAlchemyBambooProcessRepository,
)
from app.adapters.database.models import (
    BambooFactoryRow,
    BambooInspectionWindowRow,
    BambooPayrollFactRow,
    BambooRecordRow,
    BambooSignatureRow,
    BambooStageSubmissionRow,
    Base,
)
from app.modules.bamboo_process.errors_ds import BambooPermissionDenied
from app.modules.bamboo_process.facade_ds import BambooProcessFacade
from app.modules.bamboo_process.models_ds import (
    BambooActor,
    BambooFormType,
    BambooRole,
    BambooStage,
)
from app.modules.bamboo_process.ports_ds import BambooRepositoryConflict


def _actor(role: BambooRole) -> BambooActor:
    return BambooActor(
        actor_id=f"E-{role.value}",
        employee_code=f"E-{role.value}",
        employee_name=role.value,
        factory_id="FACTORY-A",
        factory_name="竹丝一厂",
        role=role,
    )


def test_independent_forms_metadata_and_payroll_facts_survive_restart(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'bamboo.db').as_posix()}")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 22, 2, 30, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        session.add(
            BambooFactoryRow(
                factory_id="FACTORY-A",
                code="A",
                name="竹丝一厂",
                active=True,
                revision=1,
                created_at=now,
                updated_at=now,
            )
        )

    repository = SqlAlchemyBambooProcessRepository(engine)
    identifiers = iter(
        [
            "BR-SORT",
            "SUB-SORT",
            "SIG-SORT",
            "BR-JOINT",
            "SUB-DIP",
            "SIG-DIP",
            "SUB-DRY",
            "SIG-DRY",
        ]
    )
    service = BambooProcessFacade(
        repository,
        clock=lambda: now,
        id_factory=lambda: next(identifiers),
    )
    sort_actor = _actor(BambooRole.SORT_OPERATOR)
    sorting = service.create_record(
        actor=sort_actor,
        base_info={"cage_no": "3-018", "length": "2.3", "bundle_count": 10},
        source_type="MOBILE_CREATED",
        source_ref="create-db-1",
    )
    sorting = service.submit_stage(
        sorting.record_id,
        actor=sort_actor,
        stage=BambooStage.SORT,
        values={"moisture": [12, 13, 12], "wage_amount": "80"},
        expected_revision=1,
        idempotency_key="sort-db-1",
        device_id="device-a",
        request_id="request-a",
    )

    linked = repository.find_linked(BambooFormType.DIPPING_DRYING, sorting.record_id)
    assert linked is not None
    linked = service.submit_stage(
        linked.record_id,
        actor=_actor(BambooRole.DIPPING_OPERATOR),
        stage=BambooStage.DIPPING,
        values={"moisture": [11, 12, 13], "wage_amount": "30"},
        expected_revision=1,
        idempotency_key="dip-db-1",
        device_id="device-b",
        request_id="request-b",
    )
    linked = service.submit_stage(
        linked.record_id,
        actor=_actor(BambooRole.DRYING_RACK_OPERATOR),
        stage=BambooStage.DRYING,
        values={
            "moisture": [8, 9, 10],
            "rack_numbers": ["R-01", "R-02"],
            "rack_count": 2,
            "wage_amount": "20",
        },
        expected_revision=2,
        idempotency_key="dry-db-1",
        device_id="device-c",
        request_id="request-c",
    )

    restarted = SqlAlchemyBambooProcessRepository(engine)
    restored_sorting = restarted.get(sorting.record_id)
    restored_linked = restarted.get(linked.record_id)
    assert restored_sorting == sorting
    assert restored_linked == linked
    assert restored_sorting is not None
    assert restored_linked is not None
    assert restored_sorting.form_type is BambooFormType.SORTING
    assert restored_sorting.current_stage is BambooStage.SUPERVISOR
    assert restored_linked.form_type is BambooFormType.DIPPING_DRYING
    assert restored_linked.current_stage is BambooStage.SUPERVISOR
    assert restored_linked.source_type == "SYSTEM_LINKED"
    assert restored_linked.source_ref == restored_sorting.record_id
    assert restored_linked.source_record_id == restored_sorting.record_id
    assert restored_linked.production_object_id == restored_sorting.production_object_id
    assert restored_linked.source_snapshot == {
        "record_id": restored_sorting.record_id,
        "display_no": restored_sorting.display_no,
        "revision": 2,
        "base_info": restored_sorting.base_info,
    }
    assert restarted.find_idempotent_result(sort_actor.actor_id, "sort-db-1") == sorting

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(BambooRecordRow)) == 2
        assert (
            session.scalar(select(func.count()).select_from(BambooStageSubmissionRow))
            == 3
        )
        assert session.scalar(select(func.count()).select_from(BambooSignatureRow)) == 3
        facts = session.scalars(
            select(BambooPayrollFactRow).order_by(BambooPayrollFactRow.fact_type)
        ).all()
        assert [(fact.record_id, fact.fact_type) for fact in facts] == [
            (restored_linked.record_id, "DIPPING_DRYING_JOINT"),
            (restored_sorting.record_id, "SORT"),
        ]


def test_cage_occupancy_blocks_until_linked_supervisor_approval(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'cage-lock.db').as_posix()}")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        for factory_id in ("FACTORY-A", "FACTORY-B"):
            session.add(
                BambooFactoryRow(
                    factory_id=factory_id,
                    code=factory_id,
                    name=factory_id,
                    active=True,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
            )
    identifiers = count(1)
    repository = SqlAlchemyBambooProcessRepository(engine)
    service = BambooProcessFacade(
        repository,
        clock=lambda: now,
        id_factory=lambda: f"ID-{next(identifiers)}",
    )
    sort_actor = _actor(BambooRole.SORT_OPERATOR)
    base_info = {"cage_no": " Cage-01 ", "length": "2.3", "bundle_count": 10}
    sorting = service.create_record(
        actor=sort_actor,
        base_info=base_info,
        source_type="MOBILE_CREATED",
        source_ref="first",
    )

    with pytest.raises(BambooRepositoryConflict):
        service.create_record(
            actor=sort_actor,
            base_info={**base_info, "cage_no": "cage-01"},
            source_type="MOBILE_CREATED",
            source_ref="duplicate-active",
        )

    other_factory = BambooActor(
        actor_id="E-SORT-B",
        employee_code="E-SORT-B",
        employee_name="E-SORT-B",
        factory_id="FACTORY-B",
        factory_name="FACTORY-B",
        role=BambooRole.SORT_OPERATOR,
    )
    assert service.create_record(
        actor=other_factory,
        base_info={**base_info, "cage_no": "CAGE-01"},
        source_type="MOBILE_CREATED",
        source_ref="other-factory",
    ).factory_id == "FACTORY-B"

    sorting = service.submit_stage(
        sorting.record_id,
        actor=sort_actor,
        stage=BambooStage.SORT,
        values={"moisture": [12]},
        expected_revision=1,
        idempotency_key="sort",
        device_id="phone",
        request_id="request-sort",
    )
    linked = repository.find_linked(BambooFormType.DIPPING_DRYING, sorting.record_id)
    assert linked is not None
    linked = service.submit_stage(
        linked.record_id,
        actor=_actor(BambooRole.DIPPING_OPERATOR),
        stage=BambooStage.DIPPING,
        values={"moisture": [11]},
        expected_revision=1,
        idempotency_key="dip",
        device_id="phone",
        request_id="request-dip",
    )
    linked = service.submit_stage(
        linked.record_id,
        actor=_actor(BambooRole.DRYING_RACK_OPERATOR),
        stage=BambooStage.DRYING,
        values={"moisture": [9], "rack_numbers": ["R-1"]},
        expected_revision=2,
        idempotency_key="dry",
        device_id="phone",
        request_id="request-dry",
    )
    with pytest.raises(BambooRepositoryConflict):
        service.create_record(
            actor=sort_actor,
            base_info={**base_info, "cage_no": "CAGE-01"},
            source_type="MOBILE_CREATED",
            source_ref="before-supervisor",
        )

    service.submit_stage(
        linked.record_id,
        actor=_actor(BambooRole.SUPERVISOR),
        stage=BambooStage.SUPERVISOR,
        values={},
        expected_revision=3,
        idempotency_key="supervisor",
        device_id="phone",
        request_id="request-supervisor",
    )
    reused = service.create_record(
        actor=sort_actor,
        base_info={**base_info, "cage_no": "cage-01"},
        source_type="MOBILE_CREATED",
        source_ref="after-supervisor",
    )
    assert reused.record_id != sorting.record_id


def test_supervisor_opens_two_hour_inspection_window_and_blocks_manager(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'inspection-window.db').as_posix()}")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        session.add(
            BambooFactoryRow(
                factory_id="FACTORY-A",
                code="A",
                name="竹丝一厂",
                active=True,
                revision=1,
                created_at=now,
                updated_at=now,
            )
        )
    identifiers = count(1)
    repository = SqlAlchemyBambooProcessRepository(engine)
    service = BambooProcessFacade(
        repository,
        clock=lambda: now,
        id_factory=lambda: f"WINDOW-{next(identifiers)}",
    )
    record = service.create_record(
        actor=_actor(BambooRole.SORT_OPERATOR),
        base_info={"cage_no": "W-1", "length": "2.3", "bundle_count": 10},
        source_type="MOBILE_CREATED",
        source_ref="window",
    )
    record = service.submit_stage(
        record.record_id,
        actor=_actor(BambooRole.SORT_OPERATOR),
        stage=BambooStage.SORT,
        values={"moisture": [12]},
        expected_revision=1,
        idempotency_key="window-sort",
        device_id="phone",
        request_id="request-sort",
    )
    record = service.submit_stage(
        record.record_id,
        actor=_actor(BambooRole.SUPERVISOR),
        stage=BambooStage.SUPERVISOR,
        values={"result": "APPROVED"},
        expected_revision=2,
        idempotency_key="window-supervisor",
        device_id="phone",
        request_id="request-supervisor",
    )

    with Session(engine) as session:
        window = session.get(BambooInspectionWindowRow, record.record_id)
        assert window is not None
        assert window.status == "OPEN"
        assert window.opened_at.replace(tzinfo=UTC) == now
        assert window.deadline_at.replace(tzinfo=UTC) == now + timedelta(hours=2)

    with pytest.raises(BambooPermissionDenied, match="检测窗口"):
        service.submit_stage(
            record.record_id,
            actor=_actor(BambooRole.PLANT_MANAGER),
            stage=BambooStage.PLANT_AUDIT,
            values={"result": "APPROVED"},
            expected_revision=3,
            idempotency_key="window-manager-too-early",
            device_id="phone",
            request_id="request-manager-early",
        )

    expired_service = BambooProcessFacade(
        repository,
        clock=lambda: now + timedelta(hours=2),
        id_factory=lambda: f"WINDOW-{next(identifiers)}",
    )
    completed = expired_service.submit_stage(
        record.record_id,
        actor=_actor(BambooRole.PLANT_MANAGER),
        stage=BambooStage.PLANT_AUDIT,
        values={"result": "APPROVED"},
        expected_revision=3,
        idempotency_key="window-manager-expired",
        device_id="phone",
        request_id="request-manager-expired",
    )
    assert completed.current_stage is None
