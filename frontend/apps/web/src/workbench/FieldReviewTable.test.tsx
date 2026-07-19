// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

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
      onEdit={vi.fn()}
    />,
  );

  const row = screen.getByRole("row", { name: /姓名/ });
  expect(row.textContent).toContain("必须对照字段裁片人工确认");
  expect(row.textContent).not.toContain("不应显示的候选");
  expect(row.textContent).not.toContain("99%");
});
