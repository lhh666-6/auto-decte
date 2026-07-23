"""Atomic transaction boundary for electronic form submissions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, Self

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.database.electronic_forms_repository_ds import (
    SqlAlchemyElectronicSubmissionReceiptRepository,
)
from app.adapters.database.fact_record_repository_ds import (
    SqlAlchemyFactRecordRepository,
)
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.modules.submission_ledger.service_ds import SubmissionLedgerService

if TYPE_CHECKING:
    from app.application.electronic_submissions_ds import ElectronicFormCommand
    from app.modules.electronic_forms.models_ds import ElectronicSubmissionReceipt


class ElectronicSubmissionUnitOfWork(Protocol):
    forms: SqlAlchemyFormRepository
    receipts: SqlAlchemyElectronicSubmissionReceiptRepository
    facts: SqlAlchemyFactRecordRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None: ...

    def flush(self) -> None: ...

    def record_finance_acceptance(
        self,
        receipt: ElectronicSubmissionReceipt,
        command: ElectronicFormCommand,
    ) -> None: ...


class SqlAlchemyElectronicSubmissionUnitOfWork:
    """Own the single session used by every electronic-submission write."""

    def __init__(
        self,
        engine: Engine,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self._engine = engine
        self._session_factory = session_factory or sessionmaker(
            bind=engine,
            expire_on_commit=False,
        )
        self.session: Session | None = None
        self.forms: SqlAlchemyFormRepository
        self.receipts: SqlAlchemyElectronicSubmissionReceiptRepository
        self.facts: SqlAlchemyFactRecordRepository

    def __enter__(self) -> Self:
        self.session = self._session_factory()
        self.forms = SqlAlchemyFormRepository(self._engine, self.session)
        self.receipts = SqlAlchemyElectronicSubmissionReceiptRepository(self.session)
        self.facts = SqlAlchemyFactRecordRepository(self._engine, self.session)
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        if self.session is None:
            return
        try:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()
            self.session = None

    def flush(self) -> None:
        if self.session is None:
            raise RuntimeError("UnitOfWork has not been entered")
        self.session.flush()

    def record_finance_acceptance(
        self,
        receipt: ElectronicSubmissionReceipt,
        command: ElectronicFormCommand,
    ) -> None:
        if self.session is None:
            raise RuntimeError("UnitOfWork has not been entered")
        SubmissionLedgerService(self._engine).record_acceptance(
            submission_id=receipt.receipt_id,
            factory_id=command.factory_id,
            subject_employee_code=command.subject_employee_code,
            actor_id=command.actor_id,
            definition_version_id=command.definition_version_id,
            values=command.values,
            submitted_at=receipt.submitted_at,
            session=self.session,
        )
