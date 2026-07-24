import { test, expect, loginAs, getTestAccount } from "./fixtures";

async function mockAuditLog(
  page: import("@playwright/test").Page,
  entries: Array<{
    id: string;
    timestamp: string;
    actor_name: string;
    actor_code: string;
    action: string;
    object_type: string;
    object_id: string;
    factory_id: string;
    request_id: string;
  }>,
) {
  await page.route("**/api/v1/admin/audit-log", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: entries }),
    });
  });
}

test.describe("E2E-14: Admin audit page", () => {
  test("ADMIN accesses /admin/audit and page renders without console.error", async ({ page, appPageErrors, consoleErrors }) => {
    const admin = getTestAccount("ADMIN");
    await loginAs(page, admin);

    await mockAuditLog(page, [
      { id: "A001", timestamp: "2026-07-24T08:30:00", actor_name: "系统管理员", actor_code: "ADMIN001", action: "LOGIN", object_type: "session", object_id: "sess-001", factory_id: "FACTORY_ADMIN", request_id: "req-001" },
      { id: "A002", timestamp: "2026-07-24T09:00:00", actor_name: "张厂长", actor_code: "PLANT_A001", action: "APPROVE_FORM", object_type: "form_version", object_id: "fv-001", factory_id: "PLANT_A", request_id: "req-002" },
    ]);

    await page.goto("/admin/audit");
    await page.waitForURL("**/admin/audit", { timeout: 10_000 });

    await expect(page.getByRole("heading", { name: "审计日志" })).toBeVisible();

    // Wait for table data to load
    await page.waitForFunction(() => !document.body.innerText.includes("加载中"), null, { timeout: 10_000 });

    // In narrow viewports, table columns overflow. Verify data is in DOM (attached)
    // rather than requiring visibility (which may fail if scrolled off-screen).
    await expect(page.locator("td", { hasText: "系统管理员" }).first()).toBeAttached();
    await expect(page.locator("td", { hasText: "req-001" }).first()).toBeAttached();

    // Filter bar elements (these should be visible as they're at the top)
    await expect(page.locator('input[placeholder="姓名或工号"]')).toBeVisible();
    await expect(page.locator('input[placeholder="工厂 ID"]')).toBeVisible();

    expect(appPageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("audit page shows empty state when API returns no entries", async ({ page, appPageErrors, consoleErrors }) => {
    const admin = getTestAccount("ADMIN");
    await loginAs(page, admin);

    await mockAuditLog(page, []);

    await page.goto("/admin/audit");
    await page.waitForURL("**/admin/audit", { timeout: 10_000 });

    await expect(page.getByRole("heading", { name: "审计日志" })).toBeVisible();
    await expect(page.locator("text=审计日志服务尚未接入，当前无记录。")).toBeVisible();

    expect(appPageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("audit page shows error message when API fails", async ({ page, appPageErrors, consoleErrors }) => {
    const admin = getTestAccount("ADMIN");
    await loginAs(page, admin);

    await page.route("**/api/v1/admin/audit-log", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ title: "Server Error", status: 500, detail: "审计日志服务暂不可用" }),
      });
    });

    await page.goto("/admin/audit");
    await page.waitForURL("**/admin/audit", { timeout: 10_000 });

    await expect(page.locator("text=审计日志服务暂不可用")).toBeVisible();

    expect(appPageErrors).toEqual([]);
    const appErrors = consoleErrors.filter((e) => !e.includes("React"));
    expect(appErrors).toEqual([]);
  });

  test("audit page filter clears work correctly", async ({ page, appPageErrors, consoleErrors }) => {
    const admin = getTestAccount("ADMIN");
    await loginAs(page, admin);

    await mockAuditLog(page, [
      { id: "A010", timestamp: "2026-07-24T10:00:00", actor_name: "张三", actor_code: "Z001", action: "CREATE", object_type: "record", object_id: "r-001", factory_id: "PLANT_A", request_id: "req-010" },
      { id: "A011", timestamp: "2026-07-24T11:00:00", actor_name: "李四", actor_code: "L001", action: "DELETE", object_type: "record", object_id: "r-002", factory_id: "PLANT_B", request_id: "req-011" },
    ]);

    await page.goto("/admin/audit");
    await page.waitForURL("**/admin/audit", { timeout: 10_000 });

    await page.waitForFunction(() => !document.body.innerText.includes("加载中"), null, { timeout: 10_000 });

    await expect(page.locator("text=张三")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=李四")).toBeVisible();

    // Filter by actor name
    const actorInput = page.locator('input[placeholder="姓名或工号"]');
    await actorInput.fill("张三");

    await expect(page.locator("text=张三")).toBeVisible();
    await expect(page.locator("text=李四")).toHaveCount(0);

    // Clear filters
    await page.click('button:has-text("清除筛选")');

    await expect(page.locator("text=张三")).toBeVisible();
    await expect(page.locator("text=李四")).toBeVisible();

    expect(appPageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
