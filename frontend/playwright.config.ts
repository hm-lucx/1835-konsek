import { defineConfig, devices } from '@playwright/test'

// Brings up the backend (SQLite) and the Vite dev server, then runs the E2E
// suite against a tablet-sized viewport (≥768px, acceptance criterion).
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    viewport: { width: 1024, height: 768 },
    trace: 'on-first-retry',
  },
  projects: [{ name: 'tablet-chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'python -m uvicorn main:app --host 127.0.0.1 --port 8000',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/health',
      env: { DATABASE_URL: 'sqlite+aiosqlite:///./e2e.db' },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --port 5173 --strictPort',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
})
