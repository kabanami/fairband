// The screen page's own script run in node, for the tests that read what a drawer helper returns:
// tests/web/test_drawer_charge.py reads chargeRows (spec 2026-11-09 12). The bundle and app.js are
// loaded as the page loads them, with a stub React and the few browser objects app.js touches as
// it loads: the screen's mount and the watchlist popup's, the listeners, no storage, a root that
// draws nothing and a fetch that never answers, so the screen and the lists never arrive. The
// helper is named as window.FairbandPage names it; its arguments are a JSON list on stdin; its
// result is JSON on stdout.
//
//   node page.mjs <bundle.js> <app.js> <helper>  < arguments.json  > result.json
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

const helper = window.FairbandPage[process.argv[4]];
process.stdout.write(JSON.stringify(helper(...args)));
