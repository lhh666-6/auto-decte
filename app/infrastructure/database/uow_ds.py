"""Transaction boundary for write workflows that span multiple repositories."""

from collections.abc import Callable
from typing import Protocol, Self

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.database.repositories import SqlAlchemyFormRepository


class UnitOfWork(Protocol):
    forms: SqlAlchemyFormRepository
    audits: SqlAlchemyFormRepository

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class SqlAlchemyUnitOfWork:
    """Own one SQLAlchemy session and commit or roll it back as a whole."""

    def __init__(
        self, engine: Engine, session_factory: Callable[[], Session] | None = None
    ) -> None:
        self._engine = engine
        self._session_factory = session_factory or sessionmaker(bind=engine, expire_on_commit=False)
        self.session: Session | None = None
        self.forms: SqlAlchemyFormRepository
        self.audits: SqlAlchemyFormRepository

    def __enter__(self) -> Self:
        self.session = self._session_factory()
        self.forms = SqlAlchemyFormRepository(self._engine, self.session)
        self.audits = SqlAlchemyFormRepository(self._engine, self.session)
        return self

    def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("UnitOfWork has not been entered")
        self.session.commit()

    def rollback(self) -> None:
        if self.session is not None:
            self.session.rollback()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.session is None:
            return
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.session.close()
            self.session = None
