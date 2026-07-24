// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { FinanceGovernedExportsPage } from "./FinanceGovernedExportsPage";
import { FinanceReportTemplatesPage } from "./FinanceReportTemplatesPage";

function response(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows analyzed workbook structure and versioned mappings", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(response({ items: [{
      template_version_id: "RTV-1",
      filename: "工资模板.xlsx",
      format: "XLSX",
      structure: { sheets: [{ name: "工资明细", max_row: 10, max_column: 8 }] },
      status: "ANALYZED",
    }] }))
    .mockResolvedValueOnce(response({ items: [{
      mapping_version_id: "RMV-1",
      template_version_id: "RTV-1",
      version: 1,
      mapping_json: { sheet: "工资明细", start_row: 2, columns: [] },
      status: "DRAFT",
    }] })));
  render(<FinanceReportTemplatesPage />);
  expect(await screen.findByText("工资模板.xlsx")).toBeTruthy();
  expect(screen.getByText("映射 V1")).toBeTruthy();
  expect(screen.getByRole("button", { name: "财务确认映射" })).toBeTruthy();
});

it("offers download only for reopened and available exports", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(response({ items: [] }))
    .mockResolvedValueOnce(response({ items: [{
      export_batch_id: "GEB-1",
      download_name: "工资模板-20260723.xlsx",
      status: "AVAILABLE",
      data_watermark: "2026-07-23T00:00:00Z",
    }] })));
  const user = userEvent.setup();
  render(<FinanceGovernedExportsPage />);
  await user.click(screen.getByRole("button", { name: /导出历史/ }));
  expect(await screen.findByText("工资模板-20260723.xlsx")).toBeTruthy();
  expect(screen.getByRole("link", { name: "下载" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "血缘" })).toBeTruthy();
});
