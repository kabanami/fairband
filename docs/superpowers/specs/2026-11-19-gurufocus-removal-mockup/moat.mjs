import { open } from './pw.mjs';
const out = process.argv[2];
const chip = (who, actor) => `<span class="fb-chip fb-chip--principal fb-chip--compact mock" title="${who} set the class on 19 Nov 2026"><span class="fb-chip__glyph" aria-hidden="true">◆</span><span class="fb-chip__who figure-sm">${who}</span>${actor ? `<span class="fb-chip__role figure-sm">${actor}</span>` : ''}</span>`;
const btn = (word) => `<button type="button" class="fb-btn fb-btn--quiet fb-btn--sm mock mock-change">${word}</button>`;
const box = (state) => `
<div class="fb-menu fb-menu--filters app-notes-box mock mock-box" role="group" aria-label="Moat class" style="position:absolute;width:22rem">
  <div class="fb-menu__body" style="display:flex;flex-direction:column;gap:var(--space-2);padding:var(--space-3)">
    ${state.whose}
    <div class="app-fin__seg" role="group" aria-label="Moat class" style="align-self:flex-start">
      ${['None', 'Narrow', 'Wide'].map(c => `<button type="button" class="label" aria-pressed="${c === state.pick}">${c}</button>`).join('')}
    </div>
    <textarea class="control app-field app-notes-box__field" rows="2" placeholder="Reason (optional)" aria-label="Reason"></textarea>
  </div>
  <div class="fb-menu__foot" style="display:flex;gap:var(--space-2);align-items:center;flex-wrap:wrap">
    <button type="button" class="fb-btn fb-btn--sm">Set moat class</button>
    ${state.reset ? `<button type="button" class="fb-btn fb-btn--quiet fb-btn--sm">Use Fairband's class (${state.reset})</button>` : ''}
  </div>
</div>`;
const STATES = {
  '1-file-closed': { stamp: 'NARROW MOAT', after: btn('Change ▾') },
  '2-file-open': { stamp: 'NARROW MOAT', after: btn('Change ▾'), box: { pick: 'Narrow', whose: `<p class="caption" style="margin:0">Fairband's class, table version 1, judged <time>19 Nov 2026</time>.</p>` } },
  '3-owner-closed': { stamp: 'WIDE MOAT', after: chip('Owner') + btn('Change ▾') },
  '4-owner-open': { stamp: 'WIDE MOAT', after: chip('Owner') + btn('Change ▾'), box: { pick: 'Wide', reset: 'Narrow', whose: `<p class="caption" style="margin:0">Your class since <time>19 Nov 2026</time>. Before: Narrow.</p><p class="body" style="margin:0">Its brands and its bottlers' network keep rivals out.</p>` } },
  '5-agent-closed': { stamp: 'NARROW MOAT', after: chip('Agent', 'claude-opus-5-5') + btn('Change ▾') },
  '6-none-set': { stamp: 'MOAT NOT SET', dashed: true, after: btn('Set ▾') },
};
for (const scheme of ['light', 'dark']) {
  const { browser, page } = await open(scheme, 1440, 900);
  await page.goto('http://127.0.0.1:8499/#company/KO');
  await page.waitForSelector('.app-company__line .app-moat', { timeout: 30000 });
  await page.waitForTimeout(800);
  if (scheme === 'light') await page.screenshot({ path: `${out}/moat-0-base.png`, clip: { x: 0, y: 0, width: 1440, height: 260 } });
  for (const [name, s] of Object.entries(STATES)) {
    await page.evaluate((s) => {
      document.querySelectorAll('.mock').forEach(n => n.remove());
      const stamp = document.querySelector('.app-company__line .app-moat');
      stamp.textContent = s.stamp;
      stamp.style.borderStyle = s.dashed ? 'dashed' : 'solid';
      stamp.insertAdjacentHTML('afterend', s.after);
      if (s.box) {
        const anchor = document.querySelector('.mock-change');
        const r = anchor.getBoundingClientRect();
        document.body.insertAdjacentHTML('beforeend', `<div class="mock" style="position:absolute;left:${r.left}px;top:${r.bottom + window.scrollY + 4}px;z-index:1000">${s.html}</div>`);
      }
    }, { ...s, html: s.box ? box(s.box) : '' });
    await page.screenshot({ path: `${out}/moat-${name}-${scheme}.png`, clip: { x: 0, y: 60, width: 1000, height: s.box ? 330 : 110 } });
  }
  await browser.close();
}
