import { defineConfig, devices } from '@playwright/test';

/**
 * E2E do OneB Market.
 *
 * A API precisa estar de pé em http://localhost:8000 (o job `e2e` do CI sobe o uvicorn
 * antes de chamar `npm run test:e2e`). O Vite é iniciado pelo próprio Playwright via
 * `webServer` — reutilizando um servidor já rodando quando existir, pra não brigar com
 * o `npm run dev` de quem estiver desenvolvendo.
 */
const API_URL = process.env.VITE_API_URL ?? 'http://localhost:8000';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // os testes compartilham um único banco da API
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['list']] : 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: 'npm run dev -- --port 5173',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { VITE_API_URL: API_URL },
  },
});
