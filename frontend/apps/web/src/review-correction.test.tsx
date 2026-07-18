// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function workbench(version: 0 | 1 | 2) {
  const corrected = version === 2;
  const initial = version === 0;
  return {
    form: {
      form_id: "FORM-EXPORTED",
      template_id: "PAYROLL_HOURLY",
      template_version: "1",
      coordinate_version: "1",
      review_status: corrected ? "CORRECTED" : initial ? "NEEDS_REVIEW" : "CONFIRMED",
      export_status: corrected ? "REEXPORT_REQUIRED" : initial ? "NOT_EXPORTED" : "EXPORTED",
      current_record_version: version,
      priority: 1,
      created_at: "2026-07-16T00:00:00Z",
    },
    fields: [{
      field_id: "FIELD-1",
      field_name: "hours",
      display_name: "工时",
      data_type: "integer",
      recognition_engine: "manual",
      rules: null,
      source_region: { x: 0, y: 0, width: 1, height: 1 },
      current_value: corrected ? "9" : 8,
      current_value_source: corrected ? "human" : "confirmed",
      current_record_version: version,
      candidates: [],
    }],
    evidence: [{
      file_id: "FILE-1",
      type: "ORIGINAL_IMAGE",
      related_field_id: null,
      sha256: "evidence-sha",
      immutable: true,
      created_at: "2026-07-16T00:00:00Z",
      download_url: "/api/v1/evidence/FILE-1",
    }],
    current_record: initial ? null : {
      record_id: "RECORD-1",
      version,
      previous_version: version === 1 ? null : 1,
      status: corrected ? "CORRECTED" : "CONFIRMED",
      values: { "FIELD-1": corrected ? "9" : 8 },
      change_reason: corrected ? "人工审核工作台更正" : "initial",
      confirmed_by: "reviewer",
      created_at: "2026-07-16T00:00:00Z",
    },
    draft: null,
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("review correction", () => {
  it("corrects an exported version in place without claiming the next form", async () => {
    const user = userEvent.setup();
    let workbenchReadCount = 0;
    const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      const method = init?.method ?? "GET";
      if (path.includes("/forms/queue/")) return jsonResponse([]);
      if (path === "/api/v1/forms/FORM-EXPORTED" && method === "GET") {
        workbenchReadCount += 1;
        return jsonResponse(workbench(workbenchReadCount === 1 ? 1 : 2));
      }
      if (path === "/api/v1/forms/FORM-EXPORTED/review-history") {
        return jsonResponse({ versions: [], audits: [] });
      }
      if (path === "/api/v1/forms/FORM-EXPORTED/review-lease" && method === "POST") {
        return jsonResponse({
          form_id: "FORM-EXPORTED",
          owner_id: "reviewer",
          lease_token: "lease-correction",
          expires_at: "2099-07-16T00:00:00Z",
        });
      }
      if (path === "/api/v1/forms/FORM-EXPORTED/confirm" && method === "POST") {
        return jsonResponse({ record_id: "RECORD-1", version: 2, status: "CORRECTED" });
      }
      if (path.endsWith("/confirm-and-claim-next")) {
        return jsonResponse({ code: "WRONG_ENDPOINT", detail: "must not claim next" }, 500);
      }
      return jsonResponse({ code: "UNEXPECTED", detail: `${method} ${path}` }, 404);
    });
    render(<App />);

    await user.type(screen.getByLabelText("表单编号"), "FORM-EXPORTED");
    await user.click(screen.getByRole("button", { name: "加载表单" }));
    expect(await screen.findByRole("button", { name: "保存本次修改" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "获取审核锁" }));
    const field = await screen.findByLabelText("工时 最终填写值");
    await user.clear(field);
    await user.type(field, "9");
    await user.click(screen.getByRole("button", { name: "保存本次修改" }));

    expect(await screen.findByText("记录版本 2 · 已更正 · 待重新导出")).toBeTruthy();
    expect((screen.getByLabelText("工时 最终填写值") as HTMLInputElement).value).toBe("9");
    const confirmCall = fetcher.mock.calls.find(([path, init]) => (
      String(path) === "/api/v1/forms/FORM-EXPORTED/confirm" && init?.method === "POST"
    ));
    expect(confirmCall).toBeDefined();
    expect(confirmCall?.[1]?.headers).toEqual({
      "If-Match": "1",
      "Content-Type": "application/json",
    });
    expect(JSON.parse(String(confirmCall?.[1]?.body))).toEqual({
      expected_version: 1,
      lease_token: "lease-correction",
      values: { "FIELD-1": "9" },
      reason: "人工审核工作台更正",
      evidence_ids: ["FILE-1"],
    });
    expect(fetcher.mock.calls.some(([path]) => String(path).endsWith("/confirm-and-claim-next"))).toBe(false);
    expect(workbenchReadCount).toBe(2);
    await waitFor(() => expect(screen.getByText(/审核锁有效至/)).toBeTruthy());
  });

  it("keeps version zero on confirm-and-claim-next", async () => {
    const user = userEvent.setup();
    const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      const method = init?.method ?? "GET";
      if (path.includes("/forms/queue/")) return jsonResponse([]);
      if (path === "/api/v1/forms/FORM-NEW" && method === "GET") {
        const loaded = workbench(0);
        loaded.form.form_id = "FORM-NEW";
        return jsonResponse(loaded);
      }
      if (path === "/api/v1/forms/FORM-NEW/review-history") {
        return jsonResponse({ versions: [], audits: [] });
      }
      if (path === "/api/v1/forms/FORM-NEW/review-lease" && method === "POST") {
        return jsonResponse({
          form_id: "FORM-NEW",
          owner_id: "reviewer",
          lease_token: "lease-new",
          expires_at: "2099-07-16T00:00:00Z",
        });
      }
      if (path === "/api/v1/forms/FORM-NEW/confirm-and-claim-next" && method === "POST") {
        return jsonResponse({
          record: { record_id: "RECORD-NEW", version: 1, status: "CONFIRMED" },
          next: null,
        });
      }
      if (path.endsWith("/confirm")) return jsonResponse({ code: "WRONG_ENDPOINT" }, 500);
      return jsonResponse({ code: "UNEXPECTED", detail: `${method} ${path}` }, 404);
    });
    render(<App />);

    await user.type(screen.getByLabelText("表单编号"), "FORM-NEW");
    await user.click(screen.getByRole("button", { name: "加载表单" }));
    expect(await screen.findByRole("button", { name: "确认并下一张" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "获取审核锁" }));
    await user.click(screen.getByRole("button", { name: "确认并下一张" }));

    await waitFor(() => expect(fetcher.mock.calls.some(([path]) => (
      String(path) === "/api/v1/forms/FORM-NEW/confirm-and-claim-next"
    ))).toBe(true));
    expect(fetcher.mock.calls.some(([path]) => String(path) === "/api/v1/forms/FORM-NEW/confirm")).toBe(false);
    const confirmNextCall = fetcher.mock.calls.find(([path]) => (
      String(path) === "/api/v1/forms/FORM-NEW/confirm-and-claim-next"
    ));
    expect(confirmNextCall?.[1]?.headers).toEqual({
      "If-Match": "0",
      "Content-Type": "application/json",
    });
  });

  it("does not allow review writes without an active lease", async () => {
    const user = userEvent.setup();
    const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      const method = init?.method ?? "GET";
      if (path.includes("/forms/queue/")) return jsonResponse([]);
      if (path === "/api/v1/forms/FORM-EXPORTED" && method === "GET") {
        return jsonResponse(workbench(1));
      }
      if (path === "/api/v1/forms/FORM-EXPORTED/review-history") {
        return jsonResponse({ versions: [], audits: [] });
      }
      return jsonResponse({ code: "UNEXPECTED", detail: `${method} ${path}` }, 404);
    });
    render(<App />);

    await user.type(screen.getByLabelText("表单编号"), "FORM-EXPORTED");
    await user.click(screen.getByRole("button", { name: "加载表单" }));
    const field = await screen.findByLabelText("工时 最终填写值");
    await user.clear(field);
    await user.type(field, "9");

    for (const name of ["退回", "作废", "保存草稿", "保存本次修改"]) {
      expect((screen.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
    }
    expect(fetcher.mock.calls.some(([path, init]) => (
      init?.method !== undefined && init.method !== "GET" && String(path).includes("/forms/FORM-EXPORTED/")
    ))).toBe(false);
  });

  it("asks before switching modules with unsaved review edits", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      const method = init?.method ?? "GET";
      if (path.includes("/forms/queue/")) return jsonResponse([]);
      if (path === "/api/v1/forms/FORM-EXPORTED" && method === "GET") {
        return jsonResponse(workbench(1));
      }
      if (path === "/api/v1/forms/FORM-EXPORTED/review-history") {
        return jsonResponse({ versions: [], audits: [] });
      }
      return jsonResponse({ code: "UNEXPECTED", detail: `${method} ${path}` }, 404);
    });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<App />);

    await user.type(screen.getByLabelText("表单编号"), "FORM-EXPORTED");
    await user.click(screen.getByRole("button", { name: "加载表单" }));
    const field = await screen.findByLabelText("工时 最终填写值");
    await user.clear(field);
    await user.type(field, "9");
    await user.click(screen.getByRole("link", { name: "模板中心" }));

    expect(confirm).toHaveBeenCalledWith("当前有尚未保存的审核修改，确定离开吗？");
    expect(screen.getByRole("link", { name: "模板中心" })).toBeTruthy();
    expect(screen.getByLabelText("工时 最终填写值")).toBeTruthy();
  });
});
