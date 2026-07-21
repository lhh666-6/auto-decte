// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  login: vi.fn(),
  getSession: vi.fn(),
  getAvailableForms: vi.fn(),
}));

vi.mock("@form-detection/api-client", async (importOriginal) => ({
  ...await importOriginal<typeof import("@form-detection/api-client")>(),
  mobileApiClient: {
    login: mocks.login,
    logout: vi.fn(),
    getSession: mocks.getSession,
    getAvailableForms: mocks.getAvailableForms,
  },
}));

vi.mock("./sync/SubmissionCoordinator", () => ({
  flushPendingOutbox: vi.fn().mockResolvedValue({ succeeded: 0 }),
  pauseOutboxSync: vi.fn(),
  resumeOutboxSync: vi.fn(),
}));

import { MobileHomePage } from "./MobileHomePage";
import { MobileLoginPage } from "./MobileLoginPage";
import { MobileSessionProvider } from "./session/MobileSessionProvider";
import { RequireMobileSession } from "./session/RequireMobileSession";

afterEach(cleanup);

it("logs in with a Cookie session and loads an authorized published definition", async () => {
  const session = {
    employee_name: "测试员工",
    employee_code: "E10001",
    team_name: "测试班组",
    position: "操作工",
    roles: ["WORKER"],
    allowed_form_types: ["SHEET_PIECE_MEASUREMENT"],
    allowed_processes: ["CUTTING"],
  };
  mocks.getSession
    .mockRejectedValueOnce(new (await import("@form-detection/api-client")).MobileApiError({
      title: "Unauthorized",
      status: 401,
      code: "SESSION_REQUIRED",
      detail: "请先登录",
      request_id: "request-1",
    }))
    .mockResolvedValue(session);
  mocks.login.mockResolvedValue({ ...session, expires_at: null });
  mocks.getAvailableForms.mockResolvedValue({
    forms: [{
      form_type: "SHEET_PIECE_MEASUREMENT",
      title: "配片工作记录",
      modes: ["SELF"],
      definition_version_id: "definition-1",
      allowed_processes: ["CUTTING"],
    }],
  });

  render(
    <MemoryRouter initialEntries={["/mobile/home"]}>
      <MobileSessionProvider>
        <Routes>
          <Route path="mobile/login" element={<MobileLoginPage />} />
          <Route element={<RequireMobileSession />}>
            <Route path="mobile/home" element={<MobileHomePage />} />
          </Route>
        </Routes>
      </MobileSessionProvider>
    </MemoryRouter>,
  );

  await userEvent.type(await screen.findByPlaceholderText("请输入工号"), "E10001");
  await userEvent.type(screen.getByPlaceholderText("请输入密码或 PIN"), "2468");
  await userEvent.click(screen.getByRole("button", { name: "登录" }));

  expect(await screen.findByText("配片工作记录")).toBeTruthy();
  expect(mocks.login).toHaveBeenCalledWith("E10001", "2468", expect.any(String));
  expect(mocks.getAvailableForms).toHaveBeenCalledTimes(1);
});
