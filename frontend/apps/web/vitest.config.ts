import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Exclude Playwright e2e specs — they use @playwright/test, not vitest
    exclude: [
      "**/e2e/**",
      "**/e2e-real/**",
      "**/node_modules/**",
    ],
    globals: true,
    environment: "jsdom",
  },
});
