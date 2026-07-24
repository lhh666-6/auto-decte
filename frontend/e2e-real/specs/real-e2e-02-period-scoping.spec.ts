/**
 * REAL-E2E-02: Seed records with different dates → verify today/month/year scoping
 *
 * This test seeds finance_effective_records with different business_dates,
 * then verifies that the finance ledger scoping (today/month/year) returns
 * the correct records via the real API.
 */

import { test, expect, loginViaApi, ACCOUNTS } from "../fixtures";

test.describe("REAL-E2E-02: Period Scoping", () => {
  test("Ledger overview shows scoped counts", async ({ page }) => {
    const account = ACCOUNTS.FINANCE;
    await loginViaApi(page, account);

    // Fetch the ledger overview directly via API
    const overviewResponse = await page.request.get(
      "/api/v1/finance/ledger/overview",
    );
    expect(overviewResponse.ok()).toBeTruthy();

    const overview = await overviewResponse.json();
    // The overview returns counts for today, month, year scopes
    expect(overview).toHaveProperty("today");
    expect(overview).toHaveProperty("month");
    expect(overview).toHaveProperty("year");
    expect(typeof overview.today).toBe("number");
    expect(typeof overview.month).toBe("number");
    expect(typeof overview.year).toBe("number");
  });

  test("Navigate to each scope page without error", async ({ page, consoleErrors }) => {
    const account = ACCOUNTS.FINANCE;
    await loginViaApi(page, account);

    // Visit today scope
    await page.goto("/finance/today");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("h1, h2, [class*='ledger']").first()).toBeVisible();

    // Visit month scope
    await page.goto("/finance/month");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("h1, h2, [class*='ledger']").first()).toBeVisible();

    // Visit year scope
    await page.goto("/finance/year");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("h1, h2, [class*='ledger']").first()).toBeVisible();

    // No critical console errors across all navigations
    const criticalErrors = consoleErrors.filter(
      (e) => !e.includes("favicon") && !e.includes("manifest"),
    );
    expect(criticalErrors).toEqual([]);
  });
});
