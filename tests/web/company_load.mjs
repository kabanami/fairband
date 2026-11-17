// The company page's loader driven in node (the company page's design, 7.1 and 7.5), for
// tests/web/test_company_load.py: the bundle, app.js, finder.js, controls.js and company.js are
// loaded in the page's order, with a stub React, a stub ReactDOM whose roots keep what they last
// drew, the few browser objects the scripts touch (each view's panel one object whose `hidden`
// controls.js sets, the hash, the history the views replace) and a fetch of the driver's own,
// answered only when a step answers it, so the steps say exactly when each read lands. The reads
// the header and the screen start as the scripts load are dropped: no step answers them. The
// tabs' functions are the driver's own, so the trace reads what the page holds: each draws
// { tab, mark, price }, the mark of the tab's answer it was handed and the price of the detail.
//
// The steps, a JSON list on stdin, each one object:
//   {"do": "show", "symbol", "tab", "id"?}  a link or a tab's button opens the company page there,
//                                           on the Research tab at the report `id` where given
//                                           (FairbandPage.show, controls.js)
//   {"do": "hash", "hash"}                  the browser's Back or Forward, or a link, moves the
//                                           hash to `hash` (#company/LFOX, # for the screen, a
//                                           report's old address #report/LFOX): controls.js
//                                           reads it
//   {"do": "scroll", "top"}                 the reader scrolls the company page's panel down to
//                                           `top` pixels
//   {"do": "again"}                         the loader runs on the company and tab shown, as a
//                                           refresh's end and a note taken in the head run it
//   {"do": "answer", "url", "status", "body"}  the oldest fetch in flight to `url` answers
//   {"do": "fail", "url", "message"}        the oldest fetch in flight to `url` fails, as on the
//                                           network
//   {"do": "notes"}                         the head's Notes control is pressed: its box opens
//   {"do": "watch"}                         the head's Watchlists ▾ is pressed, on the company alone
//                                           (FairbandPage.watch): its popup opens
// After each step and the work it sets off, the trace on stdout gains what the step fetched (each
// request's method and path), the paths still in flight, the companies the step handed
// FairbandPage.notesShown, the hash, whether the company page's panel shows and how far down it
// is scrolled, the popups drawn (the watchlist popup, WatchMenu, and the Notes box, NotesBox),
// and what the company page draws: faded or not, the sentence of a failed read, the head's
// ticker and price, the tab selected and what the open tab's function drew.
//
//   node company_load.mjs <bundle.js> <app.js> <finder.js> <controls.js> <company.js>
//     < steps.json  > trace.json
import { readFileSync } from 'node:fs';

const [bundle, app, finder, controls, company] = process.argv.slice(2, 7)
  .map((path) => readFileSync(path, 'utf8'));
const steps = JSON.parse(readFileSync(0, 'utf8'));
const later = globalThis.setTimeout; // the driver's own wait for the work a step sets off

const React = {
  Fragment: Symbol('Fragment'),
  createElement(type, given, ...children) {
    return { type, props: Object.assign({}, given, { children }) };
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
const listeners = {}; // the window's listeners by event
const document = {
  hidden: false,
  body: { appendChild(node) { return node; } },
  createElement() { return { appended: true }; },
  getElementById(id) {
    return panels[id] || (panels[id] = { id, hidden: false, classList: { toggle() {} } });
  },
  addEventListener() {},
};
const location = { hash: '', pathname: '/' };
const history = {
  replaceState(state, title, url) {
    const at = url.indexOf('#');
    location.hash = at === -1 ? '' : url.slice(at);
  },
};

let inFlight = []; // the fetches not yet answered, oldest first: { url, resolve, reject }
let fetched = []; // the requests the current step made
const fetch = (url, init) => new Promise((resolve, reject) => {
  fetched.push([(init && init.method) || 'GET', url]);
  inFlight.push({ url, resolve, reject });
});

const window = {
  React, ReactDOM, document, fetch, innerWidth: 1600, innerHeight: 1100,
  addEventListener(event, listener) { (listeners[event] = listeners[event] || []).push(listener); },
};
new Function('window', 'React', bundle)(window, React);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'document', 'fetch', app)(
  window, React, ReactDOM, window.Fairband, document, fetch);
const P = window.FairbandPage;
new Function('window', 'React', 'ReactDOM', 'Fairband', 'FairbandPage', 'document', 'fetch',
  finder)(window, React, ReactDOM, window.Fairband, P, document, fetch);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'FairbandPage', 'document', 'fetch',
  'history', 'location', controls)(
  window, React, ReactDOM, window.Fairband, P, document, fetch, history, location);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'FairbandPage', 'document', 'fetch',
  company)(window, React, ReactDOM, window.Fairband, P, document, fetch);
inFlight = []; fetched = []; // the header's and the screen's own reads, which no step answers

// The tabs' functions: each draws what it was handed.
for (const tab of ['overview', 'financials', 'estimates', 'research']) {
  P.companyPage.draw[tab] = (answer, detail) => (
    { type: 'drawn', props: { tab, mark: answer.mark, price: detail.result.price } });
}
let shown = []; // the companies the current step handed notesShown
const notesShown = P.notesShown;
P.notesShown = (symbol) => { shown.push(symbol); notesShown(symbol); };

function* elements(tree) {
  if (Array.isArray(tree)) { for (const child of tree) yield* elements(child); return; }
  if (tree && typeof tree === 'object' && tree.props) {
    yield tree;
    yield* elements(tree.props.children);
  }
}

function textOf(tree) {
  if (Array.isArray(tree)) return tree.map(textOf).join('');
  if (tree && typeof tree === 'object' && tree.props) return textOf(tree.props.children);
  return tree === null || tree === undefined || tree === false ? '' : String(tree);
}

function classed(tree, name) {
  return [...elements(tree)].filter((e) => String(e.props.className || '').split(' ').includes(name));
}

const companyRoot = () => roots.find((root) => root.mount === panels.company);

// What the company page draws.
function page() {
  const tree = companyRoot().drawn;
  if (!tree) return null;
  const [head] = classed(tree, 'app-company__head');
  const [sentence] = classed(tree, 'app-note');
  const [drawn] = [...elements(tree)].filter((e) => e.type === 'drawn');
  const [selected] = [...elements(tree)].filter((e) => e.props['aria-selected'] === 'true');
  const [ticker] = classed(head || tree, 'ticker');
  return {
    faded: tree.props.className.split(' ').includes('is-loading'),
    sentence: sentence ? textOf(sentence) : null,
    ticker: ticker ? textOf(ticker) : null,
    price: head ? textOf(classed(head, 'figure-lg')[0]) : null,
    tab: selected ? textOf(selected) : null,
    drawn: drawn ? drawn.props : null,
  };
}

// The popups drawn: the roots app.js made on elements of its own, at the end of the page.
function popups() {
  return roots.filter((root) => root.mount.appended && root.drawn)
    .map((root) => root.drawn.type.name);
}

function answered(step) {
  const at = inFlight.findIndex((call) => call.url === step.url);
  if (at === -1) throw new Error('no fetch in flight to ' + step.url);
  const [call] = inFlight.splice(at, 1);
  if (step.do === 'fail') { call.reject(new TypeError(step.message)); return; }
  const body = step.body;
  call.resolve({
    ok: step.status >= 200 && step.status < 300,
    status: step.status,
    json: () => (body === undefined ? Promise.reject(new SyntaxError('not JSON'))
      : Promise.resolve(body)),
  });
}

// The head's control whose class is `name`, pressed.
function press(name) {
  const [control] = classed(companyRoot().drawn, name);
  control.props.onClick({ currentTarget: { name } });
}

const trace = [];
for (const step of steps) {
  fetched = [];
  shown = [];
  if (step.do === 'show') P.show('company', step.symbol, step.tab, step.id);
  else if (step.do === 'hash') {
    location.hash = step.hash;
    for (const listener of listeners.hashchange || []) listener();
  } else if (step.do === 'scroll') panels.company.scrollTop = step.top;
  else if (step.do === 'again') P.onShow.company();
  else if (step.do === 'answer' || step.do === 'fail') answered(step);
  else if (step.do === 'notes') press('app-notes-open');
  else if (step.do === 'watch') P.watch({ ticker: P.company.symbol }, { name: 'Watchlists' });
  else throw new Error('no step ' + step.do);
  await new Promise((done) => later(done, 0));
  trace.push({
    do: step.do,
    fetched,
    inFlight: inFlight.map((call) => call.url),
    notesShown: shown,
    hash: location.hash,
    shows: !panels.company.hidden,
    scrollTop: panels.company.scrollTop || 0,
    popups: popups(),
    page: page(),
  });
}
process.stdout.write(JSON.stringify(trace));
