from pathlib import Path

from sqlalchemy import create_engine

from app.adapters.database.models import Base
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.domain.models import Form, RecordStatus, RecordVersion


def test_repository_retains_history_and_points_to_latest_version(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    repository.add_form(Form("FORM-0001", "T1", "1"))
    repository.add_record_version(
        RecordVersion(
            record_id="RECORD-1",
            form_id="FORM-0001",
            version=1,
            status=RecordStatus.CONFIRMED,
            values={"total_quantity": 10},
        )
    )
    repository.add_record_version(
        RecordVersion(
            record_id="RECORD-2",
            form_id="FORM-0001",
            version=2,
            previous_version=1,
            status=RecordStatus.CORRECTED,
            values={"total_quantity": 12},
        )
    )

    restored = repository.get_form("FORM-0001")
    versions = repository.list_record_versions("FORM-0001")

    assert restored is not None
    assert restored.current_record_version == 2
    assert [version.version for version in versions] == [1, 2]
    assert versions[0].values == {"total_quantity": 10}
    assert versions[1].values == {"total_quantity": 12}
