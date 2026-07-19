"""Read-only report assistant application service."""

from collections.abc import Mapping, Sequence
from typing import Protocol

from app.adapters.ai.report_assistant_ds import (
    ReportAssistantProposal,
    ReportAssistantResult,
)
from app.modules.reporting.models_ds import ReportDefinition, ReportDefinitionStatus


class ReportDefinitionReader(Protocol):
    def list(self) -> Sequence[ReportDefinition]: ...


class ReportAssistantAdapter(Protocol):
    def answer(self, context: Mapping[str, object]) -> ReportAssistantProposal: ...


class ReportAssistant:
    def __init__(
        self,
        definitions: ReportDefinitionReader,
        adapter: ReportAssistantAdapter,
    ) -> None:
        self._definitions = definitions
        self._adapter = adapter

    def ask(
        self,
        question: str,
        *,
        selected_report_definition_id: str | None,
        preview_summary: Mapping[str, object] | None,
    ) -> ReportAssistantResult:
        definitions = tuple(
            item
            for item in self._definitions.list()
            if item.status is ReportDefinitionStatus.PUBLISHED
        )
        by_id = {item.definition_id: item for item in definitions}
        selected = by_id.get(selected_report_definition_id or "")
        context: dict[str, object] = {
            "question": question,
            "selected_report_definition_id": selected.definition_id if selected else None,
            "preview_summary": dict(preview_summary) if preview_summary is not None else None,
            "catalog": [
                {
                    "definition_id": item.definition_id,
                    "display_name": item.display_name,
                    "kind": item.kind.value,
                    "filters": list(item.filters),
                    "group_by": list(item.group_by),
                    "aggregates": [aggregate.operation.value for aggregate in item.aggregates],
                }
                for item in definitions
            ],
        }
        try:
            proposal = self._adapter.answer(context)
            suggested = by_id.get(proposal.suggested_report_definition_id or "")
            if proposal.suggested_report_definition_id is not None and suggested is None:
                raise ValueError("assistant suggested an unknown report definition")
            if suggested is None and proposal.suggested_filter_fields:
                raise ValueError("assistant suggested filters without a report definition")
            if suggested is not None and not set(proposal.suggested_filter_fields).issubset(
                suggested.filters
            ):
                raise ValueError("assistant suggested unsupported filters")
            return ReportAssistantResult(status="READY", **proposal.model_dump())
        except Exception:
            return ReportAssistantResult(
                status="UNAVAILABLE",
                answer="AI 助手暂时不可用，不影响人工检查和导出。请按当前报表定义继续操作。",
                next_steps=("检查排除原因", "由你确认报表后再生成 Excel"),
                requires_user_confirmation=True,
            )
