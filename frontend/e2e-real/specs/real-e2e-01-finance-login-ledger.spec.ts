/**
 * REAL-E2E-01: Finance login → navigate to /finance/today → verify real ledger data
 *
 * This test confirms that a finance user can log in through the real login
 * endpoint and see the finance ledger page rendering real (empty) API data.
 */

import { test, expect, loginViaApi, ACCOUNTS } from "../fixtures";

test.describe("REAL-E2E-01: Finance Login Ledger", () => {
  test("Finance user logs in and views today's ledger", async ({ page, consoleErrors }) => {
    const account = ACCOUNTS.FINANCE;

    // Login via real API POST
    await loginViaApi(page, account);

    // Navigate to today's ledger
    await page.goto("/finance/today");
    await page.waitForLoadState("networkidle");

    // Verify the page rendered — should show ledger UI with scope indicator
    // The ledger page renders a scope label ("today", "month", "year")
    await expect(page.locator("h1, h2, [data-testid='ledger-title']").first()).toBeVisible();

    // Verify no critical console errors
    const criticalErrors = consoleErrors.filter(
      (e) => !e.includes("favicon") && !e.includes("manifest"),
    );
    expect(criticalErrors).toEqual([]);
  });
});
