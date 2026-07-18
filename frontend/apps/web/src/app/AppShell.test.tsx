// @vitest-environment jsdom

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import {
  MemoryRouter,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { AppShell } from "./AppShell";
import { AppRoutes } from "./router";

function Page() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <>
      <span data-testid="location">{location.pathname}</span>
      <button type="button" onClick={() => navigate(-1)}>浏览器后退</button>
      <Outlet />
    </>
  );
}

afterEach(cleanup);

describe("AppShell", () => {
  it("shows the four primary destinations and local service context without fake identity controls", () => {
    render(
      <MemoryRouter initialEntries={["/templates"]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="*" element={<span>页面内容</span>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("工业工资表系统")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "工业工资表系统" })).toBeNull();
    const primaryNavigation = within(screen.getByRole("navigation", { name: "一级导航" }));
    expect(primaryNavigation.getAllByRole("link")).toHaveLength(4);
    for (const name of ["审核工作台", "模板中心", "基础数据", "导出数据"]) {
      expect(primaryNavigation.getByRole("link", { name })).toBeTruthy();
    }
    expect(screen.getByRole("link", { name: "模板中心" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByText("本地单机模式 · 服务正常")).toBeTruthy();
    expect(screen.queryByText(/当前身份/)).toBeNull();
    expect(screen.queryByRole("button", { name: "用户菜单" })).toBeNull();
  });

  it("uses browser history to return to the previous module", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/templates"]}>
        <Routes>
          <Route element={<Page />}>
            <Route element={<AppShell />}>
              <Route path="*" element={<span>页面内容</span>} />
            </Route>
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("link", { name: "导出数据" }));
    expect(screen.getByTestId("location").textContent).toBe("/exports");
    await user.click(screen.getByRole("button", { name: "浏览器后退" }));
    expect(screen.getByTestId("location").textContent).toBe("/templates");
  });

  it("renders an in-app 404 with a workbench return path", () => {
    render(
      <MemoryRouter initialEntries={["/missing-page"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "找不到这个页面" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "返回审核工作台" }).getAttribute("href"))
      .toBe("/workbench/review");
  });
});
