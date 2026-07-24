import { test, expect, loginAs, getTestAccount, installApiFallback } from "./fixtures";

test.describe("E2E-01: Login routing", () => {
  test("ADMIN logs in and lands at /admin/overview", async ({ page, pageErrors, consoleErrors }) => {
    const admin = getTestAccount("ADMIN");
    await loginAs(page, admin);

    // Verify URL matches landing path
    await expect(page).toHaveURL(/\/admin\/overview/);

    // Verify workspace shell rendered with navigation
    await expect(page.locator("nav[aria-label]")).toBeVisible();
    await expect(page.locator("nav[aria-label] a[href=\"/admin/audit\"]")).toBeVisible();

    // No uncaught errors
    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("FINANCE logs in and lands at /finance/overview", async ({ page, pageErrors, consoleErrors }) => {
    const finance = getTestAccount("FINANCE");
    await loginAs(page, finance);

    await expect(page).toHaveURL(/\/finance\/overview/);

    await expect(page.locator("nav[aria-label]")).toBeVisible();
    await expect(page.locator("nav[aria-label] a[href=\"/finance/today\"]")).toBeVisible();

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("PLANT manager logs in and lands at /plant/overview", async ({ page, pageErrors, consoleErrors }) => {
    const plant = getTestAccount("PLANT_A");
    await loginAs(page, plant);

    await expect(page).toHaveURL(/\/plant\/overview/);

    await expect(page.locator("nav[aria-label]")).toBeVisible();
    await expect(page.locator("nav[aria-label] a[href=\"/plant/production\"]")).toBeVisible();

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("unauthenticated access to /admin redirects to /login", async ({ page, pageErrors, consoleErrors }) => {
    // 1. Install broad API fallback FIRST
    await installApiFallback(page);

    // 2. Install specific session handler SECOND (takes precedence over fallback)
    // When no session cookie exists, the session API returns 401
    await page.route("**/api/v1/web/auth/session", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ title: "Unauthorized", status: 401, detail: "未登录" }),
      });
    });

    await page.goto("/admin/overview");
    await page.waitForURL("**/login", { timeout: 10_000 });

    await expect(page).toHaveURL(/\/login/);

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
