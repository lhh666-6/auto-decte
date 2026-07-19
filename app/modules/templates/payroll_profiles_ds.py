"""Reviewed production payroll profiles built from three explicit master layouts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.domain.templates_ds import (
    ElementKind,
    ExportTarget,
    FieldDefinition,
    FieldRules,
    FillPolicy,
    PageSpec,
    PaperEntryMode,
    PrintImposition,
    RecognitionMode,
    Rect,
    StaticElement,
    TemplateVersion,
)

_WORKBOOK = "企业工资记录.xlsx"
_MAIN_WORKSHEET = "工资主记录"
_DETAIL_WORKSHEET = "业务明细"
_PLACEHOLDER_LABEL = re.compile(r"(?:明细)?第\s*\d+\s*行")


class PayrollMaster(StrEnum):
    """The three reusable layout families; never exposed as finished templates."""

    TIMEKEEPING = "TIMEKEEPING"
    CRITERIA_PIECEWORK = "CRITERIA_PIECEWORK"
    FIXED_PRODUCTION_GRID = "FIXED_PRODUCTION_GRID"


@dataclass(frozen=True, slots=True)
class ProfileField:
    field_key: str
    display_name: str
    data_type: str = "text"
    entry: str = "text"
    required: bool = True


@dataclass(frozen=True, slots=True)
class PayrollTemplateProfile:
    template_key: str
    display_name: str
    description: str
    worksheet: str
    master: PayrollMaster
    page: PageSpec
    business_fields: tuple[ProfileField, ...]
    structure_checklist: tuple[str, ...]
    print_imposition: PrintImposition | None

    def __post_init__(self) -> None:
        if len({item.field_key for item in self.business_fields}) != len(self.business_fields):
            raise ValueError(f"{self.template_key} has duplicate business field keys")
        visible_business_labels = {item.display_name for item in self.business_fields}
        required_sections = {"人员信息", _master_section_title(self.master), "质量考评", "签字确认"}
        if not required_sections | visible_business_labels <= set(self.structure_checklist):
            raise ValueError(f"{self.template_key} structure checklist is incomplete")
        if any(_PLACEHOLDER_LABEL.search(item) for item in self.structure_checklist):
            raise ValueError(f"{self.template_key} uses a numbered placeholder label")


def reviewed_payroll_profiles() -> tuple[PayrollTemplateProfile, ...]:
    """Return the ten reviewed product profiles in their agreed business order."""
    return _PROFILES


def reviewed_payroll_seed_templates() -> tuple[TemplateVersion, ...]:
    """Build fresh immutable V1 definitions for all reviewed product profiles."""
    return tuple(_build_template(profile) for profile in reviewed_payroll_profiles())


def reviewed_payroll_export_seed_templates() -> tuple[TemplateVersion, ...]:
    """Build immutable V2 definitions with stable main/detail Excel mappings."""
    return tuple(
        _build_template(profile, version_number=2, stable_export_layout=True)
        for profile in reviewed_payroll_profiles()
    )


def reviewed_payroll_metadata() -> dict[str, tuple[str, str]]:
    return {
        profile.template_key: (profile.display_name, profile.description)
        for profile in reviewed_payroll_profiles()
    }


def _profile(
    template_key: str,
    display_name: str,
    description: str,
    worksheet: str,
    master: PayrollMaster,
    page: PageSpec,
    business_fields: tuple[ProfileField, ...],
) -> PayrollTemplateProfile:
    imposition = _two_up_imposition(page) if page.size == "A5" else None
    checklist = (
        display_name,
        "人员信息",
        *tuple(item.display_name for item in business_fields),
        _master_section_title(master),
        "质量考评",
        "事实说明",
        "员工签字",
        "质量签字",
        "主管签字",
        "签字确认",
    )
    return PayrollTemplateProfile(
        template_key=template_key,
        display_name=display_name,
        description=description,
        worksheet=worksheet,
        master=master,
        page=page,
        business_fields=business_fields,
        structure_checklist=checklist,
        print_imposition=imposition,
    )


def _build_template(
    profile: PayrollTemplateProfile,
    *,
    version_number: int = 1,
    stable_export_layout: bool = False,
) -> TemplateVersion:
    version = TemplateVersion.draft(
        f"TPL-SEED-{profile.template_key}-V{version_number}",
        profile.template_key,
        version_number,
        profile.page,
    )
    for element in _static_elements(profile):
        version.add_static_element(element)
    for specification, region in zip(_COMMON_FIELDS, _COMMON_REGIONS, strict=True):
        version.add_field(
            _field(
                specification,
                region,
                profile,
                stable_export_layout=stable_export_layout,
                detail=False,
            )
        )
    business_regions = _business_regions(len(profile.business_fields))
    for specification, region in zip(profile.business_fields, business_regions, strict=True):
        version.add_field(
            _field(
                specification,
                region,
                profile,
                stable_export_layout=stable_export_layout,
                detail=True,
            )
        )
    for specification, region in zip(_ASSESSMENT_FIELDS, _ASSESSMENT_REGIONS, strict=True):
        version.add_field(
            _field(
                specification,
                region,
                profile,
                stable_export_layout=stable_export_layout,
                detail=False,
            )
        )
    for specification, region in zip(_SIGNATURE_FIELDS, _SIGNATURE_REGIONS, strict=True):
        version.add_field(
            _field(
                specification,
                region,
                profile,
                stable_export_layout=stable_export_layout,
                detail=False,
            )
        )
    version.set_print_imposition(profile.print_imposition)
    version.mark_ready_to_publish()
    version.publish()
    return version


def _static_elements(profile: PayrollTemplateProfile) -> tuple[StaticElement, ...]:
    return (
        StaticElement(
            "title", ElementKind.TITLE, Rect(0.10, 0.04, 0.40, 0.055), profile.display_name
        ),
        StaticElement(
            "personnel_section",
            ElementKind.ROLE_SECTION,
            Rect(0.06, 0.245, 0.88, 0.028),
            "人员信息",
        ),
        StaticElement(
            "personnel_labels",
            ElementKind.LABEL,
            Rect(0.06, 0.273, 0.88, 0.02),
            "日期 / 班次 / 工号 / 姓名 / 班组 / 工单",
        ),
        StaticElement(
            "business_section",
            ElementKind.ROLE_SECTION,
            Rect(0.06, 0.425, 0.88, 0.028),
            _master_section_title(profile.master),
        ),
        StaticElement("business_grid", ElementKind.TABLE_GRID, Rect(0.06, 0.455, 0.88, 0.24)),
        StaticElement(
            "quality_section", ElementKind.ROLE_SECTION, Rect(0.06, 0.705, 0.88, 0.025), "质量考评"
        ),
        StaticElement("quality_grid", ElementKind.TABLE_GRID, Rect(0.06, 0.735, 0.88, 0.115)),
        StaticElement("quality_pass_box", ElementKind.CHECKBOX, Rect(0.065, 0.745, 0.03, 0.03)),
        StaticElement("quality_improve_box", ElementKind.CHECKBOX, Rect(0.285, 0.745, 0.03, 0.03)),
        StaticElement("quality_fail_box", ElementKind.CHECKBOX, Rect(0.525, 0.745, 0.03, 0.03)),
        StaticElement(
            "signature_section",
            ElementKind.ROLE_SECTION,
            Rect(0.06, 0.855, 0.88, 0.025),
            "签字确认",
        ),
        StaticElement(
            "worker_signature_line", ElementKind.SIGNATURE_LINE, Rect(0.06, 0.925, 0.26, 0.008)
        ),
        StaticElement(
            "quality_signature_line", ElementKind.SIGNATURE_LINE, Rect(0.37, 0.925, 0.26, 0.008)
        ),
        StaticElement(
            "supervisor_signature_line", ElementKind.SIGNATURE_LINE, Rect(0.68, 0.925, 0.26, 0.008)
        ),
    )


def _field(
    specification: ProfileField,
    region: Rect,
    profile: PayrollTemplateProfile,
    *,
    stable_export_layout: bool,
    detail: bool,
) -> FieldDefinition:
    paper_mode = PaperEntryMode.HANDWRITTEN_TEXT
    recognition_mode = RecognitionMode.NONE
    fill_policy = FillPolicy.MANUAL_ONLY
    input_type = "text_box"
    if specification.entry == "digit":
        paper_mode = PaperEntryMode.DIGIT_BOXES
        recognition_mode = RecognitionMode.DIGIT_OCR
        fill_policy = FillPolicy.SUGGEST_ONLY
        input_type = "digit_boxes"
    elif specification.entry == "checkbox":
        paper_mode = PaperEntryMode.CHECKBOX
        recognition_mode = RecognitionMode.OMR
        fill_policy = FillPolicy.SUGGEST_ONLY
        input_type = "checkbox"
    elif specification.entry == "signature":
        paper_mode = PaperEntryMode.SIGNATURE
        input_type = "signature"
    numeric = specification.data_type in {"integer", "decimal"}
    allowed_values: tuple[str, ...] = ()
    if specification.field_key == "shift":
        allowed_values = ("白班", "夜班")
    return FieldDefinition(
        field_key=specification.field_key,
        display_name=specification.display_name,
        data_type=specification.data_type,
        input_type=input_type,
        region=region,
        page=profile.page,
        paper_entry_mode=paper_mode,
        recognition_mode=recognition_mode,
        fill_policy=fill_policy,
        rules=FieldRules(
            required=specification.required,
            minimum_value=0.0 if numeric else None,
            allowed_values=allowed_values,
            master_data_source="employees" if specification.field_key == "worker_number" else None,
            allow_exception_reason=specification.field_key
            in {
                "facts_description",
                "deduction_amount",
                "quality_deduction",
                "safety_deduction",
                "energy_deduction",
            },
        ),
        export_target=ExportTarget(
            _WORKBOOK,
            _DETAIL_WORKSHEET
            if stable_export_layout and detail
            else (_MAIN_WORKSHEET if stable_export_layout else profile.worksheet),
            specification.display_name if stable_export_layout else specification.field_key,
        ),
        requires_manual_confirmation=specification.field_key == "worker_name",
    )


def _business_regions(count: int) -> tuple[Rect, ...]:
    if count > 12:
        raise ValueError("reviewed profile supports at most twelve business fields")
    return tuple(
        Rect(0.06 + (index % 3) * 0.295, 0.46 + (index // 3) * 0.058, 0.27, 0.055)
        for index in range(count)
    )


def _master_section_title(master: PayrollMaster) -> str:
    return {
        PayrollMaster.TIMEKEEPING: "工时与作业记录",
        PayrollMaster.CRITERIA_PIECEWORK: "等级、数量与计价",
        PayrollMaster.FIXED_PRODUCTION_GRID: "固定生产明细",
    }[master]


def _two_up_imposition(page: PageSpec) -> PrintImposition:
    if page.orientation == "portrait":
        return PrintImposition(PageSpec.a4_landscape(), columns=2, rows=1)
    return PrintImposition(PageSpec.a4_portrait(), columns=1, rows=2)


def _text(field_key: str, display_name: str, *, required: bool = True) -> ProfileField:
    return ProfileField(field_key, display_name, required=required)


def _digit(
    field_key: str,
    display_name: str,
    *,
    data_type: str = "decimal",
    required: bool = True,
) -> ProfileField:
    return ProfileField(field_key, display_name, data_type, "digit", required)


_COMMON_FIELDS = (
    _text("work_date", "日期"),
    _text("shift", "班次"),
    ProfileField("worker_number", "工号", "text", "text", True),
    _text("worker_name", "姓名"),
    _text("team_name", "班组"),
    _text("work_order_number", "工单号", required=False),
)
_COMMON_REGIONS = (
    Rect(0.06, 0.295, 0.20, 0.058),
    Rect(0.28, 0.295, 0.14, 0.058),
    Rect(0.44, 0.295, 0.22, 0.058),
    Rect(0.68, 0.295, 0.26, 0.058),
    Rect(0.06, 0.36, 0.28, 0.058),
    Rect(0.36, 0.36, 0.28, 0.058),
)
_ASSESSMENT_FIELDS = (
    ProfileField("assessment_passed", "考评合格", "boolean", "checkbox"),
    ProfileField("assessment_improvement", "需要改进", "boolean", "checkbox", False),
    ProfileField("assessment_failed", "考评不合格", "boolean", "checkbox", False),
    _text("facts_description", "事实说明", required=False),
)
_ASSESSMENT_REGIONS = (
    Rect(0.065, 0.745, 0.17, 0.045),
    Rect(0.285, 0.745, 0.19, 0.045),
    Rect(0.525, 0.745, 0.20, 0.045),
    Rect(0.06, 0.795, 0.88, 0.055),
)
_SIGNATURE_FIELDS = (
    ProfileField("worker_signature", "员工签字", "text", "signature"),
    ProfileField("quality_signature", "质量签字", "text", "signature"),
    ProfileField("supervisor_signature", "主管签字", "text", "signature"),
)
_SIGNATURE_REGIONS = (
    Rect(0.06, 0.885, 0.26, 0.045),
    Rect(0.37, 0.885, 0.26, 0.045),
    Rect(0.68, 0.885, 0.26, 0.045),
)


_PROFILES = (
    _profile(
        "PAYROLL_TIMEKEEPING_DAILY",
        "计时工日工资表",
        "适用于计时工每日工时、考评与工资确认",
        "计时工日工资",
        PayrollMaster.TIMEKEEPING,
        PageSpec.a5_portrait(),
        (
            _text("start_time", "上班时间"),
            _text("end_time", "下班时间"),
            _digit("regular_hours", "正常工时"),
            _digit("overtime_hours", "加班工时", required=False),
            _digit("hourly_rate", "计时单价"),
            _digit("overtime_rate", "加班单价", required=False),
            _digit("gross_wage", "应计工资"),
            _digit("deduction_amount", "扣减金额", required=False),
            _digit("payable_wage", "实发工资"),
        ),
    ),
    _profile(
        "PAYROLL_FORKLIFT_DAILY",
        "叉车工日工资表",
        "适用于叉车工工时、装卸任务与安全考评",
        "叉车工日工资",
        PayrollMaster.TIMEKEEPING,
        PageSpec.a5_landscape(),
        (
            _text("forklift_number", "叉车编号"),
            _text("start_time", "上班时间"),
            _text("end_time", "下班时间"),
            _digit("forklift_hours", "叉车工时"),
            _digit("loading_count", "装车次数", data_type="integer", required=False),
            _digit("unloading_count", "卸车次数", data_type="integer", required=False),
            _digit("hourly_rate", "计时单价"),
            _digit("task_bonus", "任务奖励", required=False),
            _digit("safety_deduction", "安全扣减", required=False),
            _digit("payable_wage", "实发工资"),
        ),
    ),
    _profile(
        "PAYROLL_RACK_LOADING_DAILY",
        "装架组日工资表",
        "适用于装架组按架型、数量和质量计件",
        "装架组日工资",
        PayrollMaster.CRITERIA_PIECEWORK,
        PageSpec.a5_portrait(),
        (
            _text("rack_type", "架型"),
            _text("product_grade", "产品等级"),
            _digit("rack_count", "装架数量", data_type="integer"),
            _digit("qualified_count", "合格数量", data_type="integer"),
            _digit("unit_price", "计件单价"),
            _digit("rework_count", "返工数量", data_type="integer", required=False),
            _digit("quality_deduction", "质量扣减", required=False),
            _digit("payable_wage", "实发工资"),
        ),
    ),
    _profile(
        "PAYROLL_BAMBOO_RACK_DAILY",
        "竹丝装架日工资表",
        "适用于竹丝装架按等级、重量和合格架数计件",
        "竹丝装架日工资",
        PayrollMaster.CRITERIA_PIECEWORK,
        PageSpec.a5_portrait(),
        (
            _text("bamboo_grade", "竹丝等级"),
            _digit("bundle_count", "竹丝捆数", data_type="integer"),
            _digit("strand_weight_kg", "竹丝重量(kg)"),
            _digit("qualified_rack_count", "合格架数", data_type="integer"),
            _digit("unit_price", "计件单价"),
            _digit("material_deduction", "材料扣减", required=False),
            _digit("payable_wage", "实发工资"),
        ),
    ),
    _profile(
        "PAYROLL_DRYING_DAILY",
        "干燥组日工资表",
        "适用于干燥组按窑次、重量和合格产出计件",
        "干燥组日工资",
        PayrollMaster.CRITERIA_PIECEWORK,
        PageSpec.a5_landscape(),
        (
            _text("kiln_number", "干燥窑号"),
            _text("batch_number", "生产批次"),
            _text("product_grade", "产品等级"),
            _digit("input_weight_kg", "入窑重量(kg)"),
            _digit("qualified_weight_kg", "合格重量(kg)"),
            _digit("drying_rate", "干燥折算率"),
            _digit("unit_price", "计件单价"),
            _digit("energy_deduction", "能耗扣减", required=False),
            _digit("payable_wage", "实发工资"),
        ),
    ),
    _profile(
        "PAYROLL_STEAMING_DAILY",
        "蒸煮日工资表",
        "适用于蒸煮岗位按锅次、合格数量和质量计件",
        "蒸煮日工资",
        PayrollMaster.CRITERIA_PIECEWORK,
        PageSpec.a5_portrait(),
        (
            _text("vat_number", "蒸煮锅号"),
            _text("batch_number", "生产批次"),
            _text("product_grade", "产品等级"),
            _digit("pot_count", "蒸煮锅次", data_type="integer"),
            _digit("qualified_count", "合格数量", data_type="integer"),
            _digit("unit_price", "计件单价"),
            _digit("quality_deduction", "质量扣减", required=False),
            _digit("payable_wage", "实发工资"),
        ),
    ),
    _profile(
        "PAYROLL_CARBONIZATION_DAILY",
        "炭化日工资表",
        "适用于炭化岗位按窑次、篮数和合格产出计件",
        "炭化日工资",
        PayrollMaster.CRITERIA_PIECEWORK,
        PageSpec.a5_portrait(),
        (
            _text("carbonization_kiln", "炭化窑号"),
            _text("batch_number", "生产批次"),
            _text("product_grade", "产品等级"),
            _digit("basket_count", "炭化篮数", data_type="integer"),
            _digit("qualified_count", "合格数量", data_type="integer"),
            _digit("unit_price", "计件单价"),
            _digit("energy_deduction", "能耗扣减", required=False),
            _digit("payable_wage", "实发工资"),
        ),
    ),
    _profile(
        "PAYROLL_BOILER_DAILY",
        "锅炉/导热油炉日工资表",
        "适用于锅炉与导热油炉岗位的产出、能耗和安全考评",
        "锅炉日工资",
        PayrollMaster.CRITERIA_PIECEWORK,
        PageSpec.a5_landscape(),
        (
            _text("boiler_number", "炉号"),
            _text("fuel_type", "燃料类型"),
            _digit("shift_hours", "运行小时"),
            _digit("steam_output_ton", "蒸汽产量(吨)", required=False),
            _digit("heat_output_mwh", "供热量(MWh)", required=False),
            _digit("unit_price", "计价单价"),
            _digit("fuel_deduction", "燃料扣减", required=False),
            _digit("safety_deduction", "安全扣减", required=False),
            _digit("payable_wage", "实发工资"),
        ),
    ),
    _profile(
        "PAYROLL_HOT_PRESS_DAILY",
        "热压岗位日工资表",
        "适用于热压岗位固定规格生产明细与质量计件",
        "热压岗位日工资",
        PayrollMaster.FIXED_PRODUCTION_GRID,
        PageSpec.a4_landscape(),
        (
            _text("press_number", "热压机号"),
            _text("product_specification", "产品规格"),
            _text("product_grade", "产品等级"),
            _text("planned_batch", "计划批次"),
            _digit("qualified_board_count", "合格板数", data_type="integer"),
            _digit("defective_board_count", "不合格板数", data_type="integer", required=False),
            _digit("unit_price", "计件单价"),
            _digit("glue_deduction", "胶耗扣减", required=False),
            _digit("quality_deduction", "质量扣减", required=False),
            _digit("payable_wage", "实发工资"),
        ),
    ),
    _profile(
        "PAYROLL_SHEET_CUTTING_DAILY",
        "开片组日工资表",
        "适用于开片组固定规格投入、合格产出和损耗计件",
        "开片组日工资",
        PayrollMaster.FIXED_PRODUCTION_GRID,
        PageSpec.a4_landscape(),
        (
            _text("saw_number", "开片锯号"),
            _text("source_board_specification", "原板规格"),
            _text("cut_specification", "开片规格"),
            _text("product_grade", "产品等级"),
            _digit("input_board_count", "投入板数", data_type="integer"),
            _digit("qualified_sheet_count", "合格片数", data_type="integer"),
            _digit("scrap_sheet_count", "废片数", data_type="integer", required=False),
            _digit("unit_price", "计件单价"),
            _digit("blade_deduction", "刀具扣减", required=False),
            _digit("quality_deduction", "质量扣减", required=False),
            _digit("payable_wage", "实发工资"),
        ),
    ),
)
