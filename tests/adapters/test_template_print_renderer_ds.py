"""Printable template artifact behavior."""

from pathlib import Path

import cv2

from app.adapters.templates.print_renderer_ds import TemplatePrintRenderer
from app.domain.templates_ds import PageSpec, TemplateVersion


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
