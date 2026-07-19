// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import type { ReviewField } from "@form-detection/api-client";

import { FieldReviewTable } from "./FieldReviewTable";

afterEach(cleanup);

it("keeps a persisted human-confirmed low-confidence value ready after reload", () => {
  render(
    <FieldReviewTable
      fields={[{
        field_id: "FORM-1:TEMPLATE-1:work_hours",
        field_name: "work_hours",
        display_name: "工作小时",
        data_type: "decimal",
        recognition_engine: "digits",
        paper_entry_mode: "DIGIT_BOXES",
        recognition_mode: "DIGIT_OCR",
        fill_policy: "SUGGEST_ONLY",
        requires_manual_confirmation: false,
        review_group: "WORKER",
        rules: {
          required: true,
          minimum_value: 0,
          maximum_value: 24,
          allowed_values: [],
          master_data_source: null,
          master_data_options: [],
        },
        source_region: { x: 0, y: 0, width: 10, height: 10 },
        current_value: 8,
        current_value_source: "HUMAN_CONFIRMED",
        current_record_version: 1,
        candidates: [{
          attempt_id: "ATTEMPT-1",
          candidate_value: "3",
          confidence: 0.4,
          engine: "digits",
          model_version: "1",
          crop_file_id: "CROP-1",
        }],
      }]}
      edits={{}}
      recordValues={{ "FORM-1:TEMPLATE-1:work_hours": 8 }}
      ruleFailures={{}}
      selectedFieldId={null}
      hoveredFieldId={null}
      onSelectField={vi.fn()}
      onHoverField={vi.fn()}
      onEdit={vi.fn()}
    />,
  );

  const row = screen.getByRole("row", { name: /工作小时/ });
  expect(row.textContent).toContain("已就绪");
  expect(row.textContent).not.toContain("待确认");
});

it("hides stale candidates for manual fields and requires explicit name confirmation", () => {
  const onEdit = vi.fn();
  render(
    <FieldReviewTable
      fields={[{
        field_id: "FIELD-NAME",
        field_name: "worker_name",
        display_name: "姓名",
        data_type: "text",
        recognition_engine: "manual",
        paper_entry_mode: "HANDWRITTEN_TEXT",
        recognition_mode: "NONE",
        fill_policy: "MANUAL_ONLY",
        requires_manual_confirmation: true,
        review_group: "WORKER",
        rules: null,
        source_region: {},
        current_value: "张三",
        current_value_source: "RECOGNIZED",
        current_record_version: 0,
        candidates: [{
          attempt_id: "STALE-CANDIDATE",
          candidate_value: "不应显示的候选",
          confidence: 0.99,
          engine: "legacy",
          model_version: "1",
          crop_file_id: "CROP-NAME",
        }],
      }]}
      edits={{}}
      recordValues={{}}
      ruleFailures={{}}
      selectedFieldId="FIELD-NAME"
      hoveredFieldId={null}
      onSelectField={vi.fn()}
      onHoverField={vi.fn()}
      onEdit={onEdit}
    />,
  );

  const row = screen.getByRole("row", { name: /姓名/ });
  expect(row.textContent).toContain("必须对照字段裁片人工确认");
  expect(row.textContent).not.toContain("不应显示的候选");
  expect(row.textContent).not.toContain("99%");
  fireEvent.click(screen.getByRole("button", { name: "确认姓名与原图一致" }));
  expect(onEdit).toHaveBeenCalledWith("FIELD-NAME", "张三");
});

it("groups fields by review role and shows an active employee match", () => {
  render(
    <FieldReviewTable
      fields={[
        reviewField("worker_number", "工号", "WORKER", {
          current_value: "E001",
          rules: employeeRules(),
        }),
        reviewField("qualified_count", "合格数量", "QUALITY"),
        reviewField("unit_price", "计件单价", "SUPERVISOR"),
        reviewField("worker_signature", "员工签字", "SIGNATURE"),
      ]}
      edits={{}}
      recordValues={{}}
      ruleFailures={{}}
      selectedFieldId={null}
      hoveredFieldId={null}
      onSelectField={vi.fn()}
      onHoverField={vi.fn()}
      onEdit={vi.fn()}
    />,
  );

  for (const label of ["工人填写", "质量填写", "主管填写", "签字确认"]) {
    expect(screen.getByText(label)).toBeTruthy();
  }
  expect(screen.getByRole("row", { name: /工号/ }).textContent).toContain("工号已匹配");
});

it("keeps an unknown worker number in manual handling", () => {
  render(
    <FieldReviewTable
      fields={[reviewField("worker_number", "工号", "WORKER", {
        current_value: "E999",
        rules: employeeRules(),
      })]}
      edits={{}}
      recordValues={{}}
      ruleFailures={{}}
      selectedFieldId={null}
      hoveredFieldId={null}
      onSelectField={vi.fn()}
      onHoverField={vi.fn()}
      onEdit={vi.fn()}
    />,
  );

  expect(screen.getByRole("row", { name: /工号/ }).textContent)
    .toContain("工号未在员工库中匹配，必须人工处理");
});

function employeeRules(): NonNullable<ReviewField["rules"]> {
  return {
    required: true,
    minimum_value: null,
    maximum_value: null,
    allowed_values: [],
    master_data_source: "employees",
    master_data_options: [{ value: "E001", label: "张三" }],
  };
}

function reviewField(
  fieldName: string,
  displayName: string,
  reviewGroup: ReviewField["review_group"],
  overrides: Partial<ReviewField> = {},
): ReviewField {
  return {
    field_id: `FIELD-${fieldName}`,
    field_name: fieldName,
    display_name: displayName,
    data_type: "text",
    recognition_engine: "manual",
    paper_entry_mode: reviewGroup === "SIGNATURE" ? "SIGNATURE" : "HANDWRITTEN_TEXT",
    recognition_mode: "NONE",
    fill_policy: "MANUAL_ONLY",
    requires_manual_confirmation: false,
    review_group: reviewGroup,
    rules: null,
    source_region: {},
    current_value: "已填写",
    current_value_source: "HUMAN_CONFIRMED",
    current_record_version: 1,
    candidates: [],
    ...overrides,
  };
}
