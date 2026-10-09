const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/browser',
  timeout: 30000,
  fullyParallel: false,
  workers: 1,
  outputDir: 'artifacts/browser-tests',
  use: {
    baseURL: 'http://127.0.0.1:8001', trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: process.platform === 'win32'
      ? '.venv\\Scripts\\python.exe -m uvicorn tests.browser_server:app --host 127.0.0.1 --port 8001'
      : '.venv/bin/python -m uvicorn tests.browser_server:app --host 127.0.0.1 --port 8001',
    url: 'http://127.0.0.1:8001/api/v1/health',
    reuseExistingServer: false,
    timeout: 30000,
  },
});
