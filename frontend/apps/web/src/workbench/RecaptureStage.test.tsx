// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ReviewHistory, WorkbenchDetail } from "@form-detection/api-client";

import { RecaptureStage } from "./RecaptureStage";

const DETAIL = {
  form: {
    form_id: "FORM-RECAPTURE",
    review_status: "RECAPTURE_REQUIRED",
  },
  evidence: [{
    file_id: "FILE-OLD",
    type: "CORRECTED_IMAGE",
    related_field_id: null,
    download_url: "/old-photo.png",
  }],
  fields: [{
    field_id: "FIELD-HOURS",
    field_name: "hours",
    display_name: "工时",
    current_value: "无法辨认",
  }],
  current_record: {
    version: 1,
    values: { hours: "8" },
  },
  draft: null,
} as unknown as WorkbenchDetail;

const HISTORY = {
  versions: [],
  audits: [{
    event_id: "AUDIT-RETURN",
    event_type: "FORM_RETURNED",
    actor_id: "reviewer",
    timestamp: "2026-07-17T08:00:00Z",
    reason: "照片反光，工时字段无法确认",
    evidence_ids: ["FILE-OLD"],
  }],
} satisfies ReviewHistory;

afterEach(cleanup);

describe("RecaptureStage", () => {
  it("keeps the two-column evidence context and explains the real capability boundary", () => {
    render(<RecaptureStage detail={DETAIL} history={HISTORY} onUpload={vi.fn()} />);

    expect(screen.getByTestId("recapture-workbench-grid")).toBeTruthy();
    expect(screen.getByRole("img", { name: "上次拍摄的表单" })).toBeTruthy();
    expect(screen.getByText(/上次结果/)).toBeTruthy();
    expect(screen.getByText(/hours.*8/)).toBeTruthy();
    expect(screen.getByText("照片反光，工时字段无法确认")).toBeTruthy();
    expect(screen.getByText(/异常字段/)).toBeTruthy();
    expect(screen.getByText(/工时.*无法辨认/)).toBeTruthy();
    expect(screen.getByText("历史记录")).toBeTruthy();
    expect(screen.getByText(/会创建一张新表单/)).toBeTruthy();
    expect(screen.getByText(/尚不能自动关联为原表单的替换证据/)).toBeTruthy();
    expect(screen.queryByText(/已替换原照片|追溯关系已保存/)).toBeNull();
  });

  it("passes a new image to the existing import flow", () => {
    const onUpload = vi.fn();
    render(<RecaptureStage detail={DETAIL} history={HISTORY} onUpload={onUpload} />);
    const file = new File(["new"], "new-form.png", { type: "image/png" });

    fireEvent.change(screen.getByLabelText("上传新的表单照片"), {
      target: { files: [file] },
    });

    expect(onUpload).toHaveBeenCalledWith(file);
  });
});
