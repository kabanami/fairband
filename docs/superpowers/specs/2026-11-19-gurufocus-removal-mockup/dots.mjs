import { open } from './pw.mjs';
const out = process.argv[2];
const MARKED = ['APD', 'COST', 'CX', 'JNJ', 'SIMO', 'TSLA'];
const VARIANTS = {
  A: { html: '<span class="mock-dot" style="font-family:\'IBM Plex Mono\';font-size:22px;line-height:0;margin-right:5px;vertical-align:-3px">\u2022</span>' },
  C: { html: '<span class="mock-dot" style="display:inline-block;width:6px;height:6px;border-radius:50%;background:currentColor;margin-right:7px;vertical-align:2px"></span>' },
};
for (const scheme of ['light', 'dark']) {
  const { browser, page } = await open(scheme, 1440, 900);
  await page.goto('http://127.0.0.1:8499/');
  await page.waitForFunction(() => window.FairbandPage && (window.FairbandPage.rows() || []).length > 0, null, { timeout: 30000 });
  await page.waitForTimeout(600);
  for (const [name, v] of Object.entries(VARIANTS)) {
    await page.evaluate(({ marked, html }) => {
      document.querySelectorAll('.mock-dot').forEach(n => n.remove());
      for (const tr of document.querySelectorAll('tbody tr')) {
        const t = tr.querySelector('.ticker, td');
        const a = tr.querySelector('a.fb-screen__company'); const sym = a ? a.textContent.trim() : '';
        const cell = tr.querySelector('td.fb-screen__mech');
        if (cell && marked.includes(sym)) {
          cell.insertAdjacentHTML('afterbegin', html);
          cell.title = '3 warnings: heavy capital spending; negative free cash flow; new shares issued. Preliminary estimate only. To ask an agent for a reviewed valuation, open the company and click Request research.';
        }
      }
    }, { marked: MARKED, html: v.html });
    await page.screenshot({ path: `${out}/dot-${name}-${scheme}.png`, clip: { x: 640, y: 180, width: 520, height: 300 } });
  }
  await browser.close();
}
