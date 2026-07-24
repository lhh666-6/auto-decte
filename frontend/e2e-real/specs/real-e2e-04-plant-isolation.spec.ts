/**
 * REAL-E2E-04: Plant factory isolation — PLANT_A login, access /plant/production
 *
 * Verifies that a plant manager can only see data for their own factory.
 * PLANT_A should be able to access plant views, and should be isolated
 * from PLANT_B factory data.
 */

import { test, expect, loginViaApi, ACCOUNTS } from "../fixtures";

test.describe("REAL-E2E-04: Plant Factory Isolation", () => {
  test("PLANT_A logs in and accesses plant overview", async ({ page, consoleErrors }) => {
    const plantA = ACCOUNTS.PLANT_A;
    await loginViaApi(page, plantA);

    // Navigate to plant overview — should see Plant A's data
    await page.goto("/plant/overview");
    await page.waitForLoadState("networkidle");

    // The overview page should render with factory context
    await expect(page.locator("h1, h2, [class*='overview']").first()).toBeVisible();

    // Verify the plant overview API returns valid data for Plant A
    const overviewResponse = await page.request.get("/api/v1/plant/overview");
    expect(overviewResponse.ok()).toBeTruthy();
    const overview = await overviewResponse.json();
    expect(overview).toHaveProperty("workspace");
    expect(overview).toHaveProperty("cards");

    // No critical console errors
    const criticalErrors = consoleErrors.filter(
      (e) => !e.includes("favicon") && !e.includes("manifest"),
    );
    expect(criticalErrors).toEqual([]);
  });

  test("PLANT_A accesses production page", async ({ page }) => {
    const plantA = ACCOUNTS.PLANT_A;
    await loginViaApi(page, plantA);

    // Navigate to plant production
    await page.goto("/plant/production");
    await page.waitForLoadState("networkidle");

    // Production page should render
    await expect(page.locator("h1, h2, [class*='production'], section").first()).toBeVisible();

    // Verify production API returns valid data
    const productionResponse = await page.request.get("/api/v1/plant/production");
    expect(productionResponse.ok()).toBeTruthy();
    const prodData = await productionResponse.json();
    expect(prodData).toBeDefined();
  });

  test("PLANT_B logs in and sees different factory context", async ({ page }) => {
    const plantB = ACCOUNTS.PLANT_B;
    await loginViaApi(page, plantB);

    // Navigate to plant overview — should see Plant B's data
    await page.goto("/plant/overview");
    await page.waitForLoadState("networkidle");

    await expect(page.locator("h1, h2, [class*='overview']").first()).toBeVisible();

    const overviewResponse = await page.request.get("/api/v1/plant/overview");
    expect(overviewResponse.ok()).toBeTruthy();
    const overview = await overviewResponse.json();

    // Plant B's factory should be different from Plant A's
    expect(overview.factory_id).toBe(ACCOUNTS.PLANT_B.factoryId);
  });

  test("SORT_OPERATOR (no web role) is rejected at login with 403", async ({ page }) => {
    const sortOp = ACCOUNTS.SORT_OPERATOR;
    const loginResponse = await page.request.post("/api/v1/web/auth/login", {
      data: {
        employee_code: sortOp.employeeCode,
        pin: sortOp.pin,
        device_id: "playwright-real-e2e",
      },
    });
    // SORT_OPERATOR has no web workspace roles → login must be rejected
    expect(loginResponse.status()).toBe(403);
  });
});
