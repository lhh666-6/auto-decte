// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { RequireWebSession } from "./RequireWebSession";
import { WebLoginPage } from "./WebLoginPage";
import { WebSessionProvider } from "./WebSessionProvider";
import { WorkspaceOverviewPage } from "./WorkspaceOverviewPage";
import { WorkspaceShell } from "./WorkspaceShell";
import { logoutWebSession } from "./api";
import { AdminAuditPage } from "./AdminAuditPage";
import { AdminNotificationsPage } from "./AdminNotificationsPage";
import { AdminOrganizationPage } from "./AdminOrganizationPage";
import { AdminRolesPage } from "./AdminRolesPage";
import type { WebSession } from "./types";

const MANAGER_SESSION: WebSession = {
  employee_code: "MANAGER-A",
  employee_name: "一厂厂长",
  workspace_role: "PLANT_MANAGER",
  workspace_roles: ["PLANT_MANAGER"],
  factory_id: "FACTORY-A",
  factory_name: "竹丝一厂",
  landing_path: "/plant/overview",
};

const FINANCE_SESSION: WebSession = {
  employee_code: "FINANCE-1",
  employee_name: "财务员",
  workspace_role: "FINANCE",
  workspace_roles: ["FINANCE"],
  factory_id: "",
  factory_name: "",
  landing_path: "/finance/overview",
};

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function LocationProbe() {
  return <span data-testid="location">{useLocation().pathname}</span>;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  document.cookie = "web_csrf=; Max-Age=0; path=/";
});

describe("Web three-role workspaces", () => {
  it("logs in with the shared employee account and follows the server landing path", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ code: "WEB_SESSION_REQUIRED" }, 401))
      .mockResolvedValueOnce(jsonResponse(FINANCE_SESSION));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <WebSessionProvider>
          <Routes>
            <Route path="/login" element={<WebLoginPage />} />
            <Route path="*" element={<LocationProbe />} />
          </Routes>
        </WebSessionProvider>
      </MemoryRouter>,
    );

    await user.type(await screen.findByLabelText("员工号"), "FINANCE-1");
    await user.type(screen.getByLabelText("PIN"), "2468");
    await user.click(screen.getByRole("button", { name: "登录工作区" }));

    await waitFor(() => {
      expect(screen.getByTestId("location").textContent).toBe("/finance/overview");
    });
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/v1/web/auth/login",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });

  it("redirects a plant manager away from finance routes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(MANAGER_SESSION)));

    render(
      <MemoryRouter initialEntries={["/finance/overview"]}>
        <WebSessionProvider>
          <Routes>
            <Route
              path="/finance/overview"
              element={(
                <RequireWebSession workspace="FINANCE">
                  <span>不应显示的财务内容</span>
                </RequireWebSession>
              )}
            />
            <Route path="/plant/overview" element={<LocationProbe />} />
          </Routes>
        </WebSessionProvider>
      </MemoryRouter>,
    );

    expect((await screen.findByTestId("location")).textContent).toBe("/plant/overview");
    expect(screen.queryByText("不应显示的财务内容")).toBeNull();
  });

  it("shows the server reason when Web login is rejected", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ code: "WEB_SESSION_REQUIRED" }, 401))
      .mockResolvedValueOnce(jsonResponse({
        code: "WEB_ROLE_REQUIRED",
        detail: "当前账号没有 Web 管理角色。",
      }, 403));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <WebSessionProvider>
          <WebLoginPage />
        </WebSessionProvider>
      </MemoryRouter>,
    );

    await user.type(await screen.findByLabelText("员工号"), "WORKER-1");
    await user.type(screen.getByLabelText("PIN"), "2468");
    await user.click(screen.getByRole("button", { name: "登录工作区" }));

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "当前账号没有 Web 管理角色。",
    );
  });

  it("shows role-specific desktop navigation and current factory context", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(MANAGER_SESSION)));

    render(
      <MemoryRouter initialEntries={["/plant/overview"]}>
        <WebSessionProvider>
          <RequireWebSession workspace="PLANT_MANAGER">
            <WorkspaceShell workspace="PLANT_MANAGER">
              <span>概览内容</span>
            </WorkspaceShell>
          </RequireWebSession>
        </WebSessionProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("一厂厂长")).toBeTruthy();
    expect(screen.getByText("竹丝一厂")).toBeTruthy();
    const navigation = screen.getByRole("navigation", { name: "厂长工作区导航" });
    for (const label of ["本厂概览", "本厂生产", "质量与异常"]) {
      expect(screen.getByRole("link", { name: label })).toBeTruthy();
    }
    expect(navigation.querySelectorAll("a").length).toBeGreaterThanOrEqual(4);
  });

  it("loads overview cards from the matching server workspace", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(FINANCE_SESSION))
      .mockResolvedValueOnce(jsonResponse({
        workspace: "FINANCE",
        title: "财务概览",
        scope: "GLOBAL",
        factory_id: "",
        factory_name: "",
        cards: [
          { key: "today_submissions", label: "今日新增提交", value: 12 },
          { key: "exceptions", label: "异常记录", value: 2 },
        ],
      }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={["/finance/overview"]}>
        <WebSessionProvider>
          <RequireWebSession workspace="FINANCE">
            <WorkspaceOverviewPage workspace="FINANCE" />
          </RequireWebSession>
        </WebSessionProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "财务概览" })).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy();
    expect(screen.getByText("异常记录")).toBeTruthy();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/v1/finance/overview",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("submits the page-readable Web CSRF token when logging out", async () => {
    document.cookie = "web_csrf=csrf-token; path=/";
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    await logoutWebSession();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/web/auth/logout",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": "csrf-token" },
      }),
    );
  });
});

describe("Admin governance pages", () => {
  it("renders AdminOrganizationPage and loads employees", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ items: [{ factory_id: "F1", code: "F1", name: "工厂一" }] }))
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse({ items: [{ employee_code: "E1", employee_name: "张三", factory_id: "F1", role_code: "SORT_OPERATOR", role_name: "分拣工" }] }))
      .mockResolvedValueOnce(jsonResponse({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AdminOrganizationPage />);

    expect(await screen.findByText("组织架构")).toBeTruthy();
    expect(screen.getByText("张三")).toBeTruthy();
  });

  it("renders AdminRolesPage with web workspace roles", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ items: [
        { role_code: "SORT_OPERATOR", display_name: "分拣工" },
        { role_code: "INSPECTOR", display_name: "检验员" },
      ] }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AdminRolesPage />);

    expect(await screen.findByText("角色权限")).toBeTruthy();
    expect(screen.getByText("系统管理员")).toBeTruthy();
    expect(screen.getByText("分拣工")).toBeTruthy();
  });

  it("renders AdminAuditPage and shows empty state when API unavailable", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ code: "NOT_FOUND", detail: "审计日志服务暂不可用" }, 404));
    vi.stubGlobal("fetch", fetchMock);

    render(<AdminAuditPage />);

    expect(await screen.findByText("审计日志")).toBeTruthy();
    expect(screen.getByText("审计日志服务暂不可用")).toBeTruthy();
  });

  it("renders AdminNotificationsPage and loads notifications", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ items: [
        { notification_id: "N1", category: "form", title: "新表单待审批", body: "表单 X 需要审批", link: "", payload: {}, created_at: "2026-01-01" },
      ] }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AdminNotificationsPage />);

    expect(await screen.findByText("通知管理")).toBeTruthy();
    expect(screen.getByText("新表单待审批")).toBeTruthy();
  });

  it("renders AdminOrganizationPage error state when API fails", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockRejectedValueOnce(new Error("网络错误"))
      .mockRejectedValueOnce(new Error("网络错误"));
    vi.stubGlobal("fetch", fetchMock);

    render(<AdminOrganizationPage />);

    expect(await screen.findByText("网络错误")).toBeTruthy();
  });
});
