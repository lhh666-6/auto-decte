"""Template draft, preflight, publication and cloning use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

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

_OUTER_MARGIN_MM = 5.0
_QR_SAFE_ZONE_MM = 29.0
_QR_GAP_MM = 5.0
_CORNER_MARKER_MM = 12.0
_FIELD_MINIMUMS_MM = {
    "employee_id_boxes": (6.0, 8.0),
    "digit_boxes": (7.0, 8.0),
    "checkbox": (4.0, 4.0),
    "handwriting_line": (0.0, 8.0),
    "text_box": (0.0, 8.0),
}


class TemplateVersionRepository(Protocol):
    def add_version(self, version: TemplateVersion) -> None: ...

    def get_version(self, version_id: str) -> TemplateVersion | None: ...

    def replace_version(self, version: TemplateVersion) -> None: ...

    def list_versions(self, template_key: str) -> list[TemplateVersion]: ...

    def list_template_keys(self) -> list[str]: ...

    def get_template_metadata(self, template_key: str) -> tuple[str, str] | None: ...

    def update_template_metadata(
        self, template_key: str, display_name: str, description: str
    ) -> None: ...

    def delete_version(self, version_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class PreflightReport:
    issues: tuple[PreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


class TemplateVersions:
    """Own template-version lifecycle transitions outside the UI layer."""

    def __init__(self, repository: TemplateVersionRepository) -> None:
        self._repository = repository

    def create_draft(
        self,
        template_key: str,
        page: PageSpec,
        display_name: str | None = None,
        description: str = "",
    ) -> TemplateVersion:
        prior_versions = self._repository.list_versions(template_key)
        next_version = max((item.version for item in prior_versions), default=0) + 1
        version = TemplateVersion.draft(
            version_id=f"TPL-{uuid4().hex}",
            template_key=template_key,
            version=next_version,
            page=page,
        )
        self._repository.add_version(version)
        if display_name is not None:
            self.update_metadata(template_key, display_name, description)
        return version

    def get_metadata(self, template_key: str) -> tuple[str, str]:
        metadata = self._repository.get_template_metadata(template_key)
        if metadata is None:
            raise KeyError(f"Unknown template: {template_key}")
        return metadata

    def update_metadata(
        self, template_key: str, display_name: str, description: str
    ) -> tuple[str, str]:
        cleaned_name = display_name.strip()
        cleaned_description = description.strip()
        if not cleaned_name:
            raise ValueError("template display name is required")
        if len(cleaned_name) > 100:
            raise ValueError("template display name must not exceed 100 characters")
        if len(cleaned_description) > 500:
            raise ValueError("template description must not exceed 500 characters")
        self._repository.update_template_metadata(
            template_key, cleaned_name, cleaned_description
        )
        return cleaned_name, cleaned_description

    def discard_draft(self, version_id: str) -> None:
        version = self.get(version_id)
        if version.status not in {
            TemplateStatus.DRAFT,
            TemplateStatus.PREFLIGHT_FAILED,
            TemplateStatus.READY_TO_PUBLISH,
        }:
            raise ValueError("only editable template drafts can be discarded")
        self._repository.delete_version(version_id)

    def retire_template(self, template_key: str) -> None:
        versions = self._repository.list_versions(template_key)
        if not versions:
            raise KeyError(f"Unknown template: {template_key}")
        editable = {
            TemplateStatus.DRAFT,
            TemplateStatus.PREFLIGHT_FAILED,
            TemplateStatus.READY_TO_PUBLISH,
        }
        if any(version.status in editable for version in versions):
            raise ValueError("discard active drafts before retiring the template")
        candidates = [
            version
            for version in versions
            if version.status in {TemplateStatus.PUBLISHED, TemplateStatus.DEPRECATED}
        ]
        if not candidates:
            raise ValueError("template has no active published versions to retire")
        for version in candidates:
            version.retire()
            self._repository.replace_version(version)

    def get(self, version_id: str) -> TemplateVersion:
        version = self._repository.get_version(version_id)
        if version is None:
            raise KeyError(f"Unknown template version: {version_id}")
        return version

    def list_templates(self) -> list[TemplateVersion]:
        versions = [
            version
            for template_key in self._repository.list_template_keys()
            for version in self._repository.list_versions(template_key)
        ]
        return sorted(
            versions,
            key=lambda version: (version.template_key, version.version, version.version_id),
        )

    def add_field(self, version_id: str, definition: FieldDefinition) -> TemplateVersion:
        version = self.get(version_id)
        version.add_field(definition)
        self._repository.replace_version(version)
        return version

    def replace_field(
        self, version_id: str, field_key: str, definition: FieldDefinition
    ) -> TemplateVersion:
        version = self.get(version_id)
        version.replace_field(field_key, definition)
        self._repository.replace_version(version)
        return version

    def remove_field(self, version_id: str, field_key: str) -> TemplateVersion:
        version = self.get(version_id)
        version.remove_field(field_key)
        self._repository.replace_version(version)
        return version

    def add_static_element(self, version_id: str, element: StaticElement) -> TemplateVersion:
        version = self.get(version_id)
        version.add_static_element(element)
        self._repository.replace_version(version)
        return version

    def replace_static_element(
        self, version_id: str, element_id: str, element: StaticElement
    ) -> TemplateVersion:
        version = self.get(version_id)
        current = next(
            (item for item in version.static_elements if item.element_id == element_id), None
        )
        if current is None:
            raise KeyError(f"Unknown static element: {element_id}")
        if current.kind is not ElementKind.TABLE_GRID or element.kind is not ElementKind.TABLE_GRID:
            raise ValueError("only table grids may be changed through controlled grid settings")
        version.replace_static_element(element_id, element)
        self._repository.replace_version(version)
        return version

    def set_print_imposition(
        self, version_id: str, imposition: PrintImposition | None
    ) -> TemplateVersion:
        version = self.get(version_id)
        version.set_print_imposition(imposition)
        self._repository.replace_version(version)
        return version

    def preflight(self, version_id: str) -> PreflightReport:
        version = self.get(version_id)
        issues = tuple(
            issue
            for field in version.fields
            for issue in _protected_zone_issues(
                field.region,
                version.page,
                item_label=f"Field {field.field_key}",
            )
        ) + tuple(
            issue
            for field in version.fields
            for issue in _physical_field_issues(field)
        ) + tuple(
            issue
            for element in version.static_elements
            for issue in _protected_zone_issues(
                element.region,
                version.page,
                item_label=f"Static element {element.element_id}",
            )
        ) + tuple(
            issue
            for element in version.static_elements
            for issue in _physical_static_element_issues(element, version.page)
        ) + tuple(
            PreflightIssue(
                code="RECOGNITION_ENGINE_MISMATCH",
                detail=(
                    f"字段“{field.display_name}”的纸面控件、数据类型和识别方式不兼容。"
                ),
            )
            for field in version.fields
            if not _recognition_configuration_is_valid(field)
        ) + tuple(
            issue
            for field in version.fields
            for issue in _field_behavior_issues(field)
        ) + _core_paper_business_issues(version)
        if version.print_imposition is not None and not version.print_imposition.fits(version.page):
            issues += (
                PreflightIssue(
                    code="IMPOSITION_DOES_NOT_FIT",
                    detail="当前单表尺寸无法放入设置的拼版位置，请调整纸张、边距或拼版行列。",
                ),
            )
        if issues:
            version.mark_preflight_failed()
        else:
            version.mark_ready_to_publish()
        self._repository.replace_version(version)
        return PreflightReport(issues)

    def publish(self, version_id: str) -> TemplateVersion:
        version = self.get(version_id)
        version.publish()
        self._repository.replace_version(version)
        return version

    def clone(self, version_id: str) -> TemplateVersion:
        source = self.get(version_id)
        if source.status is not TemplateStatus.PUBLISHED:
            raise ValueError("only published template versions can be cloned")
        clone = self.create_draft(source.template_key, source.page)
        clone.parent_version_id = source.version_id
        for definition in source.fields:
            clone.add_field(definition)
        for element in source.static_elements:
            clone.add_static_element(element)
        clone.set_print_imposition(source.print_imposition)
        self._repository.replace_version(clone)
        return clone


def _overlaps(left: Rect, right: Rect) -> bool:
    return (
        left.x < right.x + right.width
        and left.x + left.width > right.x
        and left.y < right.y + right.height
        and left.y + left.height > right.y
    )


def _recognition_configuration_is_valid(field: FieldDefinition) -> bool:
    if field.recognition_mode is RecognitionMode.NONE:
        return field.recognition_engine == "manual"
    if field.recognition_mode is RecognitionMode.HANDWRITING_OCR:
        return field.paper_entry_mode is PaperEntryMode.HANDWRITTEN_TEXT
    if field.recognition_mode is RecognitionMode.DIGIT_OCR:
        return field.paper_entry_mode is PaperEntryMode.DIGIT_BOXES and field.data_type in {
            "integer",
            "decimal",
        }
    if field.recognition_mode is RecognitionMode.PRINTED_OCR:
        return field.paper_entry_mode is PaperEntryMode.PREPRINTED
    if field.recognition_mode is RecognitionMode.OMR:
        return field.paper_entry_mode is PaperEntryMode.CHECKBOX and (
            field.data_type == "boolean" or bool(field.choice_options)
        )
    if field.recognition_mode is RecognitionMode.QR:
        return field.paper_entry_mode in {PaperEntryMode.PREPRINTED, PaperEntryMode.NONE}
    if field.recognition_mode is RecognitionMode.CALCULATED:
        return field.paper_entry_mode is PaperEntryMode.NONE
    return False


def _field_behavior_issues(field: FieldDefinition) -> tuple[PreflightIssue, ...]:
    mode = field.recognition_mode
    policy = field.fill_policy
    allowed_policies = {
        RecognitionMode.NONE: {FillPolicy.MANUAL_ONLY},
        RecognitionMode.HANDWRITING_OCR: {
            FillPolicy.SUGGEST_ONLY,
            FillPolicy.PREFILL_WHEN_CONFIDENT,
        },
        RecognitionMode.DIGIT_OCR: {
            FillPolicy.SUGGEST_ONLY,
            FillPolicy.PREFILL_WHEN_CONFIDENT,
        },
        RecognitionMode.PRINTED_OCR: {
            FillPolicy.SUGGEST_ONLY,
            FillPolicy.PREFILL_WHEN_CONFIDENT,
        },
        RecognitionMode.OMR: {
            FillPolicy.SUGGEST_ONLY,
            FillPolicy.PREFILL_WHEN_CONFIDENT,
        },
        RecognitionMode.QR: {
            FillPolicy.SUGGEST_ONLY,
            FillPolicy.PREFILL_WHEN_CONFIDENT,
        },
        RecognitionMode.CALCULATED: {FillPolicy.CALCULATED},
    }
    issues: list[PreflightIssue] = []
    if mode is None or policy not in allowed_policies[mode]:
        issues.append(
            PreflightIssue(
                code="FIELD_BEHAVIOR_MISMATCH",
                detail=f"字段“{field.display_name}”的识别方式与审核填入方式不匹配。",
            )
        )
    if mode in {RecognitionMode.NONE, RecognitionMode.CALCULATED}:
        if field.confidence_threshold is not None:
            issues.append(
                PreflightIssue(
                    code="CONFIDENCE_THRESHOLD_NOT_ALLOWED",
                    detail=f"字段“{field.display_name}”不使用自动识别，不能设置自动填入可靠度。",
                )
            )
    elif policy is FillPolicy.PREFILL_WHEN_CONFIDENT and (
        field.confidence_threshold is None and mode is not RecognitionMode.QR
    ):
        issues.append(
            PreflightIssue(
                code="CONFIDENCE_THRESHOLD_REQUIRED",
                detail=f"字段“{field.display_name}”允许自动填入时必须设置可靠度。",
            )
        )
    if mode is RecognitionMode.CALCULATED:
        if not field.calculation_expression or not field.calculation_expression.strip():
            issues.append(
                PreflightIssue(
                    code="CALCULATION_RULE_REQUIRED",
                    detail=f"系统计算字段“{field.display_name}”缺少计算规则。",
                )
            )
    elif field.calculation_expression is not None:
        issues.append(
            PreflightIssue(
                code="CALCULATION_RULE_NOT_ALLOWED",
                detail=f"字段“{field.display_name}”不是系统计算字段，不能保留计算规则。",
            )
        )
    if field.field_key in {"worker_name", "employee_name"} and (
        not field.requires_manual_confirmation
        or policy not in {FillPolicy.MANUAL_ONLY, FillPolicy.SUGGEST_ONLY}
    ):
        issues.append(
            PreflightIssue(
                code="NAME_REQUIRES_MANUAL_CONFIRMATION",
                detail=f"姓名字段“{field.display_name}”必须由工作人员对照原图确认。",
            )
        )
    return tuple(issues)


def _protected_zone_issues(
    region: Rect,
    page: PageSpec,
    *,
    item_label: str,
) -> tuple[PreflightIssue, ...]:
    return tuple(
        PreflightIssue(code=code, detail=f"{item_label}与{label}重叠，请移动到安全区域。")
        for code, label, zone in _protected_zones(page)
        if _overlaps(region, zone)
    )


def _protected_zones(page: PageSpec) -> tuple[tuple[str, str, Rect], ...]:
    edge_x = _OUTER_MARGIN_MM / page.width_mm
    edge_y = _OUTER_MARGIN_MM / page.height_mm
    marker_width = _CORNER_MARKER_MM / page.width_mm
    marker_height = _CORNER_MARKER_MM / page.height_mm
    qr_width = _QR_SAFE_ZONE_MM / page.width_mm
    qr_height = _QR_SAFE_ZONE_MM / page.height_mm
    template_qr_x = 1 - edge_x - qr_width
    sheet_qr_x = template_qr_x - _QR_GAP_MM / page.width_mm - qr_width
    return (
        (
            "QR_SAFE_ZONE_OVERLAP",
            "模板二维码安全区",
            Rect(template_qr_x, edge_y, qr_width, qr_height),
        ),
        (
            "SHEET_SAFE_ZONE_OVERLAP",
            "表单实例二维码安全区",
            Rect(sheet_qr_x, edge_y, qr_width, qr_height),
        ),
        (
            "CORNER_MARKER_OVERLAP",
            "左上角定位标记",
            Rect(0, 0, marker_width, marker_height),
        ),
        (
            "CORNER_MARKER_OVERLAP",
            "右上角定位标记",
            Rect(1 - marker_width, 0, marker_width, marker_height),
        ),
        (
            "CORNER_MARKER_OVERLAP",
            "左下角定位标记",
            Rect(0, 1 - marker_height, marker_width, marker_height),
        ),
        (
            "CORNER_MARKER_OVERLAP",
            "右下角定位标记",
            Rect(1 - marker_width, 1 - marker_height, marker_width, marker_height),
        ),
        ("PRINT_EDGE_OVERLAP", "顶部打印边距", Rect(0, 0, 1, edge_y)),
        ("PRINT_EDGE_OVERLAP", "底部打印边距", Rect(0, 1 - edge_y, 1, edge_y)),
        ("PRINT_EDGE_OVERLAP", "左侧打印边距", Rect(0, 0, edge_x, 1)),
        ("PRINT_EDGE_OVERLAP", "右侧打印边距", Rect(1 - edge_x, 0, edge_x, 1)),
    )


def _physical_field_issues(field: FieldDefinition) -> tuple[PreflightIssue, ...]:
    minimum = _FIELD_MINIMUMS_MM.get(field.input_type)
    if minimum is None:
        return ()
    width_mm = field.region.width * field.page.width_mm
    height_mm = field.region.height * field.page.height_mm
    if width_mm + 1e-9 >= minimum[0] and height_mm + 1e-9 >= minimum[1]:
        return ()
    return (
        PreflightIssue(
            code="PHYSICAL_MINIMUM_SIZE",
            detail=(
                f"字段“{field.display_name}”当前为 {width_mm:.1f} × {height_mm:.1f} mm，"
                f"至少需要 {minimum[0]:.1f} × {minimum[1]:.1f} mm。"
            ),
        ),
    )


def _physical_static_element_issues(
    element: StaticElement, page: PageSpec
) -> tuple[PreflightIssue, ...]:
    if element.kind is not ElementKind.CHECKBOX:
        return ()
    width_mm = element.region.width * page.width_mm
    height_mm = element.region.height * page.height_mm
    if width_mm + 1e-9 >= 4 and height_mm + 1e-9 >= 4:
        return ()
    return (
        PreflightIssue(
            code="PHYSICAL_MINIMUM_SIZE",
            detail=(
                f"固定勾选框“{element.element_id}”当前为 {width_mm:.1f} × {height_mm:.1f} mm，"
                "至少需要 4.0 × 4.0 mm。"
            ),
        ),
    )


def _core_paper_business_issues(version: TemplateVersion) -> tuple[PreflightIssue, ...]:
    if not version.template_key.startswith("PAYROLL_CORE_"):
        return ()
    issues: list[PreflightIssue] = []
    if not any(element.kind is ElementKind.TITLE for element in version.static_elements):
        issues.append(PreflightIssue("TITLE_REQUIRED", "正式工资表必须有一个固定标题。"))
    if not any(element.kind is ElementKind.TABLE_GRID for element in version.static_elements):
        issues.append(PreflightIssue("TABLE_GRID_REQUIRED", "正式工资表必须有固定明细表。"))
    for field in version.fields:
        if field.paper_entry_mode is PaperEntryMode.DIGIT_BOXES and field.digit_count is None:
            issues.append(
                PreflightIssue(
                    "DIGIT_COUNT_REQUIRED",
                    f"数字格“{field.display_name}”必须明确填写位数。",
                )
            )
        if field.paper_entry_mode is PaperEntryMode.CHECKBOX:
            if not field.choice_group or not field.choice_options:
                issues.append(
                    PreflightIssue(
                        "CHOICE_GROUP_REQUIRED",
                        f"勾选项“{field.display_name}”必须设置固定选项组。",
                    )
                )
            elif field.max_selections is None:
                issues.append(
                    PreflightIssue(
                        "CHOICE_SELECTION_LIMIT_REQUIRED",
                        f"勾选项“{field.display_name}”必须设置最多选择几项。",
                    )
                )
        if field.field_key == "exception_reason" and not field.conditional_required_on:
            issues.append(
                PreflightIssue(
                    "CONDITIONAL_REQUIRED_RULE_MISSING",
                    "异常事实说明必须设置何时必填，不能成为无约束自由填写区。",
                )
            )
        if field.paper_entry_mode is PaperEntryMode.SIGNATURE and not field.signature_role:
            issues.append(
                PreflightIssue(
                    "SIGNATURE_ROLE_REQUIRED",
                    f"签字线“{field.display_name}”必须指定签字角色。",
                )
            )
        if _is_money_field(field) and field.recognition_mode is not RecognitionMode.CALCULATED:
            issues.append(
                PreflightIssue(
                    "MONEY_MUST_BE_CALCULATED",
                    f"金额字段“{field.display_name}”必须由系统计算，不能让工人填写。",
                )
            )
        if (
            field.paper_entry_mode is PaperEntryMode.HANDWRITTEN_TEXT
            and field.region.width * field.page.width_mm
            * field.region.height * field.page.height_mm
            > 2500
        ):
            issues.append(
                PreflightIssue(
                    "FREE_TEXT_AREA_TOO_LARGE",
                    f"手写区“{field.display_name}”面积过大，请改为固定选项或缩小范围。",
                )
            )
        if field.export_target is None:
            issues.append(
                PreflightIssue(
                    "EXPORT_MAPPING_REQUIRED",
                    f"字段“{field.display_name}”缺少 Excel 导出映射。",
                )
            )
    return tuple(issues)


def _is_money_field(field: FieldDefinition) -> bool:
    key = field.field_key.lower()
    return any(token in key for token in ("wage", "reward", "deduction", "amount", "pay")) or any(
        token in field.display_name for token in ("工资", "金额", "奖励", "扣减", "扣款")
    )
