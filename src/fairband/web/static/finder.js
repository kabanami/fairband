/* The header's finder (the company page's design, the decision log of 2026-11-17), loaded after
   app.js and before controls.js, which draws it in the header's right slot on every view but the
   Screen, whose table has a field of its own: a field that opens a company's page. It matches as
   the Screen's field does (narrow, app.js), a ticker that starts with the text or a name that
   holds it, on the rows the page already holds, so it asks the server nothing, and lists eight at
   most: the ticker that is the text, then the tickers that start with it, the names that start
   with it and the names that hold it, the larger company first within each. The arrow keys move
   the mark, turning round at the ends; Enter opens the marked company, the first when no key
   moved the mark; Escape, a blur and a pick close the list. A pick sets the hash to the address
   the ticker's link names (companyHref), so the browser's Back returns to the view left, and
   empties the field. The matching, the keys' steps and the list are pure functions on
   FairbandPage.finder for the tests, which read them in node; view keeps the text, the mark and
   whether the list is open. */
(function () {
  'use strict';

  var h = React.createElement;
  var P = FairbandPage;

  var LIMIT = 8;

  /* The rows the text finds, best first: 0 the ticker itself, 1 a ticker that starts with it, 2 a
     name that starts with it, 3 a name that holds it; within a rank the larger market cap first,
     a row with none last, then by ticker. No text and no rows find nothing. */
  function matches(rows, query) {
    var needle = String(query || '').trim().toLowerCase();
    if (!needle || !rows) return [];
    var ranked = [];
    rows.forEach(function (row) {
      var ticker = String(row.ticker || '').toLowerCase();
      var name = String(row.name || '').toLowerCase();
      var at = name.indexOf(needle);
      var rank = ticker === needle ? 0 : ticker.indexOf(needle) === 0 ? 1
        : at === 0 ? 2 : at > 0 ? 3 : -1;
      if (rank !== -1) ranked.push({ row: row, rank: rank });
    });
    ranked.sort(function (a, b) {
      return a.rank - b.rank || (b.row.marketCap || 0) - (a.row.marketCap || 0) ||
        (a.row.ticker < b.row.ticker ? -1 : a.row.ticker > b.row.ticker ? 1 : 0);
    });
    return ranked.slice(0, LIMIT).map(function (found) { return found.row; });
  }

  /* What a key does on a list of count companies with the mark on active: the mark's new place,
     the place of the company to open, or the list closed; null for a key that is the field's own
     and for Enter and the arrows on an empty list. */
  function step(count, active, key) {
    if (key === 'Escape') return { close: true };
    if (!count) return null;
    if (key === 'ArrowDown') return { active: (active + 1) % count };
    if (key === 'ArrowUp') return { active: (active - 1 + count) % count };
    if (key === 'Enter') return { go: active };
    return null;
  }

  /* The list under the field, in the bundle's menu frame: a company a row, its ticker then its
     name, the marked one selected; a press on a row picks it and leaves the focus in the field.
     With nothing found, the sentence that says so. */
  function list(found, active, pick) {
    return h('ul', {
      id: 'app-finder-list', role: 'listbox', className: 'fb-menu app-finder__list'
    },
      found.length ? found.map(function (row, i) {
        return h('li', {
          key: row.ticker, id: 'app-finder-opt-' + i, role: 'option',
          className: 'app-finder__opt', 'aria-selected': i === active ? 'true' : 'false',
          onMouseDown: function (event) { event.preventDefault(); pick(row); }
        },
          h('span', { className: 'ticker' }, row.ticker),
          row.name ? h('span', { className: 'body app-finder__name' }, row.name) : null);
      }) : h('li', { className: 'caption app-finder__none' }, 'No company matches'));
  }

  var SHUT = { query: '', active: 0, open: false };

  /* The field and, while it holds text and has the focus, its list. */
  function Finder() {
    var held = React.useState(SHUT);
    var state = held[0];
    var set = held[1];
    var rows = P.rows();
    var open = state.open && !!rows; /* no list before the rows arrive */
    var found = open ? matches(rows, state.query) : [];

    function pick(row) {
      set(SHUT);
      window.location.hash = P.companyHref(row);
    }
    function close() { set({ query: state.query, active: 0, open: false }); }
    function typed(event) {
      var query = event.target.value;
      set({ query: query, active: 0, open: !!query.trim() });
    }
    function focused() {
      if (state.query.trim() && !state.open) set({ query: state.query, active: 0, open: true });
    }
    function key(event) {
      var does = open ? step(found.length, state.active, event.key) : null;
      if (!does) return;
      event.preventDefault();
      if (does.close) set(SHUT);
      else if (does.go !== undefined) pick(found[does.go]);
      else set({ query: state.query, active: does.active, open: true });
    }

    return h('div', { className: 'app-finder' },
      h('input', {
        id: 'app-finder-q', type: 'text', className: 'app-finder__q', role: 'combobox',
        placeholder: 'Ticker or company', 'aria-label': 'Find a company',
        'aria-expanded': open ? 'true' : 'false', 'aria-controls': 'app-finder-list',
        'aria-autocomplete': 'list',
        'aria-activedescendant': found.length ? 'app-finder-opt-' + state.active : null,
        autoComplete: 'off', spellCheck: false, value: state.query,
        onChange: typed, onKeyDown: key, onFocus: focused, onBlur: close
      }),
      open ? list(found, state.active, pick) : null);
  }

  /* What controls.js and the tests use. */
  P.finder = { matches: matches, step: step, list: list, view: Finder };
})();
