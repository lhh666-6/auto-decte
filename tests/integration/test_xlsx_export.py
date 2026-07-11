from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import create_engine

from app.adapters.database.models import Base
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.export.xlsx import XlsxExporter
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.export_forms import ExportForms
from app.application.import_forms import ImportForms
from app.application.query_forms import FormFilters, QueryForms
from app.application.review_forms import ReviewForms
from app.domain.models import ExportStatus


def setup_confirmed_form(tmp_path: Path):  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    imports = ImportForms(
        repository, repository, repository, LocalEvidenceStorage(tmp_path / "evidence")
    )
    reviews = ReviewForms(repository, repository)
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    evidence = imports.import_image(image, "FORM-0001", "T1", "1", "operator")
    reviews.confirm(
        "FORM-0001",
        0,
        {"employee_id": "E001", "total_quantity": 10, "qualified_quantity": 9},
        "reviewer",
        "confirmed",
        (evidence.file_id,),
    )
    service = ExportForms(repository, XlsxExporter(), QueryForms(repository))
    return service, reviews, repository


def test_xlsx_has_four_sheets_persisted_batch_and_reverse_trace(tmp_path: Path) -> None:
    service, _, repository = setup_confirmed_form(tmp_path)

    batch = service.export("OUTPUT", FormFilters(), tmp_path / "exports", "finance")

    workbook = load_workbook(batch.file_path, read_only=True)
    assert workbook.sheetnames == ["正式数据", "异常与复核", "汇总", "导出说明"]
    official_rows = list(workbook["正式数据"].iter_rows(values_only=True))
    headers, data = official_rows
    row = dict(zip(headers, data, strict=True))
    assert row["export_batch_id"] == batch.export_batch_id
    assert row["form_id"] == "FORM-0001"
    assert row["record_version"] == 1
    assert Path(batch.file_path).exists()
    assert len(batch.file_sha256) == 64
    assert repository.list_export_batches()[0].included_records == (("FORM-0001", 1),)
    assert repository.get_form("FORM-0001").export_status is ExportStatus.EXPORTED  # type: ignore[union-attr]


def test_correction_after_export_requires_new_export_and_old_file_remains(tmp_path: Path) -> None:
    service, reviews, repository = setup_confirmed_form(tmp_path)
    first = service.export("OUTPUT", FormFilters(), tmp_path / "exports", "finance")

    reviews.confirm(
        "FORM-0001",
        1,
        {"employee_id": "E001", "total_quantity": 11, "qualified_quantity": 10},
        "reviewer",
        "correction",
        (),
    )

    assert repository.get_form("FORM-0001").export_status is ExportStatus.REEXPORT_REQUIRED  # type: ignore[union-attr]
    assert Path(first.file_path).exists()
    second = service.export("OUTPUT", FormFilters(), tmp_path / "exports", "finance")
    assert second.file_path != first.file_path
    assert Path(first.file_path).exists()
    assert Path(second.file_path).exists()
