"""Application service for electronic form definitions bound to templates.

Validates that published definitions reference real, published template
and job-profile versions. Field keys must exist in the target template.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.modules.electronic_forms.facade_ds import ElectronicDefinitionService
from app.modules.electronic_forms.models_ds import (
    ElectronicFormDefinitionVersion,
    PresentationConfig,
    PresentationField,
)


@dataclass
class DefinitionTemplateBinding:
    """Checked binding between an electronic definition and a template."""

    definition: ElectronicFormDefinitionVersion
    template_display_name: str
    job_profile_display_name: str | None


class DefinitionValidationError(ValueError):
    pass


def validate_presentation_fields(
    definition: ElectronicFormDefinitionVersion,
    template_repo: SqlAlchemyTemplateRepository,
) -> None:
    """Raise DefinitionValidationError if any presentation field_key
    does not exist in the bound template version."""
    if definition.template_version_id is None:
        return
    template = template_repo.get_version(definition.template_version_id)
    if template is None:
        raise DefinitionValidationError(
            f"Template version {definition.template_version_id} not found.",
        )
    valid_keys: set[str] = set()
    for field_def in template.field_definitions or []:
        valid_keys.add(field_def.field_key)
    config = definition.presentation_config
    if config is None:
        return
    for pf in config.fields:
        if pf.field_key not in valid_keys:
            raise DefinitionValidationError(
                f"Presentation field '{pf.field_key}' not found in "
                f"template '{template.template_key}' version {template.version}. "
                f"Valid keys: {sorted(valid_keys)!r}",
            )


def publish_definition(
    definition_version_id: str,
    definition_svc: ElectronicDefinitionService,
    template_repo: SqlAlchemyTemplateRepository,
) -> ElectronicFormDefinitionVersion:
    """Publish after validating template binding and field keys."""
    definition = definition_svc._repo.get(definition_version_id)
    if definition is None:
        raise DefinitionValidationError("Definition not found.")

    if definition.template_version_id is None:
        raise DefinitionValidationError(
            "Cannot publish a definition without a bound template version.",
        )
    template = template_repo.get_version(definition.template_version_id)
    if template is None:
        raise DefinitionValidationError(
            f"Template version {definition.template_version_id} not found.",
        )
    if template.status.value != "PUBLISHED":
        raise DefinitionValidationError(
            f"Template '{template.template_key}' version {template.version} "
            f"is not PUBLISHED (status: {template.status.value}).",
        )

    if definition.job_profile_version_id:
        # Validate job profile exists (get by its version_id — we need to search)
        # The template repo doesn't have get_job_profile_by_version_id,
        # so we iterate over known profiles for now.
        _validate_job_profile(definition, template_repo)

    validate_presentation_fields(definition, template_repo)
    return definition_svc.publish(definition_version_id)


def _validate_job_profile(
    definition: ElectronicFormDefinitionVersion,
    template_repo: SqlAlchemyTemplateRepository,
) -> None:
    """Check that the job profile version exists and is published."""
    # Scan all known profile keys; in production this would be a direct lookup.
    # For now we check that the profile exists in the template_repo.
    profiles = template_repo.list_job_profiles("")  # empty returns all?
    # Actually list_job_profiles requires a profile_key. We iterate template keys.
    template_keys = template_repo.list_template_keys()
    for tk in template_keys:
        for profile in template_repo.list_job_profiles(tk):
            if profile.profile_version_id == definition.job_profile_version_id:
                if profile.status.value != "PUBLISHED":
                    raise DefinitionValidationError(
                        f"Job profile '{profile.profile_key}' version "
                        f"{profile.version} is not PUBLISHED.",
                    )
                return
    raise DefinitionValidationError(
        f"Job profile version {definition.job_profile_version_id} not found.",
    )
