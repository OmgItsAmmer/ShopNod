import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';
import { BACKEND, DB, PY, ROOT } from './env';

/**
 * `docker compose up` (from backend/) must be running, or set nothing and Playwright starts the API, the MCP server
 * and the built web app (shop dashboard + `/shopper`) itself. `reuseExistingServer` keeps your own servers if they are up.
 */
export default defineConfig({
  testDir: '.',
  testMatch: '*.spec.ts',
  globalSetup: './global-setup.ts',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:3000',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : [
        {
          command: `${PY} -m uvicorn shopnod_api.main:app --port 8000 --log-level warning`,
          cwd: BACKEND,
          url: 'http://localhost:8000/healthz',
          reuseExistingServer: true,
          timeout: 60_000,
          env: { DATABASE_URL: DB, CORS_ORIGINS: 'http://localhost:3000', DEMO_MODE: 'true', WEATHER_ENABLED: 'false' },
        },
        {
          command: `${PY} -m uvicorn shopnod_mcp.server:app --port 8001 --log-level warning`,
          cwd: BACKEND,
          url: 'http://localhost:8001/healthz',
          reuseExistingServer: true,
          timeout: 60_000,
          env: { DATABASE_URL: DB },
        },
        {
          command: 'npx next start -p 3000',
          cwd: path.join(ROOT, 'shopkeeper-web'),
          url: 'http://localhost:3000',
          reuseExistingServer: true,
          timeout: 60_000,
          env: { API_INTERNAL_URL: 'http://localhost:8000', NEXT_DIST_DIR: process.env.NEXT_DIST_DIR ?? '.next' },
        },
      ],
});
