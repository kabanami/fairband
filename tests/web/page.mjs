// The screen page's own script run in node, for the tests that read what a drawer helper returns:
// tests/web/test_drawer_form.py reads the drawer's parts (sections). The bundle and app.js are
// loaded as the page loads them, with a stub React and the few browser objects app.js touches as
// it loads: the screen's mount and the watchlist popup's, the listeners, no storage, a root that
// draws nothing and a fetch that never answers, so the screen and the lists never arrive. The
// helper is named as window.FairbandPage names it, by a dotted path for one a later script
// hangs on it ("reportCharts.roicPoints"); its arguments are a JSON list on stdin; its result is
// JSON on stdout. Scripts named after the helper are loaded after app.js, as the page loads them
// (charts.js; tests/web/test_report_charts.py; report_parts.js and its Appendix A's overrides,
// "reportAppendix.overrides"; tests/web/test_report_reader.py; the Research tab's scripts and
// their builders, "researchText.lay", "research.bar", "researchRecords.panels";
// tests/web/test_company_research*.py; inbox.js, whose root is the stub's, and its row,
// "inbox.row"; tests/web/test_inbox_launch.py; watchlists.js, which finds no storage, and the
// list the watchlist page opens on and its head, "lists.opens", "lists.head";
// tests/web/test_watchlist_page.py).
//
// A bundle component is named as window names it ("Fairband.HistoryBars") and called with its
// props, the one argument; the stub's hooks give it its first state, its refs and no effect, and
// what comes back is the tree it draws, each component in it called with its props in turn, since
// the stub draws nothing (tests/web/test_report_charts.py reads HistoryBars' bars).
//
// JSON holds no function, so an argument's value written {"$page": "<helper>"} is that helper of
// window.FairbandPage, named as the helper is: a component can be handed one of the page's own
// functions as a prop (ScreenTable's companyHref and onWatch; tests/web/test_ticker_link.py).
// A name that is no function, a table a script hangs there ("investor.FILTERS"), answers its value
// through JSON, which leaves its functions out; the arguments are then not read.
//
//   node page.mjs <bundle.js> <app.js> <helper> [<script.js> ...]  < arguments.json  > result.json
import { readFileSync } from 'node:fs';

const [bundle, app] = [process.argv[2], process.argv[3]].map((path) => readFileSync(path, 'utf8'));
const args = JSON.parse(readFileSync(0, 'utf8'));

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
const fetch = () => new Promise(() => {});
const window = { React, ReactDOM, document, fetch, addEventListener() {} };

new Function('window', 'React', bundle)(window, React);
new Function('window', 'React', 'ReactDOM', 'Fairband', 'document', 'fetch', app)(
  window, React, ReactDOM, window.Fairband, document, fetch);

// The views' loaders, which controls.js holds on the page: a view's script (inbox.js, company.js)
// registers its own there as it loads, and controls.js, which draws the header and polls, is not
// loaded here.
window.FairbandPage.onShow = window.FairbandPage.onShow || {};
for (const path of process.argv.slice(5)) {
  new Function('window', 'React', 'ReactDOM', 'Fairband', 'FairbandPage', 'document', 'fetch',
    readFileSync(path, 'utf8'))(
    window, React, ReactDOM, window.Fairband, window.FairbandPage, document, fetch);
}

function drawn(node) {
  if (Array.isArray(node)) return node.map(drawn);
  if (node === null || typeof node !== 'object' || !node.props) return node;
  if (typeof node.type === 'function') return drawn(node.type(node.props));
  return { type: node.type, props: Object.assign({}, node.props, { children: drawn(node.props.children) }) };
}

function page(path) {
  return path.split('.').reduce((held, key) => held[key], window.FairbandPage);
}

function revived(value) {
  if (Array.isArray(value)) return value.map(revived);
  if (value === null || typeof value !== 'object') return value;
  const keys = Object.keys(value);
  if (keys.length === 1 && keys[0] === '$page') return page(value.$page);
  return Object.fromEntries(keys.map((key) => [key, revived(value[key])]));
}

const name = process.argv[4];
const component = name.startsWith('Fairband.');
const helper = component ? name.split('.').reduce((held, key) => held[key], window) : page(name);
const result = typeof helper === 'function' ? helper(...revived(args)) : helper;
process.stdout.write(JSON.stringify(component ? drawn(result) : result));
