"""Strict, read-only report assistant contracts and provider wrapper."""

import json
from collections.abc import Callable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReportAssistantProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str = Field(min_length=1, max_length=4000)
    suggested_report_definition_id: str | None = None
    suggested_filter_fields: tuple[str, ...] = ()
    next_steps: tuple[str, ...] = Field(default=(), max_length=5)
    requires_user_confirmation: Literal[True] = True


class ReportAssistantResult(ReportAssistantProposal):
    status: Literal["READY", "UNAVAILABLE"]


class StructuredReportAssistantProvider:
    def __init__(self, completion: Callable[[str], str]) -> None:
        self._completion = completion

    def answer(self, context: Mapping[str, object]) -> ReportAssistantProposal:
        prompt = json.dumps(
            {
                "role": "工业工资报表只读助手",
                "rules": [
                    "只回答、解释或生成临时建议，不修改任何业务数据",
                    "不得发布报表、生成或删除文件",
                    "不得执行 Python、SQL、Shell、JavaScript、公式或模型给出的任何代码",
                    "只能推荐 catalog 中已有的精确报表定义和该定义允许的筛选字段",
                    "所有建议都必须由用户确认",
                    "只返回符合约定的 JSON",
                ],
                **context,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return ReportAssistantProposal.model_validate_json(self._completion(prompt))


class DisabledReportAssistant:
    def answer(self, context: Mapping[str, object]) -> ReportAssistantProposal:
        del context
        raise RuntimeError("report assistant is disabled")
