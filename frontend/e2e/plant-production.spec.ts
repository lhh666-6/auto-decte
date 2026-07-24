import { test, expect, loginAs, getTestAccount } from "./fixtures";

/**
 * Mock /api/v1/plant/production response.
 */
async function mockPlantProduction(
  page: import("@playwright/test").Page,
  factoryId: string,
  records: Array<{
    record_id: string;
    display_no: string;
    cage_no: string;
    current_stage: string;
    status: string;
    revision: number;
    form_type?: string;
  }>,
) {
  await page.route("**/api/v1/plant/production", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        overview: {
          total: records.length,
          active: records.filter((r) => r.status === "ACTIVE").length,
          completed: records.filter((r) => r.status === "COMPLETED").length,
        },
        records: records.map((r) => ({
          record_id: r.record_id,
          display_no: r.display_no,
          factory_id: factoryId,
          form_type: r.form_type ?? "SORTING",
          source_record_id: null,
          base_info: {},
          cage_no: r.cage_no,
          current_stage: r.current_stage,
          status: r.status,
          revision: r.revision,
          created_at: "2026-07-24T08:00:00",
          updated_at: "2026-07-24T08:00:00",
        })),
      }),
    });
  });
}

test.describe("E2E-03: Plant production visibility", () => {
  test("PLANT_A manager sees production records for their factory", async ({ page, appPageErrors, consoleErrors }) => {
    const plantA = getTestAccount("PLANT_A");
    await loginAs(page, plantA);

    await mockPlantProduction(page, "PLANT_A", [
      { record_id: "R001", display_no: "SR-20260724-001", cage_no: "C001", current_stage: "SORT", status: "ACTIVE", revision: 1 },
      { record_id: "R002", display_no: "SR-20260724-002", cage_no: "C002", current_stage: "PLANT_AUDIT", status: "ACTIVE", revision: 3 },
    ]);

    await page.goto("/plant/production");
    await page.waitForURL("**/plant/production", { timeout: 10_000 });

    // Check page title
    await expect(page.getByRole("heading", { name: "本厂竹丝生产看板" })).toBeVisible();

    // Check records are visible
    await expect(page.locator("text=SR-20260724-001")).toBeVisible();
    await expect(page.locator("text=SR-20260724-002")).toBeVisible();
    await expect(page.locator("text=C001")).toBeVisible();
    await expect(page.locator("text=C002")).toBeVisible();

    expect(appPageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("plant manager sees 'view and sign' link for PLANT_AUDIT stage records", async ({ page, appPageErrors, consoleErrors }) => {
    const plantA = getTestAccount("PLANT_A");
    await loginAs(page, plantA);

    await mockPlantProduction(page, "PLANT_A", [
      { record_id: "R003", display_no: "SR-20260724-003", cage_no: "C003", current_stage: "PLANT_AUDIT", status: "ACTIVE", revision: 2 },
    ]);

    await page.goto("/plant/production");
    await page.waitForURL("**/plant/production", { timeout: 10_000 });

    // The "查看并签字" link for PLANT_AUDIT stage
    await expect(page.locator('a:has-text("查看并签字")')).toBeVisible();

    expect(appPageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});

test.describe("E2E-04: Cross-factory isolation", () => {
  test("PLANT_A manager does NOT see PLANT_B records", async ({ page, appPageErrors, consoleErrors }) => {
    const plantA = getTestAccount("PLANT_A");
    await loginAs(page, plantA);

    await mockPlantProduction(page, "PLANT_A", [
      { record_id: "RA001", display_no: "SR-20260724-A01", cage_no: "CA01", current_stage: "DIPPING", status: "ACTIVE", revision: 1 },
    ]);

    await page.goto("/plant/production");
    await page.waitForURL("**/plant/production", { timeout: 10_000 });

    // PLANT_A's own record is visible
    await expect(page.locator("text=SR-20260724-A01")).toBeVisible();

    // PLANT_B records should NOT be visible
    await expect(page.locator("text=SR-20260724-B01")).toHaveCount(0);

    expect(appPageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("PLANT_B manager sees only PLANT_B records", async ({ page, appPageErrors, consoleErrors }) => {
    const plantB = getTestAccount("PLANT_B");
    await loginAs(page, plantB);

    await mockPlantProduction(page, "PLANT_B", [
      { record_id: "RB001", display_no: "SR-20260724-B01", cage_no: "CB01", current_stage: "SORT", status: "ACTIVE", revision: 1 },
      { record_id: "RB002", display_no: "SR-20260724-B02", cage_no: "CB02", current_stage: "DRYING", status: "ACTIVE", revision: 2 },
    ]);

    await page.goto("/plant/production");
    await page.waitForURL("**/plant/production", { timeout: 10_000 });

    await expect(page.locator("text=SR-20260724-B01")).toBeVisible();
    await expect(page.locator("text=SR-20260724-B02")).toBeVisible();

    // PLANT_A records should NOT be visible
    await expect(page.locator("text=SR-20260724-A01")).toHaveCount(0);

    expect(appPageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test("filter by cage_no works on production page", async ({ page, appPageErrors, consoleErrors }) => {
    const plantA = getTestAccount("PLANT_A");
    await loginAs(page, plantA);

    await mockPlantProduction(page, "PLANT_A", [
      { record_id: "R010", display_no: "SR-20260724-010", cage_no: "CAGE-X", current_stage: "SORT", status: "ACTIVE", revision: 1 },
      { record_id: "R011", display_no: "SR-20260724-011", cage_no: "CAGE-Y", current_stage: "SORT", status: "ACTIVE", revision: 1 },
    ]);

    await page.goto("/plant/production");
    await page.waitForURL("**/plant/production", { timeout: 10_000 });

    // Both records initially visible
    await expect(page.locator("text=SR-20260724-010")).toBeVisible();
    await expect(page.locator("text=SR-20260724-011")).toBeVisible();

    // Filter by cage number
    const searchInput = page.locator('input[type="search"]');
    await searchInput.fill("CAGE-X");

    // Record with CAGE-X visible, CAGE-Y hidden
    await expect(page.locator("text=SR-20260724-010")).toBeVisible();
    await expect(page.locator("text=SR-20260724-011")).toHaveCount(0);

    expect(appPageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
