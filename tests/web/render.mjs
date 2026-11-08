// A design system component rendered to HTML in node, for the tests that read what the bundle
// draws: ReportReader (spec 2026-11-06 Tier 2, 13.1 "The text's shape" and 18.4) for
// tests/web/test_reader_blocks.py, BandMeter (18.2) for tests/web/test_band_meter.py. The bundle
// is loaded as the page loads it, with a stub React whose createElement builds a tree; the tree is
// written as HTML, a class as `class`, a style as its declarations (each key as given, `;`-joined,
// a number on a length as React prints it: 0 bare, else in px), text and attributes escaped, no
// key and no handler.
//
//   node render.mjs <bundle.js> [Component]  < props.json  > out.html
//
// The component is named as window.Fairband names it, ReportReader when none is given; its props
// are JSON on stdin; the HTML is on stdout.
import { readFileSync } from 'node:fs';

const bundle = readFileSync(process.argv[2], 'utf8');
const props = JSON.parse(readFileSync(0, 'utf8'));

const Fragment = Symbol('Fragment');
const React = {
  Fragment,
  createElement(type, given, ...children) {
    return { type, props: Object.assign({}, given, { children }) };
  },
  useState(initial) { return [typeof initial === 'function' ? initial() : initial, () => {}]; },
  useRef(initial) { return { current: initial === undefined ? null : initial }; },
  useEffect() {},
  useLayoutEffect() {},
  useMemo(make) { return make(); },
  useCallback(callback) { return callback; },
  useId() { return 'id'; },
  forwardRef(render) { return (given) => render(given, null); },
  memo(component) { return component; },
};
const window = { React };
new Function('window', 'React', bundle)(window, React);

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
const escape = (text) => String(text).replace(/[&<>"]/g, (c) => ESCAPES[c]);
const NAMES = { className: 'class', htmlFor: 'for' };

function declarations(style) {
  const said = Object.entries(style)
    .filter(([, value]) => value != null && typeof value !== 'boolean' && value !== '')
    .map(([name, value]) => `${name}:${typeof value === 'number' && value !== 0
      && !name.startsWith('--') ? value + 'px' : value}`);
  return said.length ? said.join(';') : null;
}

function attributes(given) {
  return Object.entries(given)
    .map(([name, value]) => [name, name === 'style' && value && typeof value === 'object'
      ? declarations(value) : value])
    .filter(([name, value]) => name !== 'children' && name !== 'key' && value != null
      && value !== false && typeof value !== 'object' && typeof value !== 'function')
    .map(([name, value]) => ` ${NAMES[name] || name}="${escape(value === true ? '' : value)}"`)
    .join('');
}

function render(node) {
  if (node == null || typeof node === 'boolean') return '';
  if (Array.isArray(node)) return node.map(render).join('');
  if (typeof node !== 'object') return escape(node);
  const { type, props: given } = node;
  if (type === Fragment) return render(given.children);
  if (typeof type === 'function') {
    const kids = given.children;
    return render(type(Object.assign({}, given, { children: kids.length === 1 ? kids[0] : kids })));
  }
  return `<${type}${attributes(given)}>${render(given.children)}</${type}>`;
}

const component = window.Fairband[process.argv[3] || 'ReportReader'];
process.stdout.write(render(React.createElement(component, props)));
