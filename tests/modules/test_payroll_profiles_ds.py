"""Reviewed structure and production-readiness checks for ten payroll profiles."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from app.adapters.database.models import Base
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.application.template_versions_ds import TemplateVersions
from app.domain.templates_ds import ElementKind, PaperEntryMode, TemplateStatus
from app.infrastructure.database.sqlite_ds import create_sqlite_engine
from app.modules.templates.payroll_profiles_ds import (
    PayrollMaster,
    reviewed_payroll_export_seed_templates,
    reviewed_payroll_profiles,
    reviewed_payroll_seed_templates,
)

EXPECTED_TITLES = {
    "PAYROLL_TIMEKEEPING_DAILY": "计时工日工资表",
    "PAYROLL_FORKLIFT_DAILY": "叉车工日工资表",
    "PAYROLL_RACK_LOADING_DAILY": "装架组日工资表",
    "PAYROLL_BAMBOO_RACK_DAILY": "竹丝装架日工资表",
    "PAYROLL_DRYING_DAILY": "干燥组日工资表",
    "PAYROLL_STEAMING_DAILY": "蒸煮日工资表",
    "PAYROLL_CARBONIZATION_DAILY": "炭化日工资表",
    "PAYROLL_BOILER_DAILY": "锅炉/导热油炉日工资表",
    "PAYROLL_HOT_PRESS_DAILY": "热压岗位日工资表",
    "PAYROLL_SHEET_CUTTING_DAILY": "开片组日工资表",
}
REQUIRED_STATIC_KINDS = {
    ElementKind.TITLE,
    ElementKind.TABLE_GRID,
    ElementKind.CHECKBOX,
    ElementKind.SIGNATURE_LINE,
    ElementKind.ROLE_SECTION,
}
NUMBERED_PLACEHOLDER = re.compile(r"(?:明细)?第\s*\d+\s*行")


def _repository(tmp_path: Path) -> SqlAlchemyTemplateRepository:
    engine = create_sqlite_engine(tmp_path / "profiles.db")
    Base.metadata.create_all(engine)
    return SqlAlchemyTemplateRepository(engine)


def test_reviewed_profiles_define_three_masters_and_ten_real_chinese_forms() -> None:
    profiles = reviewed_payroll_profiles()

    assert len(profiles) == 10
    assert {profile.template_key: profile.display_name for profile in profiles} == EXPECTED_TITLES
    assert Counter(profile.master for profile in profiles) == {
        PayrollMaster.TIMEKEEPING: 2,
        PayrollMaster.CRITERIA_PIECEWORK: 6,
        PayrollMaster.FIXED_PRODUCTION_GRID: 2,
    }
    for profile in profiles:
        assert profile.display_name in profile.structure_checklist
        assert {field.display_name for field in profile.business_fields} <= set(
            profile.structure_checklist
        )
        assert not any(NUMBERED_PLACEHOLDER.search(item) for item in profile.structure_checklist)


def test_reviewed_templates_realize_the_structure_checklists_without_placeholders() -> None:
    templates = reviewed_payroll_seed_templates()
    profiles = {profile.template_key: profile for profile in reviewed_payroll_profiles()}

    assert len(templates) == 10
    for template in templates:
        profile = profiles[template.template_key]
        static_text = {element.text for element in template.static_elements if element.text}
        field_labels = {field.display_name for field in template.fields}
        visible_labels = static_text | field_labels

        assert template.status is TemplateStatus.PUBLISHED
        assert set(profile.structure_checklist) <= visible_labels
        assert REQUIRED_STATIC_KINDS <= {element.kind for element in template.static_elements}
        assert {
            PaperEntryMode.DIGIT_BOXES,
            PaperEntryMode.CHECKBOX,
            PaperEntryMode.SIGNATURE,
        } <= {field.paper_entry_mode for field in template.fields}
        assert all(field.export_target is not None for field in template.fields)
        assert all(field.region.is_inside() for field in template.fields)
        assert not any(NUMBERED_PLACEHOLDER.search(label) for label in visible_labels)
        assert next(
            field for field in template.fields if field.field_key == "worker_name"
        ).requires_manual_confirmation


def test_reviewed_export_v2_keeps_v1_immutable_and_uses_stable_main_detail_columns() -> None:
    v1_templates = reviewed_payroll_seed_templates()
    v2_templates = reviewed_payroll_export_seed_templates()
    profiles = {profile.template_key: profile for profile in reviewed_payroll_profiles()}

    assert len(v2_templates) == 10
    assert {template.template_key for template in v2_templates} == set(EXPECTED_TITLES)
    for v1, v2 in zip(v1_templates, v2_templates, strict=True):
        profile = profiles[v2.template_key]
        common_keys = {field.field_key for field in v2.fields[:6]}
        business_keys = {field.field_key for field in profile.business_fields}

        assert v1.version == 1
        assert v2.version == 2
        assert v1.version_id != v2.version_id
        assert {field.export_target.worksheet for field in v1.fields if field.export_target} == {
            profile.worksheet
        }
        for field in v2.fields:
            assert field.export_target is not None
            assert field.export_target.business_column == field.display_name
            if field.field_key in business_keys:
                assert field.export_target.worksheet == "业务明细"
            else:
                assert field.field_key in common_keys | {
                    "assessment_passed",
                    "assessment_improvement",
                    "assessment_failed",
                    "facts_description",
                    "worker_signature",
                    "quality_signature",
                    "supervisor_signature",
                }
                assert field.export_target.worksheet == "工资主记录"


def test_reviewed_a5_forms_are_two_up_and_a4_forms_remain_single_sheet() -> None:
    templates = reviewed_payroll_seed_templates()

    for template in templates:
        if template.page.size == "A5":
            assert template.print_imposition is not None
            assert template.print_imposition.slot_count == 2
            assert template.print_imposition.fits(template.page)
        else:
            assert template.page.size == "A4"
            assert template.page.orientation == "landscape"
            assert template.print_imposition is None


def test_every_reviewed_layout_passes_physical_and_protected_zone_preflight(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    service = TemplateVersions(repository)

    for published in reviewed_payroll_seed_templates():
        repository.add_version(published)
        draft = service.clone(published.version_id)
        report = service.preflight(draft.version_id)
        assert report.ok, (published.template_key, report.issues)
