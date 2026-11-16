// The request button's launch driven in node (spec 2026-11-16 agent launch, 10), for
// tests/web/test_launch_following.py: the bundle and app.js are loaded as tests/web/page.mjs loads
// them, with a stub React and the few browser objects app.js touches, and with a fetch and timers
// of the driver's own. A fetch is answered only when a step answers it, oldest first, and a timer
// runs only when a step fires it, so the steps say exactly when each post and read lands.
//
// One request for AAPL (FairbandPage.asking) is driven, as the drawer drives its company's, with
// launching set up. The steps, a JSON list on stdin, each one object:
//   {"do": "post"}                        Post in Request research's menu, Open Claude Code ticked
//   {"do": "answer", "status", "body"}    the oldest fetch in flight answers
//   {"do": "fail", "message"}             the oldest fetch in flight fails, as on the network
//   {"do": "tick"}                        the oldest timer runs
//   {"do": "stop"}                        the drawer closes or shows another company (stopLaunch)
//   {"do": "landed", "item"}              the view's read of the company lands with its open item
//                                         (followItem), which the line is then drawn with
// After each step and the work it sets off, the trace on stdout gains what the step fetched (each
// request's method, path and JSON body), the fetches still in flight, the delays of the timers set,
// how many times `after` has run, and what Request research draws: the request's error line, and
// the open item's line with its button and whether it is in the error style.
//
//   node following.mjs <bundle.js> <app.js>  < steps.json  > trace.json
import { readFileSync } from 'node:fs';

const [bundle, app] = [process.argv[2], process.argv[3]].map((path) => readFileSync(path, 'utf8'));
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
};
const ReactDOM = { createRoot() { return { render() {} }; } };
const document = {
  body: { appendChild(node) { return node; } },
  createElement() { return {}; },
  getElementById() { return {}; },
  addEventListener() {},
};

let inFlight = []; // the fetches not yet answered, oldest first: { resolve, reject }
let fetched = []; // the requests the current step made
const fetch = (url, init) => new Promise((resolve, reject) => {
  const body = init && init.body !== undefined ? JSON.parse(init.body) : null;
  fetched.push([(init && init.method) || 'GET', url, body]);
  inFlight.push({ resolve, reject });
});

let timers = []; // the timers set and not yet run or cleared, oldest first: { id, run, ms }
let lastId = 0;
const setTimeout = (run, ms) => {
  lastId += 1;
  timers.push({ id: lastId, run, ms });
  return lastId;
};
const clearTimeout = (id) => { timers = timers.filter((timer) => timer.id !== id); };

const window = { React, ReactDOM, document, fetch, addEventListener() {} };
new Function('window', 'React', bundle)(window, React);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'document', 'fetch', 'setTimeout',
  'clearTimeout', app)(
  window, React, ReactDOM, window.Fairband, document, fetch, setTimeout, clearTimeout);
const P = window.FairbandPage;
inFlight = []; fetched = []; timers = []; // the screen's own load, which no step answers

const ask = P.asking('AAPL');
let item = null; // the open item, as the view's last read of the company had it
let afters = 0;
const after = () => { afters += 1; };
const redraw = () => {};

// The elements of a tree as created, not drawn: a component's element is kept, not called.
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

// Post in the menu: the menu opens, and its form is submitted as Post or Enter submits it.
function post() {
  ask.open = true;
  const tree = P.requestResearch(ask, item, redraw, after, true);
  const menu = [...elements(tree)].find((e) => e.type && e.type.name === 'RequestMenu');
  menu.type(menu.props).props.onSubmit({ preventDefault() {} });
}

function answered(step) {
  const call = inFlight.shift();
  if (!call) throw new Error('no fetch in flight to answer');
  if (step.do === 'fail') { call.reject(new Error(step.message)); return; }
  const body = step.body;
  call.resolve({
    ok: step.status >= 200 && step.status < 300,
    status: step.status,
    json: () => (body === undefined ? Promise.reject(new Error('not JSON'))
      : Promise.resolve(body)),
  });
}

function fire() {
  const timer = timers.shift();
  if (!timer) throw new Error('no timer to run');
  timer.run();
}

// What Request research draws: the button and its menu, the request's error line, then the open
// item's line (requestResearch's three parts, in that order).
function drawn() {
  const [, error, line] = P.requestResearch(ask, item, redraw, after, true).props.children;
  const button = line ? line.props.children[1] : null;
  return {
    error: error ? textOf(error) : null,
    line: line ? textOf(line.props.children[0]) : null,
    button: button ? textOf(button) : null,
    failed: line ? line.props.className.split(' ').includes('app-request__error') : null,
  };
}

const trace = [];
for (const step of steps) {
  fetched = [];
  if (step.do === 'post') post();
  else if (step.do === 'answer' || step.do === 'fail') answered(step);
  else if (step.do === 'tick') fire();
  else if (step.do === 'stop') P.stopLaunch(ask);
  else if (step.do === 'landed') { item = step.item; P.followItem(ask, item, redraw, after); }
  else throw new Error('no step ' + step.do);
  await new Promise((done) => later(done, 0));
  trace.push(Object.assign({
    do: step.do, fetched, inFlight: inFlight.length, timers: timers.map((t) => t.ms), afters
  }, drawn()));
}
process.stdout.write(JSON.stringify(trace));
