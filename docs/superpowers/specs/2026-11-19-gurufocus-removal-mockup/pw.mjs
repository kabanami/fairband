import { createRequire } from 'module';
import os from 'os';
const require = createRequire(import.meta.url);
const { chromium } = require(os.homedir() + '/.npm/_npx/e41f203b7505f1fb/node_modules/playwright-core');
export async function open(scheme = 'light', width = 1440, height = 900) {
  const browser = await chromium.launch({ executablePath: os.homedir() + '/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome', args: ['--no-sandbox'] });
  const page = await browser.newPage({ colorScheme: scheme, viewport: { width, height }, deviceScaleFactor: 2 });
  return { browser, page };
}
