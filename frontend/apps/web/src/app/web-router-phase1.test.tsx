// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { AppRoutes } from "./router";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("opens the unified Web login when no management session exists", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(jsonResponse({ code: "WEB_SESSION_REQUIRED" }, 401)),
  );

  render(
    <MemoryRouter initialEntries={["/"]}>
      <AppRoutes />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: "工业工资表系统" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "登录工作区" })).toBeTruthy();
});

it("routes an authenticated finance user from root to the finance overview", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(jsonResponse({
      employee_code: "FINANCE-1",
      employee_name: "财务员",
      workspace_role: "FINANCE",
      workspace_roles: ["FINANCE"],
      factory_id: "",
      factory_name: "",
      landing_path: "/finance/overview",
    }))
    .mockResolvedValueOnce(jsonResponse({
      workspace: "FINANCE",
      title: "财务概览",
      scope: "GLOBAL",
      factory_id: "",
      factory_name: "",
      cards: [{ key: "today", label: "今日新增提交", value: 3 }],
    }));
  vi.stubGlobal("fetch", fetchMock);

  render(
    <MemoryRouter initialEntries={["/"]}>
      <AppRoutes />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: "财务概览" })).toBeTruthy();
  expect(screen.getByRole("navigation", { name: "财务工作区导航" })).toBeTruthy();
});

it("keeps the old desktop routes available during the staged replacement", () => {
  render(
    <MemoryRouter initialEntries={["/templates"]}>
      <AppRoutes />
    </MemoryRouter>,
  );

  expect(screen.getByText("工业工资表系统")).toBeTruthy();
  expect(screen.getByRole("link", { name: "模板中心" })).toBeTruthy();
});
