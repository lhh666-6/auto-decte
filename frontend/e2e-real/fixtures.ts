/**
 * Real-stack Playwright E2E fixtures.
 *
 * Key principle: NO page.route() or route.fulfill() for any /api/** paths.
 * All API calls go through the real Vite proxy → FastAPI → isolated SQLite.
 */

import type { Page } from "@playwright/test";
import { test as base } from "@playwright/test";

// ─── Test Accounts (must match scripts/run_playwright_real_backend.py) ─────

export interface TestAccount {
  employeeCode: string;
  employeeName: string;
  pin: string;
  workspaceRoles: string[];
  landingPath: string;
  factoryId: string;
  factoryName: string;
}

const TEST_PIN = "2468";

export const ACCOUNTS: Record<string, TestAccount> = {
  ADMIN: {
    employeeCode: "ADMIN001",
    employeeName: "系统管理员",
    pin: TEST_PIN,
    workspaceRoles: ["ADMIN"],
    landingPath: "/admin/overview",
    factoryId: "FACTORY_ADMIN",
    factoryName: "管理中心",
  },
  FINANCE: {
    employeeCode: "FIN001",
    employeeName: "财务主管",
    pin: TEST_PIN,
    workspaceRoles: ["FINANCE"],
    landingPath: "/finance/overview",
    factoryId: "FACTORY_ADMIN",
    factoryName: "管理中心",
  },
  PLANT_A: {
    employeeCode: "PLANT_A001",
    employeeName: "张厂长",
    pin: TEST_PIN,
    workspaceRoles: ["PLANT_MANAGER"],
    landingPath: "/plant/overview",
    factoryId: "PLANT_A",
    factoryName: "甲厂",
  },
  PLANT_B: {
    employeeCode: "PLANT_B001",
    employeeName: "李厂长",
    pin: TEST_PIN,
    workspaceRoles: ["PLANT_MANAGER"],
    landingPath: "/plant/overview",
    factoryId: "PLANT_B",
    factoryName: "乙厂",
  },
  SORT_OPERATOR: {
    employeeCode: "SORT001",
    employeeName: "分选工小王",
    pin: TEST_PIN,
    workspaceRoles: [],
    landingPath: "/login",
    factoryId: "PLANT_A",
    factoryName: "甲厂",
  },
};

export function getAccount(key: string): TestAccount {
  const account = ACCOUNTS[key];
  if (!account) throw new Error(`Unknown test account: ${key}`);
  return { ...account };
}

// ─── Real Login Helpers (real HTTP POST, no mocking) ──────────────────────

/**
 * Log in through the real web login endpoint.
 * Navigates to /login, fills the form, submits, and waits for redirect.
 */
export async function loginAs(page: Page, account: TestAccount): Promise<void> {
  await page.goto("/login");
  await page.waitForSelector('input[name="employee_code"]');

  await page.fill('input[name="employee_code"]', account.employeeCode);
  await page.fill('input[name="pin"]', account.pin);
  await page.click('button[type="submit"]');

  // After login, the app navigates to the landing path
  await page.waitForURL(`**${account.landingPath}**`, { timeout: 15_000 });
}

/**
 * Log in by posting directly to the login API, then navigate.
 * Faster than form-based login when the test doesn't need to exercise the
 * login form itself.
 */
export async function loginViaApi(
  page: Page,
  account: TestAccount,
): Promise<void> {
  const loginResponse = await page.request.post("/api/v1/web/auth/login", {
    data: {
      employee_code: account.employeeCode,
      pin: account.pin,
      device_id: "playwright-real-e2e",
    },
  });
  if (!loginResponse.ok()) {
    throw new Error(
      `Login failed (${loginResponse.status()}): ${await loginResponse.text()}`,
    );
  }

  // The response sets cookies; Playwright's APIRequestContext does not share
  // cookies with the browser context, so we need to transfer them.
  const setCookieHeader = loginResponse.headers()["set-cookie"];
  if (setCookieHeader) {
    const cookies = Array.isArray(setCookieHeader)
      ? setCookieHeader
      : [setCookieHeader];
    for (const cookieStr of cookies) {
      const [nameValue, ..._rest] = cookieStr.split(";");
      const [name, value] = nameValue.split("=");
      if (name && value) {
        await page.context().addCookies([
          {
            name: name.trim(),
            value: value.trim(),
            domain: "localhost",
            path: "/",
          },
        ]);
      }
    }
  }

  // Navigate to the landing page
  await page.goto(account.landingPath);
  await page.waitForLoadState("networkidle");
}

// ─── Custom Fixture ────────────────────────────────────────────────────────

export interface RealE2EFixtures {
  pageErrors: string[];
  consoleErrors: string[];
}

export const test = base.extend<RealE2EFixtures>({
  pageErrors: async ({ page }, use) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => {
      errors.push(`[pageerror] ${error.message}`);
    });
    await use(errors);
  },
  consoleErrors: async ({ page }, use) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        // Filter browser-generated network errors
        if (
          text.includes("Failed to load resource") ||
          text.includes("the server responded with a status of")
        ) {
          return;
        }
        errors.push(`[console.error] ${text}`);
      }
    });
    await use(errors);
  },
});

export { expect } from "@playwright/test";
