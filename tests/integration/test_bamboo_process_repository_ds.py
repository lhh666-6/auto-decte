from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.adapters.database.bamboo_process_repository_ds import (
    SqlAlchemyBambooProcessRepository,
)
from app.adapters.database.models import (
    BambooFactoryRow,
    BambooPayrollFactRow,
    BambooRecordRow,
    BambooSignatureRow,
    BambooStageSubmissionRow,
    Base,
)
from app.modules.bamboo_process.facade_ds import BambooProcessFacade
from app.modules.bamboo_process.models_ds import (
    BambooActor,
    BambooFormType,
    BambooRole,
    BambooStage,
)


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
