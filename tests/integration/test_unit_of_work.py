from pathlib import Path

import pytest

from app.adapters.database.models import Base
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.import_forms import ImportForms
from app.domain.models import AuditEvent
from app.infrastructure.database.sqlite import create_sqlite_engine
from app.infrastructure.database.uow import SqlAlchemyUnitOfWork
from app.modules.review.facade import ConfirmReviewCommand, ReviewFacade


class FailingAuditRepository:
    def add_audit_event(self, event: AuditEvent) -> None:
        raise RuntimeError("audit storage is unavailable")


def test_confirmation_rolls_back_version_when_audit_insert_fails(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "demo.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    imports = ImportForms(
        repository, repository, repository, LocalEvidenceStorage(tmp_path / "evidence")
    )
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    imports.import_image(image, "FORM-1", "T1", "1", "operator-a")

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(engine)

    facade = ReviewFacade(uow_factory=uow_factory, audits=FailingAuditRepository())

    with pytest.raises(RuntimeError, match="audit storage"):
        facade.confirm(
            ConfirmReviewCommand(
                form_id="FORM-1",
                expected_version=0,
                values={"total_quantity": 10},
                actor_id="reviewer-a",
                reason="initial confirmation",
                evidence_ids=(),
            )
        )

    assert repository.list_record_versions("FORM-1") == []
    assert repository.get_form("FORM-1").current_record_version == 0  # type: ignore[union-attr]


def test_confirmation_commits_version_status_and_audit_together(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "demo.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    imports = ImportForms(
        repository, repository, repository, LocalEvidenceStorage(tmp_path / "evidence")
    )
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    imports.import_image(image, "FORM-1", "T1", "1", "operator-a")
    facade = ReviewFacade(uow_factory=lambda: SqlAlchemyUnitOfWork(engine))

    record = facade.confirm(
        ConfirmReviewCommand(
            form_id="FORM-1",
            expected_version=0,
            values={"total_quantity": 10},
            actor_id="reviewer-a",
            reason="initial confirmation",
            evidence_ids=(),
        )
    )

    assert record.version == 1
    assert repository.get_form("FORM-1").current_record_version == 1  # type: ignore[union-attr]
    assert repository.list_audit_events("FORM-1")[-1].event_type == "CONFIRM"
