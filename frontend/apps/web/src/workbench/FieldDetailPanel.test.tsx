// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import type { EvidenceItem, ReviewField } from "@form-detection/api-client";

import { FieldDetailPanel } from "./FieldDetailPanel";

afterEach(cleanup);

const NAME_FIELD: ReviewField = {
  field_id: "FIELD-NAME",
  field_name: "worker_name",
  display_name: "姓名",
  data_type: "text",
  recognition_engine: "manual",
  paper_entry_mode: "HANDWRITTEN_TEXT",
  recognition_mode: "NONE",
  fill_policy: "MANUAL_ONLY",
  requires_manual_confirmation: true,
  rules: {
    required: true,
    minimum_value: null,
    maximum_value: null,
    allowed_values: [],
    master_data_source: null,
    master_data_options: [],
  },
  source_region: { x: 1, y: 2, width: 3, height: 4 },
  current_value: "张三",
  current_value_source: "RECOGNIZED",
  current_record_version: 0,
  candidates: [{
    attempt_id: "STALE",
    candidate_value: "不应出现的姓名候选",
    confidence: 0.99,
    engine: "legacy",
    model_version: "1",
    crop_file_id: "CROP-NAME",
  }],
};

const NAME_CROP: EvidenceItem = {
  file_id: "CROP-NAME",
  type: "FIELD_CROP",
  related_field_id: "FIELD-NAME",
  sha256: "crop-sha",
  immutable: true,
  created_at: "2026-07-19T00:00:00Z",
  download_url: "/crop-name.png",
};

it("shows the name crop and manual-only behavior without stale recognition output", () => {
  render(
    <FieldDetailPanel
      selectedField={NAME_FIELD}
      evidence={[NAME_CROP]}
      history={null}
      warningCount={1}
      ruleFailure={null}
      onUseCandidate={vi.fn()}
    />,
  );

  expect(screen.getByText("必须人工确认")).toBeTruthy();
  expect(screen.getByRole("img", { name: "原图裁片" }).getAttribute("src")).toBe("/crop-name.png");
  expect(screen.getByText("手写文字 · 不自动识别 · 完全由工作人员填写")).toBeTruthy();
  expect(screen.getByText("该字段不产生识别候选或可靠度")).toBeTruthy();
  expect(screen.queryByText("不应出现的姓名候选")).toBeNull();
  expect(screen.queryByText("99%")).toBeNull();
  expect(screen.getByText("必填")).toBeTruthy();
});
