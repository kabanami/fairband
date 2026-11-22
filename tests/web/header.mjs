// The header and the status line under it driven in node (the company page's design, the decision
// log of 2026-11-17), for tests/web/test_header.py: the bundle, app.js, finder.js and controls.js
// are loaded in the page's order, with a stub React, a stub ReactDOM whose roots keep what they
// last drew, the few browser objects the scripts touch (each view's panel one object whose
// `hidden` controls.js sets, a query that finds no element, as app.js asks for the table's
// scroller when the Watchlists view turns the table to its list, the hash, the history the views
// replace) and a fetch of the driver's own, answered only when a step answers it. The reads the
// scripts start as they load stay in flight, so a step can answer the first read of the
// refresh's state.
//
// The steps, a JSON list on stdin, each one object:
//   {"do": "show", "view", "section"}            a header view, a link or a hash opens `view`
//                                                (FairbandPage.show, controls.js)
//   {"do": "answer", "url", "status", "body"}    the oldest fetch in flight to `url` answers
//   {"do": "details"}                            Details ▾ is pressed
// After each step and the work it sets off, the trace on stdout gains the view the header marks,
// whether its right slot holds the finder, and what the bar under it draws: its class, the status
// region's words, whether Details ▾ stands beside them and whether its menu is open, whether the
// run's bar is drawn, and the notice.
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
const panels = {}; // the page's elements by id, each made once
const document = {
  hidden: false,
  body: { appendChild(node) { return node; } },
  createElement() { return { appended: true }; },
  getElementById(id) {
    return panels[id] || (panels[id] = { id, hidden: false, classList: { toggle() {} } });
  },
  querySelector() { return null; },
  addEventListener() {},
};
const location = { hash: '', pathname: '/' };
const history = {
  replaceState(state, title, url) {
    const at = url.indexOf('#');
    location.hash = at === -1 ? '' : url.slice(at);
  },
};
const inFlight = []; // the fetches not yet answered, oldest first: { url, resolve }
const fetch = (url) => new Promise((resolve) => { inFlight.push({ url, resolve }); });
// The page's timers never fire: the driver follows no poll.
const window = {
  React, ReactDOM, document, fetch, innerWidth: 1600, innerHeight: 1100, addEventListener() {},
};
const quiet = { setTimeout() { return 0; }, clearTimeout() {} };

new Function('window', 'React', bundle)(window, React);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'document', 'fetch', app)(
  window, React, ReactDOM, window.Fairband, document, fetch);
const P = window.FairbandPage;
new Function('window', 'React', 'ReactDOM', 'Fairband', 'FairbandPage', 'document', 'fetch',
  finder)(window, React, ReactDOM, window.Fairband, P, document, fetch);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'FairbandPage', 'document', 'fetch',
  'history', 'location', 'setTimeout', 'clearTimeout', controls)(
  window, React, ReactDOM, window.Fairband, P, document, fetch, history, location,
  quiet.setTimeout, quiet.clearTimeout);
// The view that reads as it opens, the company page, has no script here: its loader does nothing.
P.onShow.company = P.onShow.company || (() => {});

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
  if (step.do === 'show') P.show(step.view, step.section);
  else if (step.do === 'answer') answered(step);
  else if (step.do === 'details') {
    const [button] = [...elements(rootOn('controls').drawn)]
      .filter((e) => e.type === window.Fairband.Button && textOf(e) === 'Details ▾');
    button.props.onClick();
  } else throw new Error('no step ' + step.do);
  await new Promise((done) => later(done, 0));
  const header = rootOn('header').drawn;
  const bar = [...elements(rootOn('controls').drawn)];
  const [status] = bar.filter((e) => e.props.role === 'status');
  const [notice] = bar.filter((e) => e.type === 'p');
  trace.push({
    do: step.do,
    view: header.props.view,
    ran: header.props.engineRanAt,
    finder: [...elements(header.props.children)].some((e) => e.type === P.finder.view),
    actions: [...elements(header.props.children)]
      .filter((e) => e.type === window.Fairband.Button)
      .map((e) => e.props['aria-label'] || textOf(e)),
    bar: rootOn('controls').drawn.props.className,
    status: status ? textOf(status) : null,
    details: bar.some((e) => e.type === window.Fairband.Button && textOf(e) === 'Details ▾'),
    menu: bar.some((e) => String(e.props.className || '').split(' ').includes('fb-menu--filters')),
    run: bar.some((e) => e.type === window.Fairband.RunProgress),
    notice: notice ? textOf(notice) : null,
  });
}
process.stdout.write(JSON.stringify(trace));
