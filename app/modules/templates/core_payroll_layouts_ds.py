"""Six controlled V2 payroll paper layouts and their versioned job profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.templates_ds import (
    CoreLayoutKind,
    ElementKind,
    FieldDefinition,
    FieldRules,
    FillPolicy,
    PageSpec,
    PaperEntryMode,
    PayrollJobProfileVersion,
    PrintImposition,
    RecognitionMode,
    Rect,
    StaticElement,
    TemplateVersion,
)


@dataclass(frozen=True, slots=True)
class _FieldSpec:
    key: str
    label: str
    kind: str
    digits: int | None = None
    choices: tuple[str, ...] = ()
    max_selections: int | None = None
    expression: str | None = None


@dataclass(frozen=True, slots=True)
class _LayoutSpec:
    core: CoreLayoutKind
    template_key: str
    title: str
    page: PageSpec
    headers: tuple[str, ...]
    weights: tuple[float, ...]
    rows: tuple[tuple[_FieldSpec, ...], tuple[_FieldSpec, ...]]
    extra_header_fields: tuple[_FieldSpec, ...]
    quality_fields: tuple[_FieldSpec, ...]
    exception_condition: str
    money_fields: tuple[_FieldSpec, ...]
    signature_roles: tuple[tuple[str, str, str], ...]


def core_payroll_seed_templates() -> tuple[TemplateVersion, ...]:
    """Build the six immutable paper-layout V2 definitions in product order."""
    return tuple(_build_layout(specification) for specification in _LAYOUTS)


def reviewed_job_profile_seed_versions() -> tuple[PayrollJobProfileVersion, ...]:
    """Build published V2 job configurations that reuse the six core layouts."""
    templates = {spec.core: _build_layout(spec) for spec in _LAYOUTS}
    profiles: list[PayrollJobProfileVersion] = []
    for profile_key, display_name, core, unit, fixed in _JOB_PROFILES:
        template = templates[core]
        profile = PayrollJobProfileVersion.draft(
            f"PROFILE-SEED-{profile_key}-V2",
            profile_key,
            2,
            display_name=display_name,
            core_layout=core,
            template_version_id=template.version_id,
            template_version=template.version,
            unit=unit,
            fixed_options={"position_name": display_name, "unit": unit, **fixed},
            pricing_rules={"source": "master_data", "worker_editable": False},
            deduction_rules={"source": "review_result", "worker_editable": False},
            export_mapping={"layout": core.value, "profile_key": profile_key},
        )
        profile.mark_ready_to_publish()
        profile.publish()
        profiles.append(profile)
    return tuple(profiles)


def core_payroll_metadata() -> dict[str, tuple[str, str]]:
    return {
        specification.template_key: (
            specification.title,
            "V2 六类核心纸质工资表；岗位差异由版本化岗位配置预印",
        )
        for specification in _LAYOUTS
    }


class JobProfileSeedRepository(Protocol):
    def add_job_profile(self, profile: PayrollJobProfileVersion) -> None: ...

    def get_job_profile_by_key_version(
        self, profile_key: str, version: int
    ) -> PayrollJobProfileVersion | None: ...


@dataclass(frozen=True, slots=True)
class JobProfileSeedInstallResult:
    installed: tuple[str, ...]
    existing: tuple[str, ...]


def install_reviewed_job_profile_seeds(
    repository: JobProfileSeedRepository,
) -> JobProfileSeedInstallResult:
    """Install exact V2 profile bindings without rewriting existing versions."""
    installed: list[str] = []
    existing: list[str] = []
    for expected in reviewed_job_profile_seed_versions():
        current = repository.get_job_profile_by_key_version(expected.profile_key, expected.version)
        if current is None:
            repository.add_job_profile(expected)
            installed.append(expected.profile_key)
            continue
        if _profile_content(current) != _profile_content(expected):
            raise ValueError(
                f"Job profile {expected.profile_key} version {expected.version} "
                "conflicts with the built-in V2 definition"
            )
        existing.append(expected.profile_key)
    return JobProfileSeedInstallResult(tuple(installed), tuple(existing))


def _profile_content(profile: PayrollJobProfileVersion) -> tuple[object, ...]:
    return (
        profile.profile_key,
        profile.version,
        profile.display_name,
        profile.core_layout,
        profile.template_version_id,
        profile.template_version,
        profile.parent_profile_version_id,
        profile.unit,
        profile.fixed_options,
        profile.pricing_rules,
        profile.deduction_rules,
        profile.export_mapping,
    )


def _build_layout(specification: _LayoutSpec) -> TemplateVersion:
    version = TemplateVersion.draft(
        f"TPL-SEED-{specification.template_key}-V2",
        specification.template_key,
        2,
        specification.page,
    )
    for element in _static_elements(specification):
        version.add_static_element(element)
    for field in _common_fields(specification.page):
        version.add_field(field)
    for specification_field, region in zip(
        specification.extra_header_fields,
        _extra_header_regions(len(specification.extra_header_fields)),
        strict=True,
    ):
        version.add_field(_field(specification_field, region, specification.page))
    for row_index, row in enumerate(specification.rows):
        regions = _grid_data_regions(specification.weights, row_index)
        for specification_field, region in zip(row, regions[1:], strict=True):
            version.add_field(_field(specification_field, region, specification.page))
    for specification_field, region in zip(
        specification.quality_fields,
        _horizontal_regions(0.695, 0.92, len(specification.quality_fields), 0.055),
        strict=True,
    ):
        version.add_field(_field(specification_field, region, specification.page))
    version.add_field(
        _field(
            _FieldSpec("exception_reason", "异常事实", "text"),
            Rect(0.04, 0.755, 0.58, 0.065),
            specification.page,
            conditional_required_on=specification.exception_condition,
        )
    )
    for specification_field, region in zip(
        specification.money_fields,
        _horizontal_regions(0.825, 0.56, len(specification.money_fields), 0.04),
        strict=True,
    ):
        version.add_field(_field(specification_field, region, specification.page))
    for (field_key, label, role), region in zip(
        specification.signature_roles,
        _horizontal_regions(0.87, 0.84, len(specification.signature_roles), 0.04, start_x=0.08),
        strict=True,
    ):
        version.add_field(
            _field(_FieldSpec(field_key, label, "signature"), region, specification.page, role=role)
        )
    if specification.page.size == "A5":
        version.set_print_imposition(PrintImposition(PageSpec.a4_portrait(), rows=2))
    version.mark_ready_to_publish()
    version.publish()
    return version


def _static_elements(specification: _LayoutSpec) -> tuple[StaticElement, ...]:
    elements: list[StaticElement] = [
        StaticElement(
            "title", ElementKind.TITLE, Rect(0.08, 0.04, 0.54, 0.045), specification.title
        ),
        StaticElement(
            "identity_note",
            ElementKind.LABEL,
            Rect(0.04, 0.095, 0.58, 0.025),
            "岗位、班组、单位和计价规则由岗位配置预印；右上角为表单二维码",
        ),
        StaticElement(
            "business_grid",
            ElementKind.TABLE_GRID,
            Rect(0.04, 0.385, 0.92, 0.29),
            rows=3,
            columns=len(specification.headers),
            column_weights=specification.weights,
        ),
        StaticElement(
            "quality_section",
            ElementKind.ROLE_SECTION,
            Rect(0.04, 0.68, 0.92, 0.025),
            "质量、安全与完成状态",
        ),
    ]
    header_regions = _grid_header_regions(specification.weights)
    for index, (label, region) in enumerate(
        zip(specification.headers, header_regions, strict=True)
    ):
        elements.append(
            StaticElement(f"business_header_{index + 1}", ElementKind.LABEL, region, label)
        )
    for row_index in range(2):
        elements.append(
            StaticElement(
                f"business_row_{row_index + 1}",
                ElementKind.LABEL,
                _grid_data_regions(specification.weights, row_index)[0],
                str(row_index + 1),
            )
        )
    return tuple(elements)


def _common_fields(page: PageSpec) -> tuple[FieldDefinition, ...]:
    return (
        _field(
            _FieldSpec("position_name", "岗位", "preprinted"), Rect(0.04, 0.125, 0.14, 0.055), page
        ),
        _field(
            _FieldSpec("work_date", "日期", "digit", digits=8), Rect(0.20, 0.125, 0.22, 0.075), page
        ),
        _field(
            _FieldSpec("shift", "班次", "choice", choices=("白班", "夜班"), max_selections=1),
            Rect(0.44, 0.125, 0.19, 0.075),
            page,
        ),
        _field(
            _FieldSpec("worker_number", "工号", "digit", digits=6),
            Rect(0.04, 0.215, 0.22, 0.075),
            page,
        ),
        _field(
            _FieldSpec("worker_name", "姓名：系统匹配", "derived"),
            Rect(0.28, 0.215, 0.22, 0.075),
            page,
            derived_from="worker_number",
        ),
        _field(_FieldSpec("team_name", "班组", "preprinted"), Rect(0.52, 0.24, 0.11, 0.05), page),
        _field(
            _FieldSpec("work_order_number", "工单号", "digit", digits=8),
            Rect(0.04, 0.305, 0.28, 0.065),
            page,
        ),
    )


def _field(
    specification: _FieldSpec,
    region: Rect,
    page: PageSpec,
    *,
    derived_from: str | None = None,
    conditional_required_on: str | None = None,
    role: str | None = None,
) -> FieldDefinition:
    mode = specification.kind
    paper = PaperEntryMode.HANDWRITTEN_TEXT
    recognition = RecognitionMode.NONE
    fill = FillPolicy.MANUAL_ONLY
    data_type = "text"
    input_type = "text_box"
    if mode == "digit":
        paper = PaperEntryMode.DIGIT_BOXES
        recognition = RecognitionMode.DIGIT_OCR
        fill = FillPolicy.SUGGEST_ONLY
        data_type = "integer"
        input_type = "digit_boxes"
    elif mode == "choice":
        paper = PaperEntryMode.CHECKBOX
        recognition = RecognitionMode.OMR
        fill = FillPolicy.SUGGEST_ONLY
        input_type = "checkbox"
    elif mode == "preprinted":
        paper = PaperEntryMode.PREPRINTED
        input_type = "preprinted"
    elif mode == "derived":
        paper = PaperEntryMode.NONE
        input_type = "none"
    elif mode == "calculated":
        paper = PaperEntryMode.NONE
        recognition = RecognitionMode.CALCULATED
        fill = FillPolicy.CALCULATED
        data_type = "decimal"
        input_type = "none"
    elif mode == "signature":
        paper = PaperEntryMode.SIGNATURE
        input_type = "signature"
    numeric = data_type in {"integer", "decimal"}
    return FieldDefinition(
        specification.key,
        specification.label,
        data_type,
        input_type,
        region,
        page,
        paper_entry_mode=paper,
        recognition_mode=recognition,
        fill_policy=fill,
        rules=FieldRules(
            required=mode not in {"text", "calculated"}, minimum_value=0 if numeric else None
        ),
        calculation_expression=specification.expression,
        digit_count=specification.digits,
        choice_group=specification.key if specification.choices else None,
        choice_options=specification.choices,
        max_selections=specification.max_selections,
        derived_from_field_key=derived_from,
        conditional_required_on=conditional_required_on,
        signature_role=role,
    )


def _grid_header_regions(weights: tuple[float, ...]) -> tuple[Rect, ...]:
    return _grid_regions(weights, 0)


def _grid_data_regions(weights: tuple[float, ...], row_index: int) -> tuple[Rect, ...]:
    return _grid_regions(weights, row_index + 1)


def _grid_regions(weights: tuple[float, ...], row_index: int) -> tuple[Rect, ...]:
    x = 0.04
    width = 0.92
    row_height = 0.29 / 3
    total = sum(weights)
    regions: list[Rect] = []
    for weight in weights:
        cell_width = width * weight / total
        regions.append(
            Rect(
                x + 0.003,
                0.385 + row_index * row_height + 0.004,
                cell_width - 0.006,
                row_height - 0.008,
            )
        )
        x += cell_width
    return tuple(regions)


def _extra_header_regions(count: int) -> tuple[Rect, ...]:
    return _horizontal_regions(0.305, 0.62, count, 0.065, start_x=0.34)


def _horizontal_regions(
    y: float, width: float, count: int, height: float, *, start_x: float = 0.04
) -> tuple[Rect, ...]:
    if count == 0:
        return ()
    gap = 0.012
    item_width = (width - gap * (count - 1)) / count
    return tuple(
        Rect(start_x + index * (item_width + gap), y, item_width, height) for index in range(count)
    )


def _digit(key: str, label: str, count: int) -> _FieldSpec:
    return _FieldSpec(key, label, "digit", digits=count)


def _choice(key: str, label: str, choices: tuple[str, ...], maximum: int = 1) -> _FieldSpec:
    return _FieldSpec(key, label, "choice", choices=choices, max_selections=maximum)


def _calc(key: str, label: str, expression: str) -> _FieldSpec:
    return _FieldSpec(key, label, "calculated", expression=expression)


def _preprinted(key: str, label: str) -> _FieldSpec:
    return _FieldSpec(key, label, "preprinted")


_TIMEKEEPING_ROWS = tuple(
    tuple(
        item
        for item in (
            _digit(f"start_time_{row}", "开始", 4),
            _digit(f"end_time_{row}", "结束", 4),
            _digit(f"rest_minutes_{row}", "休息", 3),
            _calc(
                f"effective_hours_{row}",
                "有效工时：系统计算",
                f"end_time_{row}-start_time_{row}-rest_minutes_{row}/60",
            ),
            _choice(f"work_type_{row}", "工作类型", ("正常", "加班")),
            _choice(f"completed_{row}", "完成", ("是", "否")),
        )
    )
    for row in (1, 2)
)

_EQUIPMENT_ROWS = tuple(
    (
        _digit(f"start_time_{row}", "开始", 4),
        _digit(f"end_time_{row}", "结束", 4),
        _calc(f"effective_hours_{row}", "有效工时：系统计算", f"end_time_{row}-start_time_{row}"),
        _digit(f"load_count_{row}", "装车", 3),
        _digit(f"unload_count_{row}", "卸车", 3),
        _digit(f"downtime_minutes_{row}", "停机", 3),
        _choice(f"task_completed_{row}", "任务", ("完成", "未完成")),
    )
    for row in (1, 2)
)

_RACK_ROWS = tuple(
    (
        _digit(f"batch_number_{row}", "批次", 6),
        _choice(f"operation_type_{row}", "作业", ("装架", "拆架")),
        _digit(f"completed_quantity_{row}", "完成数", 4),
        _digit(f"qualified_quantity_{row}", "合格数", 4),
        _calc(
            f"rejected_quantity_{row}",
            "不合格：系统计算",
            f"completed_quantity_{row}-qualified_quantity_{row}",
        ),
        _choice(f"completion_status_{row}", "确认", ("已完成", "未完成")),
    )
    for row in (1, 2)
)

_FURNACE_ROWS = tuple(
    (
        _digit(f"start_time_{row}", "开始", 4),
        _digit(f"end_time_{row}", "结束", 4),
        _digit(f"input_quantity_{row}", "装入数", 4),
        _digit(f"completed_quantity_{row}", "完成数", 4),
        _choice(f"temperature_level_{row}", "温度等级", ("低", "标准", "高")),
        _choice(f"operation_status_{row}", "运行", ("正常", "异常")),
        _choice(f"result_{row}", "结果", ("合格", "返工", "报废")),
    )
    for row in (1, 2)
)

_HOT_PRESS_ROWS = tuple(
    (
        _digit(f"order_number_{row}", "工单", 8),
        _preprinted(f"product_spec_{row}", "产品规格"),
        _digit(f"layers_{row}", "层数", 2),
        _digit(f"batch_number_{row}", "批次", 3),
        _digit(f"input_quantity_{row}", "投入", 4),
        _digit(f"qualified_quantity_{row}", "合格", 4),
        _digit(f"rework_quantity_{row}", "返工", 3),
        _calc(
            f"scrap_quantity_{row}",
            "报废：系统计算",
            f"input_quantity_{row}-qualified_quantity_{row}-rework_quantity_{row}",
        ),
        _choice(f"quality_result_{row}", "质量", ("合格", "需返工")),
    )
    for row in (1, 2)
)

_SHEET_ROWS = tuple(
    (
        _digit(f"order_number_{row}", "工单", 8),
        _preprinted(f"raw_material_spec_{row}", "原料规格"),
        _preprinted(f"finished_spec_{row}", "成品规格"),
        _digit(f"input_quantity_{row}", "投入", 4),
        _digit(f"qualified_quantity_{row}", "合格", 4),
        _calc(
            f"defect_quantity_{row}",
            "次品：系统计算",
            f"input_quantity_{row}-qualified_quantity_{row}",
        ),
        _preprinted(f"unit_{row}", "单位"),
        _choice(f"completion_status_{row}", "状态", ("完成", "未完成")),
    )
    for row in (1, 2)
)

_LAYOUTS = (
    _LayoutSpec(
        CoreLayoutKind.TIMEKEEPING,
        "PAYROLL_CORE_TIMEKEEPING",
        "计时类日工资表",
        PageSpec.a5_landscape(),
        ("序号", "开始时间", "结束时间", "休息分钟", "有效工时", "工作类型", "是否完成"),
        (0.45, 1, 1, 0.9, 1, 1, 1.15),
        _TIMEKEEPING_ROWS,  # type: ignore[arg-type]
        (),
        (_choice("assessment", "考评", ("合格", "需改进", "不合格")),),
        "assessment!=合格",
        (_calc("calculated_wage", "工资：系统计算", "effective_hours*hourly_rate"),),
        (
            ("worker_signature", "员工签字", "worker"),
            ("team_lead_signature", "班组长", "team_lead"),
            ("supervisor_signature", "主管", "supervisor"),
        ),
    ),
    _LayoutSpec(
        CoreLayoutKind.EQUIPMENT_TIMEKEEPING,
        "PAYROLL_CORE_EQUIPMENT_TIMEKEEPING",
        "叉车/设备计时工资表",
        PageSpec.a5_landscape(),
        ("序号", "开始", "结束", "有效工时", "装车次数", "卸车次数", "异常停机", "任务完成"),
        (0.4, 0.85, 0.85, 0.9, 0.85, 0.85, 0.9, 1.25),
        _EQUIPMENT_ROWS,  # type: ignore[arg-type]
        (
            _digit("device_number", "设备编号", 6),
            _preprinted("device_type", "设备类型"),
            _choice("work_area", "作业区域", ("A", "B", "C")),
        ),
        (
            _choice("safety_result", "安全检查", ("正常", "发现问题")),
            _choice("issue_type", "问题类型", ("超速", "碰撞", "设备故障", "未按路线", "其他"), 3),
        ),
        "safety_result==发现问题",
        (
            _calc("task_reward", "任务奖励：系统计算", "completed_tasks*task_rate"),
            _calc("safety_deduction", "安全扣减：系统计算", "reviewed_safety_deduction"),
        ),
        (
            ("worker_signature", "员工签字", "worker"),
            ("team_lead_signature", "班组长", "team_lead"),
            ("supervisor_signature", "主管", "supervisor"),
        ),
    ),
    _LayoutSpec(
        CoreLayoutKind.RACK_DRYING_PIECEWORK,
        "PAYROLL_CORE_RACK_DRYING_PIECEWORK",
        "装架与干燥计件工资表",
        PageSpec.a5_landscape(),
        ("序号", "批次号", "作业类型", "完成数量", "合格数量", "不合格数", "完成确认"),
        (0.45, 1.1, 1, 1, 1, 1, 1.2),
        _RACK_ROWS,  # type: ignore[arg-type]
        (_preprinted("product_spec", "产品规格"), _preprinted("unit", "单位")),
        (
            _choice("quality_result", "质量结果", ("全部合格", "有返工", "有报废")),
            _choice(
                "issue_type",
                "问题类型",
                ("装架不齐", "数量不符", "干燥异常", "材料异常", "其他"),
                3,
            ),
        ),
        "quality_result!=全部合格",
        (
            _preprinted("piece_rate", "计件单价"),
            _calc("calculated_wage", "计件工资：系统计算", "qualified_quantity*piece_rate"),
        ),
        (
            ("worker_signature", "员工签字", "worker"),
            ("team_lead_signature", "班组长", "team_lead"),
            ("supervisor_signature", "主管", "supervisor"),
        ),
    ),
    _LayoutSpec(
        CoreLayoutKind.FURNACE_WORK,
        "PAYROLL_CORE_FURNACE_WORK",
        "炉类作业工资表",
        PageSpec.a5_landscape(),
        ("炉次", "开始时间", "结束时间", "装入数量", "完成数量", "温度等级", "运行状态", "结果"),
        (0.45, 0.9, 0.9, 0.9, 0.9, 1.05, 1, 1.2),
        _FURNACE_ROWS,  # type: ignore[arg-type]
        (_digit("furnace_number", "炉号", 3),),
        (
            _choice(
                "safety_checks",
                "安全检查",
                ("压力正常", "温度正常", "阀门正常", "现场清洁", "交接完成"),
                5,
            ),
            _choice(
                "issue_type",
                "异常类型",
                ("温度异常", "压力异常", "设备故障", "材料异常", "其他"),
                3,
            ),
        ),
        "operation_status_1==异常",
        (
            _calc("furnace_wage", "炉次工资：系统计算", "completed_runs*run_rate"),
            _calc("safety_deduction", "安全扣减：系统计算", "reviewed_safety_deduction"),
        ),
        (
            ("worker_signature", "员工签字", "worker"),
            ("handover_signature", "交接人员", "handover"),
            ("supervisor_signature", "主管", "supervisor"),
        ),
    ),
    _LayoutSpec(
        CoreLayoutKind.HOT_PRESS,
        "PAYROLL_CORE_HOT_PRESS",
        "热压生产明细工资表",
        PageSpec.a4_landscape(),
        (
            "序号",
            "工单号",
            "产品规格",
            "层数",
            "批次",
            "投入数",
            "合格数",
            "返工数",
            "报废数",
            "质量结果",
        ),
        (0.4, 1.15, 1.2, 0.65, 0.75, 0.85, 0.85, 0.8, 0.85, 1.15),
        _HOT_PRESS_ROWS,  # type: ignore[arg-type]
        (),
        (
            _choice("equipment_status", "设备状态", ("正常", "短暂停机", "故障")),
            _choice(
                "issue_type",
                "问题类型",
                ("温度", "压力", "时间", "表面质量", "尺寸", "材料", "其他"),
                3,
            ),
        ),
        "equipment_status!=正常",
        (
            _preprinted("piece_rate", "计件单价"),
            _calc("calculated_wage", "应计工资：系统计算", "qualified_quantity*piece_rate"),
        ),
        (
            ("worker_signature", "员工签字", "worker"),
            ("quality_signature", "质检确认", "quality"),
            ("team_lead_signature", "班组长", "team_lead"),
            ("supervisor_signature", "主管", "supervisor"),
        ),
    ),
    _LayoutSpec(
        CoreLayoutKind.SHEET_CUTTING,
        "PAYROLL_CORE_SHEET_CUTTING",
        "开片生产明细工资表",
        PageSpec.a4_landscape(),
        (
            "序号",
            "工单号",
            "原料规格",
            "成品规格",
            "投入数",
            "合格数",
            "次品数",
            "单位",
            "完成状态",
        ),
        (0.4, 1.1, 1.25, 1.25, 0.85, 0.85, 0.85, 0.7, 1.2),
        _SHEET_ROWS,  # type: ignore[arg-type]
        (),
        (
            _choice(
                "quality_issue",
                "质量问题",
                ("尺寸偏差", "边缘破损", "表面缺陷", "材料问题", "设备问题", "其他"),
                3,
            ),
            _choice("rework_status", "返工处理", ("无需返工", "已返工", "待返工")),
        ),
        "quality_issue!=无",
        (
            _preprinted("piece_rate", "计件单价"),
            _calc("calculated_wage", "应计工资：系统计算", "qualified_quantity*piece_rate"),
        ),
        (
            ("worker_signature", "员工签字", "worker"),
            ("quality_signature", "质检确认", "quality"),
            ("team_lead_signature", "班组长", "team_lead"),
            ("supervisor_signature", "主管", "supervisor"),
        ),
    ),
)


_JOB_PROFILES: tuple[tuple[str, str, CoreLayoutKind, str, dict[str, object]], ...] = (
    ("PAYROLL_TIMEKEEPING_DAILY", "计时工", CoreLayoutKind.TIMEKEEPING, "小时", {}),
    (
        "PAYROLL_FORKLIFT_DAILY",
        "叉车工",
        CoreLayoutKind.EQUIPMENT_TIMEKEEPING,
        "次",
        {"device_type": "叉车"},
    ),
    (
        "PAYROLL_RACK_LOADING_DAILY",
        "装架组",
        CoreLayoutKind.RACK_DRYING_PIECEWORK,
        "架",
        {"operation_types": ["装架", "拆架"]},
    ),
    (
        "PAYROLL_BAMBOO_RACK_DAILY",
        "竹丝装架",
        CoreLayoutKind.RACK_DRYING_PIECEWORK,
        "架",
        {"operation_types": ["装架", "拆架"]},
    ),
    (
        "PAYROLL_DRYING_DAILY",
        "干燥组",
        CoreLayoutKind.RACK_DRYING_PIECEWORK,
        "篮",
        {"operation_types": ["入窑", "出窑"]},
    ),
    (
        "PAYROLL_STEAMING_DAILY",
        "蒸煮",
        CoreLayoutKind.FURNACE_WORK,
        "炉",
        {"furnace_type": "蒸煮炉"},
    ),
    (
        "PAYROLL_CARBONIZATION_DAILY",
        "炭化",
        CoreLayoutKind.FURNACE_WORK,
        "炉",
        {"furnace_type": "炭化炉"},
    ),
    (
        "PAYROLL_BOILER_DAILY",
        "锅炉/导热油炉",
        CoreLayoutKind.FURNACE_WORK,
        "炉",
        {"furnace_type": "锅炉"},
    ),
    ("PAYROLL_HOT_PRESS_DAILY", "热压", CoreLayoutKind.HOT_PRESS, "张", {}),
    ("PAYROLL_SHEET_CUTTING_DAILY", "开片", CoreLayoutKind.SHEET_CUTTING, "张/片", {}),
)
