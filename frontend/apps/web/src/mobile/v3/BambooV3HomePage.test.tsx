// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { MobileApiError, type MobileApiClient, type MobileSession } from "@form-detection/api-client";

const mocks = vi.hoisted(() => ({
  getBambooDashboard: vi.fn(),
}));

vi.mock("@form-detection/api-client", async (importOriginal) => ({
  ...await importOriginal<typeof import("@form-detection/api-client")>(),
  mobileApiClient: { getBambooDashboard: mocks.getBambooDashboard },
}));

import { MobileLoginPage } from "../MobileLoginPage";
import { MobileSessionProvider } from "../session/MobileSessionProvider";
import { BambooV3HomePage } from "./BambooV3HomePage";

const operatorSession: MobileSession = {
  employee_name: "王分选",
  employee_code: "ZS001",
  team_name: "竹丝生产组",
  position: "分选工",
  roles: ["WORKER"],
  allowed_form_types: [],
  allowed_processes: ["BAMBOO_PROCESS"],
  factory_id: "FACTORY-A",
  factory_name: "竹丝示范一厂",
  bamboo_role: "SORT_OPERATOR",
};

function authenticatedClient(session: MobileSession): MobileApiClient {
  return {
    getSession: vi.fn().mockResolvedValue(session),
    login: vi.fn(),
    logout: vi.fn(),
  } as unknown as MobileApiClient;
}

function renderHome(session: MobileSession = operatorSession) {
  return render(
    <MemoryRouter>
      <MobileSessionProvider client={authenticatedClient(session)}>
        <BambooV3HomePage />
      </MobileSessionProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getBambooDashboard.mockResolvedValue({ available: 3, waiting: 2, completed: 8 });
});

afterEach(cleanup);

describe("Bamboo V3 home", () => {
  it("shows the V3 identity, network state, dashboard and role entry", async () => {
    renderHome();

    expect(await screen.findByRole("heading", { name: "竹丝工序记录" })).toBeTruthy();
    expect(screen.getByText("完成工作后主动记录")).toBeTruthy();
    expect(screen.getByText("王分选")).toBeTruthy();
    expect(screen.getByText("竹丝示范一厂")).toBeTruthy();
    expect(screen.getByText("分选工")).toBeTruthy();
    expect(screen.getByText("联网")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("可处理").nextElementSibling?.textContent).toBe("3"));
    expect(screen.getByText("等待中").nextElementSibling?.textContent).toBe("2");
    expect(screen.getByText("已完成").nextElementSibling?.textContent).toBe("8");
    expect(screen.getByRole("link", { name: /开始记录工作/ }).getAttribute("href")).toBe("/mobile/work");
    expect(screen.queryByText("可填写的记录类型")).toBeNull();
    expect(document.body.textContent).not.toContain("???");
    await waitFor(() => expect(mocks.getBambooDashboard).toHaveBeenCalledTimes(1));
  });

  it("asks an unassigned employee to wait for a role and does not load work", async () => {
    renderHome({ ...operatorSession, bamboo_role: "", position: "待分配" });

    expect(await screen.findByText("等待管理员或厂长分配职务")).toBeTruthy();
    expect(screen.queryByRole("link", { name: /开始记录工作/ })).toBeNull();
    expect(mocks.getBambooDashboard).not.toHaveBeenCalled();
  });

  it("keeps finance approval on desktop and exposes no mobile approval action", async () => {
    renderHome({
      ...operatorSession,
      employee_name: "孙财务",
      employee_code: "CW001",
      position: "财务审批",
      bamboo_role: "FINANCE_APPROVER",
    });

    expect(await screen.findByText("财务审批请前往网页端")).toBeTruthy();
    expect(screen.getByRole("link", { name: "进入网页端" }).getAttribute("href")).toBe("/");
    expect(screen.queryByRole("link", { name: /开始记录工作/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /审批/ })).toBeNull();
    expect(mocks.getBambooDashboard).not.toHaveBeenCalled();
  });
});

describe("Bamboo V3 login", () => {
  it("uses the V3 product wording instead of the legacy payroll shell", async () => {
    const anonymous = new MobileApiError({
      title: "未登录",
      status: 401,
      code: "SESSION_REQUIRED",
      detail: "请先登录",
      request_id: "request-login",
    });
    const client = {
      getSession: vi.fn().mockRejectedValue(anonymous),
      login: vi.fn(),
      logout: vi.fn(),
    } as unknown as MobileApiClient;

    render(
      <MemoryRouter>
        <MobileSessionProvider client={client}>
          <MobileLoginPage />
        </MobileSessionProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "竹丝工序记录" })).toBeTruthy();
    expect(screen.getByText("工序流转与签字记录")).toBeTruthy();
    expect(screen.getByLabelText("工号")).toBeTruthy();
    expect(screen.getByLabelText("密码 / PIN")).toBeTruthy();
    expect(screen.queryByText("工业工资表系统")).toBeNull();
  });
});
