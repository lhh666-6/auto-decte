"""Build the printable pack required for the remaining Task 16 field acceptance."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.adapters.templates.print_renderer_ds import TemplatePrintRenderer
from app.domain.templates_ds import ElementKind, StaticElement, TemplateArtifact
from app.modules.templates.payroll_profiles_ds import reviewed_payroll_export_seed_templates

REPRESENTATIVE_KEYS = (
    "PAYROLL_TIMEKEEPING_DAILY",
    "PAYROLL_STEAMING_DAILY",
    "PAYROLL_SHEET_CUTTING_DAILY",
)


def build_acceptance_pack(output_root: Path, *, print_batch: str) -> dict[str, object]:
    """Render the three representative V2 templates and a field evidence checklist."""
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Acceptance pack directory is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    renderer = TemplatePrintRenderer(output_root)
    renderer.validate_print_support()
    templates_by_key = {
        template.template_key: template for template in reviewed_payroll_export_seed_templates()
    }
    entries: list[dict[str, object]] = []
    for index, template_key in enumerate(REPRESENTATIVE_KEYS, start=1):
        template = templates_by_key[template_key]
        first_sequence = index * 100
        artifacts = renderer.render(
            template,
            print_batch=print_batch,
            sequence=first_sequence,
        )
        artifact_by_kind = {artifact.kind: artifact for artifact in artifacts}
        print_artifact = artifact_by_kind.get("PRINT_IMPOSED_PDF") or artifact_by_kind[
            "PRINT_PDF"
        ]
        entries.append(
            {
                "template_key": template.template_key,
                "display_name": _template_title(template.static_elements),
                "version": template.version,
                "master_representative": index,
                "page": {
                    "size": template.page.size,
                    "orientation": template.page.orientation,
                    "width_mm": template.page.width_mm,
                    "height_mm": template.page.height_mm,
                    "canonical_dpi": template.page.canonical_dpi,
                },
                "first_sheet_sequence": first_sequence,
                "print_file": _relative_uri(output_root, print_artifact),
                "artifacts": [
                    {
                        "kind": artifact.kind,
                        "path": _relative_uri(output_root, artifact),
                        "sha256": artifact.sha256,
                    }
                    for artifact in artifacts
                ],
            }
        )

    manifest: dict[str, object] = {
        "pack_version": 1,
        "print_batch": print_batch,
        "print_scale_percent": 100,
        "auto_fit_allowed": False,
        "templates": entries,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "FIELD_ACCEPTANCE_RECORD.md").write_text(
        _field_record(entries),
        encoding="utf-8",
    )
    return manifest


def _relative_uri(output_root: Path, artifact: TemplateArtifact) -> str:
    return Path(artifact.internal_uri).relative_to(output_root).as_posix()


def _template_title(elements: Sequence[StaticElement]) -> str:
    for element in elements:
        if element.kind is ElementKind.TITLE:
            return element.text
    raise ValueError("Representative template has no printable title")


def _field_record(entries: list[dict[str, object]]) -> str:
    rows = "\n".join(
        f"| {entry['display_name']} | V{entry['version']} | {entry['print_file']} |  |  |  |"
        for entry in entries
    )
    return f"""# Task 16 实体纸面复验记录

## 打印前

- [ ] PDF 打印比例为 100%，已关闭“适合页面”。
- [ ] 记录打印机品牌/型号、驱动版本、纸张和打印时间。
- [ ] 校验 `manifest.json` 中的文件 SHA-256。

## 逐模板记录

| 模板 | 版本 | 打印文件 | 实测宽×高(mm) | 照片文件 | 闭环结果 |
|---|---:|---|---|---|---|
{rows}

每个模板必须留存：

- [ ] 卡尺或毫米尺与纸张同框照片，单边误差 ≤ 1 mm。
- [ ] 一般室内阴影与轻微旋转照片。
- [ ] 模板码和纸张实例码解析结果。
- [ ] 透视校正图和字段裁片。
- [ ] 人工复核记录与最终 Excel。
- [ ] 两拼表左右裁切后分别解析的实例序号。

## 环境信息

- 打印机：
- 驱动版本：
- 手机/相机：
- 拍摄软件：
- 室内光线：
- 验收人：
- 日期时间：
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Task 16 paper acceptance pack")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runtime/paper-acceptance-pack"),
        help="Empty output directory for PDFs, PNGs, manifest and field checklist",
    )
    parser.add_argument(
        "--print-batch",
        default="ACCEPTANCE_20260719",
        help="Uppercase batch identifier encoded into sheet QR codes",
    )
    args = parser.parse_args(argv)
    try:
        manifest = build_acceptance_pack(args.output, print_batch=args.print_batch)
    except (FileExistsError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    templates = manifest.get("templates")
    if not isinstance(templates, list):
        raise RuntimeError("Acceptance pack manifest has no template list")
    print(f"Built {len(templates)} representative templates in {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
