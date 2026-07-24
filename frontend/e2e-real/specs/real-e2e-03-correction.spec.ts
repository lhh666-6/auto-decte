/**
 * REAL-E2E-03: Finance correction — verify correction API and ledger pages
 *
 * This test verifies that the finance user can access the ledger and
 * corrections endpoints through the real API stack.
 */

import { test, expect, loginViaApi, ACCOUNTS } from "../fixtures";

test.describe("REAL-E2E-03: Finance Correction", () => {
  test("Finance ledger page loads with corrections data", async ({ page, consoleErrors }) => {
    const account = ACCOUNTS.FINANCE;
    await loginViaApi(page, account);

    // Navigate to today's ledger
    await page.goto("/finance/today");
    await page.waitForLoadState("networkidle");

    // The page should render — confirm basic UI presence
    await expect(page.locator("h1, h2, [class*='ledger']").first()).toBeVisible();

    // Verify the corrections API returns valid JSON (even if empty)
    const correctionsResponse = await page.request.get(
      "/api/v1/finance/corrections",
    );
    expect(correctionsResponse.ok()).toBeTruthy();
    const correctionsData = await correctionsResponse.json();
    expect(correctionsData).toBeDefined();

    // No critical console errors
    const criticalErrors = consoleErrors.filter(
      (e) => !e.includes("favicon") && !e.includes("manifest"),
    );
    expect(criticalErrors).toEqual([]);
  });

  test("Finance corrections page /finance/exceptions loads", async ({ page }) => {
    const account = ACCOUNTS.FINANCE;
    await loginViaApi(page, account);

    // Navigate to exceptions page
    await page.goto("/finance/exceptions");
    await page.waitForLoadState("networkidle");

    // Page should render without crashing
    await expect(page.locator("h1, h2, section").first()).toBeVisible();
  });
});
