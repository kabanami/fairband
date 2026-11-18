// The company page's Investor relations tab driven in node (the Investor relations tab's design,
// 7.1, 7.3, 7.4 and 7.6; Review Focus 4 and 5), for tests/web/test_company_investor.py: the bundle,
// app.js and the scripts named after it (company.js, company_investor.js) are loaded in the page's
// order, with a stub React; a document whose company page's panel (#company) keeps how far down it
// is scrolled, and whose other elements, found by id, are those the tab drew, each recording that
// it was scrolled into view; a fetch of the driver's own, answered only when a step answers it, so
// the steps say exactly when each read lands, the reads app.js makes as it loads dropped, as no
// step answers them; a companyPage.redraw that draws the tab again, as the
// page draws it when one of the tab's own reads lands; and a FairbandPage.show that keeps the
// address it is handed in FairbandPage.company and, for the Investor relations tab of the company
// drawn, draws the tab again on the new word, as the page does with no read (company.js, redrawn).
//
// The steps, a JSON list on stdin, each one object:
//   {"do": "draw", "answer", "detail", "word"}  the page draws the tab on `answer` and the
//                                               company's `detail` at the address's word `word`
//                                               (null, 2026Q4, filings): a tab's answer landing,
//                                               another company's, or a change of the word; the
//                                               address is the tab's at that word
//   {"do": "press", "class", "text"}            the drawn tab's element of the class `class` whose
//                                               text is `text` is pressed
//   {"do": "type", "words"}                     `words` are typed in the find box, its whole value
//   {"do": "answer", "url", "status", "body"}   the oldest fetch in flight to `url` answers
//   {"do": "fail", "url", "message"}            the oldest fetch in flight to `url` fails, as on
//                                               the network
//   {"do": "scroll", "top"}                     the reader scrolls the company page's panel down to
//                                               `top` pixels
// After each step and the work it sets off, the trace on stdout gains what the step fetched (each
// request's method and path) and the headers each carried (null for none), the paths still in
// flight, the times companyPage.redraw was called, the addresses FairbandPage.show was handed
// (each [view, symbol, tab, id]), how far down the panel is scrolled, the ids scrolled into view
// (each [id, options]), the data date the page would draw at the tabs' row's right end
// (companyPage.dataDate['investor-relations'] on the answer and the word drawn) and the tree the
// tab draws, each component in it drawn with its props in turn, as page.mjs draws one.
//
//   node investor.mjs <bundle.js> <app.js> <script.js> ...  < steps.json  > trace.json
import { readFileSync } from 'node:fs';

const [bundle, app, ...scripts] = process.argv.slice(2).map((path) => readFileSync(path, 'utf8'));
const steps = JSON.parse(readFileSync(0, 'utf8'));
const later = globalThis.setTimeout; // the driver's own wait for the work a step sets off
const IR = 'investor-relations';

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
const ReactDOM = { createRoot() { return { render() {} }; } };

let live = null; // the tree the tab last drew, its handlers kept
let scrolled = []; // the ids scrolled into view this step
const panel = { id: 'company', scrollTop: 0 }; // the company page's panel, which scrolls
const document = {
  body: { appendChild(node) { return node; } },
  createElement() { return {}; },
  addEventListener() {},
  getElementById(id) {
    if (id === 'company') return panel;
    const [found] = [...elements(live)].filter((e) => e.props.id === id);
    if (!found) return null;
    return { scrollIntoView(how) { scrolled.push([id, how === undefined ? null : how]); } };
  },
};

let inFlight = []; // the fetches not yet answered, oldest first: { url, resolve, reject }
let fetched = []; // the requests the current step made
let headers = []; // the headers each of them carried, null for none
const fetch = (url, init) => new Promise((resolve, reject) => {
  fetched.push([(init && init.method) || 'GET', url]);
  headers.push((init && init.headers) || null);
  inFlight.push({ url, resolve, reject });
});
const window = { React, ReactDOM, document, fetch, addEventListener() {} };

new Function('window', 'React', bundle)(window, React);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'document', 'fetch', app)(
  window, React, ReactDOM, window.Fairband, document, fetch);
window.FairbandPage.onShow = window.FairbandPage.onShow || {};
for (const script of scripts) {
  new Function('window', 'React', 'ReactDOM', 'Fairband', 'FairbandPage', 'document', 'fetch',
    script)(window, React, ReactDOM, window.Fairband, window.FairbandPage, document, fetch);
}
const P = window.FairbandPage;
const C = P.companyPage;
inFlight = []; fetched = []; headers = []; // the screen's own reads as app.js loads, unanswered

let at = null; // what the page draws: { answer, detail, word }
let redrawn = 0; // the times the tab asked the page to draw again this step
C.redraw = () => {
  redrawn += 1;
  if (at) draw();
};
let shows = []; // the addresses FairbandPage.show was handed this step
P.show = (view, symbol, tab, id) => {
  const word = id === undefined ? null : id;
  shows.push([view, symbol, tab, word]);
  P.company = { symbol, tab, id: word };
  if (at && view === 'company' && tab === IR && symbol === at.answer.symbol) {
    at = { ...at, word };
    draw();
  }
};

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
  return [...elements(tree)]
    .filter((e) => String(e.props.className || '').split(' ').includes(name));
}

// The tree with each component in it drawn with its props, as page.mjs draws one.
function drawn(node) {
  if (Array.isArray(node)) return node.map(drawn);
  if (node === null || typeof node !== 'object' || !node.props) return node;
  if (typeof node.type === 'function') return drawn(node.type(node.props));
  const children = drawn(node.props.children);
  return { type: node.type, props: Object.assign({}, node.props, { children }) };
}

function draw() {
  live = drawn(C.draw[IR](at.answer, at.detail, at.word));
}

function answered(step) {
  const found = inFlight.findIndex((call) => call.url === step.url);
  if (found === -1) throw new Error('no fetch in flight to ' + step.url);
  const [call] = inFlight.splice(found, 1);
  if (step.do === 'fail') { call.reject(new TypeError(step.message)); return; }
  const body = step.body;
  call.resolve({
    ok: step.status >= 200 && step.status < 300,
    status: step.status,
    json: () => (body === undefined ? Promise.reject(new SyntaxError('not JSON'))
      : Promise.resolve(body)),
  });
}

const trace = [];
for (const step of steps) {
  fetched = [];
  headers = [];
  redrawn = 0;
  shows = [];
  scrolled = [];
  if (step.do === 'draw') {
    at = { answer: step.answer, detail: step.detail, word: step.word };
    P.company = { symbol: step.answer.symbol, tab: IR, id: step.word };
    draw();
  } else if (step.do === 'press') {
    const [pressed] = classed(live, step.class).filter((e) => textOf(e) === step.text);
    if (!pressed) throw new Error('nothing of the class ' + step.class + ' reads ' + step.text);
    pressed.props.onClick({ preventDefault() {}, stopPropagation() {} });
  } else if (step.do === 'type') {
    const [box] = classed(live, 'app-ir__find');
    if (!box) throw new Error('no find box');
    box.props.onChange({ target: { value: step.words } });
  } else if (step.do === 'answer' || step.do === 'fail') answered(step);
  else if (step.do === 'scroll') panel.scrollTop = step.top;
  else throw new Error('no step ' + step.do);
  await new Promise((done) => later(done, 0));
  trace.push({
    do: step.do,
    fetched,
    headers,
    inFlight: inFlight.map((call) => call.url),
    redrawn,
    shows,
    scrollTop: panel.scrollTop,
    scrolled,
    asOf: at ? C.dataDate[IR](at.answer, at.word) : null,
    tree: live,
  });
}
process.stdout.write(JSON.stringify(trace));
