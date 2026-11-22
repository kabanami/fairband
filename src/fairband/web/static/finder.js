/* The header's finder (the company page's design, the decision log of 2026-11-17), loaded after
   app.js and before controls.js, which draws it in the header's right slot on every view but the
   Screen, whose table has a field of its own: a field that opens a company's page. It finds the
   rows the Screen's field finds (finds, app.js), a ticker that starts with the text or a name
   that holds it, on the rows the page already holds, so it asks the server nothing, and lists
   eight at most: the ticker that is the text, then the tickers that start with it, the names
   that start with it and the names that hold it, the larger company first within each. The
   arrow keys move the mark, turning round at the ends; Enter opens the marked company, the first
   when no key moved the mark; Escape empties the field. A key the open list takes is the finder's
   alone, as its preventDefault says, and an open drawer stays (app.js). A blur closes the list and
   keeps the text. A pick sets the hash to the address the ticker's link names (companyHref), so
   the browser's Back returns to the view left, and empties the field, which keeps the focus. With
   nothing found, and while the rows are not in, the list says so in one row. The matching, the
   keys' steps and the list are pure functions on FairbandPage.finder for the tests, which read
   them in node; view keeps the text, the mark and whether the list is open. */
(function () {
  'use strict';

  var h = React.createElement;
  var P = FairbandPage;

  var LIMIT = 8;
  var WAIT_MS = 300; /* between two looks for the rows, while an open list waits for them */

  /* The rows the text finds, best first: 0 the ticker itself, 1 a ticker that starts with it, 2 a
     name that starts with it, 3 a name that holds it; within a rank the larger market cap first,
     a row with none last, then by ticker. No text and no rows find nothing. */
  function matches(rows, query) {
    var needle = String(query || '').trim().toLowerCase();
    if (!needle || !rows) return [];
    var ranked = [];
    rows.forEach(function (row) {
      if (!P.finds(row, needle)) return;
      var ticker = row.ticker.toLowerCase();
      var rank = ticker === needle ? 0 : ticker.indexOf(needle) === 0 ? 1
        : String(row.name || '').toLowerCase().indexOf(needle) === 0 ? 2 : 3;
      ranked.push({ row: row, rank: rank });
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
     name, the marked one selected; a press of the main button on a row picks it and leaves the
     focus in the field. With no company, one row that cannot be picked: the note it is given, or
     that nothing matches. */
  function list(found, active, pick, note) {
    return h('ul', {
      id: 'app-finder-list', role: 'listbox', 'aria-label': 'Companies',
      className: 'fb-menu app-finder__list'
    },
      found.length ? found.map(function (row, i) {
        return h('li', {
          key: row.ticker, id: 'app-finder-opt-' + i, role: 'option',
          className: 'app-finder__opt', 'aria-selected': i === active ? 'true' : 'false',
          onMouseDown: function (event) {
            if (event.button) return; /* the main button alone picks */
            event.preventDefault();
            pick(row);
          }
        },
          h('span', { className: 'ticker' }, row.ticker),
          row.name ? h('span', { className: 'body app-finder__name' }, row.name) : null);
      }) : h('li', {
        role: 'option', 'aria-disabled': 'true', 'aria-selected': 'false',
        className: 'caption app-finder__none'
      }, note || 'No company matches'));
  }

  var SHUT = { query: '', active: 0, open: false };

  /* The field and, while it holds text and has the focus, its list. */
  function Finder() {
    var held = React.useState(SHUT);
    var state = held[0];
    var set = held[1];
    var rows = P.rows();
    var found = state.open ? matches(rows, state.query) : [];
    /* The rows may change under an open list (a refresh's end loads them again): the mark stays
       on it. */
    var active = Math.min(state.active, Math.max(found.length - 1, 0));
    /* Nothing draws the header as the rows arrive: an open list that waits for them asks again
       shortly, until they are in or the list closes. */
    React.useEffect(function () {
      if (rows || !state.open) return undefined;
      var timer = setTimeout(function () {
        set({ query: state.query, active: state.active, open: true });
      }, WAIT_MS);
      return function () { clearTimeout(timer); };
    });

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
      /* a key of a text being composed is the text's own */
      if (event.nativeEvent && event.nativeEvent.isComposing) return;
      var does = state.open ? step(found.length, active, event.key) : null;
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
        'aria-expanded': state.open ? 'true' : 'false',
        'aria-controls': state.open ? 'app-finder-list' : null,
        'aria-autocomplete': 'list',
        'aria-activedescendant': found.length ? 'app-finder-opt-' + active : null,
        autoComplete: 'off', spellCheck: false, value: state.query,
        onChange: typed, onKeyDown: key, onFocus: focused, onBlur: close
      }),
      state.open
        ? list(found, active, pick, rows ? null : 'The companies have not loaded.') : null);
  }

  /* What controls.js and the tests use. */
  P.finder = { matches: matches, step: step, list: list, view: Finder };
})();
