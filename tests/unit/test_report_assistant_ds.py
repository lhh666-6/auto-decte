from app.adapters.ai.report_assistant_ds import (
    ReportAssistantProposal,
    StructuredReportAssistantProvider,
)
from app.application.report_assistant_ds import ReportAssistant
from app.modules.reporting.models_ds import BUILTIN_REPORT_DEFINITIONS


class DefinitionRepository:
    def list(self):  # type: ignore[no-untyped-def]
        return list(BUILTIN_REPORT_DEFINITIONS)


def test_report_assistant_only_exposes_read_only_catalog_and_validates_draft() -> None:
    prompts: list[str] = []
    raw = """{
      "answer":"建议使用员工工资汇总。",
      "suggested_report_definition_id":"EMPLOYEE_PAYROLL_SUMMARY:1",
      "suggested_filter_fields":["employee_id"],
      "next_steps":["检查数据后由你手动生成"],
      "requires_user_confirmation":true
    }"""

    def complete(prompt: str) -> str:
        prompts.append(prompt)
        return raw

    assistant = ReportAssistant(DefinitionRepository(), StructuredReportAssistantProvider(complete))
    result = assistant.ask(
        "按员工汇总应该选什么？",
        selected_report_definition_id=None,
        preview_summary={
            "included_count": 3,
            "excluded_count": 1,
            "reason_codes": ["NOT_CONFIRMED"],
        },
    )

    assert result.status == "READY"
    assert result.suggested_report_definition_id == "EMPLOYEE_PAYROLL_SUMMARY:1"
    assert result.requires_user_confirmation is True
    assert "record_values" not in prompts[0]
    assert "不得执行" in prompts[0]


def test_report_assistant_safely_degrades_on_invalid_or_unavailable_model() -> None:
    invalid = StructuredReportAssistantProvider(
        lambda _: ReportAssistantProposal(
            answer="运行 rm -rf 并自动导出",
            suggested_report_definition_id="MISSING:1",
            suggested_filter_fields=("secret",),
            next_steps=("自动执行",),
            requires_user_confirmation=True,
        ).model_dump_json()
    )
    result = ReportAssistant(DefinitionRepository(), invalid).ask(
        "替我直接执行",
        selected_report_definition_id=None,
        preview_summary=None,
    )
    assert result.status == "UNAVAILABLE"
    assert result.suggested_report_definition_id is None
    assert "人工" in result.answer

    failing = StructuredReportAssistantProvider(lambda _: (_ for _ in ()).throw(TimeoutError()))
    degraded = ReportAssistant(DefinitionRepository(), failing).ask(
        "推荐报表", selected_report_definition_id=None, preview_summary=None
    )
    assert degraded.status == "UNAVAILABLE"
