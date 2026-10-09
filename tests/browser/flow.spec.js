const { test, expect } = require('@playwright/test');
const { execFileSync } = require('node:child_process');

const python = process.platform === 'win32' ? '.venv\\Scripts\\python.exe' : '.venv/bin/python';
const photo = execFileSync(python, ['-c', 'from tests.test_api import photo; import sys; sys.stdout.buffer.write(photo())']);

test('English landing fits viewport and camera denial offers a backup', async ({ page }) => {
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('A greener city');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByRole('button', { name: 'Start Climate Scan' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('#camera-status')).toContainText('Camera access is unavailable');
  await expect(page.locator('#image-file')).toBeVisible();
  await page.getByRole('button', { name: 'Close camera' }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  expect(errors).toEqual([]);
});

test('photo to real HTTP report, history and deletion', async ({ page }) => {
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await page.getByRole('button', { name: 'Start Climate Scan' }).click();
  await page.locator('#image-file').setInputFiles({ name: 'outdoor-test.jpg', mimeType: 'image/jpeg', buffer: photo });
  await expect(page.locator('#preview')).toBeVisible();
  await page.getByRole('button', { name: 'Analyze this place' }).click();
  await expect(page).toHaveURL(/\/scans\//);
  await expect(page.getByRole('heading', { name: 'What the image tells us' })).toBeVisible({ timeout: 20000 });
  await expect(page.getByText('Rules-based fallback', { exact: true })).toBeVisible();
  await expect(page.getByText('Jev confidence: not available', { exact: true })).toBeVisible();
  await expect(page.getByText('TEMPLATE EXPLANATION · GEMMA NOT USED')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: `artifacts/report-${test.info().project.name}.png`, fullPage: true });
  await page.getByRole('link', { name: 'My scans' }).click();
  await expect(page.locator('.scan-item')).toHaveCount(1);
  await page.locator('.scan-item').click();
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Delete this scan' }).click();
  await expect(page).toHaveURL('/history');
  await expect(page.locator('.empty-state')).toBeVisible();
  expect(errors).toEqual([]);
});

test('small viewport has no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto('/');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByRole('button', { name: 'Start Climate Scan' }).click();
  expect(await page.locator('dialog').evaluate(d => d.scrollWidth <= d.clientWidth)).toBeTruthy();
});

test('virtual camera capture creates a preview and releases the camera', async ({ page }) => {
  // The headless Windows runtime has no capture device. Supply a real MediaStream
  // from a canvas to test capture/retake/cleanup without claiming a hardware test.
  await page.addInitScript(() => {
    window.testCameraTracks = [];
    navigator.mediaDevices.getUserMedia = async () => {
      const canvas = document.createElement('canvas');
      canvas.width = 640; canvas.height = 480;
      const ctx = canvas.getContext('2d');
      const paint = () => { ctx.fillStyle = '#63804c'; ctx.fillRect(0, 0, 640, 480); };
      paint();
      const stream = canvas.captureStream(10);
      window.testCameraTracks.push(...stream.getTracks());
      const timer = setInterval(paint, 100);
      setTimeout(() => clearInterval(timer), 10000);
      return stream;
    };
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Start Climate Scan' }).click();
  await expect(page.locator('#take-photo')).toBeVisible();
  await expect.poll(() => page.locator('#camera').evaluate(video => video.videoWidth)).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Capture photo', exact: true }).click();
  await expect(page.locator('#preview')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Analyze this place' })).toBeEnabled();
  expect(await page.locator('#camera').evaluate(video => video.srcObject)).toBeNull();
  await page.getByRole('button', { name: 'Retake', exact: true }).click();
  await expect(page.locator('#camera')).toBeVisible();
  await page.getByRole('button', { name: 'Close camera' }).click();
  await expect.poll(() => page.locator('#camera').evaluate(video => video.srcObject === null)).toBeTruthy();
  expect(await page.evaluate(() => window.testCameraTracks.every(track => track.readyState === 'ended'))).toBeTruthy();
});
