"""V2 six-core payroll layout seed definitions."""

from app.adapters.database.models import Base
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.domain.templates_ds import (
    CoreLayoutKind,
    ElementKind,
    JobProfileStatus,
    PaperEntryMode,
    TemplateStatus,
)
from app.infrastructure.database.sqlite_ds import create_sqlite_engine
from app.modules.templates.core_payroll_layouts_ds import (
    core_payroll_seed_templates,
    install_reviewed_job_profile_seeds,
    reviewed_job_profile_seed_versions,
)


def test_exactly_six_distinct_core_layouts_use_required_landscape_paper() -> None:
    templates = core_payroll_seed_templates()

    assert len(templates) == 6
    assert len({item.template_key for item in templates}) == 6
    assert all(item.status is TemplateStatus.PUBLISHED for item in templates)
    pages = {item.template_key: (item.page.size, item.page.orientation) for item in templates}
    assert pages == {
        "PAYROLL_CORE_TIMEKEEPING": ("A5", "landscape"),
        "PAYROLL_CORE_EQUIPMENT_TIMEKEEPING": ("A5", "landscape"),
        "PAYROLL_CORE_RACK_DRYING_PIECEWORK": ("A5", "landscape"),
        "PAYROLL_CORE_FURNACE_WORK": ("A5", "landscape"),
        "PAYROLL_CORE_HOT_PRESS": ("A4", "landscape"),
        "PAYROLL_CORE_SHEET_CUTTING": ("A4", "landscape"),
    }


def test_core_layouts_use_real_two_row_grids_and_controlled_identity_fields() -> None:
    for template in core_payroll_seed_templates():
        grid = next(item for item in template.static_elements if item.element_id == "business_grid")
        assert grid.kind is ElementKind.TABLE_GRID
        assert grid.rows == 3
        assert grid.columns >= 7
        assert len(grid.column_weights) == grid.columns

        fields = {item.field_key: item for item in template.fields}
        assert fields["work_date"].digit_count == 8
        assert fields["worker_number"].digit_count == 6
        assert fields["worker_name"].paper_entry_mode is PaperEntryMode.NONE
        assert fields["worker_name"].derived_from_field_key == "worker_number"
        assert fields["shift"].choice_options == ("白班", "夜班")
        assert fields["shift"].max_selections == 1
        assert fields["worker_signature"].signature_role == "worker"
        assert fields["supervisor_signature"].signature_role == "supervisor"


def test_each_core_layout_has_its_required_business_columns_and_calculations() -> None:
    templates = {item.template_key: item for item in core_payroll_seed_templates()}

    expected = {
        "PAYROLL_CORE_TIMEKEEPING": {
            "start_time_1",
            "rest_minutes_1",
            "effective_hours_1",
            "work_type_1",
        },
        "PAYROLL_CORE_EQUIPMENT_TIMEKEEPING": {
            "device_number",
            "load_count_1",
            "unload_count_1",
            "downtime_minutes_1",
        },
        "PAYROLL_CORE_RACK_DRYING_PIECEWORK": {
            "batch_number_1",
            "operation_type_1",
            "completed_quantity_1",
            "rejected_quantity_1",
        },
        "PAYROLL_CORE_FURNACE_WORK": {
            "furnace_number",
            "input_quantity_1",
            "temperature_level_1",
            "operation_status_1",
        },
        "PAYROLL_CORE_HOT_PRESS": {
            "layers_1",
            "rework_quantity_1",
            "scrap_quantity_1",
            "equipment_status",
        },
        "PAYROLL_CORE_SHEET_CUTTING": {
            "raw_material_spec_1",
            "finished_spec_1",
            "defect_quantity_1",
            "rework_status",
        },
    }
    for key, required in expected.items():
        fields = {item.field_key: item for item in templates[key].fields}
        assert required <= fields.keys()
        calculated = [field for field in fields.values() if field.calculation_expression]
        assert calculated
        assert all(field.paper_entry_mode is PaperEntryMode.NONE for field in calculated)


def test_ten_reviewed_job_profiles_bind_exactly_one_of_six_core_versions() -> None:
    templates = {item.version_id: item for item in core_payroll_seed_templates()}
    profiles = reviewed_job_profile_seed_versions()

    assert len(profiles) == 10
    assert all(item.status is JobProfileStatus.PUBLISHED for item in profiles)
    assert {item.core_layout for item in profiles} == set(CoreLayoutKind)
    for profile in profiles:
        template = templates[profile.template_version_id]
        assert profile.template_version == template.version
        assert profile.core_layout.value in template.template_key
        assert profile.fixed_options["position_name"] == profile.display_name

    mapping = {item.profile_key: item.core_layout for item in profiles}
    assert mapping["PAYROLL_TIMEKEEPING_DAILY"] is CoreLayoutKind.TIMEKEEPING
    assert mapping["PAYROLL_FORKLIFT_DAILY"] is CoreLayoutKind.EQUIPMENT_TIMEKEEPING
    assert mapping["PAYROLL_RACK_LOADING_DAILY"] is CoreLayoutKind.RACK_DRYING_PIECEWORK
    assert mapping["PAYROLL_STEAMING_DAILY"] is CoreLayoutKind.FURNACE_WORK
    assert mapping["PAYROLL_HOT_PRESS_DAILY"] is CoreLayoutKind.HOT_PRESS
    assert mapping["PAYROLL_SHEET_CUTTING_DAILY"] is CoreLayoutKind.SHEET_CUTTING


def test_job_profile_seed_install_is_idempotent_after_core_templates_exist(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "job-profile-seeds.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyTemplateRepository(engine)
    for template in core_payroll_seed_templates():
        repository.add_version(template)

    first = install_reviewed_job_profile_seeds(repository)
    second = install_reviewed_job_profile_seeds(repository)

    assert len(first.installed) == 10
    assert first.existing == ()
    assert second.installed == ()
    assert len(second.existing) == 10
    assert all(len(repository.list_job_profiles(key)) == 1 for key in first.installed)
