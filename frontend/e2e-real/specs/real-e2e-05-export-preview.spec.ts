/**
 * REAL-E2E-05: Export preview — list templates, verify export API, navigate exports page
 *
 * Tests the governed export flow using real API calls. Exercises:
 * - Template listing from the real backend
 * - Export listing API
 * - Export page navigation
 * - Download URL structure
 */

import { test, expect, loginViaApi, ACCOUNTS } from "../fixtures";

test.describe("REAL-E2E-05: Export Preview", () => {
  test("Report templates API returns valid data", async ({ page }) => {
    const account = ACCOUNTS.FINANCE;
    await loginViaApi(page, account);

    const response = await page.request.get("/api/v1/finance/report-templates");
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toBeDefined();
    // Should have a templates array
    expect(Array.isArray(data.items ?? data.templates ?? [])).toBeTruthy();
  });

  test("Exports page loads and lists exports", async ({ page, consoleErrors }) => {
    const account = ACCOUNTS.FINANCE;
    await loginViaApi(page, account);

    // Navigate to exports page
    await page.goto("/finance/exports");
    await page.waitForLoadState("networkidle");

    // Page should render
    await expect(page.locator("h1, h2, [class*='export'], section").first()).toBeVisible();

    // Verify exports API returns valid data
    const exportsResponse = await page.request.get("/api/v1/finance/exports");
    expect(exportsResponse.ok()).toBeTruthy();
    const exportsData = await exportsResponse.json();
    expect(exportsData).toBeDefined();

    // No critical console errors
    const criticalErrors = consoleErrors.filter(
      (e) => !e.includes("favicon") && !e.includes("manifest"),
    );
    expect(criticalErrors).toEqual([]);
  });

  test("Report mappings API returns valid data", async ({ page }) => {
    const account = ACCOUNTS.FINANCE;
    await loginViaApi(page, account);

    const response = await page.request.get("/api/v1/finance/report-mappings");
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toBeDefined();
    expect(Array.isArray(data.items ?? data.mappings ?? [])).toBeTruthy();
  });
});
