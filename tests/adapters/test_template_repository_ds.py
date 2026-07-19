"""Persistence behavior for template versions."""

from pathlib import Path

import pytest

from app.adapters.database.models import Base
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.domain.templates_ds import (
    CoreLayoutKind,
    ElementKind,
    FieldDefinition,
    FillPolicy,
    PageSpec,
    PaperEntryMode,
    PayrollJobProfileVersion,
    PrintImposition,
    RecognitionMode,
    Rect,
    StaticElement,
    TemplateArtifact,
    TemplateVersion,
)
from app.infrastructure.database.sqlite_ds import create_sqlite_engine


def test_repository_round_trips_fields_and_safe_artifact_metadata(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "template.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyTemplateRepository(engine)
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, PageSpec.a4_portrait())
    version.add_field(
        FieldDefinition(
            "worker_name",
            "姓名",
            "text",
            "text_box",
            Rect(0.1, 0.1, 0.2, 0.05),
            version.page,
        )
    )
    version.add_field(
        FieldDefinition(
            "hours",
            "工时",
            "decimal",
            "digit_boxes",
            Rect(0.1, 0.2, 0.2, 0.05),
            version.page,
        )
    )

    repository.add_version(version)
    repository.add_artifact(
        TemplateArtifact(
            "ART-1",
            version.version_id,
            "PRINT_PDF",
            "PAYROLL_HOURLY-v1.pdf",
            "evidence://templates/ART-1.pdf",
            "a" * 64,
        )
    )

    loaded = repository.get_version(version.version_id)

    assert loaded is not None
    assert loaded.template_key == "PAYROLL_HOURLY"
    assert [field.field_key for field in loaded.fields] == ["worker_name", "hours"]
    artifact = repository.list_artifacts(version.version_id)[0]
    assert artifact.download_name == "PAYROLL_HOURLY-v1.pdf"
    assert artifact.sha256 == "a" * 64

    loaded.mark_ready_to_publish()
    repository.replace_version(loaded)

    assert repository.get_version(version.version_id).status.value == "READY_TO_PUBLISH"  # type: ignore[union-attr]
    assert repository.list_versions("PAYROLL_HOURLY")[0].version_id == version.version_id


def test_repository_round_trips_versioned_job_profiles(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "job-profiles.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyTemplateRepository(engine)
    template = TemplateVersion.draft(
        "TPL-TIMEKEEPING-V2", "CORE_TIMEKEEPING", 2, PageSpec.a5_landscape()
    )
    repository.add_version(template)
    profile = PayrollJobProfileVersion.draft(
        "PROFILE-TIMEKEEPING-V1",
        "TIMEKEEPING_DAY",
        1,
        display_name="计时工白班",
        core_layout=CoreLayoutKind.TIMEKEEPING,
        template_version_id=template.version_id,
        template_version=template.version,
        unit="小时",
        fixed_options={"shift": ["白班", "夜班"]},
        pricing_rules={"hourly_rate": 18.5},
        deduction_rules={"late_per_minute": 0.5},
        export_mapping={"normal_hours": "正常工时"},
    )

    repository.add_job_profile(profile)

    loaded = repository.get_job_profile(profile.profile_version_id)
    assert loaded == profile
    assert repository.get_job_profile_by_key_version("TIMEKEEPING_DAY", 1) == profile
    assert repository.list_job_profiles("TIMEKEEPING_DAY") == [profile]


def test_repository_preserves_published_job_profile_content(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "published-job-profile.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyTemplateRepository(engine)
    template = TemplateVersion.draft(
        "TPL-EQUIPMENT-V1", "CORE_EQUIPMENT", 1, PageSpec.a5_landscape()
    )
    repository.add_version(template)
    profile = PayrollJobProfileVersion.draft(
        "PROFILE-FORKLIFT-V1",
        "FORKLIFT_DAY",
        1,
        display_name="叉车工日班",
        core_layout=CoreLayoutKind.EQUIPMENT_TIMEKEEPING,
        template_version_id=template.version_id,
        template_version=template.version,
        fixed_options={"equipment": ["叉车"]},
    )
    repository.add_job_profile(profile)
    profile.mark_ready_to_publish()
    repository.replace_job_profile(profile)
    profile.publish()
    repository.replace_job_profile(profile)

    forged = repository.get_job_profile(profile.profile_version_id)
    assert forged is not None
    forged.fixed_options["equipment"] = ["被篡改"]
    with pytest.raises(ValueError, match="published"):
        repository.replace_job_profile(forged)


def test_repository_lists_distinct_template_keys_in_lexical_order(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "template.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyTemplateRepository(engine)
    page = PageSpec.a4_portrait()

    repository.add_version(TemplateVersion.draft("TPL-H-1", "PAYROLL_HOURLY", 1, page))
    repository.add_version(TemplateVersion.draft("TPL-H-2", "PAYROLL_HOURLY", 2, page))
    repository.add_version(
        TemplateVersion.draft("TPL-P-1", "PAYROLL_STANDARD_PIECE", 1, page)
    )

    assert repository.list_template_keys() == ["PAYROLL_HOURLY", "PAYROLL_STANDARD_PIECE"]


def test_repository_persists_metadata_and_removes_draft_only_family(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "template.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyTemplateRepository(engine)
    draft = TemplateVersion.draft("TPL-DRAFT", "CUSTOM_FORM", 1, PageSpec.a4_portrait())
    repository.add_version(draft)

    repository.update_template_metadata("CUSTOM_FORM", "自定义表单", "测试用途")

    assert repository.get_template_metadata("CUSTOM_FORM") == ("自定义表单", "测试用途")
    repository.delete_version(draft.version_id)
    assert repository.get_version(draft.version_id) is None
    assert repository.get_template_metadata("CUSTOM_FORM") is None


def test_repository_round_trips_custom_layout_imposition_and_field_behavior(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "physical-layout.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyTemplateRepository(engine)
    page = PageSpec.custom(100.5, 130.2)
    version = TemplateVersion.draft("TPL-PHYSICAL", "PAYROLL_PHYSICAL", 1, page)
    version.add_static_element(
        StaticElement(
            "payroll_title",
            ElementKind.TITLE,
            Rect(0.1, 0.1, 0.5, 0.06),
            text="车间工资表",
        )
    )
    version.add_static_element(
        StaticElement(
            "detail_grid",
            ElementKind.TABLE_GRID,
            Rect(0.1, 0.25, 0.8, 0.4),
            rows=4,
            columns=3,
            column_weights=(1, 2, 1),
        )
    )
    version.set_print_imposition(
        PrintImposition(
            carrier=PageSpec.a4_landscape(),
            columns=2,
            horizontal_gap_mm=5,
            margin_mm=5,
        )
    )
    version.add_field(
        FieldDefinition(
            "worker_name",
            "姓名",
            "text",
            "text_box",
            Rect(0.1, 0.25, 0.4, 0.08),
            page,
            paper_entry_mode=PaperEntryMode.HANDWRITTEN_TEXT,
            recognition_mode=RecognitionMode.HANDWRITING_OCR,
            fill_policy=FillPolicy.SUGGEST_ONLY,
        )
    )

    repository.add_version(version)
    loaded = repository.get_version(version.version_id)

    assert loaded is not None
    assert loaded.page == page
    assert loaded.static_elements == version.static_elements
    assert loaded.static_elements[1].rows == 4
    assert loaded.static_elements[1].columns == 3
    assert loaded.static_elements[1].column_weights == (1, 2, 1)
    assert loaded.print_imposition == version.print_imposition
    assert loaded.fields == version.fields


def test_repository_cannot_replace_or_delete_published_layout(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "immutable-layout.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyTemplateRepository(engine)
    version = TemplateVersion.draft("TPL-PUBLISHED", "PAYROLL_PUBLISHED", 1, PageSpec.a4_portrait())
    version.add_field(
        FieldDefinition(
            "hours",
            "工时",
            "decimal",
            "digit_boxes",
            Rect(0.1, 0.2, 0.2, 0.05),
            version.page,
        )
    )
    version.mark_ready_to_publish()
    version.publish()
    repository.add_version(version)

    forged = TemplateVersion(
        version_id=version.version_id,
        template_key=version.template_key,
        version=version.version,
        page=version.page,
        status=version.status,
        fields=[],
    )

    with pytest.raises(ValueError, match="published"):
        repository.replace_version(forged)
    with pytest.raises(ValueError, match="published"):
        repository.delete_version(version.version_id)

    loaded = repository.get_version(version.version_id)
    assert loaded is not None
    loaded.retire()
    repository.replace_version(loaded)
    assert repository.get_version(version.version_id).status.value == "RETIRED"  # type: ignore[union-attr]
