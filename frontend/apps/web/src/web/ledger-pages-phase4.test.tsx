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
  render(<FinanceLedgerPage />);
  expect(await screen.findByText("SUB-2")).toBeTruthy();
  expect(screen.getByText("20")).toBeTruthy();
  expect(screen.getByText("FACTORY-A")).toBeTruthy();
});

it("shows plant correction and task status without cross-factory navigation", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
    corrections: [{
      correction_id: "COR-1",
      original_submission_id: "SUB-1",
      status: "RETURNED",
      reason: "数量错误",
    }],
    tasks: [{
      task_id: "BT-1",
      task_type: "CORRECTION_REFILL",
      status: "PENDING",
      assigned_to: "E001",
    }],
  })));
  render(<PlantExceptionsPage />);
  expect(await screen.findByText("数量错误")).toBeTruthy();
  expect(screen.getByText("处理人：E001")).toBeTruthy();
});
