// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { AdminPayrollApprovalsPage } from "./AdminPayrollApprovalsPage";
import { PayrollResultsPage } from "./PayrollResultsPage";

function response(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows payroll rule details to the administrator before approval", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ items: [{
    rule_version_id: "PRV-1",
    rule_key: "PIECE",
    name: "计件工资",
    factory_id: "FACTORY-A",
    version: 2,
    dsl: { metric: "quantity", rate: "2.5", base: "0" },
    status: "PENDING_APPROVAL",
  }] })));
  render(<AdminPayrollApprovalsPage />);
  expect(await screen.findByText("计件工资 V2")).toBeTruthy();
  expect(screen.getByRole("button", { name: "批准生效" })).toBeTruthy();
});

it("renders only server-confirmed plant payroll results", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ items: [{
    result_id: "PCR-1",
    employee_code: "E001",
    factory_id: "FACTORY-A",
    business_date: "2026-07-23",
    amount: "25.00",
  }] })));
  render(<PayrollResultsPage workspace="plant" />);
  expect(await screen.findByText("¥ 25.00")).toBeTruthy();
  expect(screen.getByText("E001")).toBeTruthy();
});
