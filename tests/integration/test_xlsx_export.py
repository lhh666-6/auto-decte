from datetime import date
from pathlib import Path

import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine

from app.adapters.database.models import Base
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.adapters.export.xlsx import XlsxExporter
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.export_forms import ExportForms
from app.application.import_forms import ImportForms
from app.application.query_forms import FormFilters, QueryForms, SearchResult
from app.application.review_forms import ReviewForms
from app.domain.models import ExportStatus, Form, RecordStatus, RecordVersion, ReviewStatus
from app.domain.templates_ds import (
    ExportTarget,
    FieldDefinition,
    FieldRules,
    PageSpec,
    Rect,
    TemplateVersion,
)
from app.modules.reporting.facade_ds import ReportingFacade
from app.modules.reporting.models_ds import ExportMapping


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


def test_preview_uses_stable_template_mapping_and_explains_unconfirmed_forms(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'preview.db'}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    templates = SqlAlchemyTemplateRepository(engine)
    imports = ImportForms(
        repository, repository, repository, LocalEvidenceStorage(tmp_path / "evidence")
    )
    reviews = ReviewForms(repository, repository)
    template = TemplateVersion.draft("TPL-T1-V1", "T1", 1, PageSpec.a4_portrait())
    template.add_field(
        FieldDefinition(
            "employee_id",
            "Display name must not become an export column",
            "text",
            "text_box",
            Rect(0.1, 0.1, 0.2, 0.05),
            template.page,
            export_target=ExportTarget("payroll.xlsx", "employees", "employee_code"),
        )
    )
    templates.add_version(template)
    for sequence in (1, 2):
        image = tmp_path / f"scan-{sequence}.png"
        image.write_bytes(f"image-{sequence}".encode())
        evidence = imports.import_image(image, f"FORM-{sequence:04d}", "T1", "1", "operator")
        if sequence == 1:
            reviews.confirm(
                "FORM-0001",
                0,
                {"employee_id": "E001"},
                "reviewer",
                "confirmed",
                (evidence.file_id,),
            )
    service = ExportForms(
        repository,
        XlsxExporter(),
        QueryForms(repository),
        template_repository=templates,
    )

    preview = service.preview(FormFilters(), actor_id="finance")

    assert [(item.form_id, item.record_version) for item in preview.included] == [
        ("FORM-0001", 1)
    ]
    assert [(item.form_id, item.reason) for item in preview.excluded] == [
        ("FORM-0002", "NOT_CONFIRMED")
    ]
    assert [
        (
            item.template_id,
            item.template_version,
            item.field_key,
            item.workbook,
            item.worksheet,
            item.business_column,
        )
        for item in preview.mapping_snapshot
    ] == [("T1", "1", "employee_id", "payroll.xlsx", "employees", "employee_code")]
    assert repository.list_export_batches() == []
    assert repository.get_form("FORM-0001").export_status is ExportStatus.NOT_EXPORTED  # type: ignore[union-attr]


def test_preview_excludes_confirmed_record_that_fails_basic_final_validation(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'invalid-preview.db'}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    templates = SqlAlchemyTemplateRepository(engine)
    template = TemplateVersion.draft("TPL-T1-V1", "T1", 1, PageSpec.a4_portrait())
    template.add_field(
        FieldDefinition(
            "employee_id",
            "Employee",
            "text",
            "text_box",
            Rect(0.1, 0.1, 0.2, 0.05),
            template.page,
            rules=FieldRules(required=True),
            export_target=ExportTarget("payroll.xlsx", "employees", "employee_code"),
        )
    )
    templates.add_version(template)
    imports = ImportForms(
        repository, repository, repository, LocalEvidenceStorage(tmp_path / "invalid-evidence")
    )
    image = tmp_path / "invalid.png"
    image.write_bytes(b"invalid")
    evidence = imports.import_image(image, "FORM-INVALID", "T1", "1", "operator")
    ReviewForms(repository, repository).confirm(
        "FORM-INVALID", 0, {}, "reviewer", "confirmed", (evidence.file_id,)
    )
    service = ExportForms(
        repository,
        XlsxExporter(),
        QueryForms(repository),
        template_repository=templates,
    )

    preview = service.preview(FormFilters())

    assert preview.included == ()
    assert [(item.form_id, item.reason) for item in preview.excluded] == [
        ("FORM-INVALID", "FINAL_VALIDATION_FAILED")
    ]
    assert preview.mapping_snapshot == ()

    batch = service.export("OUTPUT", FormFilters(), tmp_path / "exports", "finance")

    assert batch.included_records == tuple(
        (item.form_id, item.record_version) for item in preview.included
    )
    assert repository.get_form("FORM-INVALID").export_status is ExportStatus.NOT_EXPORTED  # type: ignore[union-attr]


def test_reporting_facade_preview_requires_template_repository(tmp_path: Path) -> None:
    _, _, repository = setup_confirmed_form(tmp_path)
    facade = ReportingFacade(repository, QueryForms(repository))

    with pytest.raises(
        RuntimeError, match="template repository is required for export preview"
    ):
        facade.preview(FormFilters())


def test_reporting_facade_preview_explains_missing_template(tmp_path: Path) -> None:
    _, _, repository = setup_confirmed_form(tmp_path)
    templates = SqlAlchemyTemplateRepository(
        create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    )
    facade = ReportingFacade(
        repository, QueryForms(repository), template_repository=templates
    )

    preview = facade.preview(FormFilters())

    assert preview.included == ()
    assert [(item.form_id, item.reason) for item in preview.excluded] == [
        ("FORM-0001", "TEMPLATE_NOT_FOUND")
    ]


def test_preview_excludes_template_without_any_export_mapping(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'unmapped-preview.db'}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    templates = SqlAlchemyTemplateRepository(engine)
    templates.add_version(
        TemplateVersion.draft("TPL-EMPTY-V1", "EMPTY", 1, PageSpec.a4_portrait())
    )
    imports = ImportForms(
        repository, repository, repository, LocalEvidenceStorage(tmp_path / "unmapped-evidence")
    )
    image = tmp_path / "unmapped.png"
    image.write_bytes(b"unmapped")
    evidence = imports.import_image(image, "FORM-UNMAPPED", "EMPTY", "1", "operator")
    ReviewForms(repository, repository).confirm(
        "FORM-UNMAPPED", 0, {}, "reviewer", "confirmed", (evidence.file_id,)
    )
    service = ExportForms(
        repository,
        XlsxExporter(),
        QueryForms(repository),
        template_repository=templates,
    )

    preview = service.preview(FormFilters())

    assert preview.included == ()
    assert [(item.form_id, item.reason) for item in preview.excluded] == [
        ("FORM-UNMAPPED", "NO_VALID_MAPPING")
    ]


def test_template_export_groups_mappings_and_uses_only_each_forms_template(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'mapped-export.db'}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    templates = SqlAlchemyTemplateRepository(engine)
    imports = ImportForms(
        repository, repository, repository, LocalEvidenceStorage(tmp_path / "mapped-evidence")
    )
    reviews = ReviewForms(repository, repository)

    template_one = TemplateVersion.draft("TPL-T1-V1", "T1", 1, PageSpec.a4_portrait())
    template_one.add_field(
        FieldDefinition(
            "employee_id",
            "This display name must never become a column",
            "text",
            "text_box",
            Rect(0.1, 0.1, 0.2, 0.05),
            template_one.page,
            export_target=ExportTarget("企业工资记录.xlsx", "人员", "员工编号"),
        )
    )
    template_one.add_field(
        FieldDefinition(
            "total_quantity",
            "Another ignored display name",
            "integer",
            "number",
            Rect(0.1, 0.2, 0.2, 0.05),
            template_one.page,
            export_target=ExportTarget("企业工资记录.xlsx", "产量", "总产量"),
        )
    )
    template_two = TemplateVersion.draft("TPL-T2-V1", "T2", 1, PageSpec.a4_portrait())
    template_two.add_field(
        FieldDefinition(
            "employee_id",
            "Also ignored",
            "text",
            "text_box",
            Rect(0.1, 0.1, 0.2, 0.05),
            template_two.page,
            export_target=ExportTarget("企业工资记录.xlsx", "人员", "外部人员编号"),
        )
    )
    templates.add_version(template_one)
    templates.add_version(template_two)

    for form_id, template_id, values in (
        ("FORM-T1", "T1", {"employee_id": "E001", "total_quantity": 10}),
        ("FORM-T2", "T2", {"employee_id": "EXT-2"}),
    ):
        image = tmp_path / f"{form_id}.png"
        image.write_bytes(form_id.encode())
        evidence = imports.import_image(image, form_id, template_id, "1", "operator")
        reviews.confirm(form_id, 0, values, "reviewer", "confirmed", (evidence.file_id,))

    service = ExportForms(
        repository,
        XlsxExporter(),
        QueryForms(repository),
        template_repository=templates,
    )

    batch = service.export("OUTPUT", FormFilters(), tmp_path / "exports", "finance")

    workbook = load_workbook(batch.file_path, read_only=True)
    assert workbook.sheetnames == ["人员", "产量"]
    people_rows = list(workbook["人员"].iter_rows(values_only=True))
    people = [dict(zip(people_rows[0], row, strict=True)) for row in people_rows[1:]]
    assert people == [
        {
            "export_batch_id": batch.export_batch_id,
            "form_id": "FORM-T1",
            "record_version": 1,
            "员工编号": "E001",
            "外部人员编号": None,
        },
        {
            "export_batch_id": batch.export_batch_id,
            "form_id": "FORM-T2",
            "record_version": 1,
            "员工编号": None,
            "外部人员编号": "EXT-2",
        },
    ]
    production_rows = list(workbook["产量"].iter_rows(values_only=True))
    assert production_rows == [
        ("export_batch_id", "form_id", "record_version", "总产量"),
        (batch.export_batch_id, "FORM-T1", 1, 10),
    ]
    assert "This display name must never become a column" not in people_rows[0]


def test_template_export_rejects_multiple_workbooks(tmp_path: Path) -> None:
    result = _search_result({"first": "one", "second": "two"})
    mappings = (
        ExportMapping("T1", "1", "first", "first.xlsx", "data", "first"),
        ExportMapping("T1", "1", "second", "second.xlsx", "data", "second"),
    )

    with pytest.raises(ValueError, match="one workbook"):
        XlsxExporter().write(
            tmp_path / "multiple.xlsx",
            "BATCH-1",
            "OUTPUT",
            [result],
            {},
            mappings=mappings,
        )


@pytest.mark.parametrize(
    ("unsafe", "expected"),
    [
        ("=1+1", "'=1+1"),
        ("+SUM(A1:A2)", "'+SUM(A1:A2)"),
        ("-2+3", "'-2+3"),
        ("@cmd", "'@cmd"),
        ("\ufeff=hidden", "'=hidden"),
    ],
)
def test_template_export_neutralizes_formula_like_text(
    tmp_path: Path, unsafe: str, expected: str
) -> None:
    destination = tmp_path / "safe.xlsx"
    XlsxExporter().write(
        destination,
        "BATCH-SAFE",
        "OUTPUT",
        [_search_result({"value": unsafe})],
        {},
        mappings=(ExportMapping("T1", "1", "value", "safe.xlsx", "data", "value"),),
    )

    cell = load_workbook(destination, data_only=False)["data"]["D2"]
    assert cell.value == expected
    assert cell.data_type != "f"


@pytest.mark.parametrize(
    ("value", "expected_data_type"),
    [(42, "n"), (True, "b"), (date(2026, 7, 16), "d"), (None, "n")],
)
def test_template_export_preserves_non_text_cell_types(
    tmp_path: Path, value: object, expected_data_type: str
) -> None:
    destination = tmp_path / "typed.xlsx"
    XlsxExporter().write(
        destination,
        "BATCH-TYPED",
        "OUTPUT",
        [_search_result({"value": value})],
        {},
        mappings=(ExportMapping("T1", "1", "value", "typed.xlsx", "data", "value"),),
    )

    cell = load_workbook(destination, data_only=False)["data"]["D2"]
    assert cell.data_type == expected_data_type


def _search_result(values: dict[str, object]) -> SearchResult:
    form = Form(
        "FORM-SAFE",
        "T1",
        "1",
        review_status=ReviewStatus.CONFIRMED,
        current_record_version=1,
    )
    record = RecordVersion(
        "RECORD-SAFE",
        form.form_id,
        1,
        RecordStatus.CONFIRMED,
        values,
        confirmed_by="reviewer",
    )
    return SearchResult(form, record)
