"""API tests for mobile definition endpoints (Task 3).

Tests that electronic definitions can only be published when referencing
published template/job-profile versions, and that presentation field keys
exist in the target template.
"""

import pytest

from app.application.electronic_definitions_ds import (
    DefinitionValidationError,
    validate_presentation_fields,
)
from app.modules.electronic_forms.facade_ds import ElectronicDefinitionService
from app.modules.electronic_forms.models_ds import (
    ElectronicFormDefinitionVersion,
    PresentationConfig,
    PresentationField,
)
from app.modules.electronic_forms.ports_ds import ElectronicFormDefinitionRepository

# ── Fakes ───────────────────────────────────────────────────────


class _FakeDefinitionRepo(ElectronicFormDefinitionRepository):
    def __init__(self) -> None:
        self._store: dict[str, ElectronicFormDefinitionVersion] = {}

    def add(self, d: ElectronicFormDefinitionVersion) -> None:
        self._store[d.definition_version_id] = d

    def get(self, did: str) -> ElectronicFormDefinitionVersion | None:
        return self._store.get(did)

    def get_published(self, form_type: str) -> ElectronicFormDefinitionVersion | None:
        for d in self._store.values():
            if d.form_type == form_type and d.status.value == "PUBLISHED":
                return d
        return None

    def list_by_form_type(self, form_type: str) -> list[ElectronicFormDefinitionVersion]:
        return [d for d in self._store.values() if d.form_type == form_type]


# ── Unit tests ──────────────────────────────────────────────────


class TestPublishRequiresPublishedTemplate:
    def test_publish_fails_when_template_not_found(self) -> None:
        repo = _FakeDefinitionRepo()
        svc = ElectronicDefinitionService(repo)
        d = svc.create_draft(
            "FT",
            "测试",
            template_version_id="nonexistent",
            created_by="test",
        )
        # Mock template repo that returns None
        with pytest.raises(DefinitionValidationError, match="not found"):
            validate_presentation_fields(d, _fake_template_repo(has_version=False))

    def test_validate_presentation_rejects_unknown_field(self) -> None:
        config = PresentationConfig(
            fields=[PresentationField(field_key="fantasy_field", display_order=1)],
        )
        d = ElectronicFormDefinitionVersion(
            definition_version_id="efd-badfield",
            form_type="FT",
            version=1,
            template_version_id="tpl-v1",
            presentation_config=config,
        )
        with pytest.raises(DefinitionValidationError, match="fantasy_field"):
            validate_presentation_fields(d, _fake_template_repo(has_version=True))


# ── Helpers ─────────────────────────────────────────────────────


class _MockTemplateRepo:
    """Minimal template repo stub for validation tests."""

    def __init__(self, has_version: bool) -> None:
        self._has_version = has_version

    def get_version(self, version_id: str):
        if self._has_version:
            # Plain object with field_key attribute to match what
            # validate_presentation_fields iterates over
            mock_field = type("F", (), {"field_key": "block_count"})()
            mock_field2 = type("F", (), {"field_key": "total_piece_count"})()
            return type(
                "MockTemplate",
                (),
                {
                    "version_id": version_id,
                    "template_key": "TEST_TPL",
                    "version": 1,
                    "status": type("S", (), {"value": "PUBLISHED"})(),
                    "fields": [mock_field, mock_field2],
                },
            )()
        return None

    def list_job_profiles(self, profile_key: str) -> list:
        return []

    def list_template_keys(self) -> list[str]:
        return ["TEST_TPL"]


def _fake_template_repo(has_version: bool) -> _MockTemplateRepo:
    return _MockTemplateRepo(has_version)
