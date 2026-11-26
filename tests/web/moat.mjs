// The moat box driven in node (spec 2026-11-19 8.8), for tests/web/test_moat_control.py: the
// bundle and app.js are loaded as tests/web/page.mjs loads them, with a stub React, a stub ReactDOM
// whose roots keep what they last drew, and a fetch of the driver's own, answered only when a step
// answers it, so the steps say exactly when a write or a read lands; the reads the screen and the
// lists start as app.js loads stay unanswered, the screen's until a drawer step answers it, and a
// read no step names is never answered.
//
// The steps, a JSON list on stdin, each one object:
//   {"do": "open", "detail"}             the company page's control is pressed, drawn on `detail`
//                                        (moatControl), its `after` the driver's counter; the same
//                                        control each time, as the page's head keeps it
//   {"do": "pick", "class"}              the box's class of that name is pressed
//   {"do": "type", "text"}               the reason's field comes to hold `text`
//   {"do": "set"}                        Set moat class is pressed
//   {"do": "return"}                     Use Fairband's class is pressed
//   {"do": "answer", "status", "body"}   the oldest write in flight answers; a body that is a
//                                        string is no JSON, as a 500's plain text
//   {"do": "read", "url", "body"}        the oldest read in flight of `url` answers 200, or
//                                        `status` where the step has one, with `body`; with
//                                        none in flight, nothing happens
//   {"do": "notes"}                      a Notes control is pressed (openNotes)
//   {"do": "drawer", "symbol"}           the screen's newest read in flight lands with the row of
//                                        `symbol` alone, and the row opens its drawer as a click
//                                        on it does (the table's onOpen)
// After each step and the work it sets off, the trace on stdout gains what the step fetched (each
// request's method, path and JSON body), the times `after` has run and the control has taken
// focus back, whether a Notes box is drawn, the moat box drawn, null for none: the text of its
// line and of its reason, the classes pressed, the field's text, Set moat class's disabled, the
// return's words and its disabled (null without one), and the sentence under the buttons; and the
// drawer, null for none: its company, whether it is loading and its Buy level's figure, the
// level the moat class sets (null without one). The drawer draws no moat stamp (the founder,
// 2026-11-26), and it opens on two reads, its detail and the company page's Overview answer
// (readDrawer): a step that answers the second with a refusal leaves the drawer with no chart,
// which this driver, without the company page's scripts, could not draw.
//
//   node moat.mjs <bundle.js> <app.js>  < steps.json  > trace.json
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
const document = {
  body: { appendChild(node) { return node; } },
  createElement() { return {}; },
  getElementById() { return {}; },
  addEventListener() {},
};

let inFlight = []; // the requests not yet answered, oldest first: { method, url, resolve }
let fetched = []; // the requests the current step made
const fetch = (url, init) => new Promise((resolve) => {
  const method = (init && init.method) || 'GET';
  const body = init && init.body !== undefined ? JSON.parse(init.body) : null;
  fetched.push([method, url, body]);
  inFlight.push({ method, url, resolve });
});

// The first request in flight that `test` holds, answered `status` with `body`, and no longer in
// flight; nothing where none is.
function settle(test, status, body) {
  answer(inFlight.find(test), status, body);
}

// The request `found` answered `status` with `body`, and no longer in flight; nothing for none.
function answer(found, status, body) {
  if (!found) return;
  inFlight.splice(inFlight.indexOf(found), 1);
  found.resolve({
    ok: status < 400,
    status,
    json() {
      return typeof body === 'string' ? Promise.reject(new SyntaxError(body))
        : Promise.resolve(body);
    },
  });
}

const window = { React, ReactDOM, document, fetch, addEventListener() {} };
new Function('window', 'React', bundle)(window, React);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'document', 'fetch', app)(
  window, React, ReactDOM, window.Fairband, document, fetch);
const P = window.FairbandPage;
fetched = []; // the screen's and the lists' own reads, unanswered, are no step's

let afters = 0;
let focused = 0;
// The company page's control, kept by the head from one draw to the next, and a Notes control.
const anchor = { isConnected: true, focus() { focused += 1; }, contains() { return false; } };
const notesAnchor = { isConnected: true, focus() {}, contains() { return false; } };

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

const drawnBy = (name) => roots.find((root) => root.drawn && root.drawn.type &&
  root.drawn.type.name === name);

// The moat box as its root draws it: the component called with its props, the stub's hooks
// giving it its refs and no effect.
function box() {
  const root = drawnBy('MoatBox');
  return root ? root.drawn.type(root.drawn.props) : null;
}

function button(tree, test) {
  return [...elements(tree)].find((e) => typeof e.props.onClick === 'function' && test(e));
}

function seen() {
  const tree = box();
  let drawn = null;
  if (tree) {
    const [whose] = classed(tree, 'app-moat-box__whose');
    const [reason] = classed(tree, 'app-moat-box__reason');
    const [field] = classed(tree, 'app-moat-box__field');
    const [error] = classed(tree, 'app-moat-box__error');
    const set = button(tree, (e) => textOf(e) === 'Set moat class');
    const back = button(tree, (e) => textOf(e).startsWith('Use Fairband'));
    drawn = {
      whose: whose ? textOf(whose) : null,
      reason: reason ? textOf(reason) : null,
      pressed: [...elements(tree)].filter((e) => e.props['aria-pressed'] === 'true').map(textOf),
      draft: field.props.value,
      set: !!set.props.disabled,
      back: back ? [textOf(back), !!back.props.disabled] : null,
      error: error ? textOf(error) : null,
    };
  }
  return { fetched, afters, focused, notes: !!drawnBy('NotesBox'), box: drawn, drawer: drawer() };
}

// The drawer the screen's root draws beside the table, null while none is open.
function drawer() {
  const screen = roots[0].drawn;
  const [aside] = screen ? classed(screen, 'app-drawer') : [];
  if (!aside) return null;
  const [levels] = classed(aside, 'app-pairs');
  const cells = levels ? [...elements(levels)].filter((e) => e.type === 'dt' || e.type === 'dd')
    : [];
  const name = cells.findIndex((e) => e.type === 'dt' && textOf(e) === 'Buy level');
  return {
    symbol: aside.props['aria-label'].replace('Detail for ', ''),
    loading: classed(aside, 'is-loading').length > 0,
    buy: name === -1 ? null : textOf(cells[name + 1]),
  };
}

const trace = [];
for (const step of steps) {
  fetched = [];
  const tree = box();
  if (step.do === 'open') {
    const control = P.moatControl(step.detail, () => { afters += 1; });
    control.props.onClick({ currentTarget: anchor });
  } else if (step.do === 'pick') {
    button(tree, (e) => e.props['aria-pressed'] !== undefined && textOf(e) === step.class)
      .props.onClick();
  } else if (step.do === 'type') {
    classed(tree, 'app-moat-box__field')[0].props.onChange({ target: { value: step.text } });
  } else if (step.do === 'set') {
    button(tree, (e) => textOf(e) === 'Set moat class').props.onClick();
  } else if (step.do === 'return') {
    button(tree, (e) => textOf(e).startsWith('Use Fairband')).props.onClick();
  } else if (step.do === 'answer') {
    settle((f) => f.method !== 'GET', step.status, step.body);
  } else if (step.do === 'read') {
    settle((f) => f.method === 'GET' && f.url === step.url, step.status || 200, step.body);
  } else if (step.do === 'notes') {
    P.notesControl('BF.B', 0, null).props.onClick({ currentTarget: notesAnchor });
  } else if (step.do === 'drawer') {
    const screens = inFlight.filter((f) => f.method === 'GET' && f.url.startsWith('/api/screen'));
    answer(screens[screens.length - 1], 200, { rows: [{ ticker: step.symbol }] });
    await new Promise((done) => later(done, 0));
    const [table] = [...elements(roots[0].drawn)].filter((e) => e.type && e.type.name === 'Screen');
    table.props.onOpen({ ticker: step.symbol });
  }
  await new Promise((done) => later(done, 0));
  trace.push(seen());
}
process.stdout.write(JSON.stringify(trace));
