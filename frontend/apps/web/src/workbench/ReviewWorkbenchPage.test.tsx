// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReviewWorkbenchPage } from "./ReviewWorkbenchPage";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function workbench() {
  return {
    form: {
      form_id: "FORM-WORKBENCH",
      template_id: "PAYROLL_HOURLY",
      template_version: "1",
      coordinate_version: "1",
      review_status: "NEEDS_REVIEW",
      export_status: "NOT_EXPORTED",
      current_record_version: 0,
      priority: 1,
      created_at: "2026-07-17T00:00:00Z",
    },
    fields: [
      {
        field_id: "FIELD-NORMAL",
        field_name: "normal",
        display_name: "正常字段",
        data_type: "text",
        recognition_engine: "ocr",
        rules: null,
        source_region: { x: 10, y: 10, width: 20, height: 20 },
        current_value: "最终值",
        current_value_source: "recognized",
        current_record_version: 0,
        candidates: [{
          attempt_id: "ATTEMPT-NORMAL",
          candidate_value: "系统值",
          confidence: 0.95,
          engine: "test",
          model_version: "1",
          crop_file_id: "CROP-NORMAL",
        }],
      },
      {
        field_id: "FIELD-ISSUE",
        field_name: "issue",
        display_name: "问题字段",
        data_type: "text",
        recognition_engine: "ocr",
        rules: null,
        source_region: { x: 40, y: 40, width: 20, height: 20 },
        current_value: "低可靠值",
        current_value_source: "recognized",
        current_record_version: 0,
        candidates: [{
          attempt_id: "ATTEMPT-ISSUE",
          candidate_value: "低可靠值",
          confidence: 0.4,
          engine: "test",
          model_version: "1",
          crop_file_id: "CROP-ISSUE",
        }],
      },
    ],
    evidence: [{
      file_id: "CORRECTED",
      type: "CORRECTED_IMAGE",
      related_field_id: null,
      sha256: "corrected-sha",
      immutable: true,
      created_at: "2026-07-17T00:00:00Z",
      download_url: "/corrected.png",
    }],
    current_record: null,
    draft: null,
  };
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("ReviewWorkbenchPage", () => {
  it("builds the 46/54 workbench and links image boxes with final values", async () => {
    const user = userEvent.setup();
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      const method = init?.method ?? "GET";
      if (path.includes("/forms/queue/")) return jsonResponse([]);
      if (path === "/api/v1/forms/FORM-WORKBENCH" && method === "GET") {
        return jsonResponse(workbench());
      }
      if (path === "/api/v1/forms/FORM-WORKBENCH/review-history") {
        return jsonResponse({ versions: [], audits: [] });
      }
      if (path === "/api/v1/forms/FORM-WORKBENCH/review-lease" && method === "POST") {
        return jsonResponse({
          form_id: "FORM-WORKBENCH",
          owner_id: "reviewer",
          lease_token: "LEASE-1",
          expires_at: "2099-07-17T08:30:00Z",
        });
      }
      return jsonResponse({ code: "UNEXPECTED", detail: `${method} ${path}` }, 404);
    });
    render(<ReviewWorkbenchPage />);

    await user.type(screen.getByLabelText("表单编号"), "FORM-WORKBENCH");
    await user.click(screen.getByRole("button", { name: "加载表单" }));

    const grid = await screen.findByTestId("review-workbench-grid");
    expect(grid.getAttribute("style")).toContain("grid-template-columns: 46% 54%");
    expect(screen.getByRole("row", { name: /问题字段/ }).className).toContain("selected");
    expect(screen.getByRole("button", { name: "定位字段 FIELD-ISSUE" }).className).toContain("selected");

    const image = screen.getByRole("img", { name: "校正后的表单" });
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 100 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 100 });
    fireEvent.load(image);
    await user.click(screen.getByRole("button", { name: "定位字段 FIELD-NORMAL" }));
    const finalInput = screen.getByLabelText("正常字段 最终填写值");
    await waitFor(() => expect(document.activeElement).toBe(finalInput));
    expect(scrollIntoView).toHaveBeenCalled();

    await user.click(screen.getByRole("row", { name: /问题字段/ }));
    expect(screen.getByRole("button", { name: "定位字段 FIELD-ISSUE" }).className).toContain("selected");
    fireEvent.mouseEnter(screen.getByRole("row", { name: /正常字段/ }));
    expect(screen.getByRole("button", { name: "定位字段 FIELD-ISSUE" }).className).toContain("selected");
    fireEvent.mouseLeave(screen.getByRole("row", { name: /正常字段/ }));

    const normalRow = screen.getByRole("row", { name: /正常字段/ });
    expect(normalRow.textContent).toContain("系统值");
    expect(normalRow.textContent).toContain("95%");
    expect((screen.getByLabelText("正常字段 最终填写值") as HTMLInputElement).value).toBe("最终值");
    expect(normalRow.textContent).toContain("已就绪");
    expect(screen.getByText("剩余问题 1")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "获取审核锁" }));
    expect(await screen.findByText(/租约到期/)).toBeTruthy();
  });

  it("persists a dragged desktop split within the 35 to 65 percent bounds", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const path = String(input);
      if (path.includes("/forms/queue/")) return jsonResponse([]);
      if (path === "/api/v1/forms/FORM-WORKBENCH") return jsonResponse(workbench());
      if (path === "/api/v1/forms/FORM-WORKBENCH/review-history") {
        return jsonResponse({ versions: [], audits: [] });
      }
      return jsonResponse({ code: "UNEXPECTED", detail: path }, 404);
    });
    render(<ReviewWorkbenchPage />);
    await user.type(screen.getByLabelText("表单编号"), "FORM-WORKBENCH");
    await user.click(screen.getByRole("button", { name: "加载表单" }));
    const grid = await screen.findByTestId("review-workbench-grid");
    vi.spyOn(grid, "getBoundingClientRect").mockReturnValue({
      x: 0, y: 0, left: 0, top: 0, right: 1000, bottom: 500,
      width: 1000, height: 500, toJSON: () => ({}),
    });
    const divider = screen.getByRole("separator", { name: "调整图片与电子表格宽度" });
    fireEvent.pointerDown(divider, { clientX: 460 });
    fireEvent.pointerMove(divider, { clientX: 720 });
    fireEvent.pointerUp(divider);

    await waitFor(() => expect(localStorage.getItem("review-workbench-split-percent")).toBe("65"));
    expect(grid.getAttribute("style")).toContain("grid-template-columns: 65% 35%");
    await user.click(screen.getByRole("tab", { name: "图片" }));
    await user.click(screen.getByRole("tab", { name: "电子表格" }));
  });

  it("shows three internal queues and one empty state for an empty queue", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([]));
    render(<ReviewWorkbenchPage routeQueue="review" />);

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    const tabs = screen.getByRole("tablist", { name: "审核任务" });
    expect(tabs.querySelectorAll('[role="tab"]')).toHaveLength(3);
    for (const name of ["待确认表单类型", "待核对", "待重新拍照"]) {
      expect(screen.getByRole("tab", { name: new RegExp(name) })).toBeTruthy();
    }
    expect(screen.queryByText("可导出")).toBeNull();
    expect(screen.getAllByText("没有待审核的表单")).toHaveLength(1);
    expect(screen.queryByText("当前没有表单")).toBeNull();
    expect(screen.queryByRole("navigation", { name: "工作队列" })).toBeNull();
  });
});
