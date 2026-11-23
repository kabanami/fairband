/* The look in a browser of the refresh experience (spec 2026-11-23 refresh experience, 5): the
   branch's page on a scratch database, its runs simulated by stubbed reads of the refresh's state
   and of the rows, and the meter matrix on a page that mounts the bundle's BandMeter. Each check
   prints ok or FAIL; the script exits 1 on any FAIL. Each state is saved as a screenshot in the
   folder given, which must lie outside the repository: the page shows real companies.

     node look.mjs <screenshots folder> [<the approved mockup, for the tint's comparison>]

   The server is the branch's on the scratch database, at LOOK_BASE (http://127.0.0.1:8499). No
   real refresh runs: the page's POST /api/refresh is answered here, and GET /api/refresh/current
   says what the simulated run is doing. The page asks for the state every 30 seconds while no run
   is alive; a run the page did not start (the named run) is announced by a visibilitychange, on
   which the page asks at once, as it does when its tab shows again.

   LOOK_ONLY names the parts to run, by commas (meters, price, tint, full, named, statistics,
   layer, under, company); all of them without it. LOOK_CSS is a rule added to every page after
   its own styles, to try a correction in the browser before it is written. */
import { createRequire } from 'module';
import fs from 'fs';
import os from 'os';
import path from 'path';

const require = createRequire(import.meta.url);
const NPX = path.join(os.homedir(), '.npm/_npx');
const PW = fs.readdirSync(NPX).map((d) => path.join(NPX, d, 'node_modules/playwright-core'))
  .find((p) => fs.existsSync(p));
const { chromium } = require(PW);
const BROWSERS = path.join(os.homedir(), '.cache/ms-playwright');
const NEWEST = fs.readdirSync(BROWSERS).filter((d) => /^chromium-\d+$/.test(d))
  .sort((a, b) => Number(a.split('-')[1]) - Number(b.split('-')[1])).pop();
const CHROME = path.join(BROWSERS, NEWEST, 'chrome-linux64/chrome');

const BASE = process.env.LOOK_BASE || 'http://127.0.0.1:8499';
const OUT = process.argv[2];
const MOCKUP = process.argv[3] || null;
if (!OUT) {
  console.error('usage: node look.mjs <screenshots folder> [<mockup.html>]');
  process.exit(2);
}
fs.mkdirSync(OUT, { recursive: true });

const WIDE = 1600;
const HIGH = 600;
const failures = [];
function check(name, ok, detail) {
  const said = detail === undefined ? '' : ' :: ' + (typeof detail === 'string' ? detail
    : JSON.stringify(detail));
  console.log((ok ? 'ok    ' : 'FAIL  ') + name + said);
  if (!ok) failures.push(name);
}
function note(text) { console.log('note  ' + text); }
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const browser = await chromium.launch({
  executablePath: CHROME, args: ['--no-sandbox'], ignoreDefaultArgs: ['--hide-scrollbars']
});

/* A page in its own context: the theme, the window, the reduced-motion setting. An error the
   page throws fails the run. */
async function open({ scheme = 'dark', width = WIDE, height = HIGH, reduce = false, scale = 1 } = {}) {
  const context = await browser.newContext({
    colorScheme: scheme, reducedMotion: reduce ? 'reduce' : 'no-preference',
    viewport: { width, height }, deviceScaleFactor: scale
  });
  if (process.env.LOOK_CSS) {
    await context.addInitScript((css) => {
      document.addEventListener('DOMContentLoaded', () => {
        const style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);
      });
    }, process.env.LOOK_CSS);
  }
  const page = await context.newPage();
  page.on('pageerror', (e) => check('the page throws no error', false, e.message));
  return page;
}

async function shot(page, name, options = {}) {
  await page.screenshot(Object.assign({ path: path.join(OUT, name + '.png') }, options));
}

/* ------------------------------------------------------------------ the simulated runs */

/* The stubbed reads: the refresh's state from `s`, the start and the cancel answered here, and
   the rows and a company's detail read from the server with `s.alter` and `s.detail` over them,
   the figures the run changed. */
async function stub(page) {
  const real = await (await fetch(BASE + '/api/refresh/current')).json();
  const s = {
    run: null, last: real.last, shown: real.shown, recent: real.recent,
    nextId: (real.last ? real.last.id : 0) + 1, alter: null, detail: null, statsDelay: 0
  };
  s.body = () => s.run ? { refresh: s.run }
    : { refresh: null, last: s.last, shown: s.shown, error: null, recent: s.recent };
  await page.route('**/api/refresh/current', (r) => r.fulfill({ json: s.body() }));
  await page.route('**/api/refresh', (r) => r.request().method() === 'POST'
    ? r.fulfill({ json: { refreshId: s.nextId } }) : r.continue());
  await page.route('**/api/refresh/cancel', (r) => r.fulfill({ json: { cancelled: true } }));
  await page.route(/\/api\/screen\?/, async (r) => {
    const response = await r.fetch();
    const body = await response.json();
    if (s.alter) body.rows = s.alter(body.rows);
    await r.fulfill({ response, json: body });
  });
  await page.route(/\/api\/companies\/[^/?]+$/, async (r) => {
    const response = await r.fetch();
    const body = await response.json();
    if (s.detail && body.result && body.result.symbol === s.detail.symbol) {
      body.result.price = s.detail.price;
    }
    await r.fulfill({ response, json: body });
  });
  await page.route(/\/api\/statistics\?/, async (r) => {
    if (s.statsDelay) await wait(s.statsDelay);
    await r.continue();
  });
  return s;
}

/* The run alive, as the server's progress says it. */
function running(s, kind, symbols, stage, done, total) {
  s.run = {
    id: s.nextId, kind, symbols, stage, done, failed: 0, remaining: total - done, current: null
  };
}

/* The run ended: its record is the last, and the shown one but for a named revalue, which the
   server passes over (refreshes.latest_shown_refresh); it leads the newest runs. */
function ended(s, calibration, status = 'done') {
  const run = s.run;
  const now = new Date();
  const record = {
    id: run.id, kind: run.kind, symbols: run.symbols, status, stage: 'done',
    startedAt: new Date(now - 30000).toISOString(), finishedAt: now.toISOString(),
    message: null, calibration
  };
  s.last = record;
  if (!(run.kind === 'revalue' && run.symbols && status === 'done')) s.shown = record;
  s.recent = [{ id: run.id, kind: run.kind, symbols: run.symbols, status }]
    .concat(s.recent).slice(0, 20);
  s.run = null;
  s.nextId += 1;
}

const PRICE_CALIBRATION = { failed: 0, repriced: 1558, skipped: 0, total: 1558 };
const FULL_CALIBRATION = {
  valued: 1512, total: 1558, flagged: 600, flags: {},
  phases: { 'Mature Growth': 700, 'Mature Stable': 500, 'High Growth': 312 }, refused: {}
};

/* The rows after a run: every `every`-th row with a price has it moved by `by`, up and down in
   turn, and price ÷ value with it; with `values`, every second of those has its value and its
   levels moved 3% too. The counts the status line must show are kept on `s`. */
function changes(s, every, by, values) {
  return function (rows) {
    let prices = 0;
    let moved = 0;
    const out = rows.map((r, i) => {
      if (typeof r.price !== 'number' || i % every !== 0) return r;
      const up = (i / every) % 2 === 0;
      const price = Math.round(r.price * (up ? 1 + by : 1 - by) * 100) / 100;
      const row = Object.assign({}, r, { price });
      if (price !== r.price) prices++;
      if (values && (i / every) % 2 === 1 && typeof r.fairValue === 'number') {
        const k = 1.03;
        const fair = Math.round(r.fairValue * k * 100) / 100;
        if (fair !== r.fairValue) moved++;
        Object.assign(row, {
          fairValue: fair, mechanical: r.mechanical == null ? null : fair,
          fairLow: r.fairLow == null ? null : Math.round(r.fairLow * k * 100) / 100,
          fairHigh: r.fairHigh == null ? null : Math.round(r.fairHigh * k * 100) / 100
        });
      }
      if (typeof row.fairValue === 'number' && row.fairValue > 0) {
        row.priceToValue = Math.round(price / row.fairValue * 100) / 100;
      }
      return row;
    });
    s.counted = { prices, values: moved };
    return out;
  };
}

/* The page loaded on `hash` and its rows and its first status read in. */
async function ready(page, hash = '') {
  await page.goto(BASE + '/' + hash);
  await page.waitForFunction(() => window.FairbandPage && FairbandPage.rows() &&
    FairbandPage.rows().length > 0);
  await page.waitForFunction(() => {
    const line = document.querySelector('#controls .app-status');
    return line && line.textContent.length > 0;
  });
}

/* The rows' CSS animations held at their start, so a screenshot shows the tint and the arrow
   at full strength, and let go again. */
async function freeze(page) {
  await page.evaluate(() => document.getAnimations().forEach((a) => {
    if (a.animationName) { a.pause(); a.currentTime = 0; }
  }));
}
async function thaw(page) {
  await page.evaluate(() => document.getAnimations().forEach((a) => {
    if (a.animationName && a.playState === 'paused') a.play();
  }));
}

/* The layer as it stands. */
async function layerState(page) {
  return page.evaluate(() => {
    const layer = document.querySelector('.app-layer');
    const panel = layer && layer.querySelector('.app-layer__panel');
    const style = layer ? getComputedStyle(layer) : null;
    const focus = document.activeElement;
    return {
      on: !!document.querySelector('.app-layer.is-on'),
      title: panel ? (panel.querySelector('.app-layer__title') || {}).textContent : null,
      say: panel ? (panel.querySelector('.app-layer__say') || {}).textContent : null,
      buttons: panel ? Array.from(panel.querySelectorAll('button')).map((b) => b.textContent) : [],
      inert: Array.from(document.body.children).filter((c) => c.id !== 'layer')
        .every((c) => c.inert),
      mainInert: document.querySelector('main.app-page').inert,
      focusPanel: !!(focus && focus.classList.contains('app-layer__panel')),
      focusOutline: focus ? getComputedStyle(focus).outlineStyle + ' ' +
        getComputedStyle(focus).outlineWidth : null,
      transition: style ? style.transitionDuration : null,
      rect: layer ? layer.getBoundingClientRect().toJSON() : null,
      panelRect: panel ? panel.getBoundingClientRect().toJSON() : null
    };
  });
}

/* The left edges of the Screen's column heads and of every cell of the rows of `tickers`, the
   top of each of those rows within the table and the table's height, which a row grown taller
   would change; and the table's own top, which the status line above it moves. */
async function edges(page, tickers) {
  return page.evaluate((tickers) => {
    const round = (x) => Math.round(x * 100) / 100;
    const table = document.querySelector('#screen table');
    const box = table.getBoundingClientRect();
    const heads = Array.from(table.querySelectorAll('thead th'))
      .map((th) => round(th.getBoundingClientRect().left));
    const cells = {};
    const tops = {};
    table.querySelectorAll('tbody tr').forEach((tr) => {
      const link = tr.querySelector('.fb-screen__company');
      if (!link || tickers.indexOf(link.textContent) === -1) return;
      cells[link.textContent] = Array.from(tr.children)
        .map((td) => round(td.getBoundingClientRect().left));
      tops[link.textContent] = round(tr.getBoundingClientRect().top - box.top);
    });
    return { heads, cells, tops, height: round(box.height), top: round(box.top) };
  }, tickers);
}

/* The largest move between two measures of the column heads, the cells, the rows' tops and the
   table's height, each in px. */
function shift(a, b) {
  const round = (x) => Math.round(x * 100) / 100;
  const most = { heads: 0, cells: 0, tops: 0, height: round(Math.abs(a.height - b.height)) };
  a.heads.forEach((x, i) => {
    if (Math.abs(x - b.heads[i]) >= 0.5) note('head ' + i + ' at ' + x + ' moved to ' + b.heads[i]);
    most.heads = Math.max(most.heads, round(Math.abs(x - b.heads[i])));
  });
  Object.keys(a.cells).forEach((t) => a.cells[t].forEach((x, i) => {
    most.cells = Math.max(most.cells, round(Math.abs(x - ((b.cells[t] || [])[i] ?? x))));
  }));
  Object.keys(a.tops).forEach((t) => {
    most.tops = Math.max(most.tops, round(Math.abs(a.tops[t] - (b.tops[t] ?? a.tops[t]))));
  });
  return most;
}
const still = (moved) => Object.values(moved).every((x) => x < 0.5);

/* What the end of a run left on the Screen. */
async function endState(page) {
  return page.evaluate(() => {
    const tinted = Array.from(document.querySelectorAll('#screen td.fb-changed'));
    const arrows = Array.from(document.querySelectorAll('#screen .fb-screen__move'));
    const line = document.querySelector('#controls .app-status');
    const count = line.querySelector('span');
    const first = tinted[0] ? getComputedStyle(tinted[0]) : null;
    const arrow = arrows[0] ? getComputedStyle(arrows[0]) : null;
    return {
      tinted: tinted.length,
      tintedRows: Array.from(new Set(tinted.map((td) =>
        td.parentElement.querySelector('.fb-screen__company').textContent))),
      arrows: arrows.length,
      arrowWords: Array.from(new Set(arrows.map((a) => a.textContent))),
      line: line.textContent,
      countTinted: !!(count && count.classList.contains('fb-changed')),
      animation: first ? first.animationName + ' ' + first.animationDuration : null,
      arrowAnimation: arrow ? arrow.animationName + ' ' + arrow.animationDuration : null,
      layerOn: !!document.querySelector('.app-layer.is-on'),
      anyTint: document.querySelectorAll('.fb-changed').length,
      anyArrow: document.querySelectorAll('.fb-screen__move').length
    };
  });
}

/* The centre of the header's view button named `word`. */
async function menuPoint(page, word) {
  return page.evaluate((word) => {
    const b = Array.from(document.querySelectorAll('#header .fb-hdr__view'))
      .find((e) => e.textContent === word);
    const r = b.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }, word);
}

async function shownView(page) {
  return page.evaluate(() => ({
    hash: location.hash,
    visible: ['screen', 'watchlists', 'statistics', 'methodology', 'settings', 'inbox', 'company']
      .filter((id) => !document.getElementById(id).hidden)
  }));
}

/* ------------------------------------------------------------------ the price run */

/* A price refresh of the whole screen: the layer, the menu that does not answer under it, then
   the end signal: the changed cells tinted, the changed prices' arrows, the line's count; 3
   seconds on nothing tinted; no column moved as the arrows came and went. Returns the paused
   screenshot of the table, for the tint's comparison. */
async function priceRun(scheme, reduce) {
  const tag = 'price-' + scheme + (reduce ? '-reduce' : '');
  const page = await open({ scheme, reduce });
  const s = await stub(page);
  await ready(page);
  const statistics = await menuPoint(page, 'Statistics');
  const before = await shownView(page);

  running(s, 'price', null, 'quotes', 0, 1558);
  await page.click('button[aria-label="Refresh prices"]');
  await page.waitForSelector('.app-layer.is-on');
  await wait(250);
  const layer = await layerState(page);
  check(tag + ': the layer is up, titled Refreshing prices',
    layer.on && layer.title === 'Refreshing prices', layer.title);
  check(tag + ': a price run has no Keep reading', !layer.buttons.includes('Keep reading'),
    layer.buttons);
  check(tag + ': everything under the layer is inert', layer.inert && layer.mainInert);
  check(tag + ': the panel holds the focus, with no ring', layer.focusPanel &&
    (layer.focusOutline.startsWith('none') || layer.focusOutline.endsWith(' 0px')),
    layer.focusOutline);
  check(tag + ': the layer fades over 150 ms', layer.transition.split(',')[0].trim() === '0.15s',
    layer.transition);
  check(tag + ': the layer covers the window', layer.rect.left === 0 && layer.rect.top === 0 &&
    layer.rect.width === WIDE && layer.rect.height === HIGH, layer.rect);
  await shot(page, tag + '-layer');

  await page.mouse.click(statistics.x, statistics.y);
  await page.keyboard.press('Escape');
  await page.evaluate(() => { location.hash = '#settings'; });
  await wait(300);
  const after = await shownView(page);
  check(tag + ': a press on the menu, Escape and a hash change no view',
    JSON.stringify(after) === JSON.stringify(before) &&
    (await layerState(page)).on, after);

  running(s, 'price', null, 'reprice', 900, 1558);
  await page.waitForFunction(() => /900/.test(document.querySelector('.app-layer__panel')
    .textContent), null, { timeout: 5000 });
  await shot(page, tag + '-progress');

  /* the end: the rows the run changed */
  s.alter = changes(s, 3, 0.012, false);
  const rows = await page.evaluate(() => FairbandPage.rows().map((r) => r.ticker));
  const watched = rows.filter((_, i) => i % 3 === 0).slice(0, 12);
  const at0 = await edges(page, watched);
  ended(s, PRICE_CALIBRATION);
  await page.waitForSelector('#screen td.fb-changed', { timeout: 6000 });
  const at1 = await edges(page, watched);
  const end = await endState(page);
  await freeze(page);
  await shot(page, tag + '-end');
  const clip = await tableClip(page);
  await thaw(page);
  const want = s.counted.prices.toLocaleString('en-US') + ' prices changed';
  check(tag + ': the layer is gone at the end', !end.layerOn);
  check(tag + ': the changed cells are tinted', end.tinted > 0, end.tinted + ' cells');
  check(tag + ': the tint is fb-changed over 1.2 s', end.animation === 'fb-changed 1.2s',
    end.animation);
  check(tag + ': the changed prices carry their arrows', end.arrows > 0 &&
    end.arrowWords.length === 2, end.arrows + ' arrows ' + end.arrowWords.join(''));
  check(tag + ': the arrow fades over 1.2 s', end.arrowAnimation === 'fb-gone 1.2s',
    end.arrowAnimation);
  check(tag + ': the line counts the prices', end.line.endsWith(' · ' + want) && end.countTinted,
    end.line);

  await wait(3000);
  const at2 = await edges(page, watched);
  const gone = await endState(page);
  check(tag + ': 3 seconds on, no tint and no arrow is left',
    gone.anyTint === 0 && gone.anyArrow === 0, gone);
  check(tag + ': the count stands, untinted', gone.line.endsWith(want) && !gone.countTinted,
    gone.line);
  check(tag + ': no column head, cell or row moves as the arrows come', still(shift(at0, at1)),
    shift(at0, at1));
  check(tag + ': no column head, cell or row moves as the arrows go', still(shift(at1, at2)),
    shift(at1, at2));
  if (at0.top !== at1.top || at1.top !== at2.top) {
    note(tag + ': the table\'s top stands at ' + at0.top + ' under the run, ' + at1.top +
      ' as the marks show and ' + at2.top + ' after');
  }
  await shot(page, tag + '-after');
  await page.context().close();
  return clip;
}

/* The Screen's first ten rows from the Fair band to the end, as a picture. */
async function tableClip(page) {
  const box = await page.evaluate(() => {
    const table = document.querySelector('#screen table');
    const band = Array.from(table.querySelectorAll('thead th'))
      .find((th) => /Fair band/.test(th.textContent)).getBoundingClientRect();
    const rows = table.querySelectorAll('tbody tr');
    const last = rows[Math.min(9, rows.length - 1)].getBoundingClientRect();
    const t = table.getBoundingClientRect();
    return { x: band.left, y: band.top, width: t.right - band.left, height: last.bottom - band.top };
  });
  return page.screenshot({ clip: box });
}

/* ------------------------------------------------------------------ the full run */

/* A full refresh: Keep reading lifts the layer, the bar stays in the status line and the tables
   fade; at the end the line counts the prices and the values. */
async function fullRun(scheme) {
  const tag = 'full-' + scheme;
  const page = await open({ scheme });
  const s = await stub(page);
  await ready(page);
  running(s, 'full', null, 'fetch', 320, 1558);
  await page.click('button[aria-label="Refresh all"]');
  await page.waitForSelector('.app-layer.is-on');
  await wait(250);
  const layer = await layerState(page);
  check(tag + ': the layer is up, titled Refreshing all, with Keep reading',
    layer.title === 'Refreshing all' && layer.buttons.join('|') === 'Cancel|Keep reading',
    layer.buttons);
  check(tag + ': the sentence names Keep reading', layer.say ===
    'The page is locked until the refresh ends. Keep reading removes the lock; the refresh goes on.',
    layer.say);
  await shot(page, tag + '-layer');

  await page.click('.app-layer button:has-text("Keep reading")');
  await wait(300);
  const kept = await page.evaluate(() => ({
    on: !!document.querySelector('.app-layer.is-on'),
    inert: document.querySelector('main.app-page').inert,
    bar: !!document.querySelector('#controls .fb-run'),
    faded: document.getElementById('screen').classList.contains('is-recomputing'),
    cancel: Array.from(document.querySelectorAll('#header button')).some((b) =>
      b.textContent === 'Cancel')
  }));
  check(tag + ': Keep reading lifts the layer', !kept.on && !kept.inert, kept);
  check(tag + ': the bar stays in the status line, Cancel in the header',
    kept.bar && kept.cancel, kept);
  check(tag + ': the tables fade under the run', kept.faded);
  await shot(page, tag + '-kept');

  const statistics = await menuPoint(page, 'Statistics');
  await page.mouse.click(statistics.x, statistics.y);
  await wait(300);
  check(tag + ': the menu answers after Keep reading',
    (await shownView(page)).visible.join() === 'statistics');
  await page.click('#header .fb-hdr__view:has-text("Screen")');
  await wait(300);

  running(s, 'full', null, 'value', 1400, 1558);
  await wait(2500);
  check(tag + ': the layer stays off for the run kept', !(await layerState(page)).on);
  s.alter = changes(s, 4, 0.02, true);
  ended(s, FULL_CALIBRATION);
  await page.waitForSelector('#screen td.fb-changed', { timeout: 6000 });
  const end = await endState(page);
  await freeze(page);
  await shot(page, tag + '-end');
  await thaw(page);
  const want = ' · ' + s.counted.prices.toLocaleString('en-US') + ' prices changed, ' +
    s.counted.values.toLocaleString('en-US') + ' values changed';
  check(tag + ': the line counts the prices and the values', end.line.endsWith(want), end.line);
  const band = await page.evaluate(() => document.querySelectorAll(
    '#screen td.fb-screen__band.fb-changed, #screen td.fb-screen__mech.fb-changed').length);
  check(tag + ': a changed value tints its band and its value', band > 0, band + ' cells');
  await page.context().close();
}

/* ------------------------------------------------------------------ the named run */

/* A revalue of one named company, an agent's: no layer and no fade while it runs; at its end
   that row's cells tinted and no count in the line. */
async function namedRun(scheme) {
  const tag = 'named-' + scheme;
  const page = await open({ scheme });
  const s = await stub(page);
  await ready(page);
  const rows = await page.evaluate(() => FairbandPage.rows().slice(0, 12));
  const named = rows.find((r) => typeof r.price === 'number' && typeof r.fairValue === 'number');
  running(s, 'revalue', [named.ticker], 'value', 0, 1);
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await page.waitForSelector('#controls .fb-run', { timeout: 5000 });
  await wait(250);
  const alive = await page.evaluate(() => ({
    layer: !!document.querySelector('.app-layer.is-on'),
    faded: Array.from(document.querySelectorAll('.is-recomputing')).map((e) => e.id),
    inert: document.querySelector('main.app-page').inert
  }));
  check(tag + ': no layer, no fade, nothing inert', !alive.layer && alive.faded.length === 0 &&
    !alive.inert, alive);
  await shot(page, tag + '-running');

  s.alter = (rs) => rs.map((r) => r.ticker !== named.ticker ? r : Object.assign({}, r, {
    price: Math.round(r.price * 1.015 * 100) / 100,
    priceToValue: Math.round(r.price * 1.015 / r.fairValue * 100) / 100
  }));
  ended(s, null);
  await page.waitForSelector('#screen td.fb-changed', { timeout: 6000 });
  const end = await endState(page);
  await freeze(page);
  await shot(page, tag + '-end');
  await thaw(page);
  check(tag + ': only the named row is tinted', end.tintedRows.join() === named.ticker,
    end.tintedRows);
  check(tag + ': its price carries its arrow', end.arrows === 1 && end.arrowWords[0] === '▲');
  check(tag + ': the line adds no count', !/changed/.test(end.line), end.line);
  await page.context().close();
}

/* ------------------------------------------------------------------ Statistics */

/* For each grouping, a group's name opens the Screen on its filter and the Screen counts the
   group's Companies; the links at rest, under the pointer, and faded while a grouping loads. */
async function statistics(scheme) {
  const tag = 'statistics-' + scheme;
  const page = await open({ scheme });
  const s = await stub(page);
  await ready(page, '#statistics');
  for (const by of ['sector', 'industry', 'phase', 'cap']) {
    if ((await page.evaluate(() => location.hash)) !== '#statistics') {
      await page.click('#header .fb-hdr__view:has-text("Statistics")');
    }
    await page.waitForSelector('.app-groups__table');
    await page.selectOption('.app-groups select', by);
    await page.waitForFunction((by) => {
      const g = document.querySelector('.app-groups');
      const head = document.querySelector('.app-groups__table th');
      return g && !g.classList.contains('is-loading') && head &&
        head.textContent === { sector: 'Sector', industry: 'Industry', phase: 'Phase',
          cap: 'Cap band' }[by];
    }, by);
    const group = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('.app-groups__table tbody tr'))
        .filter((tr) => tr.querySelector('a.app-link'));
      const tr = rows[Math.floor(rows.length / 2)];
      return { name: tr.querySelector('a').textContent,
        count: Number(tr.children[1].textContent.replace(/,/g, '')) };
    });
    if (by === 'sector') {
      await shot(page, tag + '-rest');
      await page.hover('.app-groups__table a.app-link >> nth=0');
      await shot(page, tag + '-hover');
      const looks = await page.evaluate(() => {
        const a = document.querySelector('.app-groups__table a.app-link');
        const b = document.querySelectorAll('.app-groups__table a.app-link')[1];
        const st = (e) => { const c = getComputedStyle(e); return c.color + ' ' + c.textDecorationLine; };
        return { hovered: st(a), rest: st(b) };
      });
      note(tag + ': a link at rest ' + looks.rest + ', under the pointer ' + looks.hovered);
      await page.mouse.move(0, 0);
    }
    await page.click(`.app-groups__table a.app-link:text-is("${group.name}")`);
    await wait(400);
    const view = await shownView(page);
    const shown = await page.evaluate(() => {
      const b = document.querySelector('.fb-screen__count b');
      return b ? Number(b.textContent.replace(/,/g, '')) : null;
    });
    check(tag + ': ' + by + ' ' + group.name + ' opens the Screen with its ' + group.count +
      ' companies', view.visible.join() === 'screen' && view.hash === '' &&
      shown === group.count, { view, shown });
    if (by === 'sector') await shot(page, tag + '-opened');
  }
  await page.click('#header .fb-hdr__view:has-text("Statistics")');
  await page.waitForSelector('.app-groups__table');
  s.statsDelay = 2500;
  await page.selectOption('.app-groups select', 'sector');
  await page.waitForSelector('.app-groups.is-loading');
  await wait(200);
  const faded = await page.evaluate(() => {
    const a = document.querySelector('.app-groups__table a.app-link');
    const probe = document.createElement('span');
    probe.style.color = 'var(--ink-faint)';
    document.body.appendChild(probe);
    const faint = getComputedStyle(probe).color;
    probe.remove();
    return { link: getComputedStyle(a).color, faint };
  });
  check(tag + ': a link fades to ink-faint while a grouping loads', faded.link === faded.faint,
    faded);
  await shot(page, tag + '-loading');
  await page.context().close();
}

/* ------------------------------------------------------------------ the layer's own look */

/* The layer at `width`: the panel inside the window's gutters; its fade out with the scrim; a
   second lock, whose panel takes the focus again. */
async function layerLook(scheme, width, kind) {
  const tag = 'layer-' + kind + '-' + scheme + '-' + width;
  const page = await open({ scheme, width, height: 700 });
  const s = await stub(page);
  await ready(page);
  running(s, kind, null, kind === 'price' ? 'quotes' : 'fetch', 420, 1558);
  await page.click(kind === 'price' ? 'button[aria-label="Refresh prices"]'
    : 'button[aria-label="Refresh all"]');
  await page.waitForSelector('.app-layer.is-on');
  await wait(250);
  const layer = await layerState(page);
  const p = layer.panelRect;
  check(tag + ': the panel stands inside 16px gutters', p.left >= 16 - 0.5 &&
    p.right <= width - 16 + 0.5 && p.top >= 0 && p.bottom <= 700, p);
  check(tag + ': the panel holds the focus', layer.focusPanel);
  await shot(page, tag);

  ended(s, kind === 'price' ? PRICE_CALIBRATION : FULL_CALIBRATION);
  await page.waitForFunction(() => !document.querySelector('.app-layer.is-on'), null,
    { polling: 'raf', timeout: 6000 });
  const fading = await page.evaluate(() => {
    const layer = document.querySelector('.app-layer');
    const fade = document.getAnimations().find((a) => a.transitionProperty === 'opacity' &&
      a.effect && a.effect.target === layer);
    if (fade) { fade.pause(); fade.currentTime = 75; }
    return {
      found: !!fade, opacity: Number(getComputedStyle(layer).opacity),
      panel: !!layer.querySelector('.app-layer__panel'),
      hidden: layer.getAttribute('aria-hidden'), inert: layer.inert
    };
  });
  check(tag + ': the panel fades out with the scrim', fading.found && fading.panel &&
    fading.opacity > 0 && fading.opacity < 1 && fading.hidden === 'true' && fading.inert,
    fading);
  await shot(page, tag + '-fading');
  await page.evaluate(() => document.getAnimations().forEach((a) => {
    if (a.transitionProperty) a.finish();
  }));
  await wait(1600);

  running(s, 'price', null, 'quotes', 100, 1558);
  await page.click('button[aria-label="Refresh prices"]');
  await page.waitForSelector('.app-layer.is-on');
  await wait(250);
  const second = await layerState(page);
  check(tag + ': a second lock draws its panel and gives it the focus',
    second.on && second.focusPanel && second.title === 'Refreshing prices', second);
  await shot(page, tag + '-second');
  await page.context().close();
}

/* ------------------------------------------------------------------ the page under the layer */

/* With the Methodology view open, scrolled, and the layer up: the wheel over the scrim and over
   the panel, and the keys that scroll, move nothing under it. */
async function underLayer(scheme) {
  const tag = 'under-' + scheme;
  const page = await open({ scheme });
  const s = await stub(page);
  await ready(page, '#methodology');
  await page.waitForFunction(() => document.getElementById('methodology').scrollHeight > 2000);
  await page.evaluate(() => { document.getElementById('methodology').scrollTop = 1200; });
  running(s, 'price', null, 'quotes', 100, 1558);
  await page.click('button[aria-label="Refresh prices"]');
  await page.waitForSelector('.app-layer.is-on');
  await wait(250);
  const where = () => page.evaluate(() => ({
    methodology: document.getElementById('methodology').scrollTop,
    document: document.scrollingElement.scrollTop,
    scrolled: Array.from(document.querySelectorAll('*')).filter((e) => e.scrollTop > 0)
      .map((e) => (e.id || e.className) + ':' + e.scrollTop)
  }));
  const before = await where();
  await page.mouse.move(200, 300);
  for (let i = 0; i < 3; i++) { await page.mouse.wheel(0, 500); await wait(100); }
  await page.mouse.move(WIDE / 2, HIGH / 2);
  for (let i = 0; i < 3; i++) { await page.mouse.wheel(0, 500); await wait(100); }
  for (const key of ['PageDown', 'Space', 'ArrowDown', 'End']) await page.keyboard.press(key);
  await wait(400);
  const after = await where();
  check(tag + ': the wheel and the keys scroll nothing under the layer',
    JSON.stringify(before) === JSON.stringify(after), { before, after });
  await shot(page, tag);
  await page.context().close();
}

/* ------------------------------------------------------------------ the company page's head */

/* The head's price on a run's end that changed it: the arrow before it, and the price's own
   place unmoved as the arrow comes and goes, at `width`. */
async function companyHead(scheme, width) {
  const tag = 'company-' + scheme + '-' + width;
  const page = await open({ scheme, width, height: 700, scale: 2 });
  const s = await stub(page);
  await ready(page);
  const symbol = await page.evaluate(() => {
    const r = FairbandPage.rows().find((x) => typeof x.price === 'number' && x.price > 1000 &&
      x.price < 9000);
    return r.ticker;
  });
  await page.goto(BASE + '/#company/' + encodeURIComponent(symbol));
  await page.waitForSelector('.app-company__quote p.figure-lg');
  await wait(500);
  const place = () => page.evaluate(() => {
    const p = document.querySelector('.app-company__quote p.figure-lg');
    const text = p.lastChild;
    const range = document.createRange();
    range.selectNodeContents(text);
    const r = range.getBoundingClientRect();
    const arrow = p.querySelector('.fb-screen__move');
    return {
      left: Math.round(r.left * 100) / 100, right: Math.round(r.right * 100) / 100,
      top: Math.round(r.top * 100) / 100, text: text.textContent,
      arrow: arrow ? { size: getComputedStyle(arrow).fontSize, word: arrow.textContent } : null,
      tinted: p.classList.contains('fb-changed')
    };
  });
  const at0 = await place();
  const price = await page.evaluate((symbol) => FairbandPage.rows()
    .find((x) => x.ticker === symbol).price, symbol);
  running(s, 'price', null, 'quotes', 100, 1558);
  await page.click('button[aria-label="Refresh prices"]');
  await page.waitForSelector('.app-layer.is-on');
  s.detail = { symbol, price: Math.round(price * 1.01 * 100) / 100 };
  ended(s, PRICE_CALIBRATION);
  await page.waitForSelector('.app-company__quote .fb-screen__move',
    { state: 'attached', timeout: 6000 });
  const at1 = await place();
  await freeze(page);
  await page.waitForFunction(() => !document.querySelector('.app-layer.is-on') &&
    getComputedStyle(document.querySelector('.app-layer')).visibility === 'hidden');
  const head = await page.evaluate(() => document.querySelector('.app-company__head')
    .getBoundingClientRect().toJSON());
  await shot(page, tag + '-arrow', { clip: { x: 0, y: Math.max(0, head.top - 8),
    width, height: head.height + 16 } });
  await shot(page, tag + '-page');
  await thaw(page);
  await wait(3000);
  const at2 = await place();
  check(tag + ': the head marks the price with its arrow', at1.tinted && at1.arrow &&
    at1.arrow.word === '▲', at1);
  note(tag + ': the arrow is ' + (at1.arrow && at1.arrow.size) + ' beside the price ' + at1.text);
  check(tag + ': the price does not move as the arrow comes', Math.abs(at1.left - at0.left) < 0.5,
    { before: at0.left, during: at1.left });
  check(tag + ': the price does not move as the arrow goes', Math.abs(at2.left - at1.left) < 0.5 &&
    Math.abs(at2.top - at1.top) < 0.5, { during: at1, after: at2 });
  await page.context().close();
}

/* ------------------------------------------------------------------ the tint against the mockup */

/* The mockup's table with its grey tint at its start beside the page's, in one picture for each
   theme, and the two greys as they draw over their grounds. */
async function tint(scheme, clip) {
  const tag = 'tint-' + scheme;
  const page = await open({ scheme });
  const grey = {};
  if (MOCKUP) {
    await page.goto('file://' + path.resolve(MOCKUP));
    await page.evaluate((scheme) => {
      document.documentElement.dataset.theme = scheme;
      document.documentElement.dataset.tint = 'grey';
      document.querySelectorAll('#view tbody tr').forEach((tr, i) => {
        if (i % 3 === 0) tr.querySelectorAll('td.num')[2].classList.add('is-changed');
      });
    }, scheme);
    await freeze(page);
    grey.mockup = await page.evaluate(drawn, '#view td.is-changed');
    const box = await page.evaluate(() => {
      const t = document.querySelector('#view table');
      const band = t.querySelectorAll('thead th')[3].getBoundingClientRect();
      const r = t.getBoundingClientRect();
      return { x: band.left, y: r.top, width: r.right - band.left, height: r.height };
    });
    const mock = await page.screenshot({ clip: box });
    await page.setContent('<body style="margin:0;padding:12px;background:#888;display:flex;' +
      'gap:12px;align-items:flex-start;font:12px sans-serif">' +
      '<figure style="margin:0"><figcaption>mockup v3</figcaption><img src="data:image/png;base64,' +
      mock.toString('base64') + '"></figure><figure style="margin:0"><figcaption>the page' +
      '</figcaption><img src="data:image/png;base64,' + clip.toString('base64') + '"></figure></body>');
    await shot(page, tag, { fullPage: true });
  }
  const live = await open({ scheme });
  const s = await stub(live);
  await ready(live);
  running(s, 'price', null, 'quotes', 0, 1558);
  await live.click('button[aria-label="Refresh prices"]');
  await live.waitForSelector('.app-layer.is-on');
  s.alter = changes(s, 3, 0.012, false);
  ended(s, PRICE_CALIBRATION);
  await live.waitForSelector('#screen td.fb-changed', { timeout: 6000 });
  await freeze(live);
  grey.page = await live.evaluate(drawn, '#screen td.fb-changed');
  note(tag + ': the tint at its start over its ground, mockup ' + (grey.mockup || 'not given') +
    ', page ' + grey.page);
  await live.context().close();
  await page.context().close();
}

/* The colour a tinted cell draws at its start: its background, in whatever space the browser
   computes it (an animated colour reads in oklab), painted over the first ground under it on a
   canvas of one pixel, as hex. Runs in the page. */
function drawn(selector) {
  const cell = document.querySelector(selector);
  let ground = 'rgb(255, 255, 255)';
  for (let e = cell.parentElement; e; e = e.parentElement) {
    const c = getComputedStyle(e).backgroundColor;
    if (c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') { ground = c; break; }
  }
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const paint = canvas.getContext('2d');
  paint.fillStyle = ground;
  paint.fillRect(0, 0, 1, 1);
  paint.fillStyle = getComputedStyle(cell).backgroundColor;
  paint.fillRect(0, 0, 1, 1);
  const [r, g, b] = paint.getImageData(0, 0, 1, 1).data;
  return '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('');
}

/* ------------------------------------------------------------------ the meters */

const VALUES = [9.99, 61.77, 1587.0];
const RATIOS = [0.2, 0.45, 0.5, 0.88, 0.9, 0.95, 1.0, 1.1, 1.12, 1.55, 1.6, 2.76];
const WIDTHS = [256, 380];

/* The word of a price ÷ value under policy v19's edges for a Narrow moat. */
function word(x) {
  return x < 0.7 ? 'well-below' : x < 0.9 ? 'below' : x <= 1.1 ? 'near' : x < 1.35 ? 'above'
    : 'well-above';
}

function meterPage(cases) {
  return '<!doctype html><html lang="en"><head><meta charset="utf-8">' +
    '<link rel="stylesheet" href="/static/design-system/fonts/fonts.css">' +
    '<link rel="stylesheet" href="/static/design-system/tokens/tokens.css">' +
    '<link rel="stylesheet" href="/static/design-system/components/bundle.css">' +
    '<style>body{margin:0;padding:16px;background:var(--surface);color:var(--ink)}' +
    '.grid{display:flex;flex-wrap:wrap;gap:12px}' +
    '.cell{padding:12px;background:var(--surface-raised);border:1px solid var(--hairline);' +
    'border-radius:var(--radius-lg)}.cell>p{margin:0 0 8px;color:var(--ink-faint)}</style>' +
    '</head><body><div id="root"></div>' +
    '<script src="/static/vendor/react.production.min.js"></script>' +
    '<script src="/static/vendor/react-dom.production.min.js"></script>' +
    '<script src="/static/design-system/components/bundle.js"></script>' +
    '<script>var cases = ' + JSON.stringify(cases) + '; var h = React.createElement;' +
    'ReactDOM.createRoot(document.getElementById("root")).render(h("div", { className: "grid" },' +
    ' cases.map(function (c) { return h("div", { key: c.id, className: "cell", "data-case": c.id,' +
    ' style: { width: c.width + "px" } }, h("p", { className: "caption" }, c.title),' +
    ' h(Fairband.BandMeter, c.props)); })));</script></body></html>';
}

/* The matrix of the brief: each price at each ratio of each value, at each width. By the
   rectangles drawn: the band's two labels apart, neither on the price marker's dot (its 2px ring
   included), and nothing outside the meter. */
async function meters(scheme) {
  const cents = (x) => Math.round(x * 100) / 100;
  const cases = [];
  for (const width of WIDTHS) {
    for (const value of VALUES) {
      for (const ratio of RATIOS) {
        const price = cents(value * ratio);
        cases.push({
          id: width + '/' + value + '/' + ratio, width,
          title: ratio.toFixed(2) + ' × $' + value + ' at ' + width + 'px',
          props: {
            low: cents(value * 0.9), high: cents(value * 1.1), fairValue: value,
            buyLevel: cents(value * 0.7), trimLevel: cents(value * 1.35), price,
            designation: word(price / value), showScale: false, width,
            gap: (price / value).toFixed(2) + ' × the mechanical value'
          }
        });
      }
    }
  }
  const page = await open({ scheme, width: WIDE, height: 900 });
  await page.route(BASE + '/look/meters.html', (r) => r.fulfill({
    contentType: 'text/html', body: meterPage(cases)
  }));
  await page.goto(BASE + '/look/meters.html');
  await page.waitForSelector('[data-case] .fb-band__track');
  await page.evaluate(() => document.fonts.ready.then(() => true));
  const got = await page.evaluate(() => Array.from(document.querySelectorAll('[data-case]'))
    .map((cell) => {
      const rect = (e) => e.getBoundingClientRect().toJSON();
      const mark = rect(cell.querySelector('.fb-band__price-mark'));
      const centre = mark.left + mark.width / 2;
      const brk = cell.querySelector('.fb-band__break');
      return {
        id: cell.dataset.case, band: rect(cell.querySelector('.fb-band')),
        track: rect(cell.querySelector('.fb-band__track')),
        low: rect(cell.querySelector('.fb-band__tier-label--low')),
        high: rect(cell.querySelector('.fb-band__tier-label--high')),
        dot: { left: centre - 7.5, right: centre + 7.5, top: mark.top - 8, bottom: mark.top + 7 },
        brk: brk ? rect(brk) : null, nan: /NaN/.test(cell.innerHTML)
      };
    }));
  if (scheme === 'dark') {
    const E = 0.05;
    const meet = (a, b) => a.left < b.right - E && b.left < a.right - E && a.top < b.bottom - E &&
      b.top < a.bottom - E;
    const inside = (a, b) => a.left >= b.left - E && a.right <= b.right + E;
    const bad = { apart: [], dot: [], inside: [], nan: [] };
    for (const m of got) {
      if (meet(m.low, m.high)) bad.apart.push(m.id);
      if (meet(m.low, m.dot) || meet(m.high, m.dot)) bad.dot.push(m.id);
      const out = ['low', 'high', 'dot'].filter((k) => !inside(m[k], m.band))
        .concat(m.brk && !inside(m.brk, m.track) ? ['break'] : []);
      if (out.length) bad.inside.push(m.id + ' ' + out.join('+'));
      if (m.nan) bad.nan.push(m.id);
    }
    check('meters: ' + got.length + ' meters, the two labels apart', bad.apart.length === 0,
      bad.apart);
    check('meters: no label on the price marker\'s dot', bad.dot.length === 0, bad.dot);
    check('meters: nothing leaves the meter', bad.inside.length === 0, bad.inside);
    check('meters: no NaN in the markup', bad.nan.length === 0, bad.nan);
  }
  for (const width of WIDTHS) {
    const box = await page.evaluate((width) => {
      const cells = Array.from(document.querySelectorAll('[data-case]'))
        .filter((c) => c.dataset.case.startsWith(width + '/'));
      const rs = cells.map((c) => c.getBoundingClientRect());
      const top = Math.min(...rs.map((r) => r.top));
      const bottom = Math.max(...rs.map((r) => r.bottom));
      return { x: 0, y: top + window.scrollY - 8, width: document.documentElement.clientWidth,
        height: bottom - top + 16 };
    }, width);
    await shot(page, 'meters-' + scheme + '-' + width, { clip: box, fullPage: true });
  }
  await page.context().close();
}

/* ------------------------------------------------------------------ the run */

const ONLY = process.env.LOOK_ONLY ? process.env.LOOK_ONLY.split(',') : null;
const runs = (part) => !ONLY || ONLY.includes(part);
try {
  if (runs('meters')) {
    await meters('dark');
    await meters('light');
  }
  const clips = {};
  if (runs('price') || runs('tint')) {
    clips.dark = await priceRun('dark', false);
    clips.light = await priceRun('light', false);
  }
  if (runs('price')) {
    await priceRun('dark', true);
    await priceRun('light', true);
  }
  if (runs('tint')) {
    await tint('dark', clips.dark);
    await tint('light', clips.light);
  }
  if (runs('full')) {
    await fullRun('dark');
    await fullRun('light');
  }
  if (runs('named')) {
    await namedRun('dark');
    await namedRun('light');
  }
  if (runs('statistics')) {
    await statistics('dark');
    await statistics('light');
  }
  if (runs('layer')) {
    for (const scheme of ['dark', 'light']) {
      for (const width of [WIDE, 375]) {
        await layerLook(scheme, width, 'price');
        await layerLook(scheme, width, 'full');
      }
    }
  }
  if (runs('under')) await underLayer('dark');
  if (runs('company')) {
    for (const width of [WIDE, 375]) {
      await companyHead('dark', width);
      await companyHead('light', width);
    }
  }
} catch (e) {
  check('the look ran to its end', false, e.stack || String(e));
}
await browser.close();
console.log(failures.length ? failures.length + ' failed' : 'all passed');
process.exit(failures.length ? 1 : 0);
