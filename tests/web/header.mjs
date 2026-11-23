// The header and the status line under it driven in node (the company page's design, the decision
// log of 2026-11-17), for tests/web/test_header.py: the bundle, app.js, finder.js and controls.js
// are loaded in the page's order, with a stub React, a stub ReactDOM whose roots keep what they
// last drew, the few browser objects the scripts touch (each view's panel one object whose
// `hidden` controls.js sets, a query that finds no element, as app.js asks for the table's
// scroller when the Watchlists view turns the table to its list, the hash, the history the views
// replace, the window's and the document's listeners, each panel's classes) and a fetch of the
// driver's own, answered only when a step answers it. The reads the scripts start as they load
// stay in flight, so a step can answer the first read of the refresh's state, or the screen's rows
// (/api/screen?sort=ticker&dir=asc). app.js's and controls.js's timers are held until a step fires
// them, and the company page, which has no script here, reads its company's detail as it opens, as
// company.js's loader does first (/api/companies/<symbol>).
//
// The steps, a JSON list on stdin, each one object:
//   {"do": "show", "view", "section"}            a header view, a link or a hash opens `view`
//                                                (FairbandPage.show, controls.js)
//   {"do": "hash", "hash"}                       the browser's Back or Forward, or a link, moves
//                                                the hash to `hash`: controls.js reads it
//   {"do": "answer", "url", "status", "body"}    the oldest fetch in flight to `url` answers
//   {"do": "details"}                            Details ▾ is pressed
//   {"do": "table", "query", "filters"}          the reader types `query` in the Screen's FIND and
//                                                chooses `filters` in its Filters menu
//   {"do": "filter", "filter"}                   FairbandPage.filterScreen(filter) (app.js), as a
//                                                group's name in Statistics calls it
//   {"do": "follow", "name"}                     the Statistics table's link `name` is pressed
//   {"do": "sort", "column"}                     the table's head `column` is pressed: the view
//                                                that shows sorts by it (app.js's sortBy)
//   {"do": "list", "id"}                         the watchlist page's head names the list `id`
//                                                (FairbandPage.selectList, as watchlists.js does)
//   {"do": "tick"}                               the time comes for app.js's and controls.js's
//                                                pending timers: each fires, in the order set
//   {"do": "visibility", "hidden"}               the page is hidden (true), as the browser's tab
//                                                is left, or shown again (false)
// After each step and the work it sets off, the trace on stdout gains the urls fetched since the
// step before (the reads the scripts start as they load are not counted), whether a view's panel
// holds is-recomputing, the delays of app.js's and controls.js's pending timers, the view the
// header marks, the header's views as [id, label], the hash, whether its right slot holds the
// finder, and what the bar under it draws: its class, the status region's words, the words of the
// count of what a run changed (the region's span keyed `changes`, null for none) and whether that
// span takes the tint's class, fb-changed (null for no span), whether Details ▾ stands beside
// them and whether its menu is open, whether the run's bar is drawn, and the notice;
// then the FIND and the filters of the table the screen's root last drew and its rows a run's end
// marked, each [ticker, priceMove] (null before it draws one), the Statistics table's names, each
// [name, the link's href, or null for plain text] (null before it draws one), and, on a press of a
// link, whether the press kept the browser from following it.
//
//   node header.mjs <bundle.js> <app.js> <finder.js> <controls.js>  < steps.json  > trace.json
import { readFileSync } from 'node:fs';

const [bundle, app, finder, controls] = process.argv.slice(2, 6)
  .map((path) => readFileSync(path, 'utf8'));
const steps = JSON.parse(readFileSync(0, 'utf8'));
const later = globalThis.setTimeout; // the driver's own wait for the work a step sets off

const React = {
  Fragment: Symbol('Fragment'),
  // As React: children given after the props win; with none given there, a `children` prop stays
  // (controls.js hands the header its right slot that way).
  createElement(type, given, ...children) {
    const props = Object.assign({}, given);
    if (children.length || !('children' in props)) props.children = children;
    return { type, props };
  },
  forwardRef(render) { return (given) => render(given, null); },
  memo(component) { return component; },
  useState(initial) { return [initial, () => {}]; },
  useRef(current) { return { current }; },
  useEffect() {},
  useLayoutEffect() {},
};
const roots = []; // every root made, with what it last drew
const ReactDOM = {
  createRoot(mount) {
    const root = { mount, drawn: null, render(tree) { root.drawn = tree; } };
    roots.push(root);
    return root;
  },
};
// An element's classes, as the browser's classList: toggle with a force sets or clears one.
function classList() {
  const held = new Set();
  return {
    toggle(name, force) {
      const on = force === undefined ? !held.has(name) : Boolean(force);
      if (on) held.add(name);
      else held.delete(name);
      return on;
    },
    contains(name) { return held.has(name); },
  };
}
const panels = {}; // the page's elements by id, each made once
const documentListeners = {}; // the document's listeners by event
const document = {
  hidden: false,
  body: { appendChild(node) { return node; } },
  createElement() { return { appended: true }; },
  getElementById(id) {
    return panels[id] || (panels[id] = { id, hidden: false, classList: classList() });
  },
  querySelector() { return null; },
  addEventListener(event, listener) {
    (documentListeners[event] = documentListeners[event] || []).push(listener);
  },
};
const location = { hash: '', pathname: '/' };
const history = {
  replaceState(state, title, url) {
    const at = url.indexOf('#');
    location.hash = at === -1 ? '' : url.slice(at);
  },
};
const inFlight = []; // the fetches not yet answered, oldest first: { url, resolve }
const asked = []; // the urls fetched since the step before
const fetch = (url) => new Promise((resolve) => {
  asked.push(url);
  inFlight.push({ url, resolve });
});
const listeners = {}; // the window's listeners by event
const window = {
  React, ReactDOM, document, fetch, innerWidth: 1600, innerHeight: 1100,
  addEventListener(event, listener) { (listeners[event] = listeners[event] || []).push(listener); },
};
// app.js's and controls.js's timers, each held until a tick step fires it: { id, run, ms }, in the
// order set.
const timers = [];
let timerIds = 0;
const clock = {
  setTimeout(run, ms) {
    timers.push({ id: ++timerIds, run, ms });
    return timerIds;
  },
  clearTimeout(id) {
    const at = timers.findIndex((timer) => timer.id === id);
    if (at !== -1) timers.splice(at, 1);
  },
};

new Function('window', 'React', bundle)(window, React);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'document', 'fetch', 'setTimeout',
  'clearTimeout', app)(
  window, React, ReactDOM, window.Fairband, document, fetch, clock.setTimeout, clock.clearTimeout);
const P = window.FairbandPage;
new Function('window', 'React', 'ReactDOM', 'Fairband', 'FairbandPage', 'document', 'fetch',
  finder)(window, React, ReactDOM, window.Fairband, P, document, fetch);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'FairbandPage', 'document', 'fetch',
  'history', 'location', 'setTimeout', 'clearTimeout', controls)(
  window, React, ReactDOM, window.Fairband, P, document, fetch, history, location,
  clock.setTimeout, clock.clearTimeout);
// The view that reads as it opens, the company page, has no script here: its loader reads the
// detail of the company the address names, which no step answers.
P.onShow.company = P.onShow.company ||
  (() => { P.getJson('/api/companies/' + encodeURIComponent(P.company.symbol)); });
asked.length = 0;

function* elements(tree) {
  if (Array.isArray(tree)) { for (const child of tree) yield* elements(child); return; }
  if (tree && typeof tree === 'object' && tree.props) {
    yield tree;
    yield* elements(tree.props.children);
  }
}

function textOf(tree) {
  if (Array.isArray(tree)) return tree.map(textOf).join('');
  if (tree && typeof tree === 'object' && tree.props) {
    return typeof tree.type === 'function' ? textOf(tree.type(tree.props))
      : textOf(tree.props.children);
  }
  return tree === null || tree === undefined || tree === false ? '' : String(tree);
}

const rootOn = (id) => roots.find((root) => root.mount === panels[id]);

// The table the screen's root last drew (app.js's Screen, ScreenTable's props), else null.
function table() {
  const root = rootOn('screen');
  return [...elements(root && root.drawn)].find((e) => 'onFiltersChange' in e.props) || null;
}

// The Statistics table's name cells, the first of each row, else null before it draws one.
function names() {
  const root = rootOn('statistics');
  if (!root || !root.drawn) return null;
  const cells = [...elements(root.drawn)]
    .filter((e) => e.type === 'td' && e.props.className === 'body');
  return cells.length ? cells : null;
}

function answered(step) {
  const at = inFlight.findIndex((call) => call.url === step.url);
  if (at === -1) throw new Error('no fetch in flight to ' + step.url);
  const [call] = inFlight.splice(at, 1);
  call.resolve({
    ok: step.status >= 200 && step.status < 300,
    status: step.status,
    json: () => Promise.resolve(step.body),
  });
}

const trace = [];
for (const step of steps) {
  let prevented = null;
  if (step.do === 'show') P.show(step.view, step.section);
  else if (step.do === 'hash') {
    location.hash = step.hash;
    for (const listener of listeners.hashchange || []) listener();
  } else if (step.do === 'answer') answered(step);
  else if (step.do === 'details') {
    const [button] = [...elements(rootOn('controls').drawn)]
      .filter((e) => e.type === window.Fairband.Button && textOf(e) === 'Details ▾');
    button.props.onClick();
  } else if (step.do === 'table') {
    table().props.onQueryChange(step.query);
    table().props.onFiltersChange(step.filters);
  } else if (step.do === 'filter') P.filterScreen(step.filter);
  else if (step.do === 'follow') {
    const [link] = [...elements(names())]
      .filter((e) => e.type === 'a' && textOf(e) === step.name);
    prevented = false;
    link.props.onClick({ preventDefault() { prevented = true; } });
  } else if (step.do === 'sort') table().props.onSort(step.column);
  else if (step.do === 'list') P.selectList(step.id);
  else if (step.do === 'tick') {
    for (const timer of timers.splice(0)) timer.run();
  } else if (step.do === 'visibility') {
    document.hidden = step.hidden;
    for (const listener of documentListeners.visibilitychange || []) listener();
  } else throw new Error('no step ' + step.do);
  await new Promise((done) => later(done, 0));
  const header = rootOn('header').drawn;
  const bar = [...elements(rootOn('controls').drawn)];
  const [status] = bar.filter((e) => e.props.role === 'status');
  const [changes] = [...elements(status)].filter((e) => e.props.key === 'changes');
  const [notice] = bar.filter((e) => e.type === 'p');
  const drawn = table();
  const cells = names();
  trace.push({
    do: step.do,
    reads: asked.splice(0),
    recomputing: Object.values(panels).some((e) => e.classList.contains('is-recomputing')),
    waits: timers.map((timer) => timer.ms),
    view: header.props.view,
    views: header.props.views.map((v) => [v.id, v.label]),
    hash: location.hash,
    ran: header.props.engineRanAt,
    finder: [...elements(header.props.children)].some((e) => e.type === P.finder.view),
    actions: [...elements(header.props.children)]
      .filter((e) => e.type === window.Fairband.Button)
      .map((e) => e.props['aria-label'] || textOf(e)),
    bar: rootOn('controls').drawn.props.className,
    status: status ? textOf(status) : null,
    changes: changes ? textOf(changes) : null,
    tinted: changes ? String(changes.props.className || '').split(' ').includes('fb-changed')
      : null,
    details: bar.some((e) => e.type === window.Fairband.Button && textOf(e) === 'Details ▾'),
    menu: bar.some((e) => String(e.props.className || '').split(' ').includes('fb-menu--filters')),
    run: bar.some((e) => e.type === window.Fairband.RunProgress),
    notice: notice ? textOf(notice) : null,
    find: drawn ? drawn.props.query : null,
    filters: drawn ? drawn.props.filters : null,
    marked: drawn ? drawn.props.rows.filter((r) => r.changed).map((r) => [r.ticker, r.priceMove])
      : null,
    statistics: cells && cells.map((cell) => {
      const [link] = [...elements(cell)].filter((e) => e.type === 'a');
      return [textOf(cell), link ? link.props.href : null];
    }),
    prevented,
  });
}
process.stdout.write(JSON.stringify(trace));
