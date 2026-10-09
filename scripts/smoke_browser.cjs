// Real-model smoke test. It requires a running app and a local outdoor photograph.
const { chromium } = require('@playwright/test');
const fs = require('node:fs');

(async () => {
  const imagePath = process.argv[2];
  if (!imagePath || !fs.existsSync(imagePath)) throw new Error('Usage: node scripts/smoke_browser.cjs path/to/outdoor.jpg');
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ baseURL: 'http://127.0.0.1:8000', viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto('http://127.0.0.1:8000');
    await page.getByRole('button', { name: 'Start Climate Scan' }).click();
    await page.locator('#image-file').setInputFiles(imagePath);
    await page.getByRole('button', { name: 'Analyze this place' }).click();
    await page.waitForURL(/\/scans\//);
    await page.getByRole('heading', { name: 'What the image tells us' }).waitFor({ timeout: 120000 });
    const id = new URL(page.url()).pathname.split('/').pop();
    const scan = await (await page.request.get(`/api/v1/scans/${id}`)).json();
    if (scan.status !== 'completed' || !scan.report.vision_model.startsWith('nvidia/segformer')) {
      throw new Error('A real SegFormer report was not produced.');
    }
    fs.mkdirSync('artifacts', { recursive: true });
    fs.writeFileSync('artifacts/real-http-report.json', JSON.stringify(scan, null, 2));
    await page.screenshot({ path: 'artifacts/real-report-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: 'artifacts/real-report-mobile.png', fullPage: true });
    if (errors.length) throw new Error(errors.join('\n'));
    console.log(JSON.stringify({ status: scan.status, seconds: scan.report.elapsed_seconds,
      vision: scan.report.vision_model, decision: scan.report.decision.source,
      explanation: scan.report.explanation.source, browserErrors: errors.length }));
    await page.request.delete(`/api/v1/scans/${id}`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
