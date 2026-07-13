"""Template domain behavior."""

import pytest

from app.domain.templates_ds import (
    FieldDefinition,
    PageSpec,
    Rect,
    TemplateStatus,
    TemplateVersion,
    build_sheet_payload,
    build_template_payload,
)


def test_template_payload_is_deterministic_and_checksums_key_and_version() -> None:
    assert build_template_payload("PAYROLL_HOURLY", 3) == "IFD|PAYROLL_HOURLY|3|2312"


def test_sheet_payload_has_zero_padded_sequence_and_checksum() -> None:
    assert build_sheet_payload("PB20260713A", 128) == "SHEET|PB20260713A|000128|44D8"


def test_invalid_template_key_and_out_of_canvas_field_are_rejected() -> None:
    page = PageSpec.a4_portrait()
    with pytest.raises(ValueError, match="template_key"):
        build_template_payload("hourly-pay", 1)
    with pytest.raises(ValueError, match="inside canonical canvas"):
        FieldDefinition(
            "hours",
            "工时",
            "decimal",
            "digit_boxes",
            Rect(0.9, 0.2, 0.2, 0.1),
            page,
        )


def test_published_version_cannot_be_mutated() -> None:
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, PageSpec.a4_portrait())
    version.publish()

    assert version.status is TemplateStatus.PUBLISHED
    with pytest.raises(ValueError, match="published"):
        version.add_field(
            FieldDefinition(
                "hours",
                "工时",
                "decimal",
                "digit_boxes",
                Rect(0.1, 0.1, 0.1, 0.1),
                version.page,
            )
        )
