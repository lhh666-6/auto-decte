// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { FinanceLedgerPage } from "./FinanceLedgerPage";
import { PlantExceptionsPage } from "./PlantExceptionsPage";

function response(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows real-time period projections and effective finance records", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(response({ today: 1, month: 4, year: 20 }))
    .mockResolvedValueOnce(response({ items: [{
      root_submission_id: "SUB-1",
      effective_submission_id: "SUB-2",
      factory_id: "FACTORY-A",
      subject_employee_code: "E001",
      definition_version_id: "FORM-V1",
      business_date: "2026-07-23",
      submitted_at: "2026-07-23T01:00:00Z",
      values: { quantity: 8 },
      status: "ACTIVE",
    }] }))
    .mockResolvedValueOnce(response({ items: [] })));
  render(<FinanceLedgerPage scope="today" />);
  expect(await screen.findByText("SUB-2")).toBeTruthy();
  expect(screen.getByText("正式记录数")).toBeTruthy();
  expect(screen.getByText("FACTORY-A")).toBeTruthy();
});

it("shows the shared Bamboo inspection queue", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
    bucket: "active",
    items: [{
      record_id: "REC-1",
      display_no: "ZS-20260723-001",
      cage_no: "L-01",
      status: "APPEAL_SUBMITTED",
      deadline_at: "2026-07-23T10:00:00Z",
      appeal_payload: { text_evidence: "检测湿度不合格" },
    }],
  })));
  render(<PlantExceptionsPage />);
  expect(await screen.findByText("检测湿度不合格")).toBeTruthy();
  expect(screen.getByText(/ZS-20260723-001/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "批准上诉" })).toBeTruthy();
});
