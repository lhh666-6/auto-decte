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
    parse_template_payload,
)


def test_template_payload_is_deterministic_and_checksums_key_and_version() -> None:
    assert build_template_payload("PAYROLL_HOURLY", 3) == "IFD|PAYROLL_HOURLY|3|2312"


def test_template_payload_parser_rejects_tampering_and_returns_exact_identity() -> None:
    assert parse_template_payload("IFD|PAYROLL_HOURLY|3|2312") == ("PAYROLL_HOURLY", 3)
    assert parse_template_payload("IFD|PAYROLL_HOURLY|3|FFFF") is None
    assert parse_template_payload("PAYROLL_HOURLY:3") is None


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


def test_field_definition_declares_immutable_recognition_and_prefill_policy() -> None:
    page = PageSpec.a4_portrait()
    field = FieldDefinition(
        "total_quantity",
        "Total",
        "integer",
        "digit_boxes",
        Rect(0.1, 0.2, 0.2, 0.1),
        page,
        recognition_engine="digit_template",
        minimum_prefill_confidence=0.97,
    )

    assert field.recognition_engine == "digit_template"
    assert field.minimum_prefill_confidence == 0.97
    with pytest.raises(ValueError, match="minimum_prefill_confidence"):
        FieldDefinition(
            "checked",
            "Checked",
            "boolean",
            "checkbox",
            Rect(0.1, 0.2, 0.2, 0.1),
            page,
            minimum_prefill_confidence=1.1,
        )


def test_draft_version_can_replace_then_remove_a_field() -> None:
    page = PageSpec.a4_portrait()
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, page)
    version.add_field(
        FieldDefinition(
            "hours",
            "Hours",
            "decimal",
            "digit_boxes",
            Rect(0.1, 0.1, 0.1, 0.1),
            page,
        )
    )
    other_field = FieldDefinition(
        "overtime_hours",
        "Overtime hours",
        "decimal",
        "digit_boxes",
        Rect(0.4, 0.1, 0.1, 0.1),
        page,
    )
    version.add_field(other_field)

    replacement = FieldDefinition(
        "hours",
        "Hours worked",
        "decimal",
        "digit_boxes",
        Rect(0.2, 0.1, 0.1, 0.1),
        page,
    )
    version.replace_field("hours", replacement)

    assert version.fields == [replacement, other_field]
    assert version.fields[0].display_name == "Hours worked"
    assert version.fields[0].region == Rect(0.2, 0.1, 0.1, 0.1)
    version.remove_field("hours")
    assert version.fields == [other_field]
    version.remove_field("overtime_hours")

    assert version.fields == []
    assert version.status is TemplateStatus.DRAFT


def test_draft_version_rejects_unknown_field_replacement_and_removal() -> None:
    page = PageSpec.a4_portrait()
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, page)
    replacement = FieldDefinition(
        "hours",
        "Hours worked",
        "decimal",
        "digit_boxes",
        Rect(0.2, 0.1, 0.1, 0.1),
        page,
    )

    with pytest.raises(KeyError, match="Unknown field: hours"):
        version.replace_field("hours", replacement)
    with pytest.raises(KeyError, match="Unknown field: hours"):
        version.remove_field("hours")


def test_published_version_cannot_be_mutated() -> None:
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, PageSpec.a4_portrait())
    field = FieldDefinition(
        "hours",
        "Hours",
        "decimal",
        "digit_boxes",
        Rect(0.1, 0.1, 0.1, 0.1),
        version.page,
    )
    version.add_field(field)
    with pytest.raises(ValueError, match="preflight"):
        version.publish()
    version.mark_ready_to_publish()
    version.publish()

    assert version.status is TemplateStatus.PUBLISHED
    with pytest.raises(ValueError, match="published"):
        version.replace_field("hours", field)
    with pytest.raises(ValueError, match="published"):
        version.remove_field("hours")
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
