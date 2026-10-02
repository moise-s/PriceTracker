import { defineConfig } from "@playwright/test";

// The suite drives the production build (vite preview) against a deterministic backend
// (backend/tests/e2e_harness.py): real FastAPI app, throwaway SQLite, in-process worker that
// replays sanitised fixtures. Nothing reaches the real supermarket sites.
const API_PORT = Number(process.env.E2E_API_PORT ?? 8765);
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 4173);
const ORIGIN = `http://localhost:${WEB_PORT}`;

// Uses the installed Google Chrome by default so no browser download is needed.
// Set PLAYWRIGHT_CHANNEL=bundled after `npx playwright install chromium` to use Playwright's build.
const channel = process.env.PLAYWRIGHT_CHANNEL ?? "chrome";

export default defineConfig({
  testDir: "./e2e",
  // One shared backend state: scenarios reset it and must not interleave.
  workers: 1,
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: ORIGIN,
    channel: channel === "bundled" ? undefined : channel,
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    colorScheme: "light",
    serviceWorkers: "block",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: { viewport: { width: 1280, height: 900 } },
    },
    {
      name: "mobile",
      testIgnore: /screens\.spec\.ts/,
      use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
    },
  ],
  webServer: [
    {
      command: `uv run python -m tests.e2e_harness --port ${API_PORT} --origin ${ORIGIN}`,
      cwd: "../backend",
      url: `http://127.0.0.1:${API_PORT}/api/v1/health/live`,
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: `npm run build && npx vite preview --port ${WEB_PORT} --strictPort`,
      url: ORIGIN,
      env: { PRICETRACKER_API_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 180_000,
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
});
