// The company page's Research tab driven in node (the Research tab's design, 7.2, 7.3, 7.8 and
// 7.10; Review Focus 5), for tests/web/test_company_research.py: the bundle, app.js and the
// scripts named after it (company.js, report_parts.js, company_research_text.js,
// company_research.js and company_research_records.js) are loaded in the page's order, with a
// stub React whose useState keeps its state from one draw of the tab to the next, as
// financials.mjs's does; a document whose elements, found by id, are those the tab drew, each
// recording whether it was opened and scrolled to; a fetch that answers an address from the
// input's answers, at once or, for an answer marked held, when a release step lets it land, an
// address given a list of answers taking the next at each fetch, the last for every fetch after,
// and never answers any other; a companyPage.redraw that draws the tab again, as the page draws
// it when a series lands; and a window that keeps the listeners added to it, whose localStorage
// is the driver's: none, as page.mjs has and as a browser that keeps nothing has; one whose every
// read and write throws, as a private window's may; or one holding the items given. Whether an
// element found by id is open is kept from one step to the next, as the browser keeps a details'.
//
// The input, a JSON object on stdin: {"store": null | "throws" | {<key>: <value>, ...},
// "answers"?: {<url>: <answer> | [<answer>, ...]}, "steps"}, an answer {"status", "body", "held"?}.
// The steps, a list, each one object:
//   {"do": "stored"}                     storedMarks() is read
//   {"do": "keep", "on"}                 keepMarks(on) is called
//   {"do": "mount", "answer", "detail"}  the tab opens on `answer` and the company's `detail`,
//                                        drawn anew, its state new, as when the reader opens the
//                                        Research tab or comes back to it from another tab
//   {"do": "land", "answer", "detail"}   `answer` lands while the tab is drawn, which the page
//                                        draws as draw.research gives it, keyed on its company:
//                                        another company's opens a new tab, its state new; the
//                                        same company's, another report of it among them, draws
//                                        the tab again, its state kept
//   {"do": "press", "class", "text"}     the drawn tab's element of the class `class` whose text
//                                        is `text` is pressed, the work it sets off is done, and
//                                        the tab is drawn again
//   {"do": "wait"}                       the work set off so far is done (the answers given at once
//                                        land), and the tab is drawn again
//   {"do": "release", "url"}             the oldest fetch of `url` still held lands, the work it
//                                        sets off is done, and the tab is drawn again
//   {"do": "listen"}                     the tab's print listeners are added (openForPrint), as
//                                        its effect adds them once it is drawn
//   {"do": "unlisten"}                   they are taken away, as the effect's cleanup takes them
//   {"do": "event", "name"}              the window's listeners for `name` run (beforeprint,
//                                        afterprint), as the browser runs them around a print
// After each step the trace on stdout gains what it returned (storedMarks' choice), whether it
// threw, the store's items (null for none or one that throws), the requests made (each its
// method and address) and the headers each was sent with, the elements found by id that were
// opened or scrolled to, each {open, scrolled}, whether each element found by id so far is open
// (open), the count of the window's listeners by event, the times companyPage.redraw was called,
// the height each call to reportCharts.groupCharts was given (null for none), and the tree the tab
// draws, each component in it drawn with its props in turn, as page.mjs draws one, so a test
// reads the elements the bundle's components give.
//
//   node research.mjs <bundle.js> <app.js> <script.js> ...  < input.json  > trace.json
import { readFileSync } from 'node:fs';

const [bundle, app, ...scripts] = process.argv.slice(2).map((path) => readFileSync(path, 'utf8'));
const input = JSON.parse(readFileSync(0, 'utf8'));
const later = globalThis.setTimeout; // the driver's own wait for the work a step sets off

let cells = []; // the drawn tab's state, one cell a useState, in the order it calls them
let next = 0; // the cell the next useState reads in this draw
let inside = false; // a component in the tab's tree is drawn: its own state is not the tab's
const React = {
  Fragment: Symbol('Fragment'),
  createElement(type, given, ...children) {
    return { type, props: Object.assign({}, given, { children }) };
  },
  forwardRef(render) { return (given) => render(given, null); },
  memo(component) { return component; },
  useState(initial) {
    if (inside) return [initial, () => {}];
    const at = next++;
    if (!(at in cells)) cells[at] = initial;
    return [cells[at], (value) => { cells[at] = value; }];
  },
  useRef(current) { return { current }; },
  useEffect() {},
  useLayoutEffect() {},
};
const ReactDOM = { createRoot() { return { render() {} }; } };

let touched = {}; // the elements found by id this step, by id: { open, scrolled }
const kept = {}; // whether each element found by id is open, by id, from step to step
let live = null; // the tree the tab last drew, its handlers kept
const document = {
  body: { appendChild(node) { return node; } },
  createElement() { return {}; },
  addEventListener() {},
  getElementById(id) {
    const [found] = [...elements(live)].filter((e) => e.props.id === id);
    if (!found) return null;
    const node = touched[id] || (touched[id] = { open: Boolean(kept[id]), scrolled: false });
    kept[id] = Boolean(kept[id]);
    return {
      tagName: String(found.type).toUpperCase(),
      set open(on) { node.open = on; kept[id] = on; },
      get open() { return kept[id]; },
      scrollIntoView() { node.scrolled = true; },
    };
  },
};

let fetched = []; // the requests the current step made
let headers = []; // the headers each of them was sent with, null for none
const held = []; // the fetches of held answers not yet released, oldest first: { url, land }
const answers = input.answers || {};
const asked = {}; // the fetches of each address so far, for an address given a list of answers
const fetch = (url, init) => {
  fetched.push([(init && init.method) || 'GET', url]);
  headers.push((init && init.headers) || null);
  const entry = answers[url];
  const turn = asked[url] = (asked[url] || 0) + 1;
  const given = Array.isArray(entry) ? entry[Math.min(turn, entry.length) - 1] : entry;
  if (!given) return new Promise(() => {});
  const response = {
    ok: given.status >= 200 && given.status < 300,
    status: given.status,
    json: () => Promise.resolve(given.body),
    blob: () => Promise.resolve(given.body),
  };
  if (!given.held) return Promise.resolve(response);
  return new Promise((land) => { held.push({ url, land: () => land(response) }); });
};
const listening = {}; // the window's listeners by event
const window = {
  React, ReactDOM, document, fetch,
  addEventListener(event, listener) { (listening[event] = listening[event] || []).push(listener); },
  removeEventListener(event, listener) {
    listening[event] = (listening[event] || []).filter((held) => held !== listener);
  },
};

let items = null; // the store's items, where it keeps any
if (input.store === 'throws') {
  const denied = () => { throw new Error('the store is not available'); };
  window.localStorage = { getItem: denied, setItem: denied };
} else if (input.store) {
  items = Object.assign({}, input.store);
  window.localStorage = {
    getItem(key) { return key in items ? items[key] : null; },
    setItem(key, value) { items[key] = String(value); },
  };
}

new Function('window', 'React', bundle)(window, React);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'document', 'fetch', app)(
  window, React, ReactDOM, window.Fairband, document, fetch);
window.FairbandPage.onShow = window.FairbandPage.onShow || {};
for (const script of scripts) {
  new Function('window', 'React', 'ReactDOM', 'Fairband', 'FairbandPage', 'document', 'fetch',
    script)(window, React, ReactDOM, window.Fairband, window.FairbandPage, document, fetch);
}
const T = window.FairbandPage.research;
let redrawn = 0; // the times the tab asked the page to draw again this step
window.FairbandPage.companyPage.redraw = () => {
  redrawn += 1;
  if (tab) draw();
};
let grouped = []; // the height each call to reportCharts.groupCharts was given this step
const groupCharts = window.FairbandPage.reportCharts.groupCharts;
window.FairbandPage.reportCharts.groupCharts = (tables, height) => {
  grouped.push(height === undefined ? null : height);
  return groupCharts(tables, height);
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

let tab = null; // the drawn tab: its component and its props
function draw() {
  next = 0;
  const top = tab.type(tab.props);
  inside = true;
  live = drawn(top);
  inside = false;
}

let unlisten = null; // what takes the tab's print listeners away
const trace = [];
for (const step of input.steps) {
  let result = null;
  let threw = false;
  fetched = [];
  headers = [];
  touched = {};
  redrawn = 0;
  grouped = [];
  try {
    if (step.do === 'stored') result = T.storedMarks();
    else if (step.do === 'keep') T.keepMarks(step.on);
    else if (step.do === 'mount' || step.do === 'land') {
      const given = window.FairbandPage.companyPage.draw.research(step.answer, step.detail);
      if (step.do === 'mount' || !tab || given.props.key !== tab.props.key) cells = [];
      tab = given;
      draw();
    } else if (step.do === 'press') {
      const [pressed] = classed(live, step.class).filter((e) => textOf(e) === step.text);
      if (!pressed) throw new Error('nothing of the class ' + step.class + ' reads ' + step.text);
      pressed.props.onClick({ preventDefault() {}, stopPropagation() {} });
      await new Promise((done) => later(done, 0));
      draw();
    } else if (step.do === 'wait') {
      await new Promise((done) => later(done, 0));
      draw();
    } else if (step.do === 'release') {
      const at = held.findIndex((f) => f.url === step.url);
      if (at < 0) throw new Error('no fetch of ' + step.url + ' is held');
      held.splice(at, 1)[0].land();
      await new Promise((done) => later(done, 0));
      draw();
    } else if (step.do === 'listen') unlisten = T.openForPrint();
    else if (step.do === 'unlisten') unlisten();
    else if (step.do === 'event') {
      for (const listener of listening[step.name] || []) listener();
    } else throw new Error('no step ' + step.do);
  } catch (error) {
    threw = true;
    process.stderr.write(String(error && error.stack) + '\n');
  }
  trace.push({
    do: step.do,
    result,
    threw,
    store: items && Object.assign({}, items),
    fetched,
    headers,
    touched,
    open: Object.assign({}, kept),
    listening: Object.fromEntries(
      Object.entries(listening).map(([event, held]) => [event, held.length])),
    redrawn,
    grouped,
    tree: live,
  });
}
process.stdout.write(JSON.stringify(trace));
