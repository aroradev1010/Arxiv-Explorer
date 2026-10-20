import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  outputDir: "./test-results/live",
  testDir: "./e2e",
  testMatch: "live.spec.ts",
  workers: 1,
  timeout: 90000,
  expect: { timeout: 30000 },
  use: { baseURL: "http://127.0.0.1:3000", ...devices["Desktop Chrome"] },
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: true,
    timeout: 120000,
  },
});
