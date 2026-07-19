"""Printable template artifact behavior."""

from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from app.adapters.templates.print_renderer_ds import (
    ChineseFontUnavailable,
    TemplatePrintRenderer,
)
from app.domain.templates_ds import (
    CoreLayoutKind,
    ElementKind,
    FieldDefinition,
    PageSpec,
    PayrollJobProfileVersion,
    Rect,
    StaticElement,
    TemplateArtifact,
    TemplateVersion,
    build_sheet_payload,
    build_template_payload,
    build_template_profile_payload,
)
from app.modules.templates.payroll_profiles_ds import reviewed_payroll_seed_templates


def _artifact(artifacts: tuple[TemplateArtifact, ...], kind: str) -> TemplateArtifact:
    return next(item for item in artifacts if item.kind == kind)


def _ink_in_region(image: Image.Image, region: object) -> int:
    page_width, page_height = image.size
    box = (
        round(region.x * page_width),
        round(region.y * page_height),
        round((region.x + region.width) * page_width),
        round((region.y + region.height) * page_height),
    )
    pixels = np.asarray(image.crop(box).convert("L"))
    return int(np.count_nonzero(pixels < 128))


def _decoded_payloads(image: Image.Image) -> set[str]:
    gray = np.asarray(image.convert("L"))
    detected, values, _, _ = cv2.QRCodeDetector().detectAndDecodeMulti(gray)
    assert detected
    return {value for value in values if value}


def test_renderer_generates_png_pdf_and_paper_instance_identity(tmp_path: Path) -> None:
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, PageSpec.a4_portrait())
    version.mark_ready_to_publish()
    version.publish()
    renderer = TemplatePrintRenderer(tmp_path)

    artifacts = renderer.render(version, print_batch="PB20260713A", sequence=128)

    assert {artifact.kind for artifact in artifacts} == {"PRINT_PNG", "PRINT_PDF"}
    assert all(Path(artifact.internal_uri).is_file() for artifact in artifacts)
    assert all(len(artifact.sha256) == 64 for artifact in artifacts)
    assert renderer.sheet_payload("PB20260713A", 128) == "SHEET|PB20260713A|000128|44D8"


def test_renderer_respects_configured_digit_count(tmp_path: Path) -> None:
    page = PageSpec.a5_landscape()
    version = TemplateVersion.draft("TPL-DIGITS", "PAYROLL_DIGITS", 1, page)
    field = FieldDefinition(
        "worker_number",
        "工号",
        "integer",
        "digit_boxes",
        Rect(0.2, 0.3, 0.36, 0.12),
        page,
        digit_count=8,
    )
    version.add_field(field)
    version.mark_ready_to_publish()
    version.publish()

    image = TemplatePrintRenderer(tmp_path)._render_canvas(
        version, build_template_payload(version.template_key, version.version), None
    )
    box = (
        round(field.region.x * page.canonical_width_px),
        round(field.region.y * page.canonical_height_px),
        round((field.region.x + field.region.width) * page.canonical_width_px),
        round((field.region.y + field.region.height) * page.canonical_height_px),
    )
    crop = np.asarray(image.crop(box).convert("L"))
    lower = crop[round(crop.shape[0] * 0.4) :, :]
    dark_by_column = np.count_nonzero(lower < 128, axis=0)
    line_columns = np.flatnonzero(dark_by_column > lower.shape[0] * 0.65)
    groups = 1 + int(np.count_nonzero(np.diff(line_columns) > 1))

    assert groups == 9


def test_renderer_prints_four_detectable_directional_aruco_markers(tmp_path: Path) -> None:
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, PageSpec.a4_portrait())
    version.mark_ready_to_publish()
    version.publish()
    artifact = next(
        item for item in TemplatePrintRenderer(tmp_path).render(version) if item.kind == "PRINT_PNG"
    )
    image = cv2.imread(artifact.internal_uri)
    detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))
    _, ids, _ = detector.detectMarkers(image)

    assert ids is not None
    assert set(ids.flatten()) == {10, 11, 12, 13}


def test_renderer_prints_a_decodable_template_qr_without_marker_overlap(tmp_path: Path) -> None:
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, PageSpec.a4_portrait())
    version.mark_ready_to_publish()
    version.publish()
    artifact = next(
        item for item in TemplatePrintRenderer(tmp_path).render(version) if item.kind == "PRINT_PNG"
    )
    image = cv2.imread(artifact.internal_uri)

    payload, _, _ = cv2.QRCodeDetector().detectAndDecode(image)

    assert payload == build_template_payload("PAYROLL_HOURLY", 1)


def test_renderer_prints_dual_version_qr_for_a_published_job_profile(
    tmp_path: Path,
) -> None:
    version = TemplateVersion.draft(
        "TPL-TIMEKEEPING-V2", "CORE_TIMEKEEPING", 2, PageSpec.a5_landscape()
    )
    version.mark_ready_to_publish()
    version.publish()
    profile = PayrollJobProfileVersion.draft(
        "PROFILE-DAY-V4",
        "TIMEKEEPING_DAY",
        4,
        display_name="计时工白班",
        core_layout=CoreLayoutKind.TIMEKEEPING,
        template_version_id=version.version_id,
        template_version=version.version,
    )
    profile.mark_ready_to_publish()
    profile.publish()

    artifact = next(
        item
        for item in TemplatePrintRenderer(tmp_path).render(version, job_profile=profile)
        if item.kind == "PRINT_PNG"
    )
    payload, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(artifact.internal_uri))

    assert payload == build_template_profile_payload(
        version.template_key, version.version, profile.profile_key, profile.version
    )
    assert "TIMEKEEPING_DAY-v4" in artifact.download_name


def test_renderer_rejects_a_job_profile_bound_to_another_template(tmp_path: Path) -> None:
    version = TemplateVersion.draft(
        "TPL-TIMEKEEPING-V2", "CORE_TIMEKEEPING", 2, PageSpec.a5_landscape()
    )
    version.mark_ready_to_publish()
    version.publish()
    profile = PayrollJobProfileVersion.draft(
        "PROFILE-DAY-V1",
        "TIMEKEEPING_DAY",
        1,
        display_name="计时工",
        core_layout=CoreLayoutKind.TIMEKEEPING,
        template_version_id="TPL-OTHER",
        template_version=2,
    )
    profile.mark_ready_to_publish()
    profile.publish()

    with pytest.raises(ValueError, match="does not bind"):
        TemplatePrintRenderer(tmp_path).render(version, job_profile=profile)


def test_renderer_draws_reviewed_chinese_structure_and_keeps_300_dpi(tmp_path: Path) -> None:
    version = reviewed_payroll_seed_templates()[0]
    artifacts = TemplatePrintRenderer(tmp_path).render(version)
    image = Image.open(_artifact(artifacts, "PRINT_PNG").internal_uri)
    elements = {element.element_id: element for element in version.static_elements}
    fields = {field.field_key: field for field in version.fields}

    assert image.info["dpi"] == pytest.approx((300, 300), abs=0.1)
    assert _ink_in_region(image, elements["title"].region) > 100
    assert _ink_in_region(image, elements["business_grid"].region) > 1_000
    assert _ink_in_region(image, elements["quality_pass_box"].region) > 50
    assert _ink_in_region(image, elements["worker_signature_line"].region) > 50
    assert _ink_in_region(image, elements["business_section"].region) > 100
    assert _ink_in_region(image, fields["regular_hours"].region) > 500
    assert _ink_in_region(image, fields["assessment_passed"].region) > 100
    assert _ink_in_region(image, fields["worker_signature"].region) > 100


def test_renderer_draws_internal_rows_and_weighted_columns_for_table_grid(
    tmp_path: Path,
) -> None:
    page = PageSpec.a4_portrait()
    version = TemplateVersion.draft("TPL-GRID", "CORE_GRID", 1, page)
    version.add_static_element(
        StaticElement(
            "detail_grid",
            ElementKind.TABLE_GRID,
            Rect(0.1, 0.2, 0.8, 0.5),
            rows=3,
            columns=2,
            column_weights=(1, 3),
        )
    )
    version.mark_ready_to_publish()
    version.publish()

    artifact = next(
        item
        for item in TemplatePrintRenderer(tmp_path).render(version)
        if item.kind == "PRINT_PNG"
    )
    image = np.asarray(Image.open(artifact.internal_uri).convert("L"))
    left = round(0.1 * page.canonical_width_px)
    top = round(0.2 * page.canonical_height_px)
    width = round(0.8 * page.canonical_width_px)
    height = round(0.5 * page.canonical_height_px)
    weighted_column_x = left + round(width * 0.25)
    first_row_y = top + round(height / 3)

    assert np.count_nonzero(image[top : top + height, weighted_column_x] < 128) > height * 0.8
    assert np.count_nonzero(image[first_row_y, left : left + width] < 128) > width * 0.8


def test_two_up_pdf_contains_independent_decodable_form_and_sheet_qrs(tmp_path: Path) -> None:
    version = reviewed_payroll_seed_templates()[0]
    renderer = TemplatePrintRenderer(tmp_path)

    artifacts = renderer.render(version, print_batch="PB20260719A", sequence=41)
    imposed = _artifact(artifacts, "PRINT_IMPOSED_PDF")
    preview = renderer.compose_imposition(
        version,
        print_batch="PB20260719A",
        first_sequence=41,
    )
    midpoint = preview.width // 2
    left_payloads = _decoded_payloads(preview.crop((0, 0, midpoint, preview.height)))
    right_payloads = _decoded_payloads(preview.crop((midpoint, 0, preview.width, preview.height)))
    expected_template = build_template_payload(version.template_key, version.version)

    assert Path(imposed.internal_uri).read_bytes().startswith(b"%PDF")
    assert expected_template in left_payloads
    assert expected_template in right_payloads
    assert build_sheet_payload("PB20260719A", 41) in left_payloads
    assert build_sheet_payload("PB20260719A", 42) in right_payloads
    centre_column = np.asarray(preview.convert("L"))[:, midpoint]
    assert np.any(centre_column < 50)
    assert np.any(centre_column > 240)


def test_renderer_rejects_publication_support_when_no_cjk_font_exists(tmp_path: Path) -> None:
    renderer = TemplatePrintRenderer(
        tmp_path,
        font_candidates=(tmp_path / "missing-cjk-font.ttf",),
    )

    with pytest.raises(ChineseFontUnavailable, match="中文字体"):
        renderer.validate_print_support()
