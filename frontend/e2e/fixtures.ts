import type { Page } from "@playwright/test";
import { test as base } from "@playwright/test";

// ─── Test Accounts ───────────────────────────────────────────────────────────

export interface TestAccount {
  employeeCode: string;
  employeeName: string;
  pin: string;
  workspaceRoles: string[];
  landingPath: string;
  factoryId: string;
  factoryName: string;
  bambooRole: string;
  /** True if this role is permitted to access /mobile/work */
  mobileAccess: boolean;
}

const ACCOUNTS: Record<string, TestAccount> = {
  ADMIN: {
    employeeCode: "ADMIN001",
    employeeName: "系统管理员",
    pin: "1234",
    workspaceRoles: ["ADMIN"],
    landingPath: "/admin/overview",
    factoryId: "FACTORY_ADMIN",
    factoryName: "管理中心",
    bambooRole: "",
    mobileAccess: false,
  },
  FINANCE: {
    employeeCode: "FIN001",
    employeeName: "财务主管",
    pin: "1234",
    workspaceRoles: ["FINANCE"],
    landingPath: "/finance/overview",
    factoryId: "FACTORY_ADMIN",
    factoryName: "管理中心",
    bambooRole: "FINANCE_APPROVER",
    mobileAccess: false,
  },
  PLANT_A: {
    employeeCode: "PLANT_A001",
    employeeName: "张厂长",
    pin: "1234",
    workspaceRoles: ["PLANT_MANAGER"],
    landingPath: "/plant/overview",
    factoryId: "PLANT_A",
    factoryName: "甲厂",
    bambooRole: "PLANT_MANAGER",
    mobileAccess: false,
  },
  PLANT_B: {
    employeeCode: "PLANT_B001",
    employeeName: "李厂长",
    pin: "1234",
    workspaceRoles: ["PLANT_MANAGER"],
    landingPath: "/plant/overview",
    factoryId: "PLANT_B",
    factoryName: "乙厂",
    bambooRole: "PLANT_MANAGER",
    mobileAccess: false,
  },
  SORT: {
    employeeCode: "SORT001",
    employeeName: "分选工小王",
    pin: "1234",
    workspaceRoles: [],
    landingPath: "/login",
    factoryId: "PLANT_A",
    factoryName: "甲厂",
    bambooRole: "SORT",
    mobileAccess: true,
  },
  DIPPING: {
    employeeCode: "DIP001",
    employeeName: "浸胶工老陈",
    pin: "1234",
    workspaceRoles: [],
    landingPath: "/login",
    factoryId: "PLANT_A",
    factoryName: "甲厂",
    bambooRole: "DIPPING",
    mobileAccess: true,
  },
  DRYING: {
    employeeCode: "DRY001",
    employeeName: "干燥工老刘",
    pin: "1234",
    workspaceRoles: [],
    landingPath: "/login",
    factoryId: "PLANT_A",
    factoryName: "甲厂",
    bambooRole: "DRYING",
    mobileAccess: true,
  },
  SUPERVISOR: {
    employeeCode: "SUP001",
    employeeName: "主管老赵",
    pin: "1234",
    workspaceRoles: [],
    landingPath: "/login",
    factoryId: "PLANT_A",
    factoryName: "甲厂",
    bambooRole: "SUPERVISOR",
    mobileAccess: true,
  },
  INSPECTOR: {
    employeeCode: "INS001",
    employeeName: "质检员小周",
    pin: "1234",
    workspaceRoles: [],
    landingPath: "/login",
    factoryId: "PLANT_A",
    factoryName: "甲厂",
    bambooRole: "INSPECTOR",
    mobileAccess: true,
  },
};

export function getTestAccount(key: string): TestAccount {
  const account = ACCOUNTS[key];
  if (!account) throw new Error(`Unknown test account: ${key}`);
  return { ...account };
}

export function listTestAccounts(): TestAccount[] {
  return Object.values(ACCOUNTS).map((a) => ({ ...a }));
}

// ─── Session builders ────────────────────────────────────────────────────────

function buildWebSession(account: TestAccount) {
  return {
    employee_code: account.employeeCode,
    employee_name: account.employeeName,
    workspace_role: account.workspaceRoles[0] ?? "",
    workspace_roles: account.workspaceRoles,
    factory_id: account.factoryId,
    factory_name: account.factoryName,
    landing_path: account.landingPath,
  };
}

function buildMobileSession(account: TestAccount) {
  return {
    employee_code: account.employeeCode,
    employee_name: account.employeeName,
    team_name: "测试班组",
    position: account.bambooRole,
    roles: [account.bambooRole],
    allowed_form_types: ["SORTING", "DIPPING_DRYING"],
    allowed_processes: ["SORT", "DIPPING", "DRYING", "SUPERVISOR"],
    factory_id: account.factoryId,
    factory_name: account.factoryName,
    bamboo_role: account.bambooRole,
  };
}

function buildMobileLoginResponse(account: TestAccount) {
  return {
    employee_code: account.employeeCode,
    employee_name: account.employeeName,
    team_name: "测试班组",
    position: account.bambooRole,
    roles: [account.bambooRole],
    expires_at: null,
    factory_id: account.factoryId,
    factory_name: account.factoryName,
    bamboo_role: account.bambooRole,
  };
}

const empty401 = {
  title: "Unauthorized",
  status: 401,
  detail: "未登录",
};

// ─── API Route Mocking ───────────────────────────────────────────────────────

/**
 * Install a web session that is already authenticated.
 * The session check returns a valid session immediately.
 * Use this when the test navigates directly to an authenticated page
 * (skipping the login form).
 */
export async function installWebSession(page: Page, account: TestAccount) {
  const session = buildWebSession(account);

  // 1. Install broad fallback FIRST
  await installApiFallback(page);

  // 2. Install specific auth routes SECOND (takes precedence over fallback)
  await page.route("**/api/v1/web/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(session),
    });
  });

  await page.route("**/api/v1/web/auth/logout", async (route) => {
    await route.fulfill({ status: 200, body: "{}" });
  });
}

/**
 * Install mobile session routes where the user is already authenticated.
 */
export async function installMobileSession(page: Page, account: TestAccount) {
  const session = buildMobileSession(account);

  // 1. Install broad fallback FIRST
  await installApiFallback(page);

  // 2. Install specific auth routes SECOND (takes precedence over fallback)
  await page.route("**/api/v1/mobile/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(session),
    });
  });

  await page.route("**/api/v1/mobile/auth/logout", async (route) => {
    await route.fulfill({ status: 200, body: "{}" });
  });
}

/**
 * Install routes that block ALL unhandled /api/ requests to prevent
 * network-related console errors from polluting test output.
 * Returns a 200 with empty JSON body.
 */
export async function installApiFallback(page: Page) {
  // Catch any /api/ routes not already handled by more specific route handlers.
  // Must be installed FIRST — specific handlers installed later take precedence
  // (Playwright: most recently added handler wins for overlapping patterns).
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    // Return enough shape to avoid runtime crashes on .map() etc.
    const body = url.includes("/overview")
      ? { title: "", cards: [], factory_name: "", scope: "" }
      : url.includes("/audit-log")
        ? { items: [] }
        : url.includes("/production")
          ? { overview: { total: 0, active: 0, completed: 0 }, records: [] }
          : url.includes("/bamboo/")
            ? { tasks: [], dashboard: { available: 0, waiting: 0, completed: 0 }, bucket: "available" }
            : {};
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

// ─── Login Helpers ───────────────────────────────────────────────────────────

/**
 * Execute a full web login flow:
 * 1. Session check returns 401 (not logged in) → login form appears
 * 2. Fill and submit the login form
 * 3. Login POST returns valid session; subsequent session checks return session
 * 4. Wait for navigation to the landing page
 */
export async function loginAs(page: Page, account: TestAccount) {
  let loggedIn = false;
  const session = buildWebSession(account);

  // 1. Install broad API fallback FIRST (most recently added handler wins
  //    for overlapping patterns, so we add the fallback first and let
  //    specific auth routes override it)
  await installApiFallback(page);

  // 2. Register specific auth routes SECOND (these take precedence over fallback)
  // Session check: 401 until logged in, then return valid session
  await page.route("**/api/v1/web/auth/session", async (route) => {
    if (loggedIn) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(session),
      });
    } else {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify(empty401),
      });
    }
  });

  // Login POST: accept the credentials, mark as logged in
  await page.route("**/api/v1/web/auth/login", async (route) => {
    loggedIn = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(session),
    });
  });

  await page.route("**/api/v1/web/auth/logout", async (route) => {
    loggedIn = false;
    await route.fulfill({ status: 200, body: "{}" });
  });

  await page.goto("/login");
  await page.waitForSelector('input[name="employee_code"]');

  await page.fill('input[name="employee_code"]', account.employeeCode);
  await page.fill('input[name="pin"]', account.pin);
  await page.click('button[type="submit"]');

  // After login, the app navigates to the landing path
  await page.waitForURL(`**${account.landingPath}**`, { timeout: 10_000 });
}

/**
 * Execute a full mobile login flow:
 * 1. Session check returns 401 (not logged in) → login form appears
 * 2. Fill and submit the login form
 * 3. Login POST returns valid session; subsequent session checks return session
 * 4. Wait for navigation to /mobile/home
 */
export async function loginMobile(page: Page, account: TestAccount) {
  let loggedIn = false;
  const session = buildMobileSession(account);
  const loginResponse = buildMobileLoginResponse(account);

  // 1. Install broad API fallback FIRST
  await installApiFallback(page);

  // 2. Register specific auth routes SECOND (these take precedence)
  // Session check: 401 until logged in
  await page.route("**/api/v1/mobile/auth/session", async (route) => {
    if (loggedIn) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(session),
      });
    } else {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify(empty401),
      });
    }
  });

  // Login POST
  await page.route("**/api/v1/mobile/auth/login", async (route) => {
    loggedIn = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(loginResponse),
    });
  });

  await page.route("**/api/v1/mobile/auth/logout", async (route) => {
    loggedIn = false;
    await route.fulfill({ status: 200, body: "{}" });
  });

  await page.goto("/mobile/login");
  await page.waitForSelector('input[autocomplete="username"]');

  // Mobile login uses plain inputs, not named fields
  const inputs = page.locator(".mobile-login-form input");
  await inputs.nth(0).fill(account.employeeCode);
  await inputs.nth(1).fill(account.pin);
  await page.click('.mobile-login-form button[type="submit"]');

  // After login, the app navigates to /mobile/home
  await page.waitForURL("**/mobile/home", { timeout: 10_000 });
}

// ─── Custom Fixture (page error + console error monitoring) ──────────────────

export interface E2EFixtures {
  /** Records uncaught errors emitted on the page. */
  pageErrors: string[];
  /**
   * Records console.error calls, excluding browser-generated
   * "Failed to load resource" messages (which are expected in
   * test environments with partially-mocked APIs).
   */
  consoleErrors: string[];
}

export const test = base.extend<E2EFixtures>({
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
        // Skip browser-generated network error messages
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

  /**
   * Returns only application-relevant page errors, filtering out
   * browser-specific CORS/access-control messages that can occur
   * in WebKit when the Vite proxy backend is unavailable.
   */
  appPageErrors: async ({ pageErrors }, use) => {
    await use(
      pageErrors.filter(
        (e) =>
          !e.includes("access control checks") &&
          !e.includes("due to access control"),
      ),
    );
  },
});

export { expect } from "@playwright/test";
