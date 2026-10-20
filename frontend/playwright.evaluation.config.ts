import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "evaluation-live.spec.ts",
  outputDir: "./test-results/evaluation-live",
  workers: 1,
  timeout: 120000,
  expect: { timeout: 30000 },
  use: { baseURL: "http://127.0.0.1:3002", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
  webServer: [
    {
      command:
        '".venv\\Scripts\\python.exe" -m backend.tests.api.evaluation_fixture_server',
      cwd: "..",
      url: "http://127.0.0.1:8001/api/v1/health/ready",
      reuseExistingServer: false,
      timeout: 120000,
    },
    {
      command: "npm run dev -- --port 3002",
      url: "http://127.0.0.1:3002",
      reuseExistingServer: false,
      timeout: 120000,
      env: { NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8001" },
    },
  ],
});
