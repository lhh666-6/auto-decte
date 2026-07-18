// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TemplateApi, TemplateVersion } from "@form-detection/api-client";

import { TemplatePreview } from "./TemplatePreview_ds";

const VERSION = {
  version_id: "VERSION-1",
  template_key: "PAYROLL_HOURLY",
  display_name: "小时工资表",
  description: "车间工资采集",
  version: 1,
  status: "PUBLISHED",
  parent_version_id: null,
  page: {
    size: "A4", orientation: "portrait", width_mm: 210, height_mm: 297,
    canonical_dpi: 300, canonical_width_px: 2480, canonical_height_px: 3508,
  },
  static_elements: [],
  print_imposition: null,
  fields: [
    {
      field_key: "hours", display_name: "工时", data_type: "decimal", input_type: "text_box",
      recognition_engine: "digit_template", minimum_prefill_confidence: 0.9,
      paper_entry_mode: "DIGIT_BOXES", recognition_mode: "DIGIT_OCR",
      fill_policy: "PREFILL_WHEN_CONFIDENT", confidence_threshold: 0.9,
      requires_manual_confirmation: false, calculation_expression: null,
      rules: { required: true, minimum_value: 0, maximum_value: 24, allowed_values: [], master_data_source: null, allow_exception_reason: false },
      export_target: { workbook: "records.xlsx", worksheet: "records", business_column: "hours" },
      region: { x: 0.1, y: 0.2, width: 0.2, height: 0.05 },
    },
    {
      field_key: "worker", display_name: "员工", data_type: "text", input_type: "text_box",
      recognition_engine: "manual", minimum_prefill_confidence: 1,
      paper_entry_mode: "HANDWRITTEN_TEXT", recognition_mode: "NONE",
      fill_policy: "MANUAL_ONLY", confidence_threshold: null,
      requires_manual_confirmation: false, calculation_expression: null,
      rules: { required: true, minimum_value: null, maximum_value: null, allowed_values: [], master_data_source: "employees", allow_exception_reason: false },
      export_target: { workbook: "records.xlsx", worksheet: "records", business_column: "worker" },
      region: { x: 0.1, y: 0.3, width: 0.2, height: 0.05 },
    },
  ],
  artifacts: [
    { artifact_id: "PDF-1", kind: "PDF", download_name: "PAYROLL_HOURLY_V1.pdf", sha256: "pdf-sha", download_url: "/template.pdf" },
    { artifact_id: "PNG-1", kind: "PNG", download_name: "PAYROLL_HOURLY_V1.png", sha256: "png-sha", download_url: "/template.png" },
  ],
} satisfies TemplateVersion;

afterEach(cleanup);

describe("TemplatePreview", () => {
  it("provides viewport controls, field search and bidirectional selection", async () => {
    const user = userEvent.setup();
    const api = { getVersion: vi.fn().mockResolvedValue(VERSION) } as unknown as TemplateApi;
    render(<TemplatePreview api={api} versionId="VERSION-1" onBack={vi.fn()} onTune={vi.fn()} />);

    const paper = await screen.findByTestId("template-preview-paper");
    for (const name of ["放大", "缩小", "适合页面", "适合宽度", "复位"]) {
      expect(screen.getByRole("button", { name })).toBeTruthy();
    }
    await user.click(screen.getByRole("button", { name: "放大" }));
    expect(paper.getAttribute("style")).toContain("scale(1.1)");
    await user.type(screen.getByLabelText("搜索字段"), "工时");
    expect(screen.getByRole("button", { name: "选择字段 工时" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "选择字段 员工" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "选择字段 工时" }));
    expect(screen.getByRole("button", { name: "预览字段 工时" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("shows business artifact actions and moves filenames, field keys and hashes into advanced information", async () => {
    const api = { getVersion: vi.fn().mockResolvedValue(VERSION) } as unknown as TemplateApi;
    render(<TemplatePreview api={api} versionId="VERSION-1" onBack={vi.fn()} onTune={vi.fn()} />);

    expect(await screen.findByRole("link", { name: "下载 PDF" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "下载 PNG" })).toBeTruthy();
    const advanced = screen.getByText("高级信息").closest("details") as HTMLDetailsElement;
    expect(advanced.open).toBe(false);
    expect(advanced.textContent).toContain("PAYROLL_HOURLY_V1.pdf");
    expect(advanced.textContent).toContain("hours");
    expect(advanced.textContent).toContain("pdf-sha");
  });
});
