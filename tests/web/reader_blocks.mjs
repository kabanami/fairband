// ReportReader rendered to HTML in node (spec 2026-11-06 Tier 2, 13.1 "The text's shape" and
// 18.4), for tests/web/test_reader_blocks.py. The design system's bundle is loaded as the page
// loads it, with a stub React whose createElement builds a tree; the tree is written as HTML, a
// class as `class`, text and attributes escaped, no key and no handler.
//
//   node reader_blocks.mjs <bundle.js>  < props.json  > reader.html
//
// The props are ReportReader's, as JSON on stdin; the HTML is on stdout.
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

function attributes(given) {
  return Object.entries(given)
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

process.stdout.write(render(React.createElement(window.Fairband.ReportReader, props)));
