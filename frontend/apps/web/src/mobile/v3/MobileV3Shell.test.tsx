// @vitest-environment jsdom

import type { ReactNode } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Outlet, useLocation } from "react-router-dom";

import { AppRoutes } from "../../app/router";

let mockedRole = "SORT_OPERATOR";

vi.mock("../session/MobileSessionProvider", () => ({
  MobileSessionProvider: ({ children }: { children: ReactNode }) => children,
  useMobileSession: () => ({
    status: "authenticated",
    sessionMetadata: {
      bamboo_role: mockedRole,
    },
  }),
}));

vi.mock("../session/RequireMobileSession", () => ({
  RequireMobileSession: () => <Outlet />,
}));

vi.mock("../MobileHomePage", () => ({ MobileHomePage: () => null }));
vi.mock("../MobileRecordPage", () => ({ MobileRecordPage: () => null }));
vi.mock("../MobileBambooProcessPage", () => ({ MobileBambooProcessPage: () => null }));
vi.mock("../MobileSheetPiecePage", () => ({ MobileSheetPiecePage: () => null }));
vi.mock("../MobileTeamSheetPiecePage", () => ({ MobileTeamSheetPiecePage: () => null }));
vi.mock("../MobileDraftsPage", () => ({ MobileDraftsPage: () => null }));
vi.mock("../MobileOutboxPage", () => ({ MobileOutboxPage: () => null }));
vi.mock("../MobileSubmissionsPage", () => ({ MobileSubmissionsPage: () => null }));
vi.mock("../MobileProfilePage", () => ({ MobileProfilePage: () => null }));

afterEach(cleanup);
afterEach(() => {
  mockedRole = "SORT_OPERATOR";
});

function LocationProbe() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}

function renderRoute(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
      <LocationProbe />
    </MemoryRouter>,
  );
}

describe("MobileV3Shell", () => {
  it("renders the V3 shell with exactly four navigation labels", () => {
    renderRoute("/mobile/home");

    expect(document.querySelector('[data-mobile-shell="v3"]')).not.toBeNull();
    const nav = screen.getByRole("navigation", { name: "移动端导航" });
    const labels = Array.from(nav.querySelectorAll(".mobile-nav-label"), (label) => label.textContent);
    expect(labels).toEqual(["首页", "记录工作", "提交记录", "我的"]);
  });

  it("uses SVG icons without emoji text", () => {
    renderRoute("/mobile/home");

    const nav = screen.getByRole("navigation", { name: "移动端导航" });
    const icons = Array.from(nav.querySelectorAll(".mobile-nav-icon"));
    expect(icons).toHaveLength(4);
    for (const icon of icons) {
      expect(icon.querySelector("svg")).not.toBeNull();
      expect(icon.textContent).toBe("");
    }
  });

  it.each(["FINANCE_APPROVER", ""])("hides production tabs for %s", (role) => {
    mockedRole = role;
    renderRoute("/mobile/home");

    expect(screen.queryByRole("navigation", { name: "移动端导航" })).toBeNull();
  });
});

describe("mobile V3 compatibility redirects", () => {
  it.each([
    ["/mobile/record", "/mobile/work"],
    ["/mobile/record/bamboo-process", "/mobile/work"],
    ["/mobile/drafts", "/mobile/submissions"],
    ["/mobile/outbox", "/mobile/submissions"],
    ["/mobile/record/bamboo-process/record-42", "/mobile/records/record-42"],
  ])("redirects %s to %s", async (legacyPath, v3Path) => {
    renderRoute(legacyPath);

    expect((await screen.findByTestId("location")).textContent).toBe(v3Path);
  });
});

describe("old sheet-piece routes return NotFound", () => {
  it.each([
    "/mobile/record/sheet-piece",
    "/mobile/record/team-sheet-piece",
  ])("shows NotFound for %s (no redirect)", (path) => {
    renderRoute(path);

    expect(screen.getByText("找不到这个页面")).toBeDefined();
    expect(screen.getByTestId("location").textContent).toBe(path);
  });
});
