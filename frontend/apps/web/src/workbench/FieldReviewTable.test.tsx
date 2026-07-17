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
