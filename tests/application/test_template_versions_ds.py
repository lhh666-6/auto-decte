"""Template draft, preflight and publication behavior."""

from app.application.template_versions_ds import TemplateVersions
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
)


class InMemoryTemplateRepository:
    def __init__(self) -> None:
        self.versions: dict[str, TemplateVersion] = {}

    def add_version(self, version: TemplateVersion) -> None:
        self.versions[version.version_id] = version

    def get_version(self, version_id: str) -> TemplateVersion | None:
        return self.versions.get(version_id)

    def replace_version(self, version: TemplateVersion) -> None:
        self.versions[version.version_id] = version

    def list_versions(self, template_key: str) -> list[TemplateVersion]:
        return [
            version for version in self.versions.values() if version.template_key == template_key
        ]

    def list_template_keys(self) -> list[str]:
        return list({version.template_key for version in self.versions.values()})


def test_preflight_blocks_field_overlapping_template_qr_safe_zone() -> None:
    service = TemplateVersions(InMemoryTemplateRepository())
    draft = service.create_draft("PAYROLL_HOURLY", PageSpec.a4_portrait())
    service.add_field(
        draft.version_id,
        FieldDefinition(
            "worker_name",
            "姓名",
            "text",
            "text_box",
            Rect(0.82, 0.03, 0.12, 0.08),
            draft.page,
        ),
    )

    report = service.preflight(draft.version_id)

    assert report.ok is False
    assert {issue.code for issue in report.issues} == {"QR_SAFE_ZONE_OVERLAP"}
    assert service.get(draft.version_id).status is TemplateStatus.PREFLIGHT_FAILED


def test_preflight_blocks_sheet_code_corner_markers_and_print_edges() -> None:
    protected_regions = (
        ("sheet_code", Rect(0.64, 0.04, 0.08, 0.06), "SHEET_SAFE_ZONE_OVERLAP"),
        ("corner_marker", Rect(0.03, 0.04, 0.03, 0.03), "CORNER_MARKER_OVERLAP"),
        ("print_edge", Rect(0.40, 0.005, 0.10, 0.01), "PRINT_EDGE_OVERLAP"),
    )
    for field_key, region, expected_code in protected_regions:
        service = TemplateVersions(InMemoryTemplateRepository())
        draft = service.create_draft("PAYROLL_HOURLY", PageSpec.a4_portrait())
        service.add_field(
            draft.version_id,
            FieldDefinition(field_key, field_key, "text", "text_box", region, draft.page),
        )

        report = service.preflight(draft.version_id)

        assert expected_code in {issue.code for issue in report.issues}


def test_preflight_then_publish_and_clone_preserves_immutable_parent() -> None:
    service = TemplateVersions(InMemoryTemplateRepository())
    draft = service.create_draft("PAYROLL_HOURLY", PageSpec.a4_portrait())
    service.add_field(
        draft.version_id,
        FieldDefinition(
            "worker_name",
            "姓名",
            "text",
            "text_box",
            Rect(0.1, 0.2, 0.2, 0.05),
            draft.page,
        ),
    )
    service.add_static_element(
        draft.version_id,
        StaticElement(
            "payroll_title",
            ElementKind.TITLE,
            Rect(0.1, 0.1, 0.4, 0.04),
            text="计时工资表",
        ),
    )
    service.set_print_imposition(
        draft.version_id,
        PrintImposition(carrier=PageSpec.a4_portrait()),
    )

    assert service.preflight(draft.version_id).ok is True
    published = service.publish(draft.version_id)
    clone = service.clone(published.version_id)

    assert published.status is TemplateStatus.PUBLISHED
    assert clone.status is TemplateStatus.DRAFT
    assert clone.version == 2
    assert clone.parent_version_id == published.version_id
    assert [field.field_key for field in clone.fields] == ["worker_name"]
    assert clone.static_elements == published.static_elements
    assert clone.print_imposition == published.print_imposition


def test_preflight_rejects_incompatible_recognition_engine_and_field_shape() -> None:
    service = TemplateVersions(InMemoryTemplateRepository())
    draft = service.create_draft("PAYROLL_HOURLY", PageSpec.a4_portrait())
    service.add_field(
        draft.version_id,
        FieldDefinition(
            "notes",
            "Notes",
            "text",
            "text_box",
            Rect(0.1, 0.2, 0.2, 0.05),
            draft.page,
            recognition_engine="digit_template",
        ),
    )

    report = service.preflight(draft.version_id)

    assert {issue.code for issue in report.issues} == {"RECOGNITION_ENGINE_MISMATCH"}


def test_preflight_accepts_suggestion_and_conditional_prefill_policies() -> None:
    for field_key, data_type, paper_mode, recognition_mode, fill_policy, threshold in (
        (
            "worker_name",
            "text",
            PaperEntryMode.HANDWRITTEN_TEXT,
            RecognitionMode.HANDWRITING_OCR,
            FillPolicy.SUGGEST_ONLY,
            None,
        ),
        (
            "worker_number",
            "integer",
            PaperEntryMode.DIGIT_BOXES,
            RecognitionMode.DIGIT_OCR,
            FillPolicy.PREFILL_WHEN_CONFIDENT,
            0.97,
        ),
        (
            "quality_ok",
            "boolean",
            PaperEntryMode.CHECKBOX,
            RecognitionMode.OMR,
            FillPolicy.SUGGEST_ONLY,
            None,
        ),
    ):
        service = TemplateVersions(InMemoryTemplateRepository())
        draft = service.create_draft("PAYROLL_BEHAVIOR", PageSpec.a4_portrait())
        service.add_field(
            draft.version_id,
            FieldDefinition(
                field_key,
                {"worker_name": "姓名", "worker_number": "工号", "quality_ok": "质量合格"}[
                    field_key
                ],
                data_type,
                {
                    PaperEntryMode.HANDWRITTEN_TEXT: "text_box",
                    PaperEntryMode.DIGIT_BOXES: "digit_boxes",
                    PaperEntryMode.CHECKBOX: "checkbox",
                }[paper_mode],
                Rect(0.1, 0.2, 0.3, 0.05),
                draft.page,
                paper_entry_mode=paper_mode,
                recognition_mode=recognition_mode,
                fill_policy=fill_policy,
                confidence_threshold=threshold,
            ),
        )

        assert service.preflight(draft.version_id).ok is True


def test_preflight_rejects_manual_threshold_calculation_ocr_and_name_autofill() -> None:
    invalid_fields = (
        FieldDefinition(
            "manual_note",
            "人工说明",
            "text",
            "text_box",
            Rect(0.1, 0.2, 0.3, 0.05),
            PageSpec.a4_portrait(),
            recognition_mode=RecognitionMode.NONE,
            fill_policy=FillPolicy.MANUAL_ONLY,
            confidence_threshold=0.8,
        ),
        FieldDefinition(
            "manual_prefill",
            "人工字段",
            "text",
            "text_box",
            Rect(0.1, 0.25, 0.3, 0.05),
            PageSpec.a4_portrait(),
            recognition_mode=RecognitionMode.NONE,
            fill_policy=FillPolicy.PREFILL_WHEN_CONFIDENT,
            confidence_threshold=0.8,
        ),
        FieldDefinition(
            "calculated_total",
            "自动合计",
            "decimal",
            "none",
            Rect(0.1, 0.3, 0.3, 0.05),
            PageSpec.a4_portrait(),
            paper_entry_mode=PaperEntryMode.NONE,
            recognition_mode=RecognitionMode.CALCULATED,
            fill_policy=FillPolicy.CALCULATED,
            confidence_threshold=0.9,
        ),
        FieldDefinition(
            "worker_name",
            "姓名",
            "text",
            "text_box",
            Rect(0.1, 0.4, 0.3, 0.05),
            PageSpec.a4_portrait(),
            recognition_mode=RecognitionMode.HANDWRITING_OCR,
            fill_policy=FillPolicy.PREFILL_WHEN_CONFIDENT,
            confidence_threshold=0.99,
        ),
    )
    service = TemplateVersions(InMemoryTemplateRepository())
    draft = service.create_draft("PAYROLL_INVALID_BEHAVIOR", PageSpec.a4_portrait())
    for definition in invalid_fields:
        service.add_field(draft.version_id, definition)

    report = service.preflight(draft.version_id)

    assert {issue.code for issue in report.issues} >= {
        "CONFIDENCE_THRESHOLD_NOT_ALLOWED",
        "FIELD_BEHAVIOR_MISMATCH",
        "CALCULATION_RULE_REQUIRED",
        "NAME_REQUIRES_MANUAL_CONFIRMATION",
    }


def test_preflight_uses_physical_field_sizes_and_five_millimetre_margin() -> None:
    service = TemplateVersions(InMemoryTemplateRepository())
    draft = service.create_draft("PAYROLL_SMALL", PageSpec.custom(80, 60))
    service.add_field(
        draft.version_id,
        FieldDefinition(
            "worker_number",
            "工号",
            "integer",
            "digit_boxes",
            Rect(0.04, 0.3, 0.05, 0.1),
            draft.page,
            recognition_engine="digit_template",
        ),
    )

    report = service.preflight(draft.version_id)

    assert {issue.code for issue in report.issues} >= {
        "PRINT_EDGE_OVERLAP",
        "PHYSICAL_MINIMUM_SIZE",
    }


def test_preflight_protects_qr_zone_from_static_elements_and_checks_imposition_fit() -> None:
    service = TemplateVersions(InMemoryTemplateRepository())
    draft = service.create_draft("PAYROLL_SMALL", PageSpec.custom(150, 200))
    service.add_static_element(
        draft.version_id,
        StaticElement(
            "payroll_title",
            ElementKind.TITLE,
            Rect(0.75, 0.02, 0.2, 0.1),
            text="工资表",
        )
    )
    service.set_print_imposition(
        draft.version_id,
        PrintImposition(
            carrier=PageSpec.a4_portrait(),
            columns=2,
            rows=1,
            horizontal_gap_mm=5,
            margin_mm=5,
        )
    )
    report = service.preflight(draft.version_id)

    assert {issue.code for issue in report.issues} >= {
        "QR_SAFE_ZONE_OVERLAP",
        "IMPOSITION_DOES_NOT_FIT",
    }


def test_list_templates_returns_full_versions_in_deterministic_order() -> None:
    repository = InMemoryTemplateRepository()
    page = PageSpec.a4_portrait()
    for version_id, template_key, version in (
        ("TPL-P-1", "PAYROLL_STANDARD_PIECE", 1),
        ("TPL-H-2", "PAYROLL_HOURLY", 2),
        ("TPL-H-1B", "PAYROLL_HOURLY", 1),
        ("TPL-H-1A", "PAYROLL_HOURLY", 1),
    ):
        repository.add_version(TemplateVersion.draft(version_id, template_key, version, page))

    templates = TemplateVersions(repository).list_templates()

    assert [
        (template.template_key, template.version, template.version_id) for template in templates
    ] == [
        ("PAYROLL_HOURLY", 1, "TPL-H-1A"),
        ("PAYROLL_HOURLY", 1, "TPL-H-1B"),
        ("PAYROLL_HOURLY", 2, "TPL-H-2"),
        ("PAYROLL_STANDARD_PIECE", 1, "TPL-P-1"),
    ]


def test_draft_fields_can_be_replaced_and_removed() -> None:
    service = TemplateVersions(InMemoryTemplateRepository())
    draft = service.create_draft("PAYROLL_HOURLY", PageSpec.a4_portrait())
    quantity = FieldDefinition(
        "quantity",
        "数量",
        "integer",
        "digit_boxes",
        Rect(0.2, 0.3, 0.24, 0.05),
        draft.page,
        recognition_engine="digit_template",
        minimum_prefill_confidence=0.97,
    )
    service.add_field(draft.version_id, quantity)

    updated = service.replace_field(
        draft.version_id,
        "quantity",
        FieldDefinition(
            "quantity",
            "合格数量",
            "integer",
            "digit_boxes",
            Rect(0.2, 0.3, 0.24, 0.05),
            draft.page,
            recognition_engine="digit_template",
            minimum_prefill_confidence=0.97,
        ),
    )
    assert updated.fields[0].display_name == "合格数量"

    removed = service.remove_field(draft.version_id, "quantity")

    assert removed.fields == []
