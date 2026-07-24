/**
 * REAL-E2E-06: Admin audit — login as ADMIN, open /admin/audit, verify audit-log API
 *
 * Tests that the audit log page loads and the audit-log API endpoint
 * returns valid JSON through the real backend stack.
 */

import { test, expect, loginViaApi, ACCOUNTS } from "../fixtures";

test.describe("REAL-E2E-06: Admin Audit", () => {
  test("Admin user logs in and accesses audit page", async ({ page, consoleErrors }) => {
    const admin = ACCOUNTS.ADMIN;
    await loginViaApi(page, admin);

    // Navigate to admin audit page
    await page.goto("/admin/audit");
    await page.waitForLoadState("networkidle");

    // Page should render
    await expect(page.locator("h1, h2, section, [class*='audit']").first()).toBeVisible();

    // Verify audit-log API returns valid JSON
    const auditResponse = await page.request.get("/api/v1/admin/audit-log");
    expect(auditResponse.ok()).toBeTruthy();
    const auditData = await auditResponse.json();
    expect(auditData).toBeDefined();
    // The response should contain an items array
    expect(Array.isArray(auditData.items)).toBeTruthy();

    // No critical console errors
    const criticalErrors = consoleErrors.filter(
      (e) => !e.includes("favicon") && !e.includes("manifest"),
    );
    expect(criticalErrors).toEqual([]);
  });

  test("Admin can access organization page", async ({ page }) => {
    const admin = ACCOUNTS.ADMIN;
    await loginViaApi(page, admin);

    await page.goto("/admin/organization");
    await page.waitForLoadState("networkidle");

    await expect(page.locator("h1, h2, section").first()).toBeVisible();
  });

  test("Admin can access roles page", async ({ page }) => {
    const admin = ACCOUNTS.ADMIN;
    await loginViaApi(page, admin);

    await page.goto("/admin/roles");
    await page.waitForLoadState("networkidle");

    await expect(page.locator("h1, h2, section").first()).toBeVisible();
  });

  test("Non-admin (FINANCE) cannot access admin pages", async ({ page }) => {
    const finance = ACCOUNTS.FINANCE;
    await loginViaApi(page, finance);

    // Try to access admin audit — should redirect to login or show error
    await page.goto("/admin/audit");
    await page.waitForLoadState("networkidle");

    // The app should redirect to login page since FINANCE doesn't have ADMIN role
    const currentUrl = page.url();
    expect(
      currentUrl.includes("/login") || currentUrl.includes("/finance"),
    ).toBeTruthy();
  });
});
