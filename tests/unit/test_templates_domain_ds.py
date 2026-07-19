"""Template domain behavior."""

import pytest

from app.domain.templates_ds import (
    ElementKind,
    FieldDefinition,
    FillPolicy,
    PageSpec,
    PaperEntryMode,
    PrintImposition,
    RecognitionMode,
    Rect,
    StaticElement,
    TemplateStatus,
    TemplateVersion,
    build_sheet_payload,
    build_template_payload,
    parse_sheet_payload,
    parse_template_payload,
)


def test_custom_page_uses_tenth_millimetre_precision_and_canonical_pixels() -> None:
    page = PageSpec.custom(123.4, 87.6, orientation="landscape")

    assert page.size == "CUSTOM"
    assert page.orientation == "landscape"
    assert page.width_mm == 123.4
    assert page.height_mm == 87.6
    assert page.canonical_width_px == 1457
    assert page.canonical_height_px == 1035

    for width, height in ((79.9, 100), (100, 59.9), (420.1, 100), (100, 594.1)):
        with pytest.raises(ValueError, match="custom page"):
            PageSpec.custom(width, height)
    with pytest.raises(ValueError, match="0.1 mm"):
        PageSpec.custom(100.05, 120)


def test_static_elements_and_print_imposition_are_separate_from_fields() -> None:
    page = PageSpec.custom(100, 130)
    title = StaticElement(
        "payroll_title",
        ElementKind.TITLE,
        Rect(0.1, 0.1, 0.8, 0.08),
        text="计时工资表",
    )
    imposition = PrintImposition(
        carrier=PageSpec.a4_landscape(),
        columns=2,
        rows=1,
        horizontal_gap_mm=5,
        margin_mm=5,
    )

    assert title.text == "计时工资表"
    assert imposition.slot_count == 2
    assert imposition.fits(page) is True
    with pytest.raises(ValueError, match="Static titles"):
        FieldDefinition(
            "payroll_title",
            "计时工资表",
            "text",
            "static_text",
            Rect(0.1, 0.1, 0.8, 0.08),
            page,
        )


def test_published_version_cannot_mutate_static_layout_or_imposition() -> None:
    page = PageSpec.a4_portrait()
    version = TemplateVersion.draft("TPL-LAYOUT", "PAYROLL_LAYOUT", 1, page)
    title = StaticElement(
        "payroll_title",
        ElementKind.TITLE,
        Rect(0.1, 0.1, 0.5, 0.05),
        text="工资表",
    )
    version.add_static_element(title)
    version.set_print_imposition(PrintImposition(carrier=page))
    version.mark_ready_to_publish()
    version.publish()

    with pytest.raises(ValueError, match="published"):
        version.remove_static_element(title.element_id)
    with pytest.raises(ValueError, match="published"):
        version.set_print_imposition(None)


def test_template_payload_is_deterministic_and_checksums_key_and_version() -> None:
    assert build_template_payload("PAYROLL_HOURLY", 3) == "IFD|PAYROLL_HOURLY|3|2312"


def test_template_payload_parser_rejects_tampering_and_returns_exact_identity() -> None:
    assert parse_template_payload("IFD|PAYROLL_HOURLY|3|2312") == ("PAYROLL_HOURLY", 3)
    assert parse_template_payload("IFD|PAYROLL_HOURLY|3|FFFF") is None
    assert parse_template_payload("PAYROLL_HOURLY:3") is None


def test_sheet_payload_has_zero_padded_sequence_and_checksum() -> None:
    assert build_sheet_payload("PB20260713A", 128) == "SHEET|PB20260713A|000128|44D8"
    assert parse_sheet_payload("SHEET|PB20260713A|000128|44D8") == (
        "PB20260713A",
        128,
    )
    assert parse_sheet_payload("SHEET|PB20260713A|128|44D8") is None
    assert parse_sheet_payload("SHEET|PB20260713A|000128|FFFF") is None


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


def test_field_behavior_separates_paper_recognition_and_fill_modes() -> None:
    page = PageSpec.a4_portrait()
    field = FieldDefinition(
        "worker_name",
        "姓名",
        "text",
        "text_box",
        Rect(0.1, 0.2, 0.3, 0.05),
        page,
        paper_entry_mode=PaperEntryMode.HANDWRITTEN_TEXT,
        recognition_mode=RecognitionMode.HANDWRITING_OCR,
        fill_policy=FillPolicy.SUGGEST_ONLY,
    )

    assert field.paper_entry_mode is PaperEntryMode.HANDWRITTEN_TEXT
    assert field.recognition_mode is RecognitionMode.HANDWRITING_OCR
    assert field.fill_policy is FillPolicy.SUGGEST_ONLY
    assert field.confidence_threshold is None
    assert field.requires_manual_confirmation is True


def test_switching_recognition_mode_clears_stale_policy_configuration() -> None:
    page = PageSpec.a4_portrait()
    field = FieldDefinition(
        "quantity",
        "数量",
        "integer",
        "digit_boxes",
        Rect(0.1, 0.2, 0.3, 0.05),
        page,
        recognition_mode=RecognitionMode.DIGIT_OCR,
        fill_policy=FillPolicy.PREFILL_WHEN_CONFIDENT,
        confidence_threshold=0.96,
    )

    manual = field.with_recognition_mode(RecognitionMode.NONE)

    assert manual.recognition_mode is RecognitionMode.NONE
    assert manual.fill_policy is FillPolicy.MANUAL_ONLY
    assert manual.confidence_threshold is None
    assert manual.calculation_expression is None
    assert manual.recognition_engine == "manual"


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
