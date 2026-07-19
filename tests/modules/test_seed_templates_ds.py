"""Built-in legacy payroll template installation behavior."""

from pathlib import Path

import pytest

from app.adapters.database.models import Base
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.adapters.templates.print_renderer_ds import TemplatePrintRenderer
from app.domain.templates_ds import PageSpec, TemplateStatus, TemplateVersion
from app.infrastructure.database.sqlite_ds import create_sqlite_engine
from app.modules.templates.payroll_profiles_ds import reviewed_payroll_seed_templates
from app.modules.templates.seed_templates_ds import (
    SeedTemplateConflict,
    all_payroll_seed_templates,
    install_legacy_payroll_seed_templates,
    legacy_payroll_seed_templates,
)
from app.services.container import build_services
from config.settings import Settings

LEGACY_KEYS = {
    "PAYROLL_HOURLY",
    "PAYROLL_STANDARD_PIECE",
    "PAYROLL_FIXED_PRODUCTION_GRID",
    "PAYROLL_EQUIPMENT_PROCESS",
}
REVIEWED_KEYS = {
    "PAYROLL_TIMEKEEPING_DAILY",
    "PAYROLL_FORKLIFT_DAILY",
    "PAYROLL_RACK_LOADING_DAILY",
    "PAYROLL_BAMBOO_RACK_DAILY",
    "PAYROLL_DRYING_DAILY",
    "PAYROLL_STEAMING_DAILY",
    "PAYROLL_CARBONIZATION_DAILY",
    "PAYROLL_BOILER_DAILY",
    "PAYROLL_HOT_PRESS_DAILY",
    "PAYROLL_SHEET_CUTTING_DAILY",
}
EXPECTED_KEYS = LEGACY_KEYS | REVIEWED_KEYS


def _repository(tmp_path: Path) -> SqlAlchemyTemplateRepository:
    engine = create_sqlite_engine(tmp_path / "seed.db")
    Base.metadata.create_all(engine)
    return SqlAlchemyTemplateRepository(engine)


def test_seed_templates_are_published_complete_business_definitions() -> None:
    templates = legacy_payroll_seed_templates()

    assert {template.template_key for template in templates} == LEGACY_KEYS
    assert all(template.status is TemplateStatus.PUBLISHED for template in templates)
    for template in templates:
        keys = {field.field_key for field in template.fields}
        assert {"work_date", "shift", "worker_name", "remarks", "assessment_result"} <= keys
        assert {f"line_{number:02d}" for number in range(1, 11)} <= keys
        assert all(field.rules.required is not None for field in template.fields)
        assert all(field.export_target is not None for field in template.fields)
        assert all(field.region.is_inside() for field in template.fields)


def test_all_seed_templates_keep_legacy_compatibility_and_add_reviewed_profiles() -> None:
    templates = all_payroll_seed_templates()

    assert len(templates) == 24
    assert {template.template_key for template in templates} == EXPECTED_KEYS
    assert all(template.status is TemplateStatus.PUBLISHED for template in templates)
    assert {
        template.version for template in templates if template.template_key in REVIEWED_KEYS
    } == {1, 2}
    assert {template.version for template in templates if template.template_key in LEGACY_KEYS} == {
        1
    }


def test_seed_install_is_idempotent_and_generates_print_artifacts(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    renderer = TemplatePrintRenderer(tmp_path / "evidence")

    first = install_legacy_payroll_seed_templates(repository, renderer)
    first_artifact_ids = {
        artifact.artifact_id
        for key in EXPECTED_KEYS
        for version in repository.list_versions(key)
        for artifact in repository.list_artifacts(version.version_id)
    }
    second = install_legacy_payroll_seed_templates(repository, renderer)
    second_artifact_ids = {
        artifact.artifact_id
        for key in EXPECTED_KEYS
        for version in repository.list_versions(key)
        for artifact in repository.list_artifacts(version.version_id)
    }

    assert set(first.installed) == EXPECTED_KEYS
    assert first.existing == ()
    assert second.installed == ()
    assert set(second.existing) == EXPECTED_KEYS
    assert repository.list_template_keys() == sorted(EXPECTED_KEYS)
    assert all(len(repository.list_versions(key)) == 1 for key in LEGACY_KEYS)
    assert all(len(repository.list_versions(key)) == 2 for key in REVIEWED_KEYS)
    assert len(first_artifact_ids) == 64
    assert second_artifact_ids == first_artifact_ids
    for key in EXPECTED_KEYS:
        for version in repository.list_versions(key):
            expected_kinds = {"PRINT_PDF", "PRINT_PNG"}
            if version.print_imposition is not None:
                expected_kinds.add("PRINT_IMPOSED_PDF")
            assert {
                item.kind for item in repository.list_artifacts(version.version_id)
            } == expected_kinds


def test_seed_install_adds_reviewed_v2_without_rewriting_existing_v1(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    renderer = TemplatePrintRenderer(tmp_path / "evidence")
    historical = legacy_payroll_seed_templates() + reviewed_payroll_seed_templates()
    historical_ids = {
        (template.template_key, template.version): template.version_id for template in historical
    }
    for template in historical:
        repository.add_version(template)

    result = install_legacy_payroll_seed_templates(repository, renderer)

    assert set(result.installed) == REVIEWED_KEYS
    assert set(result.existing) == EXPECTED_KEYS
    for (template_key, version), version_id in historical_ids.items():
        restored = repository.get_version_by_key_version(template_key, version)
        assert restored is not None
        assert restored.version_id == version_id
    for template_key in REVIEWED_KEYS:
        assert [version.version for version in repository.list_versions(template_key)] == [1, 2]


def test_seed_install_rejects_same_key_and_version_with_different_content(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.add_version(
        TemplateVersion.draft("TPL-CONFLICT", "PAYROLL_HOURLY", 1, PageSpec.a4_portrait())
    )

    with pytest.raises(SeedTemplateConflict, match="PAYROLL_HOURLY.*version 1"):
        install_legacy_payroll_seed_templates(
            repository,
            TemplatePrintRenderer(tmp_path / "evidence"),
        )
    assert repository.list_template_keys() == ["PAYROLL_HOURLY"]


def test_seed_install_repairs_missing_base_print_artifacts(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    renderer = TemplatePrintRenderer(tmp_path / "evidence")
    install_legacy_payroll_seed_templates(repository, renderer)
    version = repository.list_versions("PAYROLL_HOURLY")[0]
    original = repository.list_artifacts(version.version_id)
    Path(original[0].internal_uri).unlink()

    result = install_legacy_payroll_seed_templates(repository, renderer)
    repaired = repository.list_artifacts(version.version_id)

    assert "PAYROLL_HOURLY" in result.existing
    assert {artifact.download_name for artifact in repaired} == {
        "PAYROLL_HOURLY-v1.pdf",
        "PAYROLL_HOURLY-v1.png",
    }
    assert all(Path(artifact.internal_uri).is_file() for artifact in repaired)


def test_seed_reinstall_preserves_an_intentional_retired_lifecycle(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    renderer = TemplatePrintRenderer(tmp_path / "evidence")
    install_legacy_payroll_seed_templates(repository, renderer)
    version = repository.list_versions("PAYROLL_HOURLY")[0]
    version.retire()
    repository.replace_version(version)

    result = install_legacy_payroll_seed_templates(repository, renderer)

    assert "PAYROLL_HOURLY" in result.existing
    assert repository.list_versions("PAYROLL_HOURLY")[0].status.value == "RETIRED"


def test_application_composition_can_install_seeds_into_a_new_database(tmp_path: Path) -> None:
    first = build_services(Settings(data_root=tmp_path), install_seed_templates=True)
    second = build_services(Settings(data_root=tmp_path), install_seed_templates=True)

    assert set(first.template_repository.list_template_keys()) == EXPECTED_KEYS
    assert set(second.template_repository.list_template_keys()) == EXPECTED_KEYS
    assert sum(len(second.template_repository.list_versions(key)) for key in EXPECTED_KEYS) == 24


def test_application_startup_preserves_conflicting_legacy_template(tmp_path: Path) -> None:
    existing = build_services(Settings(data_root=tmp_path))
    existing.template_repository.add_version(
        TemplateVersion.draft(
            "TPL-LEGACY-HOURLY",
            "PAYROLL_HOURLY",
            1,
            PageSpec.a4_portrait(),
        )
    )

    restarted = build_services(Settings(data_root=tmp_path), install_seed_templates=True)

    assert restarted.template_repository.list_template_keys() == ["PAYROLL_HOURLY"]
    assert (
        restarted.template_repository.list_versions("PAYROLL_HOURLY")[0].version_id
        == "TPL-LEGACY-HOURLY"
    )
