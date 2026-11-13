import { defineConfig, devices } from "@playwright/test";

// E2E_MODE=fixture (default): local Python service with recorded official API payloads.
// E2E_MODE=live: run against a deployed URL (BASE_URL) that calls the real APIs.
const live = process.env.E2E_MODE === "live";
const port = Number(process.env.E2E_PORT || 8123);
const baseURL = live ? process.env.BASE_URL : `http://127.0.0.1:${port}`;
if (live && !baseURL) throw new Error("E2E_MODE=live에는 BASE_URL이 필요합니다.");

export default defineConfig({
  testDir: "tests/e2e",
  timeout: live ? 120_000 : 45_000,
  expect: { timeout: live ? 30_000 : 8_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }], ["json", { outputFile: "test-results/e2e-results.json" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "on",
    acceptDownloads: true,
    locale: "ko-KR",
    timezoneId: "Asia/Seoul",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } }, testMatch: live ? /live\.spec\.mjs$/ : /app\.spec\.mjs$/ },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: live ? /live\.spec\.mjs$/ : /mobile\.spec\.mjs$/ },
  ],
  webServer: live ? undefined : {
    command: `rm -rf test-results/e2e-store && PYTHONPATH=src CONTESTFIT_SOURCE_MODE=fixture CONTESTFIT_DATA_DIR=test-results/e2e-store python3 -m posting_validation.service --port ${port}`,
    url: `http://127.0.0.1:${port}/api/health`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
