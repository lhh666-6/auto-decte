"""Reviewed, idempotently installed legacy payroll template seeds."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from app.adapters.templates.print_renderer_ds import TemplatePrintRenderer
from app.domain.templates_ds import (
    ExportTarget,
    FieldDefinition,
    FieldRules,
    PageSpec,
    Rect,
    TemplateArtifact,
    TemplateVersion,
)

_WORKBOOK = "企业工资记录.xlsx"
_SEED_METADATA = {
    "PAYROLL_HOURLY": ("计时考核单", "适用于按工时统计的生产岗位"),
    "PAYROLL_STANDARD_PIECE": ("标准计件单", "适用于标准计件生产记录"),
    "PAYROLL_FIXED_PRODUCTION_GRID": ("固定生产明细单", "适用于固定生产明细岗位"),
    "PAYROLL_EQUIPMENT_PROCESS": ("设备工序单", "适用于设备与工序计件岗位"),
}
_COMMON_FIELDS = (
    ("work_date", "日期", "text", "text_box", True),
    ("shift", "班次", "text", "text_box", True),
    ("worker_name", "姓名", "text", "text_box", True),
    ("assessment_result", "考评结果", "text", "text_box", True),
    ("remarks", "备注", "text", "text_box", False),
)
_HEADER_REGIONS = (
    Rect(0.08, 0.16, 0.20, 0.045),
    Rect(0.31, 0.16, 0.14, 0.045),
    Rect(0.48, 0.16, 0.26, 0.045),
    Rect(0.08, 0.22, 0.26, 0.045),
    Rect(0.37, 0.22, 0.52, 0.045),
)
_SPECIAL_REGIONS = tuple(
    Rect(0.08 + (index % 4) * 0.205, 0.29 + (index // 4) * 0.06, 0.18, 0.04)
    for index in range(12)
)
_LINE_REGIONS = tuple(Rect(0.08, 0.48 + index * 0.043, 0.84, 0.034) for index in range(10))


class SeedTemplateConflict(RuntimeError):
    """An installed key/version does not match the reviewed built-in content."""


class SeedTemplateRepository(Protocol):
    def add_version(self, version: TemplateVersion) -> None: ...

    def get_version_by_key_version(
        self, template_key: str, version: int
    ) -> TemplateVersion | None: ...

    def add_artifact(self, artifact: TemplateArtifact) -> None: ...

    def list_artifacts(self, version_id: str) -> list[TemplateArtifact]: ...

    def remove_artifacts(self, version_id: str, download_names: set[str]) -> None: ...

    def update_template_metadata(
        self, template_key: str, display_name: str, description: str
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class SeedInstallResult:
    installed: tuple[str, ...]
    existing: tuple[str, ...]


def legacy_payroll_seed_templates() -> tuple[TemplateVersion, ...]:
    """Return fresh, published V1 definitions derived from the reviewed legacy forms."""
    return (
        _template(
            "PAYROLL_HOURLY",
            "计时工资",
            (
                ("start_time", "上班时间", "text", "text_box", True),
                ("end_time", "下班时间", "text", "text_box", True),
                ("work_hours", "工作小时", "decimal", "digit_boxes", True),
                ("facts_description", "事实说明", "text", "text_box", False),
                ("labor_assessment", "劳动考核", "text", "text_box", False),
                ("cost_assessment", "成本考核", "text", "text_box", False),
                ("safety_assessment", "安全考核", "text", "text_box", False),
                ("workplace_5s_assessment", "5S考核", "text", "text_box", False),
                ("equipment_assessment", "设备维护", "text", "text_box", False),
            ),
        ),
        _template(
            "PAYROLL_STANDARD_PIECE",
            "标准计件",
            (
                ("pricing_category", "计价分类", "text", "text_box", True),
                ("unit_price", "单价", "decimal", "digit_boxes", True),
                ("quantity", "数量", "decimal", "digit_boxes", True),
                ("total_amount", "合计", "decimal", "digit_boxes", True),
                ("process_name", "工序", "text", "text_box", True),
            ),
        ),
        _template(
            "PAYROLL_FIXED_PRODUCTION_GRID",
            "固定生产明细",
            (
                ("team", "班组", "text", "text_box", True),
                ("station", "台号", "text", "text_box", False),
                ("product_name", "品名", "text", "text_box", True),
                ("specification", "规格", "text", "text_box", True),
                ("quality_grade", "等级", "text", "text_box", True),
                ("quantity", "数量", "decimal", "digit_boxes", True),
                ("unit_price", "单价", "decimal", "digit_boxes", True),
                ("deduction", "追溯扣款", "decimal", "digit_boxes", False),
            ),
        ),
        _template(
            "PAYROLL_EQUIPMENT_PROCESS",
            "设备工序",
            (
                ("equipment_id", "设备编号", "text", "text_box", True),
                ("process_category", "工艺分类", "text", "text_box", True),
                ("inspection_result", "检查结果", "text", "text_box", True),
                ("quantity", "数量", "decimal", "digit_boxes", False),
                ("deduction", "扣款", "decimal", "digit_boxes", False),
                ("exception_reason", "异常原因", "text", "text_box", False),
            ),
        ),
    )


def install_legacy_payroll_seed_templates(
    repository: SeedTemplateRepository,
    renderer: TemplatePrintRenderer,
) -> SeedInstallResult:
    """Install reviewed V1 templates once and repair a missing artifact kind on retry."""
    installed: list[str] = []
    existing: list[str] = []
    expected_templates = legacy_payroll_seed_templates()
    current_versions: dict[str, TemplateVersion | None] = {}
    for expected in expected_templates:
        current = repository.get_version_by_key_version(expected.template_key, expected.version)
        current_versions[expected.template_key] = current
        if current is not None and _content_fingerprint(current) != _content_fingerprint(expected):
            raise SeedTemplateConflict(
                f"Seed {expected.template_key} version {expected.version} conflicts with "
                "the reviewed built-in definition."
            )

    for expected in expected_templates:
        current = current_versions[expected.template_key]
        if current is None:
            repository.add_version(expected)
            display_name, description = _SEED_METADATA[expected.template_key]
            repository.update_template_metadata(
                expected.template_key, display_name, description
            )
            current = expected
            installed.append(expected.template_key)
        else:
            existing.append(expected.template_key)
        _install_missing_artifacts(repository, renderer, current)
    return SeedInstallResult(tuple(installed), tuple(existing))


def _template(
    template_key: str,
    worksheet: str,
    special_fields: tuple[tuple[str, str, str, str, bool], ...],
) -> TemplateVersion:
    if len(special_fields) > len(_SPECIAL_REGIONS):
        raise ValueError("seed template has more special fields than available regions")
    page = PageSpec.a4_portrait()
    version = TemplateVersion.draft(f"TPL-SEED-{template_key}-V1", template_key, 1, page)
    for definition, region in zip(_COMMON_FIELDS, _HEADER_REGIONS, strict=True):
        version.add_field(_field(*definition, region, page, worksheet))
    for definition, region in zip(special_fields, _SPECIAL_REGIONS, strict=False):
        version.add_field(_field(*definition, region, page, worksheet))
    for index, region in enumerate(_LINE_REGIONS, start=1):
        version.add_field(
            _field(
                f"line_{index:02d}",
                f"固定明细第{index}行",
                "text",
                "text_box",
                False,
                region,
                page,
                worksheet,
            )
        )
    version.mark_ready_to_publish()
    version.publish()
    return version


def _field(
    field_key: str,
    display_name: str,
    data_type: str,
    input_type: str,
    required: bool,
    region: Rect,
    page: PageSpec,
    worksheet: str,
) -> FieldDefinition:
    numeric = data_type in {"integer", "decimal"}
    allowed_values: tuple[str, ...] = ()
    if field_key == "shift":
        allowed_values = ("白班", "夜班")
    elif field_key in {"assessment_result", "inspection_result"}:
        allowed_values = ("合格", "待改进", "不合格")
    return FieldDefinition(
        field_key=field_key,
        display_name=display_name,
        data_type=data_type,
        input_type=input_type,
        region=region,
        page=page,
        recognition_engine="digit_template" if numeric else "manual",
        minimum_prefill_confidence=0.95 if numeric else 1.0,
        rules=FieldRules(
            required=required,
            minimum_value=0.0 if numeric else None,
            allowed_values=allowed_values,
            allow_exception_reason=field_key in {"remarks", "deduction", "exception_reason"},
        ),
        export_target=ExportTarget(_WORKBOOK, worksheet, field_key),
    )


def _install_missing_artifacts(
    repository: SeedTemplateRepository,
    renderer: TemplatePrintRenderer,
    version: TemplateVersion,
) -> None:
    base_name = f"{version.template_key}-v{version.version}"
    expected_names = {f"{base_name}.png", f"{base_name}.pdf"}
    base_artifacts = [
        artifact
        for artifact in repository.list_artifacts(version.version_id)
        if artifact.download_name in expected_names
    ]
    if _artifacts_are_complete(base_artifacts, expected_names):
        return
    repository.remove_artifacts(version.version_id, expected_names)
    for artifact in renderer.render(version):
        repository.add_artifact(artifact)


def _artifacts_are_complete(
    artifacts: list[TemplateArtifact], expected_names: set[str]
) -> bool:
    if {artifact.download_name for artifact in artifacts} != expected_names:
        return False
    for artifact in artifacts:
        path = Path(artifact.internal_uri)
        if not path.is_file():
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256:
            return False
    return True


def _content_fingerprint(version: TemplateVersion) -> str:
    value = {
        "template_key": version.template_key,
        "version": version.version,
        "page": asdict(version.page),
        "parent_version_id": version.parent_version_id,
        "fields": [asdict(field) for field in version.fields],
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
