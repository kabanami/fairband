/* The screen page: fetches /api/screen and renders the design system's ScreenTable.
   No JSX and no build step: React.createElement against window.Fairband. The server sorts;
   this script only asks for an order and remembers the chosen columns. */
(function () {
  'use strict';

  var h = React.createElement;
  var COLUMNS_KEY = 'fairband.columns';

  /* ScreenTable takes no sort callback and puts no column key on its header cells, so a click
     on a header is read by the header's words. */
  var HEADERS = {
    'Ticker': 'ticker', 'Company': 'name', 'Phase': 'phase', 'Fair band': 'band',
    'Fair value': 'fairValue', 'Buy level': 'buyLevel', 'Trim level': 'trimLevel',
    'Mechanical': 'mechanical', 'Reviewed': 'reviewed', 'Price': 'price', 'Stance': 'stance',
    'Overrides': 'overrides', 'Entered': 'entered'
  };
  /* The columns that draw a row key under another name sort by that key. */
  var SORT_KEYS = { band: 'fairLow', stance: 'stance3', entered: 'enteredAt' };

  var mount = document.getElementById('screen');
  var root = ReactDOM.createRoot(mount);
  var state = {
    rows: null,
    error: null,
    sort: { column: 'ticker', direction: 'asc' },
    columns: loadColumns()
  };
  var latest = 0;

  function loadColumns() {
    try {
      var saved = JSON.parse(window.localStorage.getItem(COLUMNS_KEY));
      if (Array.isArray(saved)) return saved;
    } catch (e) { /* no storage, or not a list: the default */ }
    return Fairband.DEFAULT_COLUMNS.slice();
  }

  function setColumns(columns) {
    state.columns = columns;
    try {
      window.localStorage.setItem(COLUMNS_KEY, JSON.stringify(columns));
    } catch (e) { /* no storage: the choice lasts until the page reloads */ }
    render();
  }

  function load() {
    var request = ++latest;
    var sort = state.sort;
    var key = SORT_KEYS[sort.column] || sort.column;
    fetch('/api/screen?sort=' + encodeURIComponent(key) + '&dir=' + sort.direction)
      .then(function (response) {
        if (!response.ok) throw new Error('the server answered ' + response.status);
        return response.json();
      })
      .then(function (body) {
        if (request !== latest) return;
        state.rows = body.rows;
        state.error = null;
        render();
      })
      .catch(function (err) {
        if (request !== latest) return;
        state.error = 'The screen did not load: ' + err.message + '. Reload the page to try again.';
        render();
      });
  }

  function footnote(n) {
    return n + (n === 1 ? ' company' : ' companies') + ' · $2 bn and up';
  }

  function render() {
    if (state.error) {
      root.render(h('p', { className: 'body app-note' }, state.error));
    } else if (state.rows === null) {
      root.render(null);
    } else if (state.rows.length === 0) {
      root.render(h('p', { className: 'body app-note' }, 'No snapshots yet. Run a refresh.'));
    } else {
      root.render(h(Fairband.ScreenTable, {
        rows: state.rows,
        columns: state.columns,
        onColumnsChange: setColumns,
        sort: state.sort,
        footnote: footnote(state.rows.length),
        chooser: true
      }));
    }
  }

  /* The header's own words: its text, leaving out the aria-hidden basis glyph and sort arrow. */
  function headerWords(th) {
    var words = '';
    th.childNodes.forEach(function (node) {
      if (node.nodeType === Node.TEXT_NODE || node.getAttribute('aria-hidden') !== 'true') {
        words += node.textContent;
      }
    });
    return words.trim();
  }

  /* One listener on the mount node outlives every re-render of the header cells. A click on the
     sorted column turns its direction; a click on another column sorts it ascending. */
  mount.addEventListener('click', function (event) {
    var th = event.target.closest('th');
    var column = th && mount.contains(th) ? HEADERS[headerWords(th)] : null;
    if (!column) return;
    var turn = state.sort.column === column && state.sort.direction === 'asc';
    state.sort = { column: column, direction: turn ? 'desc' : 'asc' };
    render();
    load();
  });

  render();
  load();
})();
