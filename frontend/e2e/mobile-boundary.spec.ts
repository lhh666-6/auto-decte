import { test, expect, loginMobile, getTestAccount, installMobileSession, installApiFallback } from "./fixtures";

test.describe("E2E-02: Mobile boundary", () => {
  test("SORT worker can access /mobile/work after login", async ({ page, pageErrors, consoleErrors }) => {
    const sort = getTestAccount("SORT");
    await loginMobile(page, sort);

    // Navigate to /mobile/work
    await page.goto("/mobile/work");
    await page.waitForURL("**/mobile/work", { timeout: 10_000 });

    await expect(page).toHaveURL(/\/mobile\/work/);

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("FINANCE user is rejected from /mobile/work and redirected to /mobile/home", async ({ page, pageErrors, consoleErrors }) => {
    const finance = getTestAccount("FINANCE");
    await loginMobile(page, finance);

    // Try to access /mobile/work — should be redirected to /mobile/home
    await page.goto("/mobile/work");
    await page.waitForURL("**/mobile/home", { timeout: 10_000 });

    await expect(page).toHaveURL(/\/mobile\/home/);
    await expect(page).not.toHaveURL(/\/mobile\/work/);

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("PLANT manager is rejected from /mobile/work and redirected to /mobile/home", async ({ page, pageErrors, consoleErrors }) => {
    const plant = getTestAccount("PLANT_A");
    await loginMobile(page, plant);

    // Try to access /mobile/work — should be redirected to /mobile/home
    await page.goto("/mobile/work");
    await page.waitForURL("**/mobile/home", { timeout: 10_000 });

    await expect(page).toHaveURL(/\/mobile\/home/);
    await expect(page).not.toHaveURL(/\/mobile\/work/);

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("DIPPING worker can access /mobile/work", async ({ page, pageErrors, consoleErrors }) => {
    const dipping = getTestAccount("DIPPING");
    await loginMobile(page, dipping);

    await page.goto("/mobile/work");
    await page.waitForURL("**/mobile/work", { timeout: 10_000 });

    await expect(page).toHaveURL(/\/mobile\/work/);

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("unauthenticated user hitting /mobile/work redirects to /mobile/login", async ({ page, pageErrors, consoleErrors }) => {
    // 1. Install broad API fallback FIRST
    await installApiFallback(page);

    // 2. Install specific session handler SECOND (takes precedence over fallback)
    // No session — return 401 from session endpoint
    await page.route("**/api/v1/mobile/auth/session", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ title: "Unauthorized", status: 401, detail: "未登录" }),
      });
    });

    await page.goto("/mobile/work");
    await page.waitForURL("**/mobile/login", { timeout: 10_000 });

    await expect(page).toHaveURL(/\/mobile\/login/);

    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
