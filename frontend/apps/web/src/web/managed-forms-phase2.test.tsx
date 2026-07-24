// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { AdminFormApprovalsPage } from "./AdminFormApprovalsPage";
import { FinanceFormsPage } from "./FinanceFormsPage";
import { PlantFormsPage } from "./PlantFormsPage";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

const VERSION = {
  definition_id: "form-def-1",
  form_key: "DAILY_OUTPUT",
  name: "日产量表",
  owner_role: "WORKER",
  version_id: "form-ver-1",
  version: 1,
  schema_json: { fields: [{ key: "quantity", label: "产量", type: "number", required: true }] },
  content_hash: "abc",
  status: "DRAFT",
  revision: 1,
  created_by: "FINANCE-1",
  created_at: "2026-07-23T00:00:00Z",
  review_comment: "",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  document.cookie = "web_csrf=; Max-Age=0; path=/";
});

it("lets finance create a structured form draft and submit it for approval", async () => {
  document.cookie = "web_csrf=csrf; path=/";
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(jsonResponse({ items: [] }))
    .mockResolvedValueOnce(jsonResponse(VERSION, 201))
    .mockResolvedValueOnce(jsonResponse({ ...VERSION, status: "PENDING_APPROVAL" }));
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();

  render(<MemoryRouter><FinanceFormsPage /></MemoryRouter>);
  await user.click(await screen.findByRole("button", { name: "新建电子表单" }));
  await user.type(screen.getByLabelText("表单名称"), "日产量表");
  await user.type(screen.getByLabelText("表单标识"), "DAILY_OUTPUT");
  await user.type(screen.getByLabelText("字段名称"), "产量");
  await user.type(screen.getByLabelText("字段标识"), "quantity");
  await user.click(screen.getByRole("button", { name: "保存草稿" }));

  expect(await screen.findByText("草稿")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "提交审批" }));
  await user.type(await screen.findByPlaceholderText("请输入批准原因..."), "提交审批");
  await user.click(screen.getByRole("button", { name: "确认批准" }));
  expect(await screen.findByText("待审批")).toBeTruthy();
  expect(fetchMock).toHaveBeenLastCalledWith(
    "/api/v1/finance/form-versions/form-ver-1/submit-approval",
    expect.objectContaining({
      method: "POST",
      headers: { "X-CSRF-Token": "csrf" },
    }),
  );
});

it("lets admin approve and activate a version for selected factories", async () => {
  document.cookie = "web_csrf=csrf; path=/";
  const pending = { ...VERSION, status: "PENDING_APPROVAL" };
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(jsonResponse({ items: [pending] }))
    .mockResolvedValueOnce(jsonResponse({ ...pending, status: "APPROVED" }))
    .mockResolvedValueOnce(jsonResponse({
      version_id: "form-ver-1",
      status: "ACTIVE",
      plant_ids: ["FACTORY-A"],
    }));
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();

  render(<MemoryRouter><AdminFormApprovalsPage /></MemoryRouter>);
  // Click "批准版本" opens ReasonConfirmDialog
  await user.click(await screen.findByRole("button", { name: "批准版本" }));

  // Fill in approval reason and confirm
  await user.type(
    await screen.findByPlaceholderText("请输入批准原因..."),
    "已审核通过",
  );
  await user.click(screen.getByRole("button", { name: "确认批准" }));

  // After approval completes, the dialog closes and the activation panel appears
  await user.type(await screen.findByLabelText("启用工厂"), "FACTORY-A");
  await user.click(screen.getByRole("button", { name: "按工厂启用" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/v1/admin/form-versions/form-ver-1/activate",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ plant_ids: ["FACTORY-A"] }),
      }),
    );
  });
});

it("shows plant forms as read-only active versions", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
    items: [{ ...VERSION, status: "APPROVED", activation_status: "ACTIVE", plant_id: "FACTORY-A" }],
  })));

  render(<MemoryRouter><PlantFormsPage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "日产量表" })).toBeTruthy();
  expect(screen.getByText(/版本 1/)).toBeTruthy();
  expect(screen.getByText("只读")).toBeTruthy();
  expect(screen.queryByRole("button", { name: /编辑/ })).toBeNull();
});
