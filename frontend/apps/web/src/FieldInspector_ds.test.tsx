// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FieldInspector } from "./FieldInspector_ds";
import { createFieldDraft } from "./template-studio-model";

const PAGE = { size: "A4", orientation: "portrait", width_mm: 210, height_mm: 297, canonical_dpi: 300, canonical_width_px: 2480, canonical_height_px: 3508 } as const;

afterEach(cleanup);

describe("FieldInspector", () => {
  it("groups business settings and keeps technical coordinates in advanced settings", () => {
    render(<FieldInspector field={createFieldDraft([])} page={PAGE} editable onSave={vi.fn()} onDelete={vi.fn()} />);
    for (const group of ["常用设置", "填写与识别", "校验规则", "Excel 导出", "高级设置"]) {
      expect(screen.getByText(group)).toBeTruthy();
    }
    expect((screen.getByText("高级设置").closest("details") as HTMLDetailsElement).open).toBe(false);
  });

  it("clears stale recognition policy before saving", async () => {
    const user = userEvent.setup();
    const field = { ...createFieldDraft([]), recognition_mode: "DIGIT_OCR" as const, recognition_engine: "digit_template", fill_policy: "PREFILL_WHEN_CONFIDENT" as const, confidence_threshold: 0.97 };
    const save = vi.fn().mockResolvedValue(undefined);
    render(<FieldInspector field={field} page={PAGE} editable onSave={save} onDelete={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText("识别方式"), "NONE");
    await user.click(screen.getByRole("button", { name: "保存字段" }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({ recognition_mode: "NONE", fill_policy: "MANUAL_ONLY", confidence_threshold: null })));
  });
});
