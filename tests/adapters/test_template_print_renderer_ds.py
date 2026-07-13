"""Printable template artifact behavior."""

from pathlib import Path

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
