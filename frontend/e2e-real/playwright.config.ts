import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./specs",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [
    ["list"],
    [
      "html",
      { outputFolder: "artifacts/playwright-real/html-report", open: "never" },
    ],
  ],
  use: {
    baseURL: "http://localhost:5173",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    trace: "on-first-retry",
  },
  outputDir: "artifacts/playwright-real/test-output",

  projects: [
    {
      name: "chromium-desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1920, height: 1080 },
        launchOptions: {
          args: ["--disable-web-security"],
        },
      },
    },
    {
      name: "iPhone-14",
      use: {
        ...devices["iPhone 14"],
        viewport: { width: 390, height: 844 },
      },
    },
  ],

  webServer: [
    {
      // Backend: seed + migrate + start FastAPI on port 8000
      command:
        "cd ../.. && .venv\\Scripts\\python.exe scripts/run_playwright_real_backend.py",
      url: "http://127.0.0.1:8000/health/live",
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      // Frontend: Vite dev server on port 5173, proxies /api to :8000
      command: "npm run dev:web",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 30_000,
      cwd: "..",
    },
  ],
});
