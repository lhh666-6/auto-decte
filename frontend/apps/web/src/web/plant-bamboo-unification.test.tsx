// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { PlantProductionPage } from "./PlantProductionPage";
import { PlantSignaturePage } from "./PlantSignaturePage";

vi.mock("./WebSessionProvider", () => ({
  useWebSession: () => ({
    session: {
      employee_code: "MGR-1",
      employee_name: "张厂长",
      factory_id: "FACTORY-A",
      factory_name: "一厂",
    },
  }),
}));

function response(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("returns a shared Bamboo record by selected stage with concurrency headers", async () => {
  const production = {
    overview: { total: 1, active: 1, completed: 0 },
    records: [{
      record_id: "REC-1",
      display_no: "ZS-20260723-001",
      factory_id: "FACTORY-A",
      form_type: "SORTING",
      base_info: { cage_no: "L-01" },
      cage_no: "L-01",
      current_stage: "SUPERVISOR",
      status: "ACTIVE",
      revision: 7,
      created_at: "2026-07-23T08:00:00Z",
      updated_at: "2026-07-23T09:00:00Z",
    }],
  };
  const fetcher = vi.fn()
    .mockResolvedValueOnce(response(production))
    .mockResolvedValueOnce(response({ return_id: "RET-1", record_id: "REC-1", revision: 8 }))
    .mockResolvedValueOnce(response({ ...production, records: [] }));
  vi.stubGlobal("fetch", fetcher);

  render(<MemoryRouter><PlantProductionPage /></MemoryRouter>);
  expect(await screen.findByText(/ZS-20260723-001/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "选择环节打回" }));
  fireEvent.click(screen.getByLabelText("分选"));
  fireEvent.change(screen.getByLabelText("打回原因"), {
    target: { value: "需要重新分选" },
  });
  fireEvent.click(screen.getByRole("button", { name: "确认打回" }));

  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3));
  const [, init] = fetcher.mock.calls[1] as [string, RequestInit];
  expect(init.method).toBe("POST");
  expect(init.headers).toEqual(expect.objectContaining({
    "Idempotency-Key": expect.any(String),
  }));
  expect(JSON.parse(String(init.body))).toEqual(expect.objectContaining({
    target_stages: ["SORT"],
    expected_revision: 7,
  }));
});

it("opens an independent signature page for records awaiting plant audit", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
    overview: { total: 1, active: 1, completed: 0 },
    records: [{
      record_id: "REC-SIGN",
      display_no: "ZS-20260723-SIGN",
      factory_id: "FACTORY-A",
      form_type: "SORTING",
      base_info: { cage_no: "SIGN-01" },
      cage_no: "SIGN-01",
      current_stage: "PLANT_AUDIT",
      status: "ACTIVE",
      revision: 3,
      created_at: "2026-07-23T08:00:00Z",
      updated_at: "2026-07-23T09:00:00Z",
    }],
  })));

  render(<MemoryRouter><PlantProductionPage /></MemoryRouter>);

  const link = await screen.findByRole("link", { name: "查看并签字" });
  expect(link.getAttribute("href")).toBe("/plant/production/REC-SIGN");
});

function signatureDetail(canSign: boolean, windowStatus: string) {
  return {
    record_id: "REC-SIGN",
    display_no: "ZS-20260723-SIGN",
    factory_id: "FACTORY-A",
    form_type: "SORTING",
    source_type: "MANUAL",
    base_info: { cage_no: "SIGN-01", grade: "一级" },
    cage_no: "SIGN-01",
    current_stage: "PLANT_AUDIT",
    status: "ACTIVE",
    revision: 3,
    created_at: "2026-07-23T08:00:00Z",
    updated_at: "2026-07-23T09:00:00Z",
    submissions: [{
      submission_id: "SUB-1",
      stage: "SORT",
      version: 1,
      values: { quantity: 12 },
      actor_id: "WORKER-1",
      actor_name: "李工",
      role_code: "SORTER",
      submitted_at: "2026-07-23T08:10:00Z",
    }],
    upstream_record: null,
    inspection_window: {
      status: windowStatus,
      opened_at: "2026-07-23T09:00:00Z",
      deadline_at: "2026-07-23T11:00:00Z",
      inside_window: windowStatus === "OPEN",
      remaining_seconds: windowStatus === "OPEN" ? 3600 : 0,
      revision: 1,
    },
    signature_gate: {
      can_sign: canSign,
      reason: canSign ? "" : "INSPECTION_IN_PROGRESS",
    },
    inspections: [],
  };
}

it("keeps signature blocked while inspection is active", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(signatureDetail(false, "OPEN"))));

  render(
    <MemoryRouter initialEntries={["/plant/production/REC-SIGN"]}>
      <Routes>
        <Route path="/plant/production/:recordId" element={<PlantSignaturePage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("李工")).toBeTruthy();
  expect(screen.getByText("一级")).toBeTruthy();
  expect(screen.getByRole("button", { name: "停止检测并提前签字" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "通过并签字" })).toBeNull();
});

it("signs the current revision after a second confirmation", async () => {
  const fetcher = vi.fn()
    .mockResolvedValueOnce(response(signatureDetail(true, "COMPLETED")))
    .mockResolvedValueOnce(response({
      record_id: "REC-SIGN",
      status: "COMPLETED",
      current_stage: null,
      revision: 4,
    }))
    .mockResolvedValueOnce(response({
      ...signatureDetail(false, "COMPLETED"),
      status: "COMPLETED",
      current_stage: null,
      revision: 4,
      signature_gate: { can_sign: false, reason: "NOT_AT_PLANT_AUDIT" },
    }));
  vi.stubGlobal("fetch", fetcher);

  render(
    <MemoryRouter initialEntries={["/plant/production/REC-SIGN"]}>
      <Routes>
        <Route path="/plant/production/:recordId" element={<PlantSignaturePage />} />
      </Routes>
    </MemoryRouter>,
  );

  fireEvent.change(await screen.findByLabelText("签字备注"), {
    target: { value: "资料已核对" },
  });
  fireEvent.click(screen.getByRole("button", { name: "通过并签字" }));
  expect(screen.getByRole("dialog", { name: "签字前核对" })).toBeTruthy();
  expect(screen.getByText("签字人")).toBeTruthy();
  expect(screen.getByText("张厂长")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "确认签字" }));

  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3));
  const [url, init] = fetcher.mock.calls[1] as [string, RequestInit];
  expect(url).toBe("/api/v1/plant/records/REC-SIGN/audit");
  expect(init.headers).toEqual(expect.objectContaining({
    "Idempotency-Key": expect.any(String),
  }));
  expect(JSON.parse(String(init.body))).toEqual({
    expected_revision: 3,
    device_id: "plant-web",
    values: { result: "APPROVED", note: "资料已核对" },
  });
});
