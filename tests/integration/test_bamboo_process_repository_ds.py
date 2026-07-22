from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.adapters.database.bamboo_process_repository_ds import (
    SqlAlchemyBambooProcessRepository,
)
from app.adapters.database.models import (
    BambooFactoryRow,
    BambooSignatureRow,
    BambooStageSubmissionRow,
    Base,
)
from app.modules.bamboo_process.facade_ds import BambooProcessFacade
from app.modules.bamboo_process.models_ds import BambooActor, BambooRole, BambooStage


def test_record_and_signed_stage_survive_repository_restart(tmp_path: Path) -> None:
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
    identifiers = iter(["BR-DB-1", "SUB-DB-1", "SIG-DB-1"])
    service = BambooProcessFacade(
        repository,
        clock=lambda: now,
        id_factory=lambda: next(identifiers),
    )
    actor = BambooActor(
        actor_id="E-SORT-01",
        employee_code="E-SORT-01",
        employee_name="王分选",
        factory_id="FACTORY-A",
        factory_name="竹丝一厂",
        role=BambooRole.SORT_OPERATOR,
    )
    record = service.create_record(
        actor=actor,
        base_info={"cage_no": "3-018"},
        source_type="MOBILE_CREATED",
        source_ref=None,
    )
    signed = service.submit_stage(
        record.record_id,
        actor=actor,
        stage=BambooStage.SORT,
        values={"moisture": [12, 13, 12]},
        expected_revision=1,
        idempotency_key="sort-db-1",
        device_id="device-a",
        request_id="request-a",
    )

    restarted = SqlAlchemyBambooProcessRepository(engine)
    restored = restarted.get(record.record_id)
    assert restored == signed
    assert restored is not None
    assert restored.current_stage is BambooStage.DIPPING
    assert restored.revision == 2
    assert restored.submissions[0].values == {"moisture": [12, 13, 12]}
    assert restarted.find_idempotent_result(actor.actor_id, "sort-db-1") == signed
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(BambooStageSubmissionRow)) == 1
        assert session.scalar(select(func.count()).select_from(BambooSignatureRow)) == 1
