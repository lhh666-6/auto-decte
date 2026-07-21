// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { MobileProfilePage } from "./MobileProfilePage";
import {
  MobileSessionProvider,
  type MobileSessionClient,
} from "./session/MobileSessionProvider";

vi.mock("./storage/session-cleanup", () => ({
  cleanupSessionStorage: vi.fn(),
  getPendingLogoutCount: vi.fn().mockResolvedValue(1),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("MobileProfilePage logout", () => {
  it("stays signed in when the user cancels with pending outbox entries", async () => {
    const client = {
      getSession: vi.fn().mockResolvedValue({
        employee_name: "张三",
        employee_code: "E001",
        team_name: "甲班",
        position: "操作工",
        roles: ["WORKER"],
        allowed_form_types: [],
        allowed_processes: [],
      }),
      login: vi.fn(),
      logout: vi.fn(),
    } as unknown as MobileSessionClient;
    vi.spyOn(window, "confirm").mockReturnValue(false);

    render(
      <MemoryRouter initialEntries={["/mobile/profile"]}>
        <MobileSessionProvider client={client}>
          <Routes>
            <Route path="mobile/profile" element={<MobileProfilePage />} />
            <Route path="mobile/login" element={<div>登录页</div>} />
          </Routes>
        </MobileSessionProvider>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "退出登录" }));

    await waitFor(() => expect(window.confirm).toHaveBeenCalledOnce());
    expect(client.logout).not.toHaveBeenCalled();
    expect(screen.queryByText("登录页")).toBeNull();
    expect(screen.getByText("张三")).toBeTruthy();
  });
});
