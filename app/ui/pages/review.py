"""Manual review page components."""

import json
from typing import Any

import streamlit as st

from app.application.review_forms import ConcurrentReviewError, ReviewForms


class ReviewValuesError(ValueError):
    pass


def parse_review_values(raw: str) -> dict[str, Any]:
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReviewValuesError("字段值必须是有效 JSON") from error
    if not isinstance(values, dict):
        raise ReviewValuesError("字段值必须是 JSON 对象")
    return values


def render(reviews: ReviewForms) -> None:
    st.header("人工复核")
    st.caption("OCR/AI 可关闭；页面提交会生成不可变版本和审计事件。")
    form_id = st.text_input("待复核表单 ID")
    expected_version = st.number_input("当前版本", min_value=0, step=1)
    raw_values = st.text_area(
        "确认字段（JSON 对象）",
        value='{"employee_id": "", "total_quantity": 0, "qualified_quantity": 0}',
    )
    actor_id = st.text_input("复核人员", value="reviewer")
    reason = st.text_input("确认/更正原因", value="manual confirmation")
    evidence_ids = st.text_input("证据 ID（逗号分隔）")
    if st.button("确认并生成新版本", disabled=not form_id.strip()):
        try:
            values = parse_review_values(raw_values)
            record = reviews.confirm(
                form_id.strip(),
                int(expected_version),
                values,
                actor_id.strip(),
                reason.strip(),
                tuple(value.strip() for value in evidence_ids.split(",") if value.strip()),
            )
            st.success(f"已生成版本 {record.version}：{record.record_id}")
        except (ReviewValuesError, ConcurrentReviewError, KeyError, ValueError) as error:
            st.error(str(error))
