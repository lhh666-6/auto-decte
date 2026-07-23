// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { PlantProductionPage } from "./PlantProductionPage";

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

  render(<PlantProductionPage />);
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
