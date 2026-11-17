// The company page's Financials tab driven in node (the Financials tab's design, 7.2; Review Focus
// 5), for tests/web/test_company_financials.py: the bundle, app.js, company.js and
// company_financials.js are loaded in the page's order, with a stub React whose useState keeps
// its state from one draw of the tab to the next, and a window whose localStorage is the
// driver's: none, as page.mjs has and as a browser that keeps nothing has; one whose every read
// and write throws, as a private window's may; or one holding the items given.
//
// The input, a JSON object on stdin: {"store": null | "throws" | {<key>: <value>, ...}, "steps"}.
// The steps, a list, each one object:
//   {"do": "stored"}                    storedScale() is read
//   {"do": "keep", "scale"}             keepScale(scale) is called
//   {"do": "mount", "answer"}           the tab is drawn anew on `answer`, its state new, as when
//                                       another company's answer lands or the tab opens again
//   {"do": "press", "class", "text"}    the drawn tab's button of the class `class` whose text is
//                                       `text` is pressed, and the tab is drawn again
// After each step the trace on stdout gains what it returned (storedScale's unit), whether it
// threw, the store's items (null for none or one that throws) and the drawn tab's view: the
// sub-tab selected, the unit and the period pressed, null for a switch not drawn.
//
//   node financials.mjs <bundle.js> <app.js> <company.js> <company_financials.js>
//     < input.json  > trace.json
import { readFileSync } from 'node:fs';

const [bundle, app, ...scripts] = process.argv.slice(2).map((path) => readFileSync(path, 'utf8'));
const input = JSON.parse(readFileSync(0, 'utf8'));

let cells = []; // the drawn tab's state, one cell a useState, in the order it calls them
let next = 0; // the cell the next useState reads in this draw
const React = {
  Fragment: Symbol('Fragment'),
  createElement(type, given, ...children) {
    return { type, props: Object.assign({}, given, { children }) };
  },
  forwardRef(render) { return (given) => render(given, null); },
  memo(component) { return component; },
  useState(initial) {
    const at = next++;
    if (!(at in cells)) cells[at] = initial;
    return [cells[at], (value) => { cells[at] = value; }];
  },
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
const fetch = () => new Promise(() => {});
const window = { React, ReactDOM, document, fetch, addEventListener() {} };

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
const T = window.FairbandPage.companyFinancials;

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

let props = null; // the drawn tab's props
let tree = null; // what it last drew
function draw() {
  next = 0;
  tree = T.Financials(props);
}

// The text of the button of the class `name` that is on, null where none is drawn.
function on(name, attribute) {
  const [found] = classed(tree, name).filter((e) => e.props[attribute] === 'true');
  return found ? textOf(found) : null;
}

const trace = [];
for (const step of input.steps) {
  let result = null;
  let threw = false;
  try {
    if (step.do === 'stored') result = T.storedScale();
    else if (step.do === 'keep') T.keepScale(step.scale);
    else if (step.do === 'mount') {
      cells = [];
      props = { answer: step.answer, symbol: step.answer.symbol };
      draw();
    } else if (step.do === 'press') {
      const [button] = classed(tree, step.class).filter((e) => textOf(e) === step.text);
      button.props.onClick({});
      draw();
    } else throw new Error('no step ' + step.do);
  } catch (error) {
    threw = true;
  }
  trace.push({
    do: step.do,
    result,
    threw,
    store: items && Object.assign({}, items),
    view: tree && {
      tab: on('app-fin__tab', 'aria-selected'),
      unit: classed(tree, 'app-fin__scale').length ? on('app-fin__scale', 'aria-pressed') : null,
      period: classed(tree, 'app-fin__period').length ? on('app-fin__period', 'aria-pressed')
        : null,
    },
  });
}
process.stdout.write(JSON.stringify(trace));
