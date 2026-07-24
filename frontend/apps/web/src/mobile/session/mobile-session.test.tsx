// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { MobileApiError, type MobileApiClient, type MobileSession } from "@form-detection/api-client";

import { MobileSessionProvider } from "./MobileSessionProvider";
import { RequireMobileSession } from "./RequireMobileSession";

afterEach(cleanup);

function LoginProbe() {
  const location = useLocation();
  return <div>login:{String((location.state as { returnTo?: string } | null)?.returnTo ?? "")}</div>;
}

function anonymousClient(): MobileApiClient {
  return {
    getSession: vi.fn().mockRejectedValue(new MobileApiError({
      title: "Unauthorized",
      status: 401,
      code: "SESSION_EXPIRED",
      detail: "会话已失效",
      request_id: "request-1",
    })),
  } as unknown as MobileApiClient;
}

function authenticatedClient(overrides: Partial<MobileSession> = {}): MobileApiClient {
  const session: MobileSession = {
    employee_name: "张三",
    employee_code: "E001",
    team_name: "甲班",
    position: "操作工",
    roles: ["WORKER"],
  allowed_form_types: [],
  allowed_processes: [],
  factory_id: "FACTORY-A",
  factory_name: "竹丝一厂",
    bamboo_role: "SORT_OPERATOR",
    ...overrides,
  };
  return {
    getSession: vi.fn().mockResolvedValue(session),
  } as unknown as MobileApiClient;
}

describe("mobile session guard", () => {
  it("does not render protected content before session verification", () => {
    const client = { getSession: vi.fn(() => new Promise(() => {})) } as unknown as MobileApiClient;
    render(
      <MemoryRouter initialEntries={["/mobile/home"]}>
        <MobileSessionProvider client={client}>
          <Routes>
            <Route element={<RequireMobileSession />}>
              <Route path="mobile/home" element={<div>protected</div>} />
            </Route>
          </Routes>
        </MobileSessionProvider>
      </MemoryRouter>,
    );

    expect(screen.queryByText("protected")).toBeNull();
  });

  it("redirects an anonymous user to login with a safe return path", async () => {
    render(
      <MemoryRouter initialEntries={["/mobile/home?tab=drafts"]}>
        <MobileSessionProvider client={anonymousClient()}>
          <Routes>
            <Route path="mobile/login" element={<LoginProbe />} />
            <Route element={<RequireMobileSession />}>
              <Route path="mobile/home" element={<div>protected</div>} />
            </Route>
          </Routes>
        </MobileSessionProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("login:/mobile/home?tab=drafts")).toBeTruthy());
  });

  it("renders protected content after a valid session is loaded", async () => {
    render(
      <MemoryRouter initialEntries={["/mobile/home"]}>
        <MobileSessionProvider client={authenticatedClient()}>
          <Routes>
            <Route element={<RequireMobileSession />}>
              <Route path="mobile/home" element={<div>protected</div>} />
            </Route>
          </Routes>
        </MobileSessionProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("protected")).toBeTruthy());
  });

  it.each([
    [{ bamboo_role: "FINANCE_APPROVER", position: "财务审批" }, "/mobile/home"],
    [{ bamboo_role: "", position: "待分配" }, "/mobile/home"],
    [{ bamboo_role: "PLANT_MANAGER", position: "厂长" }, "/mobile/home"],
  ] as const)("redirects non-mobile production roles away from protected deep links", async (overrides, expectedPath) => {
    function LocationProbe() {
      return <output data-testid="location">{useLocation().pathname}</output>;
    }
    render(
      <MemoryRouter initialEntries={["/mobile/work"]}>
        <MobileSessionProvider client={authenticatedClient(overrides)}>
          <Routes>
            <Route element={<RequireMobileSession />}>
              <Route path="mobile/home" element={<div>home</div>} />
              <Route path="mobile/work" element={<div>work</div>} />
            </Route>
          </Routes>
          <LocationProbe />
        </MobileSessionProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId("location").textContent).toBe(expectedPath));
    expect(screen.queryByText("work")).toBeNull();
  });

  it("redirects PLANT_MANAGER away from records deep links", async () => {
    function LocationProbe() {
      return <output data-testid="location">{useLocation().pathname}</output>;
    }
    render(
      <MemoryRouter initialEntries={["/mobile/records/fake-id"]}>
        <MobileSessionProvider client={authenticatedClient({ bamboo_role: "PLANT_MANAGER", position: "厂长" })}>
          <Routes>
            <Route element={<RequireMobileSession />}>
              <Route path="mobile/home" element={<div>home</div>} />
              <Route path="mobile/records/:id" element={<div>records</div>} />
            </Route>
          </Routes>
          <LocationProbe />
        </MobileSessionProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId("location").textContent).toBe("/mobile/home"));
    expect(screen.queryByText("records")).toBeNull();
  });
});
