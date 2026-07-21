"""Atomic persistence tests for electronic submissions."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.adapters.database.electronic_forms_repository_ds import (
    SqlAlchemyElectronicSubmissionReceiptRepository,
)
from app.adapters.database.models import (
    AuditEventRow,
    ElectronicSubmissionReceiptRow,
    FactRecordRow,
    FormFieldRow,
    FormRow,
)
from app.application.electronic_submissions_ds import (
    ElectronicFormCommand,
    ElectronicFormIntegration,
)
from app.infrastructure.database.electronic_submission_uow_ds import (
    SqlAlchemyElectronicSubmissionUnitOfWork,
)


def _command(client_submission_id: str = "client-atomic") -> ElectronicFormCommand:
    return ElectronicFormCommand(
        form_type="SHEET_PIECE_MEASUREMENT",
        definition_version_id="efd-v1",
        mode="SELF",
        actor_id="E00128",
        subject_employee_code="E00128",
        subject_employee_name="张三",
        team_id="team-1",
        team_name="配片一组",
        device_id="device-1",
        values={
            "production_date": "2026-07-21",
            "blocks_completed": 10,
            "pieces_per_block": 24,
        },
        client_submission_id=client_submission_id,
        template_id="TPL-SHEET",
        template_version="1",
    )


def _counts(database_path: Path) -> tuple[int, int, int, int, int]:
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with Session(engine) as session:
        return tuple(
            session.scalar(select(func.count()).select_from(row_type)) or 0
            for row_type in (
                FormRow,
                FormFieldRow,
                AuditEventRow,
                ElectronicSubmissionReceiptRow,
                FactRecordRow,
            )
        )  # type: ignore[return-value]


def test_submission_commits_form_receipt_and_fact_together(tmp_path: Path) -> None:
    database_path = tmp_path / "atomic-success.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    from app.adapters.database.models import Base

    Base.metadata.create_all(engine)
    integration = ElectronicFormIntegration(
        uow_factory=lambda: SqlAlchemyElectronicSubmissionUnitOfWork(engine),
    )

    integration.accept(_command())

    assert _counts(database_path) == (1, 3, 1, 1, 1)


class _FailingReceiptRepository(SqlAlchemyElectronicSubmissionReceiptRepository):
    def add(self, receipt) -> None:  # type: ignore[no-untyped-def]
        super().add(receipt)
        raise RuntimeError("receipt write failed")


class _FailingReceiptUnitOfWork(SqlAlchemyElectronicSubmissionUnitOfWork):
    def __enter__(self):  # type: ignore[no-untyped-def]
        uow = super().__enter__()
        assert self.session is not None
        self.receipts = _FailingReceiptRepository(self.session)
        return uow


def test_receipt_failure_rolls_back_form_fields_audit_and_fact(tmp_path: Path) -> None:
    database_path = tmp_path / "atomic-failure.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    from app.adapters.database.models import Base

    Base.metadata.create_all(engine)
    integration = ElectronicFormIntegration(
        uow_factory=lambda: _FailingReceiptUnitOfWork(engine),
    )

    with pytest.raises(RuntimeError, match="receipt write failed"):
        integration.accept(_command("client-failure"))

    assert _counts(database_path) == (0, 0, 0, 0, 0)
