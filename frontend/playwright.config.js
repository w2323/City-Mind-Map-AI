import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  timeout: 90000,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5175',
    acceptDownloads: true,
    viewport: { width: 1440, height: 1000 },
    launchOptions: { channel: 'msedge', args: ['--enable-unsafe-swiftshader'] },
  },
  webServer: [
    { command: 'python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8101', cwd: '..', env: { CITYMIND_ALLOWED_ORIGINS: 'http://127.0.0.1:5175' }, url: 'http://127.0.0.1:8101/', timeout: 90000 },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5175 --strictPort', url: 'http://127.0.0.1:5175', env: { CITYMIND_BACKEND_URL: 'http://127.0.0.1:8101' }, timeout: 30000 },
  ],
});
