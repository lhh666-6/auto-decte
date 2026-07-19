"""Use cases for versioned payroll job configurations."""

from __future__ import annotations

from typing import Protocol

from app.domain.templates_ds import (
    CoreLayoutKind,
    PayrollJobProfileVersion,
    TemplateVersion,
)


class JobProfileRepository(Protocol):
    def add_job_profile(self, profile: PayrollJobProfileVersion) -> None: ...

    def get_job_profile(
        self, profile_version_id: str
    ) -> PayrollJobProfileVersion | None: ...

    def replace_job_profile(self, profile: PayrollJobProfileVersion) -> None: ...

    def list_job_profiles(self, profile_key: str) -> list[PayrollJobProfileVersion]: ...


class TemplateVersionLookup(Protocol):
    def get_version(self, version_id: str) -> TemplateVersion | None: ...


class JobProfiles:
    """Coordinate profile lifecycle without exposing persistence to HTTP handlers."""

    def __init__(
        self,
        repository: JobProfileRepository,
        template_versions: TemplateVersionLookup,
    ) -> None:
        self._repository = repository
        self._template_versions = template_versions

    def create_draft(
        self,
        profile_version_id: str,
        profile_key: str,
        version: int,
        *,
        display_name: str,
        core_layout: CoreLayoutKind,
        template_version_id: str,
        template_version: int,
        unit: str = "",
        fixed_options: dict[str, object] | None = None,
        pricing_rules: dict[str, object] | None = None,
        deduction_rules: dict[str, object] | None = None,
        export_mapping: dict[str, object] | None = None,
    ) -> PayrollJobProfileVersion:
        profile = PayrollJobProfileVersion.draft(
            profile_version_id,
            profile_key,
            version,
            display_name=display_name,
            core_layout=core_layout,
            template_version_id=template_version_id,
            template_version=template_version,
            unit=unit,
            fixed_options=fixed_options,
            pricing_rules=pricing_rules,
            deduction_rules=deduction_rules,
            export_mapping=export_mapping,
        )
        self._repository.add_job_profile(profile)
        return profile

    def get(self, profile_version_id: str) -> PayrollJobProfileVersion:
        return self._get_required(profile_version_id)

    def list_versions(self, profile_key: str) -> list[PayrollJobProfileVersion]:
        return self._repository.list_job_profiles(profile_key)

    def update_configuration(
        self,
        profile_version_id: str,
        *,
        display_name: str | None = None,
        unit: str | None = None,
        fixed_options: dict[str, object] | None = None,
        pricing_rules: dict[str, object] | None = None,
        deduction_rules: dict[str, object] | None = None,
        export_mapping: dict[str, object] | None = None,
    ) -> PayrollJobProfileVersion:
        profile = self._get_required(profile_version_id)
        profile.update_configuration(
            display_name=display_name,
            unit=unit,
            fixed_options=fixed_options,
            pricing_rules=pricing_rules,
            deduction_rules=deduction_rules,
            export_mapping=export_mapping,
        )
        self._repository.replace_job_profile(profile)
        return profile

    def publish(self, profile_version_id: str) -> PayrollJobProfileVersion:
        profile = self._get_required(profile_version_id)
        template = self._template_versions.get_version(profile.template_version_id)
        if template is None:
            raise ValueError("bound template version does not exist")
        if template.version != profile.template_version:
            raise ValueError("bound template version does not match profile")
        profile.mark_ready_to_publish()
        self._repository.replace_job_profile(profile)
        profile.publish()
        self._repository.replace_job_profile(profile)
        return profile

    def clone_as_draft(
        self,
        profile_version_id: str,
        new_profile_version_id: str,
        new_version: int,
    ) -> PayrollJobProfileVersion:
        source = self._get_required(profile_version_id)
        clone = source.clone_as_draft(new_profile_version_id, new_version)
        self._repository.add_job_profile(clone)
        return clone

    def retire(self, profile_version_id: str) -> PayrollJobProfileVersion:
        profile = self._get_required(profile_version_id)
        profile.retire()
        self._repository.replace_job_profile(profile)
        return profile

    def _get_required(self, profile_version_id: str) -> PayrollJobProfileVersion:
        profile = self._repository.get_job_profile(profile_version_id)
        if profile is None:
            raise KeyError(f"Unknown job profile version: {profile_version_id}")
        return profile
