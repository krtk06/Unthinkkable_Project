import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: "http://localhost:3100",
    trace: "on-first-retry",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    // Same 412px viewport as Pixel 7 without visual-viewport emulation, which
    // breaks automated hit-testing; CSS is width-driven so the responsive
    // layout is still exercised.
    { name: "mobile", use: { ...devices["Pixel 7"], isMobile: false, hasTouch: false } },
  ],
  webServer: {
    command: "npm run dev -- --port 3100",
    url: "http://localhost:3100",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
