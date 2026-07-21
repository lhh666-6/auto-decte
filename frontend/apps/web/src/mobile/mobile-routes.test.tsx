// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { MobileLayout } from "./MobileLayout";
import { MobileLoginPage } from "./MobileLoginPage";
import { MobileHomePage } from "./MobileHomePage";
import { MobileRecordPage } from "./MobileRecordPage";
import { MobileDraftsPage } from "./MobileDraftsPage";
import { MobileOutboxPage } from "./MobileOutboxPage";
import { MobileSubmissionsPage } from "./MobileSubmissionsPage";
import { MobileProfilePage } from "./MobileProfilePage";

afterEach(cleanup);

function renderMobileRoute(path: string, initialEntries: string[] = [path]) {
  render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route element={<MobileLayout />}>
          <Route path="mobile/login" element={<MobileLoginPage />} />
          <Route path="mobile/home" element={<MobileHomePage />} />
          <Route path="mobile/record" element={<MobileRecordPage />} />
          <Route path="mobile/drafts" element={<MobileDraftsPage />} />
          <Route path="mobile/outbox" element={<MobileOutboxPage />} />
          <Route path="mobile/submissions" element={<MobileSubmissionsPage />} />
          <Route path="mobile/profile" element={<MobileProfilePage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

// ── Navigation ─────────────────────────────────────────────────

describe("MobileLayout", () => {
  it("renders all five bottom tab navigation items", () => {
    renderMobileRoute("/mobile/home");

    const nav = screen.getByRole("navigation", { name: "移动端导航" });
    expect(nav).toBeTruthy();

    // NavLink text includes emoji + label (e.g., "🏠首页")
    const links = nav.querySelectorAll("a");
    const labelSpans = Array.from(links).map(
      (a) => a.querySelector(".mobile-nav-label")?.textContent?.trim(),
    );
    expect(labelSpans).toEqual(["首页", "记录工作", "草稿", "提交记录", "我的"]);
  });

  it("highlights the active tab by aria-current", () => {
    renderMobileRoute("/mobile/drafts");

    const activeLink = document.querySelector(".mobile-nav-item.active");
    expect(activeLink).toBeTruthy();
    const labelEl = activeLink?.querySelector(".mobile-nav-label");
    expect(labelEl?.textContent?.trim()).toBe("草稿");
  });

  it("hides bottom nav on login page", () => {
    renderMobileRoute("/mobile/login");

    const nav = screen.queryByRole("navigation", { name: "移动端导航" });
    expect(nav).toBeNull();
  });
});

// ── Login ──────────────────────────────────────────────────────

describe("MobileLoginPage", () => {
  it("renders login form with employee code and PIN inputs", () => {
    renderMobileRoute("/mobile/login");

    expect(screen.getByText("工业工资表系统")).toBeTruthy();
    expect(screen.getByPlaceholderText("请输入工号")).toBeTruthy();
    expect(screen.getByPlaceholderText("请输入密码或 PIN")).toBeTruthy();
    expect(screen.getByRole("button", { name: "登录" })).toBeTruthy();
  });

  it("shows pilot version footer", () => {
    renderMobileRoute("/mobile/login");
    expect(screen.getByText(/试点版本/)).toBeTruthy();
  });
});

// ── Home ───────────────────────────────────────────────────────

describe("MobileHomePage", () => {
  it("renders loading state initially", () => {
    renderMobileRoute("/mobile/home");
    // The component shows 加载中… while fetching session
    expect(screen.getByText("加载中…")).toBeTruthy();
  });

  it("stays in loading state when API is unavailable (no mock)", () => {
    // In the test environment there is no real API, so the page
    // remains in loading state indefinitely. This test documents
    // that the component handles this gracefully (doesn't crash).
    renderMobileRoute("/mobile/home");
    expect(screen.getByText("加载中…")).toBeTruthy();
    // When API is available, "我的草稿"等 should appear.
  });
});

// ── Record type selection ──────────────────────────────────────

describe("MobileRecordPage", () => {
  it("renders loading state initially", () => {
    renderMobileRoute("/mobile/record");
    expect(screen.getByText("加载中…")).toBeTruthy();
  });

  it("stays in loading state when API is unavailable", () => {
    renderMobileRoute("/mobile/record");
    expect(screen.getByText("加载中…")).toBeTruthy();
    // When API responses arrive, "← 返回" and form type cards appear.
  });
});

// ── Drafts ─────────────────────────────────────────────────────

describe("MobileDraftsPage", () => {
  it("renders loading state initially", () => {
    renderMobileRoute("/mobile/drafts");
    expect(screen.getByText("加载中…")).toBeTruthy();
  });
});

// ── Outbox ─────────────────────────────────────────────────────

describe("MobileOutboxPage", () => {
  it("renders loading state initially", () => {
    renderMobileRoute("/mobile/outbox");
    expect(screen.getByText("加载中…")).toBeTruthy();
  });
});

// ── Submissions ────────────────────────────────────────────────

describe("MobileSubmissionsPage", () => {
  it("renders loading state initially", () => {
    renderMobileRoute("/mobile/submissions");
    expect(screen.getByText("加载中…")).toBeTruthy();
  });
});

// ── Profile ───────────────────────────────────────────────────

describe("MobileProfilePage", () => {
  it("renders loading state initially", () => {
    renderMobileRoute("/mobile/profile");
    expect(screen.getByText("加载中…")).toBeTruthy();
  });
});
