"""Application use cases for versioned payroll job profiles."""

from dataclasses import replace

import pytest

from app.application.job_profiles_ds import JobProfiles
from app.domain.templates_ds import (
    CoreLayoutKind,
    JobProfileStatus,
    PageSpec,
    PayrollJobProfileVersion,
    TemplateVersion,
)


class InMemoryJobProfileRepository:
    def __init__(self) -> None:
        self.items: dict[str, PayrollJobProfileVersion] = {}

    def add_job_profile(self, profile: PayrollJobProfileVersion) -> None:
        self.items[profile.profile_version_id] = replace(profile)

    def get_job_profile(self, profile_version_id: str) -> PayrollJobProfileVersion | None:
        profile = self.items.get(profile_version_id)
        return replace(profile) if profile is not None else None

    def replace_job_profile(self, profile: PayrollJobProfileVersion) -> None:
        if profile.profile_version_id not in self.items:
            raise KeyError(profile.profile_version_id)
        self.items[profile.profile_version_id] = replace(profile)

    def list_job_profiles(self, profile_key: str) -> list[PayrollJobProfileVersion]:
        return [
            replace(profile)
            for profile in sorted(self.items.values(), key=lambda item: item.version)
            if profile.profile_key == profile_key
        ]


class InMemoryTemplateLookup:
    def __init__(self, *versions: TemplateVersion) -> None:
        self.items = {version.version_id: version for version in versions}

    def get_version(self, version_id: str) -> TemplateVersion | None:
        return self.items.get(version_id)


def _service(template_version: int = 2) -> JobProfiles:
    template = TemplateVersion.draft(
        "TPL-TIMEKEEPING-V2", "CORE_TIMEKEEPING", template_version, PageSpec.a5_landscape()
    )
    return JobProfiles(InMemoryJobProfileRepository(), InMemoryTemplateLookup(template))


def test_create_update_get_and_list_job_profile_drafts() -> None:
    service = _service()
    created = service.create_draft(
        "PROFILE-DAY-V1",
        "TIMEKEEPING_DAY",
        1,
        display_name="计时工白班",
        core_layout=CoreLayoutKind.TIMEKEEPING,
        template_version_id="TPL-TIMEKEEPING-V2",
        template_version=2,
        fixed_options={"shift": ["白班"]},
    )

    updated = service.update_configuration(created.profile_version_id, unit="小时")

    assert service.get(created.profile_version_id) == updated
    assert service.list_versions("TIMEKEEPING_DAY") == [updated]
    assert updated.unit == "小时"


def test_publish_requires_an_existing_matching_template_version() -> None:
    missing_service = JobProfiles(InMemoryJobProfileRepository(), InMemoryTemplateLookup())
    missing = missing_service.create_draft(
        "PROFILE-MISSING-V1",
        "TIMEKEEPING_DAY",
        1,
        display_name="计时工",
        core_layout=CoreLayoutKind.TIMEKEEPING,
        template_version_id="TPL-MISSING",
        template_version=1,
    )
    with pytest.raises(ValueError, match="does not exist"):
        missing_service.publish(missing.profile_version_id)

    mismatched_service = _service(template_version=3)
    mismatched = mismatched_service.create_draft(
        "PROFILE-MISMATCH-V1",
        "TIMEKEEPING_DAY",
        1,
        display_name="计时工",
        core_layout=CoreLayoutKind.TIMEKEEPING,
        template_version_id="TPL-TIMEKEEPING-V2",
        template_version=2,
    )
    with pytest.raises(ValueError, match="version does not match"):
        mismatched_service.publish(mismatched.profile_version_id)


def test_publish_clone_and_retire_job_profile_versions() -> None:
    service = _service()
    draft = service.create_draft(
        "PROFILE-DAY-V1",
        "TIMEKEEPING_DAY",
        1,
        display_name="计时工白班",
        core_layout=CoreLayoutKind.TIMEKEEPING,
        template_version_id="TPL-TIMEKEEPING-V2",
        template_version=2,
    )

    published = service.publish(draft.profile_version_id)
    assert published.status is JobProfileStatus.PUBLISHED
    with pytest.raises(ValueError, match="published"):
        service.update_configuration(published.profile_version_id, unit="小时")

    clone = service.clone_as_draft(published.profile_version_id, "PROFILE-DAY-V2", 2)
    assert clone.status is JobProfileStatus.DRAFT
    assert clone.parent_profile_version_id == published.profile_version_id
    assert service.retire(published.profile_version_id).status is JobProfileStatus.RETIRED
