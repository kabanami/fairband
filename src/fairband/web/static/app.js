/* The screen page: fetches /api/screen and renders the design system's ScreenTable, and beside it
   the detail drawer of the row the reader opens (spec 6.4), fetched from /api/companies/{symbol}.
   No JSX and no build step: React.createElement against window.Fairband. The server sorts and the
   engine computes; this script asks for an order, remembers the chosen columns in the reader's
   order, narrows the loaded rows to the reader's find and filters and lays out what the engine
   produced, rounded for display only. Each row's watchlist mark opens a popup that puts the
   company on the reader's lists, from /api/watchlists (spec 2026-11-04 9.4). The drawer leads with
   the valuation and the agents' report and puts the rest behind Details ▾; without a report it
   posts a research request to the work inbox, and Details takes the owner's notes (spec 2026-11-06
   Tier 2, 18.2 and 18.3). The header, the status line and the group view are controls.js, loaded
   after this script; it reaches the screen through window.FairbandPage. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var COLUMNS_KEY = 'fairband.columns';

  /* The columns that draw a row key under another name sort by that key; the agent's stance
     names its own, which the server orders by the words (spec 2026-11-06 Tier 2, 18.1). */
  var SORT_KEYS = { band: 'fairLow', designation: 'priceToValue', entered: 'enteredAt',
                    agentStance: 'agentStance' };
  /* The engine's phase names, as PhaseBadge's numbers. */
  var PHASE_NUMBER = {
    'Start-up': 1, 'Young Growth': 2, 'High Growth': 3,
    'Mature Growth': 4, 'Mature Stable': 5, 'Decline': 6
  };
  var ROUTES = {
    'mature-growth': 'Mature growth route', 'mature-stable': 'Mature stable route',
    'revenue-growth': 'Revenue growth route', 'decline': 'Decline route',
    'start-up': 'Start-up route'
  };
  /* A work item's two modes, as the inbox takes them (spec 2026-11-06 Tier 2, 8). */
  var REQUEST_MODES = ['valuation review', 'full report'];
  /* An applied override's Result row in Details when no valued review on the latest snapshot
     holds it (spec 2026-11-06 Tier 2, 18.3). */
  var NO_EFFECT = 'No effect to show: not inside a valued review on the latest snapshot';

  var mount = document.getElementById('screen');
  var root = ReactDOM.createRoot(mount);
  var state = {
    rows: null,
    error: null,
    sort: { column: 'ticker', direction: 'asc' },
    columns: loadColumns(),
    /* The FIND text and the Filters menu's choice. Neither is saved: every page load starts
       with the whole screen (screen-controls spec 4.4). */
    query: '',
    filters: F.EMPTY_FILTERS,
    drawer: null, /* { symbol, body, loading, error } while open */
    watchlists: null, /* the reader's lists, by name, once loaded: [{ id, name, symbols, … }] */
    watchlistsError: null,
    watch: null, /* { symbol, anchor, ids, name, error } while a mark's popup is open */
    pastFirstScreen: false, /* the table is scrolled more than one screen down: Top shows */
    /* The drawer's Details ▾ (spec 2026-11-06 Tier 2, 18.2): closed until the reader opens it,
       then as the reader left it, whichever company the drawer shows, for the page's life. */
    detailsOpen: false,
    research: null, /* Details' records of one company: { symbol, body, error } */
    request: null, /* Request research of one company: { symbol, open, mode, note, error, … } */
    noteDraft: null /* Add a note of one company: { symbol, text, error, posting } */
  };
  var latest = 0;
  var latestDetail = 0;
  var latestResearch = 0;

  function loadColumns() {
    try {
      var saved = JSON.parse(window.localStorage.getItem(COLUMNS_KEY));
      if (Array.isArray(saved)) return normalise(saved);
    } catch (e) { /* no storage, or not a list: the default */ }
    return F.DEFAULT_COLUMNS.slice();
  }

  /* A saved list's order is the table's. A list saved before the order mattered, or by an older
     build, may name a column the bundle no longer has, repeat one, or lack a locked one: unknown
     keys and repeats go, a missing Ticker goes first and a missing Price last, since neither can
     be switched off. A list saved under method 0.5 names the column Price vs value replaced by
     its old key: Price vs value takes that key's place. */
  function normalise(columns) {
    var named = columns.map(function (key) { return key === 'stance' ? 'designation' : key; });
    var kept = named.filter(function (key, i) {
      return F.COLUMN_KEYS.indexOf(key) !== -1 && named.indexOf(key) === i;
    });
    if (kept.indexOf('ticker') === -1) kept.unshift('ticker');
    if (kept.indexOf('price') === -1) kept.push('price');
    return kept;
  }

  function setColumns(columns) {
    state.columns = columns;
    try {
      window.localStorage.setItem(COLUMNS_KEY, JSON.stringify(columns));
    } catch (e) { /* no storage: the choice lasts until the page reloads */ }
    render();
  }

  function setQuery(query) {
    state.query = query;
    render();
  }

  function setFilters(filters) {
    state.filters = filters;
    render();
  }

  /* A symbol's row from another view (the Methodology page's examples, a watchlist): the symbol
     in FIND, the filters cleared so nothing hides its row, and the Screen view open. */
  function find(symbol) {
    state.query = symbol;
    state.filters = F.EMPTY_FILTERS;
    render();
    window.FairbandPage.show('screen');
  }

  function getJson(url) {
    return fetch(url).then(function (response) {
      if (!response.ok) throw new Error('the server answered ' + response.status);
      return response.json();
    });
  }

  /* The server refuses a write without the X-Fairband-Request header (D11): a cross-site form
     cannot send it, nor a cross-origin script without a preflight the server never answers. The
     refresh controls post through here, the watchlist popup posts and puts, and the Watchlists
     view also renames and deletes; the promise gives the status and the parsed body. */
  function send(method, url, body) {
    return fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json', 'X-Fairband-Request': '1' },
      body: JSON.stringify(body || {})
    }).then(function (response) {
      return response.json().then(function (json) {
        return { ok: response.ok, status: response.status, body: json };
      });
    });
  }

  var api = {
    post: function (url, body) { return send('POST', url, body); },
    put: function (url, body) { return send('PUT', url, body); },
    patch: function (url, body) { return send('PATCH', url, body); },
    del: function (url) { return send('DELETE', url); }
  };

  /* The server writes a timestamp in UTC (+00:00), and the design system prints a string's own
     hour and minute, so a UTC stamp would read as the reader's clock and be hours off. This is
     the same instant in the browser's offset (2026-10-31T22:20:00+00:00 is
     2026-11-01T01:20:00+03:00 at +03:00), so datetime stays true and the text reads as local
     time: the header's engine stamp, the last-refresh line, the table's Entered dates and the
     drawer's timestamps. A plain date (no T) is a day, not an instant, and passes through; so
     does a string Date cannot read. */
  function localIso(iso) {
    if (!iso || String(iso).indexOf('T') < 0) return iso;
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    var offset = -d.getTimezoneOffset();
    var abs = Math.abs(offset);
    return d.getFullYear() + '-' + two(d.getMonth() + 1) + '-' + two(d.getDate()) + 'T' +
      two(d.getHours()) + ':' + two(d.getMinutes()) + ':' + two(d.getSeconds()) +
      (offset < 0 ? '-' : '+') + two(Math.floor(abs / 60)) + ':' + two(abs % 60);
  }

  function two(n) { return (n < 10 ? '0' : '') + n; }

  /* What controls.js uses: the screen's reload when a refresh ends, the write helpers, the GET
     helper, the local-time helper and the phase numbers; and the later views, find, the lists
     (null until they load), their reload, which settles once they are in, and watch, the marks'
     onWatch, which opens the popup; the loaded rows (null until they load), the chosen columns and
     openRow, which opens a row's drawer. controls.js adds show, onShow, section and running, and
     methodology.js adds methodologySection, which the drawer's link reads; a view drawn from the
     rows or the lists sets onRender, which runs after each draw of the screen, so it draws again
     as they load and change. The report page (report.js, spec 2026-11-06 Tier 2, 18.4) draws with
     the drawer's own parts: the meter, the inputs table, a table of figures by year, an input's
     figure in its unit, the secondary valuation's rows and path, the guidance table, the phase
     evidence, pairs, a date, a total, a count, a report's footnote numbers, and Request research
     with a request of its own (asking). */
  window.FairbandPage = {
    reload: load, api: api, getJson: getJson, localIso: localIso, PHASE_NUMBER: PHASE_NUMBER,
    find: find,
    watchlists: function () { return state.watchlists; },
    reloadWatchlists: reloadWatchlists,
    watch: watch,
    rows: function () { return state.rows; },
    columns: function () { return state.columns; },
    openRow: openRow,
    meter: meter, inputsTable: inputsTable, figuresTable: figuresTable, inputFigure: inputFigure,
    secondaryRows: secondaryRows, secondaryPath: secondaryPath, guidanceTable: guidanceTable,
    phaseEvidence: phaseEvidence, pairs: pairs, when: when, whole: whole, plain: plain,
    footnotes: footnotes, asking: asking, requestResearch: requestResearch
  };

  function load() {
    var request = ++latest;
    var sort = state.sort;
    var key = SORT_KEYS[sort.column] || sort.column;
    getJson('/api/screen?sort=' + encodeURIComponent(key) + '&dir=' + sort.direction)
      .then(function (body) {
        if (request !== latest) return;
        state.rows = body.rows.map(localRow);
        state.error = null;
        render();
      })
      .catch(function (err) {
        if (request !== latest) return;
        state.error = 'The screen did not load: ' + err.message + '. Reload the page to try again.';
        render();
      });
  }

  /* A row with its entered time in the reader's offset, so the Entered cell shows the local date
     (the local-offset ISO in datetime) and agrees with the drawer's ValidityWindow, and its
     report's time likewise, so the coverage mark's title gives the local date; watched when the
     company is on a list, which fills its mark. */
  function localRow(r) {
    var row = Object.assign({}, r, { watched: (r.watchlists || []).length > 0 });
    if (r.covered) row.covered = Object.assign({}, r.covered, { at: localIso(r.covered.at) });
    return r.enteredAt ? Object.assign(row, { enteredAt: localIso(r.enteredAt) }) : row;
  }

  /* A header click, or Enter or Space on a focused header: the sorted column turns its
     direction; another column sorts ascending. */
  function sortBy(column) {
    var turn = state.sort.column === column && state.sort.direction === 'asc';
    state.sort = { column: column, direction: turn ? 'desc' : 'asc' };
    render();
    load();
  }

  /* A row click, or Enter or Space on a focused row. The previous company stays in the drawer,
     faded, until the new one lands. Details stays as the reader left it; open, its records are
     read for the company beside its detail. */
  function open(row) {
    var d = state.drawer;
    if (d && d.symbol === row.ticker && !d.error) return;
    var request = ++latestDetail;
    state.drawer = { symbol: row.ticker, body: d && d.body, loading: true, error: null };
    if (state.detailsOpen) readResearch(row.ticker);
    render();
    getJson('/api/companies/' + encodeURIComponent(row.ticker))
      .then(function (body) {
        if (request !== latestDetail) return;
        state.drawer = { symbol: row.ticker, body: body, loading: false, error: null };
        render();
      })
      .catch(function (err) {
        if (request !== latestDetail) return;
        state.drawer = {
          symbol: row.ticker, body: null, loading: false,
          error: 'The detail for ' + row.ticker + ' did not load: ' + err.message +
            '. Open the row again to retry.'
        };
        render();
      });
  }

  /* A row from another view (a watchlist's): its drawer opens as a click on the row opens it, and
     the Screen view shows, since the drawer stands beside the screen's table. */
  function openRow(symbol) {
    open({ ticker: symbol });
    window.FairbandPage.show('screen');
  }

  function close() {
    latestDetail++;
    state.drawer = null;
    render();
  }

  /* Escape closes the drawer, unless a menu is open: then Escape closes the menu first. Only while
     the Screen shows it: in another view the drawer is hidden, and Escape belongs to that view. */
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && state.drawer && !mount.hidden &&
        !document.querySelector('.fb-menu')) close();
  });

  /* ------------------------------------------------------- find and filters */

  /* An empty group narrows nothing; a non-empty one keeps only the rows whose value it names, or,
     where the row holds several (its watchlists), one of them. */
  function within(list, value) {
    if (!list.length) return true;
    if (Array.isArray(value)) return value.some(function (v) { return list.indexOf(v) !== -1; });
    return list.indexOf(value) !== -1;
  }

  /* The design system's reference rule (the gallery's apply). ScreenTable narrows nothing, so the
     page keeps the rows it loaded and draws the ones that pass; the server's order stands. The
     ticker matches by prefix and the name anywhere. A field a row lacks matches no filter: a
     placeholder has no designation or phase, and may have no sector or cap; a refusal has no
     designation, which is the row's own, never derived here; a row without a published report has
     no stance, the agent's word (spec 2026-11-06 Tier 2, 18.1). The row's phase is
     already the menu's number (the server maps the engine's phase name through PHASE_NUMBER),
     and its cap band is the menu's id once lower-cased (Mega is mega); small never matches, the
     universe's floor being $2 bn. A row on any chosen watchlist matches; Clean keeps the valued
     rows whose quality warnings count 0: a refusal or a placeholder has no value to be cheap on,
     so it is never clean (spec 2026-11-04 9.4, 9.5). */
  function narrow(rows, query, filters) {
    var needle = (query || '').trim().toLowerCase();
    return rows.filter(function (r) {
      var found = !needle || r.ticker.toLowerCase().indexOf(needle) === 0 ||
        (r.name || '').toLowerCase().indexOf(needle) !== -1;
      return found &&
        within(filters.designation, r.designation) &&
        within(filters.stance, r.agentStance) &&
        within(filters.phase, r.phase) &&
        within(filters.cap, (r.capBand || '').toLowerCase()) &&
        within(filters.sector, r.sector) &&
        within(filters.watchlist, r.watchlists || []) &&
        (!filters.reviewedOnly || r.reviewed != null) &&
        (!filters.hideExpired || r.freshness !== 'expired') &&
        (!filters.cleanOnly || (r.flagCount === 0 && r.fairValue != null));
    });
  }

  /* The menu's sectors: the screener's names found on the loaded rows, sorted, rather than the
     GICS names the design system lists by default. */
  function sectorsOf(rows) {
    var seen = {};
    rows.forEach(function (r) { if (r.sector != null) seen[r.sector] = true; });
    return Object.keys(seen).sort();
  }

  function note(text) { return h('p', { className: 'body app-note' }, text); }

  /* ------------------------------------------------------- the watchlist popup */

  /* The popup has a root of its own at the end of the page, so it opens over whichever view's
     table holds the mark (the Watchlists view's too) and over the drawer. */
  var watchMount = document.body.appendChild(document.createElement('div'));
  var watchRoot = ReactDOM.createRoot(watchMount);
  var latestLists = 0;
  var writes = Promise.resolve();

  /* The mark a click last landed on, by pointer, Enter or Space, read before ScreenTable hands
     onWatch the row alone: the popup opens under it. */
  var pressedMark = null;
  document.addEventListener('click', function (event) {
    pressedMark = event.target instanceof Element ? event.target.closest('.fb-watch') : null;
  }, true);

  /* The lists, on load and after every write; the screen draws again for the menu's names, the
     chip and the Watchlists column, and a chosen list that is gone leaves the filter. The promise
     settles once they are in or their failure is noted; it never rejects. */
  function reloadWatchlists() {
    var request = ++latestLists;
    return getJson('/api/watchlists')
      .then(function (lists) {
        if (request !== latestLists) return;
        state.watchlists = lists;
        state.watchlistsError = null;
        var ids = lists.map(function (w) { return w.id; });
        var kept = state.filters.watchlist.filter(function (id) { return ids.indexOf(id) !== -1; });
        if (kept.length < state.filters.watchlist.length) {
          state.filters = Object.assign({}, state.filters, { watchlist: kept });
        }
        render();
      })
      .catch(function (err) {
        if (request !== latestLists) return;
        state.watchlistsError = 'The watchlists did not load: ' + err.message +
          '. Reload the page to try again.';
        render();
      });
  }

  /* The ids of the lists a company is on, from the lists; before they load, from its row. */
  function membersOf(symbol, row) {
    if (!state.watchlists) return ((row && row.watchlists) || []).slice();
    return state.watchlists.filter(function (w) {
      return w.symbols.some(function (s) { return s.symbol === symbol; });
    }).map(function (w) { return w.id; });
  }

  /* onWatch: a mark opens its popup, or closes it when the popup is its own. */
  function watch(row) {
    var anchor = pressedMark;
    if (!anchor || (state.watch && state.watch.anchor === anchor)) {
      closeWatch();
      return;
    }
    state.watch = {
      symbol: row.ticker, anchor: anchor, ids: membersOf(row.ticker, row), name: '', error: null
    };
    renderWatch();
  }

  function closeWatch() {
    state.watch = null;
    renderWatch();
  }

  function renderWatch() {
    watchRoot.render(state.watch ? h(WatchMenu, {
      watch: state.watch, lists: state.watchlists || [], error: state.watchlistsError
    }) : null);
  }

  function putMemberships(symbol, ids) {
    return api.put('/api/watchlists/memberships/' + encodeURIComponent(symbol), { ids: ids });
  }

  /* A box changed: the company's lists as the boxes now stand, written at once. */
  function toggleList(w, id) {
    w.ids = w.ids.indexOf(id) === -1 ? w.ids.concat([id])
      : w.ids.filter(function (held) { return held !== id; });
    var ids = w.ids;
    queue(w, function () {
      return putMemberships(w.symbol, ids).then(function (r) { return refusal('Not saved', r); });
    });
  }

  /* Add: the list is created, then the company put on it beside the lists it is on, one step. */
  function addList(w) {
    var name = w.name.trim();
    if (!name) return;
    queue(w, function () {
      return api.post('/api/watchlists', { name: name }).then(function (r) {
        if (!r.ok) return refusal('Not created', r);
        w.name = '';
        w.ids = w.ids.concat([r.body.id]);
        return putMemberships(w.symbol, w.ids).then(function (put) {
          return refusal('Not saved', put);
        });
      });
    });
  }

  /* A refused write's sentence, with the server's reason; null for a write it took. */
  function refusal(head, r) {
    if (r.ok) return null;
    return head + ': ' + (r.body && r.body.detail ? String(r.body.detail)
      : 'the server answered ' + r.status) + '.';
  }

  /* The popup's writes run one after another in the order made, so a quick second change never
     lands before the first. After each, the rows and the lists load again and the mark follows;
     a refused write shows its sentence and puts the boxes back as the server has them. */
  function queue(w, step) {
    w.error = null;
    renderWatch();
    writes = writes.then(step).catch(function (err) {
      return 'Not saved: ' + err.message + '.';
    }).then(function (error) {
      w.error = error;
      load();
      return reloadWatchlists();
    }).then(function () {
      if (w.error) w.ids = membersOf(w.symbol, null);
      renderWatch();
    });
  }

  /* The popup, in the bundle's menu style as Details ▾ draws it: a box per list, ticked where the
     company is on it, then the New watchlist field and Add. Fixed under the mark, or over it when
     the mark sits low in the window; it follows the mark as the page scrolls and closes when the
     mark is gone (its row narrowed away) or hidden. It stands at the end of the page, away from
     the mark, so focus moves into it as it opens. */
  function WatchMenu(props) {
    var w = props.watch;
    var ref = React.useRef(null);
    React.useLayoutEffect(function () {
      if (!w.anchor.getClientRects().length) { /* gone, or its view hidden */
        closeWatch();
        return;
      }
      var rect = w.anchor.getBoundingClientRect();
      var style = ref.current.style;
      var below = rect.bottom < window.innerHeight * 0.6;
      style.left = Math.max(0, Math.min(rect.left,
        window.innerWidth - ref.current.offsetWidth)) + 'px';
      style.top = below ? rect.bottom + 4 + 'px' : 'auto';
      style.bottom = below ? 'auto' : window.innerHeight - rect.top + 4 + 'px';
    });
    React.useEffect(function () {
      var first = ref.current.querySelector('input');
      if (first) first.focus();
    }, [w.anchor]);
    var lists = props.lists;
    var error = w.error || props.error;
    return h('div', {
      ref: ref, className: 'fb-menu fb-menu--filters app-watch', role: 'group',
      'aria-label': 'Watchlists for ' + w.symbol
    },
      h('div', { className: 'fb-menu__body' },
        h('div', { className: 'fb-menu__sec' },
          h('span', { className: 'fb-menu__h label' }, 'WATCHLISTS'),
          lists.length ? lists.map(function (list) {
            return h('label', { key: list.id, className: 'fb-menu__row control' },
              h('input', {
                type: 'checkbox', checked: w.ids.indexOf(list.id) !== -1,
                onChange: function () { toggleList(w, list.id); }
              }),
              h('span', null, list.name));
          }) : h('div', { className: 'body app-muted app-watch__none' }, 'none'))),
      h('div', { className: 'fb-menu__foot' },
        h('form', {
          className: 'app-watch__new',
          onSubmit: function (event) { event.preventDefault(); addList(w); }
        },
          h('input', {
            type: 'text', className: 'control app-watch__name', placeholder: 'New watchlist',
            'aria-label': 'New watchlist', maxLength: 60, value: w.name,
            onChange: function (event) { w.name = event.target.value; renderWatch(); }
          }),
          h(F.Button, { type: 'submit', size: 'sm', disabled: !w.name.trim() }, 'Add')),
        error ? h('p', { className: 'caption app-watch__error' }, error) : null));
  }

  /* The popup closes on a press or focus outside it and its mark, and on Escape, which hands
     focus back to the mark: the three listeners controls.js gives Details ▾. A press on its own
     mark belongs to the mark, which closes it through onWatch. It follows its mark when anything
     scrolls and when the window resizes. */
  function closeWatchOutside(event) {
    var w = state.watch;
    if (!w || !(event.target instanceof Node)) return;
    if (watchMount.contains(event.target) || w.anchor.contains(event.target)) return;
    closeWatch();
  }
  document.addEventListener('pointerdown', closeWatchOutside);
  document.addEventListener('focusin', closeWatchOutside);
  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape' || !state.watch) return;
    var anchor = state.watch.anchor;
    closeWatch();
    if (anchor.isConnected) anchor.focus();
  });
  document.addEventListener('scroll', function () { if (state.watch) renderWatch(); }, true);
  window.addEventListener('resize', function () { if (state.watch) renderWatch(); });

  /* ------------------------------------------------------- the sticky bar and Top */

  /* The design system's ScreenTable, its bar measured. The bar sticks at the top of the scroller
     and the header cells stick under it at --bar-height, which follows the bar's height as its
     chips wrap (classifier-designation spec 8.2). Sideways, the bar stays in view within
     --scroller-width, the scroller's width less its scrollbar, which follows the window and the
     drawer; a scroller made taller can leave Top's threshold behind without a scroll, so the
     observer asks again. The observer lives as long as the table; without ResizeObserver the
     header takes the bar's one-line height and the bar the screen's width. The Groups view hides
     the screen, whose scroller then measures 0 wide: the observer keeps the last measures, and
     takes new ones when the screen shows again. */
  function Screen(props) {
    React.useEffect(function () {
      var bar = document.querySelector('.fb-screen__bar');
      if (!bar || typeof ResizeObserver === 'undefined') return undefined;
      var main = bar.closest('.app-main');
      var observer = new ResizeObserver(function () {
        if (main.clientWidth === 0) return;
        main.style.setProperty('--bar-height', bar.offsetHeight + 'px');
        main.style.setProperty('--scroller-width', main.clientWidth + 'px');
        pastFirstScreen(main);
      });
      observer.observe(bar);
      observer.observe(main);
      return function () { observer.disconnect(); };
    }, []);
    return h(F.ScreenTable, props);
  }

  function scrolled(event) { pastFirstScreen(event.currentTarget); }

  /* Top shows while the scroller is more than one screen down, and only then (spec 8.3); the
     page draws again only when that changes, not on every scroll. */
  function pastFirstScreen(main) {
    var past = main.scrollTop > main.clientHeight;
    if (past === state.pastFirstScreen) return;
    state.pastFirstScreen = past;
    render();
  }

  /* Back to the top at once, no smooth scrolling, and focus to FIND, since Top goes there. */
  function toTop() {
    var main = document.querySelector('.app-main');
    main.scrollTop = 0;
    document.getElementById('fb-q').focus();
  }

  function render() {
    var d = state.drawer;
    var main = null;
    if (state.error) {
      main = note(state.error);
    } else if (state.rows && state.rows.length === 0) {
      main = note('No snapshots yet. Run a refresh.');
    } else if (state.rows) {
      /* A narrowing that leaves no row still draws the table: its bar says 0 of the total and
         offers Clear. The drawer stays open when its row is narrowed away. */
      var rows = narrow(state.rows, state.query, state.filters);
      main = h(Screen, {
        rows: d ? rows.map(function (r) {
          return r.ticker === d.symbol ? Object.assign({}, r, { selected: true }) : r;
        }) : rows,
        total: state.rows.length,
        query: state.query,
        onQueryChange: setQuery,
        filters: state.filters,
        onFiltersChange: setFilters,
        sectors: sectorsOf(state.rows),
        columns: state.columns,
        onColumnsChange: setColumns,
        sort: state.sort,
        onSort: sortBy,
        onOpen: open,
        onWatch: watch,
        watchlists: state.watchlists || [],
        chooser: true
      });
    }
    /* Top comes after the table and before the drawer, so Shift+Tab from the drawer reaches it. */
    root.render(h('div', { className: d ? 'app-layout app-layout--drawer' : 'app-layout' },
      h('div', { className: 'app-main', onScroll: scrolled }, main),
      state.pastFirstScreen ? h(F.Button, {
        variant: 'quiet', size: 'sm', 'aria-label': 'Back to top', className: 'app-top',
        onClick: toTop
      }, 'Top ↑') : null,
      d ? drawer(d) : null));
    renderWatch();
    var page = window.FairbandPage;
    if (page.onRender) page.onRender();
  }

  /* ------------------------------------------------------------------ the drawer */

  function drawer(d) {
    var content;
    if (d.error) content = note(d.error);
    else if (d.body) content = sections(d.body);
    else content = h('h2', { className: 'ticker app-drawer__ticker' }, d.symbol);
    return h('aside', { className: 'app-drawer', 'aria-label': 'Detail for ' + d.symbol },
      h('div', { className: 'app-drawer__bar' },
        h(F.Button, { variant: 'quiet', size: 'sm', onClick: close }, 'Close')),
      h('div', { className: d.loading ? 'app-drawer__body is-loading' : 'app-drawer__body' },
        content));
  }

  /* The drawer's main view (spec 2026-11-06 Tier 2, 18.2), in this order and nothing else: the
     head; the meter with its levels and the route's lines under it, the reviewed value its second
     marker and named in its caption, or in its place the refusal, as before; the stance line when
     a report exists, the report's word in the row's chip classes, faded once the window of the
     snapshot it rests on has expired, then who published it and when; the report's Summary, its
     first section, then Open the report, a link to the report page; without a report, Request
     research with its menu, the server's refusal under it and the open item's line; then
     Details ▾, a disclosure over everything else (details). */
  function sections(body) {
    var r = body.result;
    var im = r.intermediates;
    var phase = PHASE_NUMBER[r.phase.phase];
    var valued = isValued(r);
    var growth = r.route === 'revenue-growth';
    var report = body.report;
    var banded = isBanded(body);
    var ask = asked(r.symbol);
    return [
      h('header', { key: 'head', className: 'app-drawer__head' },
        h('h2', { className: 'ticker app-drawer__ticker' }, r.symbol),
        phase ? h(F.PhaseBadge, { phase: phase, size: 'sm' }) : null,
        body.company && body.company.name
          ? h('p', { className: 'body app-drawer__name' }, body.company.name) : null),
      valued ? section('band', null, meter(body),
        levels(r),
        h('p', { className: 'caption app-muted' }, ROUTES[r.route] || r.route),
        youngGrowth(im.failure_probability),
        crossCheck(im.growth_route),
        growth ? discountedAt(r.inputs) : null) : null,
      /* A refused row whose secondary valuation counts on the latest snapshot shows that value in
         the screen's Reviewed column (spec 2026-11-06 Tier 2, 18.1), so the drawer draws the
         secondary's band against the price, its word at today's price, and the refusal stays
         under it (the ruling of 2026-11-07). A refused row with none has the refusal alone. */
      banded ? section('secondary-band', null, meter(body)) : null,
      /* A refusal takes the band's place: it is the answer when there is no value. A growth row
         refused with its revenue path still shows the margin the price needs (spec 5.11). A
         Mature Stable row refused for its trailing earnings shows the growth-route cross-check
         under the refusal, as a valued row shows it under the band (spec 2026-11-06 9); a
         revenue-growth refusal's cross-check does not move with the price, so it shows only among
         the intermediates. */
      r.refusal ? section('refusal', 'Refusal',
        h('p', { className: 'body app-refusal' }, r.refusal),
        'implied_margin' in im ? pairs([
          ['Margin the price needs', F.formatPercent(im.implied_margin), true]
        ]) : null,
        'e_trailing' in im ? crossCheck(im.growth_route) : null) : null,
      report ? h('p', { key: 'stance', className: 'app-stance' },
        h('span', {
          className: 'fb-stance fb-stance--' + report.stance +
            (report.expired ? ' fb-stance--expired' : '') + ' label',
          title: report.expired ? 'The snapshot window of this report has expired' : null
        }, report.stance),
        h(F.PrincipalChip, {
          principal: report.principal, actor: report.actor, at: localIso(report.createdAt)
        })) : null,
      report ? section('summary', null,
        h(F.ReportReader, {
          mode: report.mode, state: 'published', revision: 'revision ' + report.revision,
          sections: [report.summary], appendixes: false,
          /* the Summary's cites numbered as the report page's references list numbers them, so
             a number reads the same in both (13.1, 18.4) */
          footnotes: footnotes(report.references)
        }),
        h('p', { className: 'app-open' },
          h(F.Button, { href: '#report/' + encodeURIComponent(r.symbol) }, 'Open the report')))
        : section('request', null,
          requestResearch(ask, body.item, render, function () { reloadDetail(r.symbol); })),
      h('div', { key: 'disclosure', className: 'app-section app-disclosure' },
        h(F.Button, {
          variant: 'quiet', size: 'sm',
          'aria-expanded': state.detailsOpen ? 'true' : 'false',
          onClick: toggleDetails
        }, 'Details ▾')),
      state.detailsOpen ? details(body) : null
    ];
  }

  /* The meter of a company's detail (spec 2026-11-06 Tier 2, 18.2 and 18.4), as the drawer and
     the report page draw it: a valued row's mechanical band against the price, the reviewed value
     its second marker when the review on the latest snapshot has one, its caption the row's word
     and price ÷ value; a refused row whose secondary valuation counts on the latest snapshot, the
     secondary's band, its word at today's price (the ruling of 2026-11-07); else none. The scale
     is off: the drawer names the levels under it. `hero` false sets the meter's price in figure,
     under the report page's one headline figure; the drawer passes none. */
  function meter(body, hero) {
    var r = body.result;
    var review = body.review;
    var secondary = body.secondary;
    if (isValued(r)) {
      return h(F.BandMeter, {
        low: r.levels.fair_low, high: r.levels.fair_high, price: r.price, fairValue: r.value,
        buyLevel: r.levels.buy, trimLevel: r.levels.trim, designation: r.designation,
        reviewedValue: review && review.value != null ? review.value : null,
        showScale: false, caption: standing(r, body.designationEdges), hero: hero
      });
    }
    if (!isBanded(body)) return null;
    return h(F.BandMeter, {
      low: secondary.levels.fairLow, high: secondary.levels.fairHigh, price: r.price,
      fairValue: secondary.valuePerShare, buyLevel: secondary.levels.buy,
      trimLevel: secondary.levels.trim, designation: secondary.designation,
      showScale: false, caption: secondaryCaption(secondary, body.designationEdges), hero: hero
    });
  }

  /* A row the engine valued: a value, its levels and a price to draw them against. */
  function isValued(r) {
    return r.value != null && r.levels != null && r.price != null;
  }

  /* A refused row whose secondary valuation, which the detail carries only while it counts on the
     latest snapshot, has levels, and a price to draw them against: its meter is the secondary's. */
  function isBanded(body) {
    var r = body.result;
    var s = body.secondary;
    return !isValued(r) && !!r.refusal && !!s && !!s.levels && r.price != null;
  }

  /* A report's references, [{ n, ref, source }], as ReportReader's footnotes, ref → n (spec 13.1):
     the drawer's Summary and the report page number a cite alike, by the full report's list. */
  function footnotes(references) {
    var marks = {};
    (references || []).forEach(function (e) { marks[e.ref] = e.n; });
    return marks;
  }

  /* Details (spec 2026-11-06 Tier 2, 18.3), in order: the review, its bridge from the mechanical
     value when it has a value, each line under its input's label, or its refusal; the secondary
     valuation; the overrides, each a record, read-only; the guidance on file; the latest report's
     judgments; the kill criteria; the news items; the notes, with Add a note; the findings; the
     company's ledger rows; then what the drawer showed before Details, in its order. The review
     and the secondary come with the detail; the rest is its own read (readResearch). A list with
     nothing in it is left out, but for the notes, which carry the owner's field. */
  function details(body) {
    var r = body.result;
    var im = r.intermediates;
    var phase = PHASE_NUMBER[r.phase.phase];
    var growth = r.route === 'revenue-growth';
    var estimates = r.inputs.filter(function (i) { return i.kind === 'estimate'; });
    var review = body.review;
    var secondary = body.secondary;
    var found = state.research && state.research.symbol === r.symbol ? state.research : null;
    var rs = found && found.body;
    var draft = drafted(r.symbol);
    return h('div', { key: 'details', className: 'app-drawer__details' },
      review && review.value != null ? section('bridge', 'Review',
        h(F.ValueBridge, {
          mechanical: review.mechanical, reviewed: review.value,
          overrides: review.bridge.map(function (line) {
            return {
              tag: line.label,
              from: inputFigure(line.old, line.unit), to: inputFigure(line.new, line.unit),
              delta: line.delta == null ? undefined : line.delta,
              principal: line.principal, actor: line.actor, reason: line.reason
            };
          }),
          note: reviewedLevels(review.levels)
        })) : null,
      review && review.refusal ? section('review', 'Review',
        h('p', { className: 'body app-refusal' }, review.refusal)) : null,
      secondary ? block('app-secondary', 'Secondary valuation',
        pairs(secondaryRows(secondary)),
        secondaryPath(secondary),
        h('p', { className: 'app-chipline' }, h(F.PrincipalChip, {
          principal: secondary.principal, actor: secondary.actor,
          at: localIso(secondary.createdAt)
        }))) : null,
      found && found.error ? h('p', {
        key: 'unread', className: 'caption app-section app-notes__error'
      }, found.error) : null,
      rs || (found && found.error) ? null : h('p', {
        key: 'reading', className: 'caption app-muted app-section'
      }, 'Reading the research records.'),
      rs && rs.overrides.length ? block('app-overrides', 'Overrides',
        rs.overrides.map(function (o) {
          /* Its step in the valued review on the latest snapshot gives an applied override its
             effect; outside one (no review there, after a revalue, or one that refused) its
             Result row says so instead. */
          var line = review ? review.bridge.filter(function (l) {
            return l.overrideId === o.id;
          })[0] : null;
          var effect = line && line.delta != null && review.value != null ? line.delta : undefined;
          return h(F.OverrideRecord, {
            key: o.id, tag: o.tag, from: inputFigure(o.old, o.unit),
            to: inputFigure(o.new, o.unit),
            lifetime: o.lifetime, period: o.period, reason: o.reason, evidence: o.evidence,
            principal: o.principal, actor: o.actor,
            state: o.state,
            message: o.state === 'dropped' ? o.dropReason : o.message,
            effect: effect,
            reviewed: effect === undefined ? undefined : review.value,
            validUntil: effect === undefined ? undefined : r.valid_until,
            resultNote: effect === undefined ? NO_EFFECT : undefined
          });
        })) : null,
      rs && rs.guidance.length ? block('app-guidance', 'Guidance on file',
        guidanceTable(rs.guidance.map(function (g) {
          return Object.assign({}, g, {
            state: g.supersededBy == null ? 'current' : 'superseded by record ' + g.supersededBy,
            citedBy: citedBy(rs.overrides, g.id)
          });
        }))) : null,
      rs && rs.judgments.length ? block('app-judgments', 'Judgments',
        h('ul', { className: 'app-list' }, rs.judgments.map(function (j) {
          return h('li', { key: j.id },
            h('span', { className: 'label' }, words(j.judgment)),
            h('p', { className: 'body' }, j.decision));
        }))) : null,
      rs && rs.killCriteria.length ? block('app-kill-criteria', 'Kill criteria',
        h('ul', { className: 'app-list' }, rs.killCriteria.map(function (k) {
          return h('li', { key: k.id },
            h('span', { className: 'label' }, k.state),
            h('p', { className: 'body' }, k.text),
            k.stateReason ? h('p', { className: 'caption app-muted' },
              k.stateReason, ' · ', when(k.stateAt)) : null);
        }))) : null,
      rs && rs.newsItems.length ? block('app-news', 'News items',
        h('ul', { className: 'app-list' }, rs.newsItems.map(function (n) {
          return h('li', { key: n.id },
            h('span', { className: 'caption app-line' }, when(n.date),
              n.killCriterionId != null ? ' · touches kill criterion ' + n.killCriterionId : null),
            h('p', { className: 'body' }, n.headline),
            h('p', { className: 'caption app-muted' }, n.text),
            h('p', { className: 'caption app-muted app-source' }, n.source));
        }))) : null,
      block('app-notes', 'Notes',
        rs ? (rs.notes.length ? h('ul', { className: 'app-list' }, rs.notes.map(function (n) {
          return h('li', { key: n.id },
            h('p', { className: 'body app-notes__text' }, n.text),
            h('p', { className: 'app-chipline' },
              h(F.PrincipalChip, { principal: n.principal, actor: n.actor, at: localIso(n.at) }),
              n.overrideId != null ? h('span', { className: 'caption app-muted' },
                ' on override ' + n.overrideId) : null));
        })) : h('p', { className: 'caption app-muted' }, 'none')) : null,
        h('form', {
          className: 'app-notes__new',
          onSubmit: function (event) { event.preventDefault(); postNote(r.symbol); }
        },
          h('textarea', {
            className: 'control app-field app-notes__field', rows: 3, value: draft.text,
            placeholder: 'A note on ' + r.symbol, 'aria-label': 'A note on ' + r.symbol,
            onChange: function (event) { draft.text = event.target.value; render(); }
          }),
          h(F.Button, {
            type: 'submit', size: 'sm', disabled: draft.posting || !draft.text.trim()
          }, 'Add a note')),
        draft.error ? h('p', { className: 'caption app-notes__error' }, draft.error) : null),
      rs && rs.findings.length ? block('app-findings', 'Findings',
        h('ul', { className: 'app-list' }, rs.findings.map(function (f) {
          return h('li', { key: f.id },
            h('span', { className: 'caption app-line' }, 'as of ', when(f.asOf),
              f.period ? ' · ' + f.period : null),
            h('p', { className: 'body' }, f.text, f.value != null ? h('span',
              { className: 'figure-sm' }, ' ' + findingFigure(f.value, f.unit)) : null),
            h('p', { className: 'caption app-muted app-source' }, f.source.kind + ' ',
              h('code', { className: 'fb-tag figure-sm' }, f.source.ref),
              f.source.note ? ' — ' + f.source.note : null),
            h('p', { className: 'app-chipline' },
              h(F.PrincipalChip, { principal: f.principal, actor: f.actor, at: localIso(f.at) })));
        }))) : null,
      rs && rs.ledger.length ? block('app-ledger', 'Ledger',
        h('ul', { className: 'app-list' }, rs.ledger.map(function (e) {
          return h('li', { key: e.id },
            h('p', { className: 'app-chipline' },
              h(F.PrincipalChip, { principal: e.principal, actor: e.actor, at: localIso(e.at) })),
            h('p', { className: 'body' }, h('span', { className: 'label' }, e.kind), ' ',
              e.summary));
        }))) : null,
      /* What the drawer showed before Details, in its order. The window reads aging from the
         effective aging_fraction, as the Freshness column does (spec 2026-11-04 8.2). */
      section('window', null, h(F.ValidityWindow, {
        asOf: r.data_date, observedAt: r.data_date,
        enteredAt: localIso(body.snapshot.createdAt),
        validFrom: r.data_date, validUntil: r.valid_until, today: body.today,
        agingFraction: body.agingFraction
      })),
      section('phase', 'Phase evidence', pairs(evidence(r.phase, phase)),
        methodologyLink(r, phase)),
      growth ? revenueRoute(r) : null,
      /* A Decline row refused for a value at or below zero keeps its figures but has no route,
         and a Start-up row is always a refusal with its figures: each draws from the
         intermediates only its route writes. */
      'runoff_path' in im ? declineRoute(r) : null,
      'requirement' in im ? startUpRoute(r) : null,
      section('inputs', 'Inputs', inputsTable(r.inputs)),
      section('intermediates', 'Intermediate results', intermediates(r.intermediates)),
      section('flags', 'Flags', r.flags.length ? h('ul', { className: 'app-list' },
        r.flags.map(function (f) {
          return h('li', { key: f.code },
            h('span', { className: 'label' }, f.word),
            h('p', { className: 'body' }, f.sentence));
        })) : h('p', { className: 'caption app-muted' }, 'none')),
      estimates.length ? section('estimates', 'Estimates', h('ul', { className: 'app-list' },
        estimates.map(function (i) {
          return h('li', { key: i.name },
            h('span', { className: 'figure-sm' }, i.name),
            h('p', { className: 'body' }, i.estimate_method || 'no method recorded'));
        }))) : null,
      h('p', { key: 'versions', className: 'caption app-muted app-section' },
        'Policy ' + r.policy_version + ' · method ' + r.method_version));
  }

  /* ------------------------------------------------- the drawer's requests and Details' reads */

  /* Request research's state for the drawer's company, kept until the drawer shows another. */
  function asked(symbol) {
    if (!state.request || state.request.symbol !== symbol) state.request = asking(symbol);
    return state.request;
  }

  /* A company's Request research, as the drawer and the report page each keep one, so the drawer
     on one company never resets the report page's on another: the menu closed, the mode a full
     report, since a company with no report has no full report a valuation review could reuse,
     and no note. */
  function asking(symbol) {
    return {
      symbol: symbol, open: false, mode: 'full report', note: '', error: null, posting: false
    };
  }

  /* Request research (spec 18.2), as the drawer and the report page show it without a report
     (18.4): the button, disabled while an item is open, its menu, the server's refusal under it
     and the open item's line. `ask` is the view's request (asking), `redraw` draws the view again
     and `after` runs once a post ends, taken or refused, so the view reads its company again and
     the open item's line follows. */
  function requestResearch(ask, item, redraw, after) {
    return h(React.Fragment, null,
      h('div', { className: 'app-request' },
        h(F.Button, {
          disabled: !!item,
          'aria-expanded': ask.open ? 'true' : 'false',
          onClick: function () { toggleRequest(ask, redraw); }
        }, 'Request research'),
        ask.open ? h(RequestMenu, { ask: ask, redraw: redraw, after: after }) : null),
      ask.error ? h('p', { className: 'caption app-request__error' }, ask.error) : null,
      requested(item));
  }

  function toggleRequest(ask, redraw) {
    ask.open = !ask.open;
    ask.error = null;
    redraw();
  }

  /* Request research's menu (spec 18.2), in the bundle's menu style as Details ▾ draws it: the
     mode, a radio each, the note line, then Post. It opens under its button from the button's left
     edge, focus on the chosen mode; Post, or Enter in the note line, sends it. A press or focus
     outside the button and its menu closes it, as the screen's menus close, and so does Escape,
     which hands focus back to the button; the listeners last as long as the menu, and the
     drawer's own Escape, registered first, sees the menu open and waits. */
  function RequestMenu(props) {
    var ask = props.ask;
    var redraw = props.redraw;
    var after = props.after;
    var ref = React.useRef(null);
    React.useEffect(function () {
      var control = ref.current.parentNode;
      var chosen = ref.current.querySelector('input:checked');
      if (chosen) chosen.focus();
      function outside(event) {
        if (!(event.target instanceof Element) || control.contains(event.target)) return;
        ask.open = false;
        redraw();
      }
      function escape(event) {
        if (event.key !== 'Escape') return;
        ask.open = false;
        redraw();
        control.querySelector(':scope > .fb-btn').focus();
      }
      document.addEventListener('pointerdown', outside);
      document.addEventListener('focusin', outside);
      document.addEventListener('keydown', escape);
      return function () {
        document.removeEventListener('pointerdown', outside);
        document.removeEventListener('focusin', outside);
        document.removeEventListener('keydown', escape);
      };
    }, []);
    return h('form', {
      ref: ref, className: 'fb-menu fb-menu--filters app-request__menu',
      'aria-label': 'Request research on ' + ask.symbol,
      onSubmit: function (event) { event.preventDefault(); postRequest(ask, redraw, after); }
    },
      h('div', { className: 'fb-menu__body' },
        h('div', { className: 'fb-menu__sec', role: 'radiogroup', 'aria-label': 'Mode' },
          h('span', { className: 'fb-menu__h label' }, 'MODE'),
          REQUEST_MODES.map(function (mode) {
            return h('label', { key: mode, className: 'fb-menu__row control' },
              h('input', {
                type: 'radio', name: 'app-request-mode', value: mode, checked: ask.mode === mode,
                onChange: function () { ask.mode = mode; redraw(); }
              }),
              h('span', null, mode));
          })),
        h('hr'),
        h('label', { className: 'fb-menu__sec app-request__line' },
          h('span', { className: 'fb-menu__h label' }, 'NOTE'),
          h('input', {
            type: 'text', className: 'control app-field', maxLength: 200, value: ask.note,
            placeholder: 'What to look at, if anything',
            onChange: function (event) { ask.note = event.target.value; redraw(); }
          }))),
      h('div', { className: 'fb-menu__foot' },
        h(F.Button, { type: 'submit', size: 'sm', disabled: ask.posting }, 'Post')));
  }

  /* Post: the item, as the owner (no identity headers), with the request header every page write
     carries. The menu closes; a refusal, a second open item's 409 among them, shows the server's
     sentence under the button as it arrives, the note kept for another try. Either way `after`
     runs, so the view reads its company again and the open item's line follows. */
  function postRequest(ask, redraw, after) {
    if (ask.posting) return;
    ask.posting = true;
    ask.error = null;
    redraw();
    api.post('/api/inbox', { symbol: ask.symbol, mode: ask.mode, note: ask.note.trim() })
      .then(function (r) {
        if (!r.ok) throw new Error(r.body && r.body.detail ? String(r.body.detail)
          : 'the server answered ' + r.status);
        ask.note = '';
      })
      .catch(function (err) { ask.error = err.message; })
      .then(function () {
        ask.posting = false;
        ask.open = false;
        after();
      });
  }

  /* The open item's line under Request research, until the item is done or declined. */
  function requested(item) {
    if (!item) return null;
    return h('p', { className: 'caption app-requested' },
      'Requested · ' + (item.state === 'claimed' ? 'claimed by ' + item.claimedBy : 'pending'));
  }

  /* The drawer's company read again in place after a write that changes its detail, while the
     drawer still shows it and nothing else is loading; a failed read leaves what it shows. */
  function reloadDetail(symbol) {
    var d = state.drawer;
    if (!d || d.symbol !== symbol || d.loading) {
      render();
      return;
    }
    var request = ++latestDetail;
    getJson('/api/companies/' + encodeURIComponent(symbol))
      .then(function (body) {
        if (request !== latestDetail) return;
        state.drawer = { symbol: symbol, body: body, loading: false, error: null };
      })
      .catch(function () { /* the drawer keeps what it shows */ })
      .then(render);
  }

  /* Details ▾: open or closed for the page's life; opening it reads the records of a company not
     yet read, or whose read failed. */
  function toggleDetails() {
    state.detailsOpen = !state.detailsOpen;
    var d = state.drawer;
    if (state.detailsOpen && d && needsResearch(d.symbol)) readResearch(d.symbol);
    render();
  }

  function needsResearch(symbol) {
    var found = state.research;
    return !found || found.symbol !== symbol || found.error != null;
  }

  /* Details' records (GET /api/companies/{symbol}/research), the latest read winning. A read again
     for the same company, after a note, keeps the records on show until the new ones land. */
  function readResearch(symbol) {
    var request = ++latestResearch;
    var kept = state.research && state.research.symbol === symbol ? state.research.body : null;
    state.research = { symbol: symbol, body: kept, error: null };
    getJson('/api/companies/' + encodeURIComponent(symbol) + '/research')
      .then(function (body) {
        if (request !== latestResearch) return;
        state.research = { symbol: symbol, body: body, error: null };
        render();
      })
      .catch(function (err) {
        if (request !== latestResearch) return;
        state.research = {
          symbol: symbol, body: kept, error: 'The research records did not load: ' +
            err.message + '. Close Details and open it again to retry.'
        };
        render();
      });
  }

  /* Add a note's field for the drawer's company, kept until the drawer shows another. */
  function drafted(symbol) {
    if (!state.noteDraft || state.noteDraft.symbol !== symbol) {
      state.noteDraft = { symbol: symbol, text: '', error: null, posting: false };
    }
    return state.noteDraft;
  }

  /* Add a note: the note, as the owner, with the request header every page write carries; a
     refusal shows the server's sentence under the field, the text kept. Taken, the field clears
     and, while the drawer still shows the company, the records are read again, the new note
     first among them. */
  function postNote(symbol) {
    var draft = drafted(symbol);
    var text = draft.text.trim();
    if (!text || draft.posting) return;
    draft.posting = true;
    draft.error = null;
    render();
    api.post('/api/companies/' + encodeURIComponent(symbol) + '/notes', { text: text })
      .then(function (r) {
        if (!r.ok) throw new Error(r.body && r.body.detail ? String(r.body.detail)
          : 'the server answered ' + r.status);
        draft.text = '';
        if (state.drawer && state.drawer.symbol === symbol) readResearch(symbol);
      })
      .catch(function (err) { draft.error = err.message; })
      .then(function () {
        draft.posting = false;
        render();
      });
  }

  /* --------------------------------------------------------- Details' figures */

  /* A section of Details with a class of its own beside app-section. */
  function block(className, title) {
    var head = title ? h('h3', { className: 'heading' }, title) : null;
    return h.apply(null, ['section', { key: className, className: 'app-section ' + className },
      head].concat(Array.prototype.slice.call(arguments, 2)));
  }

  /* An override's or a bridge line's value in its input's unit (overrides.TAGS): a word as it
     is, a multiple to two decimals with x, any other figure as the inputs table reads its unit. */
  function inputFigure(v, unit) {
    if (typeof v === 'string') return v;
    return unit === 'multiple' ? times(v) : inputValue({ value: v, unit: unit });
  }

  /* The bridge's note: the reviewed value's own levels, which the meter, drawn on the mechanical
     band, does not show. */
  function reviewedLevels(l) {
    if (!l) return undefined;
    return 'Reviewed levels: margin of safety ' + F.formatMoney(l.buy) + ' · fair band ' +
      F.formatMoney(l.fairLow) + ' – ' + F.formatMoney(l.fairHigh) + ' · trim ' +
      F.formatMoney(l.trim);
  }

  /* The secondary valuation: its form, its value a share and its levels where it has them. */
  function secondaryRows(s) {
    var rows = [
      ['Form', s.form, false],
      ['Value a share', F.formatMoney(s.valuePerShare), true]
    ];
    var l = s.levels;
    if (l) {
      rows.push(['Margin of safety', F.formatMoney(l.buy), true],
        ['Fair band', F.formatMoney(l.fairLow) + ' – ' + F.formatMoney(l.fairHigh), true],
        ['Trim level', F.formatMoney(l.trim), true]);
    }
    return rows;
  }

  /* The secondary valuation's path (spec 18.3): on the parts form each part's name and its value,
     a total in whole dollars, with its note under it; on the drivers form the drivers in words,
     the rates as percentages. */
  function secondaryPath(s) {
    if (s.form === 'parts') {
      return h('ul', { className: 'app-list app-secondary__path' }, s.parts.map(function (p, i) {
        return h('li', { key: i },
          h('span', { className: 'app-line' },
            h('span', { className: 'body' }, p.name), ' ',
            h('span', { className: 'figure-sm' }, whole(p.value))),
          p.note ? h('p', { className: 'caption app-muted' }, p.note) : null);
      }));
    }
    var d = s.drivers;
    if (!d) return null;
    return h('div', { className: 'app-secondary__path' }, pairs([
      ['Years', plain(d.years), true],
      ['Revenue growth', percents(d.revenueGrowth), true],
      ['Operating margin', percents(d.operatingMargin), true],
      ['Tax rate', F.formatPercent(d.taxRate), true],
      ['Sales to capital', times(d.salesToCapital), true],
      ['Terminal growth', F.formatPercent(d.terminalGrowth), true]
    ]));
  }

  /* A list of rates, each a percent: 10.0%, 8.0%, 5.0%. */
  function percents(list) {
    return list.map(function (v) { return F.formatPercent(v); }).join(', ');
  }

  /* The ids of the overrides whose evidence cites guidance record `id`, guidance:<id>, as the
     server reads such a ref (refs.guidance_cited). */
  function citedBy(overrides, id) {
    return overrides.filter(function (o) {
      return (o.evidence || []).some(function (e) {
        var found = /^guidance:(\d+)$/.exec(String(e.ref).trim());
        return e.kind === 'guidance' && found !== null && Number(found[1]) === id;
      });
    }).map(function (o) { return o.id; });
  }

  /* A guidance figure in its metric's unit (store.guidance.UNITS): EPS to cents, a margin or a
     growth rate as a percent, any other a total in whole dollars. A point is one figure. */
  var GUIDED_PERCENT = ['operating_margin', 'revenue_growth', 'eps_growth'];

  function guided(v, metric) {
    if (metric === 'eps') return F.formatMoney(v);
    if (GUIDED_PERCENT.indexOf(metric) !== -1) return F.formatPercent(v);
    return whole(v);
  }

  function guidedRange(g) {
    if (g.low === g.high) return guided(g.low, g.metric);
    return guided(g.low, g.metric) + ' – ' + guided(g.high, g.metric);
  }

  /* The guidance on file (spec 18.3, and Appendix A's, 18.4): each record's metric, period and
     basis, its call's date and its state in words, the overrides citing it, then its range and
     midpoint in the metric's unit. Each record brings its state and the ids citing it, which
     Details reads from the research records and the report page from Appendix A. */
  function guidanceTable(guidance) {
    return h('table', { className: 'fb-table app-inputs' },
      h('thead', null, h('tr', null,
        h('th', { className: 'label' }, 'Guided'),
        h('th', { className: 'label fb-num' }, 'Range'))),
      h('tbody', null, guidance.map(function (g) {
        return h('tr', { key: g.id },
          h('td', null,
            h('span', { className: 'app-line' },
              h('span', { className: 'body' }, words(g.metric)), ' ',
              h('span', { className: 'figure-sm' }, g.period), ' ',
              h('span', { className: 'caption app-muted' }, g.basis)),
            h('span', { className: 'caption app-line' }, 'call ', when(g.asOf), ' · ', g.state),
            g.citedBy.length ? h('span', { className: 'caption app-line' },
              'cited by override ' + g.citedBy.join(', ')) : null),
          h('td', { className: 'fb-num' },
            h('span', { className: 'figure-sm app-line' }, guidedRange(g)),
            h('span', { className: 'caption app-muted app-line' },
              'midpoint ' + guided(g.midpoint, g.metric))));
      })));
  }

  /* A finding's value in its unit (store.research.UNITS). */
  function findingFigure(v, unit) {
    if (unit === 'currency') return whole(v);
    if (unit === 'per-share') return F.formatMoney(v);
    if (unit === 'percent') return F.formatPercent(v);
    if (unit === 'multiple') return times(v);
    return plain(v);
  }

  /* A store word in a reader's words: target_margin is target margin. */
  function words(name) { return String(name).replace(/_/g, ' '); }

  /* The band meter's caption: the row's word and its price ÷ value (classifier-designation spec
     7.3). A row valued before the designation has neither. */
  function standing(r, edges) {
    var word = F.DESIGNATION[r.designation];
    if (!word || r.price_to_value == null) return null;
    return word + ': the price is ' + ratioFigure(r.price_to_value, edges) + ' × the value';
  }

  /* A refused row's band from its secondary valuation: what drew it, then its word and price ÷
     value at the latest price, as the meter's own caption says them. */
  function secondaryCaption(s, edges) {
    var said = standing({ designation: s.designation, price_to_value: s.priceToValue }, edges);
    return 'Secondary valuation' + (said ? ' · ' + said : '');
  }

  /* Price ÷ value to two decimals, unless they would land on one of the policy's designation
     edges the ratio is not on: 0.8499 would read 0.85, where Near starts, beside the word Below.
     Then three decimals, kept a thousandth off the edge (0.849, and 1.151 for 1.1501), so the
     figure stays inside the word's band. The CLI's line does the same (__main__.py). */
  function ratioFigure(ratio, edges) {
    var two = ratio.toFixed(2);
    var edge = Number(two);
    if (ratio === edge || (edges || []).indexOf(edge) === -1) return two;
    var three = Number(ratio.toFixed(3));
    three = ratio < edge ? Math.min(three, edge - 0.001) : Math.max(three, edge + 0.001);
    return three.toFixed(3);
  }

  /* The levels under the band meter, each named for what sets it (spec 7.3): the value less the
     moat's margin of safety, the fair band, the trim multiple × the value. The margin and the
     multiple are read from the levels, so each follows the settings the row was valued under:
     1.5 × value at the default, 1.75 × value under a trim multiple of 1.75. The meter's own scale
     is off: in the drawer's rail these names would run into each other. */
  function levels(r) {
    var moat = r.intermediates.moat;
    var margin = Math.round((1 - r.levels.buy / r.value) * 100);
    var multiple = Number((r.levels.trim / r.value).toFixed(2));
    var basis = moat === 'None' ? 'value less the ' + margin + '% margin for no moat'
      : 'value less the ' + moat + ' moat\'s ' + margin + '%';
    return h('div', { className: 'app-levels' }, pairs([
      ['Fair value', F.formatMoney(r.value), true],
      ['Margin of safety', h(React.Fragment, null, F.formatMoney(r.levels.buy),
        moat ? h('span', { className: 'caption app-muted app-line' }, basis) : null), true],
      ['Fair band', F.formatMoney(r.levels.fair_low) + ' – ' +
        F.formatMoney(r.levels.fair_high), true],
      [multiple + ' × value', F.formatMoney(r.levels.trim), true]
    ]));
  }

  /* A Mature Stable or growth row's growth-route value, under the band (calibration spec 5.7,
     growth-routes spec 5.12), or under a Mature Stable refusal; a refused cross-check shows only
     among the intermediates. */
  function crossCheck(g) {
    if (!g || g.value_per_share == null) return null;
    return h('p', { className: 'caption app-muted' }, 'Growth-route cross-check: ' +
      F.formatMoney(g.value_per_share) + ' (implied growth ' + F.formatPercent(g.implied_growth) +
      ')');
  }

  /* A Young Growth row, under the band: the failure probability is unavailable in tier 1, with
     its reason, and the value is one figure, not a range (growth-routes spec 5.13). */
  function youngGrowth(failure) {
    if (!failure) return null;
    return h(React.Fragment, null,
      h('p', { className: 'caption' }, 'Failure probability: ' +
        (failure.value == null ? 'unavailable' : F.formatPercent(failure.value)) +
        (failure.reason ? ' (' + failure.reason + ')' : '')),
      h('p', { className: 'caption' }, 'The value range is not computed in tier 1'));
  }

  /* Every row of the revenue growth route discounts at the flat required return, the row's RULE
     input, where Damodaran's template starts higher; the drawer says so (growth-routes spec
     5.9). */
  function discountedAt(inputs) {
    var r = ruleValue(inputs, 'required_return');
    if (r == null) return null;
    return h('p', { className: 'caption app-muted' }, 'Discounted at the required return of ' +
      F.formatPercent(r) + ' in every year; Damodaran\'s template starts higher and falls to it ' +
      'by year 10');
  }

  /* The value of the row's RULE input `name`; null when the row has none. */
  function ruleValue(inputs, name) { return taggedValue(inputs, name, 'RULE'); }

  /* The value of the row's DATA input `name`; null when the row has none. */
  function dataValue(inputs, name) { return taggedValue(inputs, name, 'DATA'); }

  function taggedValue(inputs, name, tag) {
    for (var i = 0; i < inputs.length; i++) {
      if (inputs[i].name === name && inputs[i].tag === tag) return inputs[i].value;
    }
    return null;
  }

  function section(key, title) {
    var head = title ? h('h3', { className: 'heading' }, title) : null;
    return h.apply(null, ['section', { key: key, className: 'app-section' }, head]
      .concat(Array.prototype.slice.call(arguments, 2)));
  }

  /* [label, value, numeric] rows as a two-column list; numbers in mono, words in sans. */
  function pairs(rows) {
    return h('dl', { className: 'app-pairs' }, rows.map(function (row) {
      return h(React.Fragment, { key: row[0] },
        h('dt', { className: 'caption' }, row[0]),
        h('dd', { className: row[2] ? 'figure-sm' : 'body' }, row[1]));
    }));
  }

  /* Under the phase evidence, the link to the Methodology view's section on the row's route,
     named by its phase (spec 2026-11-04 7.7). A row refused before its route has none. */
  function methodologyLink(r, phase) {
    var P = window.FairbandPage;
    if (!r.route || !phase) return null;
    return h('p', { className: 'caption app-more' }, h('a', {
      className: 'app-link', href: '#methodology/' + P.methodologySection(r.route)
    }, 'How Fairband values a ' + r.phase.phase + ' company'));
  }

  function evidence(p, phase) {
    var rows = [['Phase', phase ? F.PHASES[phase] : '—', false]];
    if (p.reason) rows.push(['Reason', p.reason, false]);
    return rows.concat([
      ['Revenue growth, 3 years', F.formatPercent(p.growth_3y), true],
      ['Growth word', (p.growth_word || '—') +
        (p.growth_decile == null ? '' : ' · decile ' + p.growth_decile), false],
      ['Operating margin', F.formatPercent(p.margin), true],
      ['Margin trend', (p.margin_slope == null ? '—'
        : F.formatPercent(p.margin_slope).replace('%', ' points a year')) +
        (p.margin_direction ? ' · ' + p.margin_direction : ''), false],
      ['Free cash flow', p.fcf_sign || '—', false],
      ['Dickinson stage', p.dickinson || '—', false],
      ['Checks', p.checks.length
        ? p.checks.map(function (c) { return c.word; }).join(' · ') : 'none', false]
    ]);
  }

  /* A result's classifier evidence, as Phase evidence lists it, for the report page's
     Appendix A (18.4). */
  function phaseEvidence(p) {
    return pairs(evidence(p, PHASE_NUMBER[p.phase]));
  }

  /* ---------------------------------------------------- the revenue growth route */

  /* A row valued on the revenue DCF (growth-routes spec 5): the ten years, the peers that set
     the target margin, the sales-to-capital, the terminal and the bridge to equity, then the two
     solves at the price, so the arithmetic reproduces from the drawer. */
  function revenueRoute(r) {
    var im = r.intermediates;
    var held = heldYears(ruleValue(r.inputs, 'high_growth_years'));
    return section('revenue', ROUTES[r.route],
      group('years', 'Ten years', yearsTable(im)),
      group('peers', 'Target margin', peersTable(im.target_margin.peers),
        pairs(peerSummary(im.target_margin))),
      group('capital', 'Sales-to-capital', pairs(salesToCapital(im.sales_to_capital))),
      group('bridge', 'Terminal and bridge to equity', pairs([
        ['Terminal return', F.formatPercent(im.terminal_roic), true],
        ['Year-10 NOPAT, fully taxed', whole(im.terminal_nopat), true],
        ['Terminal value', whole(im.terminal_value), true],
        ['Firm value', whole(im.firm_value), true],
        ['Less debt', whole(im.debt), true],
        ['Plus cash', whole(im.cash), true],
        ['Equity', whole(im.equity), true],
        ['Shares', plain(im.shares), true],
        ['Value a share', F.formatMoney(im.value_per_share), true]
      ])),
      group('solves', 'At the price', pairs([
        [held ? 'Implied growth held in ' + held : 'Implied growth held after year 3',
          F.formatPercent(im.implied_growth), true],
        ['Margin the price needs', F.formatPercent(im.implied_margin), true]
      ])));
  }

  function group(key, title) {
    return h.apply(null, ['div', { key: key, className: 'app-group' },
      h('h4', { className: 'label app-group__head' }, title)]
      .concat(Array.prototype.slice.call(arguments, 2)));
  }

  /* The implied growth is held from year 4 to the last high-growth year, the row's RULE input;
     null when the row has none, and the label then says only where the hold starts. */
  function heldYears(last) {
    if (last == null) return null;
    if (last === 4) return 'year 4';
    return last === 5 ? 'years 4 and 5' : 'years 4 to ' + last;
  }

  /* One row a year: the revenue, the margin, EBIT, tax, NOPAT, the reinvestment and the free cash
     flow, totals to whole dollars. On the dollar ramp the margin is each year's operating income
     over its revenue, the income moving in dollars (method 5a.4), and its head says so. */
  function yearsTable(im) {
    var ramp = im.margin_path.ramp === 'dollars' ? 'ramp in dollars' : null;
    return figuresTable([
      ['Revenue', im.revenue_by_year, whole],
      ['Margin', im.margin_path.by_year, F.formatPercent, ramp],
      ['EBIT', im.ebit_by_year, whole],
      ['Tax', im.tax_by_year, whole],
      ['NOPAT', im.nopat_by_year, whole],
      ['Reinvestment', im.reinvestment_by_year, whole],
      ['Free cash flow', im.fcff_by_year, whole]
    ]);
  }

  /* A row a year from year 1, a column for each [head, the figures by year, their format, and a
     note on the head when there is one]. Wider than the rail, the table scrolls on its own, by
     keyboard too: its box takes focus. */
  function figuresTable(columns) {
    return h('div', { className: 'app-scroll', tabIndex: 0 },
      h('table', { className: 'fb-table app-figures' },
        h('thead', null, h('tr', null,
          h('th', { className: 'label fb-num' }, 'Year'),
          columns.map(function (c) {
            return h('th', { key: c[0], className: 'label fb-num' },
              c[3] ? noted(c[0], c[3]) : c[0]);
          }))),
        h('tbody', null, columns[0][1].map(function (_, t) {
          return h('tr', { key: t },
            h('td', { className: 'fb-num figure-sm' }, plain(t + 1)),
            columns.map(function (c) {
              return h('td', { key: c[0], className: 'fb-num figure-sm' }, c[2](c[1][t]));
            }));
        }))));
  }

  /* The mature peers counted for the target margin, each with its ten-year margin and its market
     cap. */
  function peersTable(peers) {
    return h('div', { className: 'app-scroll', tabIndex: 0 },
      h('table', { className: 'fb-table app-figures' },
        h('thead', null, h('tr', null,
          h('th', { className: 'label' }, 'Peer'),
          h('th', { className: 'label fb-num' }, 'Margin'),
          h('th', { className: 'label fb-num' }, 'Market cap'))),
        h('tbody', null, peers.map(function (p) {
          return h('tr', { key: p.symbol },
            h('td', { className: 'figure-sm' }, p.symbol),
            h('td', { className: 'fb-num figure-sm' }, F.formatPercent(p.margin)),
            h('td', { className: 'fb-num figure-sm' }, whole(p.market_cap)));
        }))));
  }

  /* The median is the target; the largest peer by market cap is the success scenario and sets
     nothing (spec 5.5). */
  function peerSummary(t) {
    return [
      ['Median, the target', F.formatPercent(t.value), true],
      ['Peers counted', plain(t.count), true],
      ['Largest peer', t.largest_symbol == null ? '—' : noted(t.largest_symbol + ' ' +
        F.formatPercent(t.largest_margin), 'the success scenario'), true]
    ];
  }

  /* The measure used, own or peers, and both figures (spec 5.6). */
  function salesToCapital(s) {
    return [
      ['Measure used', s.used || 'none', false],
      ['Own five-year marginal', s.own_usable ? times(s.own)
        : noted(times(s.own), 'not usable'), true],
      ['Mature peers\' median', times(s.peers), true]
    ];
  }

  /* A figure with words after it, in sans and in brackets; the figure stays mono. */
  function noted(text, note) {
    return h(React.Fragment, null, text, h('span', { className: 'caption' }, ' (' + note + ')'));
  }

  /* A line in place of a figure the route could not compute, saying why. */
  function missing(text) { return h('p', { className: 'caption app-muted' }, text); }

  /* -------------------------------------------------------------- the Decline route */

  /* A row valued on the run-off (spec 2026-11-03 section 10): the ten years, the margin held in
     each, the rating that sets π, the floor and the distress weighting, then Altman Z″ and
     Piotroski F, which decide nothing. A row refused for a value at or below zero shows all of
     it but the decline rate at the price. */
  function declineRoute(r) {
    var im = r.intermediates;
    return section('decline', ROUTES.decline,
      group('runoff', 'Run-off', runoffTable(im), pairs(runoffSummary(im))),
      group('margin', 'Normalized margin', pairs(normalizedMargin(im.margin))),
      group('rating', 'Rating', pairs(rating(im.rating))),
      group('floor', 'Floor and distress', pairs(floorAndDistress(im)), weighting(im)),
      group('altman', 'Altman Z″', altmanZ(im.altman_z)),
      group('piotroski', 'Piotroski F', piotroskiF(im.piotroski_f)));
  }

  /* A fall in revenue releases the capital it needed, recovered in part; a rise reinvests in
     full; each in the year of the change, so no year has both (spec 10.4). */
  function runoffTable(im) {
    return figuresTable([
      ['Revenue', im.revenue_by_year, whole],
      ['EBIT', im.ebit_by_year, whole],
      ['NOPAT', im.nopat_by_year, whole],
      ['Release', im.release_by_year, whole],
      ['Reinvestment', im.reinvestment_by_year, whole],
      ['Free cash flow', im.fcff_by_year, whole]
    ]);
  }

  /* The decline rate, after the years the consensus gives (K, 3 to N) or the three years that
     shrink at it without a usable consensus, fading to zero by year N (method 6a.2); when the
     consensus reaches year N - 1 or N no year reads the rate (at K = N - 1 the one fade year, N,
     is at zero), so the note says where the consensus ends instead, and that year N is flat; the
     sales-to-capital the release and the reinvestment read; the terminal value, flat on year N's
     revenue (6a.5), and the firm value; and, on a valued row, the decline rate at which the value
     is the price. */
  function runoffSummary(im) {
    var path = im.runoff_path, s = im.sales_to_capital;
    var years = path.ntm_revenue == null ? 'years 1 to 3 at the decline rate'
      : 'years 1 to ' + path.consensus_years + ' from the consensus';
    var fade = path.consensus_years < path.runoff_years - 1
      ? years + '; fades to zero by year ' + path.runoff_years
      : path.consensus_years < path.runoff_years
        ? 'the consensus runs to year ' + path.consensus_years + '; year ' + path.runoff_years
          + ' is flat'
        : 'the consensus runs to year ' + path.runoff_years;
    var rows = [
      ['Decline rate', noted(F.formatPercent(path.d), fade), true],
      ['Sales-to-capital', noted(times(s.value), s.used === 'own-latest'
        ? 'own, newest year' : 'mature peers\' median'), true],
      ['Terminal value', noted(whole(im.terminal_value), 'flat'), true],
      ['Firm value', whole(im.firm_value), true]
    ];
    if ('implied_decline_rate' in im) {
      rows.push(['Implied decline rate', im.implied_decline_rate == null
        ? noted('—', 'none from −50% to 0') : F.formatPercent(im.implied_decline_rate), true]);
    }
    return rows;
  }

  /* The one margin held (spec 10.3): the median of the last five fiscal years' margins when
     three or more are read, else the trailing margin; the one used is marked. */
  function normalizedMargin(m) {
    function used(text, which) { return m.used === which ? noted(text, 'used') : text; }
    return [
      ['Median', used(m.median == null ? noted('—', 'fewer than three years')
        : F.formatPercent(m.median), 'median'), true],
      ['Trailing', used(F.formatPercent(m.trailing), 'trailing'), true],
      ['Years read', m.years.length ? m.years.map(function (year, k) {
        return year + ' ' + F.formatPercent(m.margins[k]);
      }).join(' · ') : 'none', true]
    ];
  }

  /* The synthetic rating on EBIT at the normalized margin over the trailing interest, and its
     ten-year probability of default (spec 10.7): with no net debt there is nothing to default
     on; with no debt line on file, or net debt and no interest expense on file, no rating and
     no π, the note saying which. */
  function rating(g) {
    var pi = 'π, ten-year default probability';
    if (g.note === 'no net debt') {
      return [['Rating', 'no net debt', false], [pi, F.formatPercent(g.pi), true]];
    }
    if (g.rating == null) {
      return [['Rating', 'unavailable: ' + (g.note || 'no interest expense on file'), false],
        [pi, 'unavailable', false]];
    }
    return [
      ['Rating', g.rating, false],
      ['EBIT at the normalized margin', whole(g.ebit), true],
      ['Interest expense, trailing', whole(g.interest), true],
      ['Coverage', times(g.coverage), true],
      [pi, F.formatPercent(g.pi), true]
    ];
  }

  /* The firm value to the going-concern value a share; the net current asset value a share, which
     floors it when above zero and above it (spec 10.6): no floor without one or at or below zero,
     and above zero a floor that binds or does not; the distress-sale value a share. */
  function floorAndDistress(im) {
    var ncav = im.ncav_per_share;
    var floor = ncav == null || ncav <= 0 ? 'no floor'
      : im.floored_per_share > im.going_concern_per_share ? 'the floor binds'
        : 'the floor does not bind';
    return [
      ['Less debt', whole(im.debt), true],
      ['Plus cash', whole(im.cash), true],
      ['Shares', plain(im.shares), true],
      ['Going concern a share', F.formatMoney(im.going_concern_per_share), true],
      ['NCAV a share', noted(ncav == null ? '—' : F.formatMoney(ncav), floor), true],
      ['Distress-sale value a share', noted(F.formatMoney(im.distress_per_share),
        F.formatPercent(im.distress_sale_fraction) + ' of firm value + cash − debt'), true]
    ];
  }

  /* The value a share (spec 10.7): the floored value weighted against the distress-sale value at
     π, or the floored value alone when π is unavailable. */
  function weighting(im) {
    var pi = im.pi.value;
    var floored = F.formatMoney(im.floored_per_share);
    if (pi == null) {
      return h('p', { className: 'caption' }, 'π unavailable: the value is the floored value, ' +
        floored);
    }
    return h('p', { className: 'caption' },
      h('span', { className: 'app-line' }, 'value = floored × (1 − π) + distress × π'),
      h('span', { className: 'app-line' }, '= ' + floored + ' × (1 − ' + F.formatPercent(pi) +
        ') + ' + F.formatMoney(im.distress_per_share) + ' × ' + F.formatPercent(pi) + ' = ' +
        F.formatMoney(im.value_per_share)));
  }

  /* Altman Z″ on the newest annual balance sheet (spec 10.8): its four ratios, the score and the
     zone. */
  function altmanZ(z) {
    if (!z) {
      return missing('No score: a line it reads is missing, or total assets or total ' +
        'liabilities is not above zero');
    }
    return pairs([
      ['Fiscal year', plain(z.year), true],
      ['X1, working capital ÷ assets', decimals(z.x1, 3), true],
      ['X2, retained earnings ÷ assets', decimals(z.x2, 3), true],
      ['X3, operating income ÷ assets', decimals(z.x3, 3), true],
      ['X4, equity ÷ liabilities', decimals(z.x4, 3), true],
      ['Score', noted(decimals(z.score, 2), z.zone + ' zone'), true]
    ]);
  }

  /* Piotroski's nine signals, the newest fiscal year against the one before (spec 10.8). */
  var SIGNALS = {
    roa_positive: 'Return on assets above zero',
    cfo_positive: 'Operating cash flow above zero',
    roa_up: 'Return on assets up',
    accrual: 'Operating cash flow above net income',
    leverage_down: 'Long-term debt to assets down',
    liquidity_up: 'Current ratio up',
    no_issuance: 'No common stock issued',
    gross_margin_up: 'Gross margin up',
    turnover_up: 'Asset turnover up'
  };

  /* The score of the signals read, then each signal, met, not met or not read for a missing line,
     the word in a box of its own so the signals line up. */
  function piotroskiF(f) {
    if (!f) return missing('No score: fewer than two annual balance sheets');
    return h(React.Fragment, null,
      pairs([
        ['Fiscal year', plain(f.year) + ' against ' + plain(f.prior_year), true],
        ['Score', f.score + ' of ' + f.read + (f.read < f.signals.length ? ' read' : ''), true]
      ]),
      h('ul', { className: 'app-list app-signals' }, f.signals.map(function (s) {
        var mark = s.value === true ? 'met' : s.value === false ? 'not met' : 'not read';
        return h('li', { key: s.name },
          h('span', { className: 'caption app-mark' }, mark),
          h('span', { className: 'body' }, SIGNALS[s.name] || s.name));
      })));
  }

  /* ------------------------------------------------------------- the Start-up route */

  /* A Start-up row (spec 2026-11-03 section 9), a refusal by design: the revenue in year 10 the
     price needs at the mature peers' margin, the net cash a share as a floor and the years the
     cash covers the burn. */
  function startUpRoute(r) {
    var im = r.intermediates;
    return section('start-up', ROUTES['start-up'],
      group('requirement', 'Revenue the price needs', requirement(im.requirement),
        movedCap(im, r.inputs)),
      group('floor', 'Cash floor', pairs(cashFloor(im)), belowFloor(r)),
      group('burn', 'Burn cover', pairs(burnCover(im))));
  }

  /* The year-10 revenue at which the straight ramp from today's revenue and operating income to
     the target margin is worth the enterprise value the price implies (spec 9.2), and the ramp;
     or the reason the requirement is not computed. */
  function requirement(req) {
    var target = req.target_margin, s = req.sales_to_capital;
    var rows = req.reason ? [['Not computed', req.reason, false]]
      : [['Year-10 revenue', whole(req.revenue_y10), true]];
    if (!req.reason && req.revenue_0 > 0) {
      rows.push(['Against today', h(React.Fragment, null,
        decimals(req.revenue_y10 / req.revenue_0, 1),
        h('span', { className: 'caption' }, ' × the trailing revenue')), true]);
    }
    rows = rows.concat([
      ['Trailing revenue', whole(req.revenue_0), true],
      ['Enterprise value at the price', req.ev_price != null && req.ev_price <= 0
        ? noted(whole(req.ev_price), 'net cash covers the price') : whole(req.ev_price), true],
      ['Target margin', target == null ? '—'
        : noted(F.formatPercent(target.value), peersBehind(target)), true],
      ['Sales-to-capital', s == null ? '—' : noted(times(s.value), 'mature peers\' median'), true]
    ]);
    return h(React.Fragment, null, pairs(rows), req.path ? figuresTable([
      ['Revenue', req.path.revenue, whole],
      ['EBIT', req.path.ebit, whole],
      ['NOPAT', req.path.nopat, whole],
      ['Reinvestment', req.path.reinvestment, whole],
      ['Free cash flow', req.path.fcff, whole]
    ]) : null, req.path ? pairs([
      ['Terminal value', whole(req.terminal_value), true],
      ['Terminal return', F.formatPercent(req.terminal_roic), true]
    ]) : null);
  }

  /* The peers' count and where they came from: FMP's list, or the industry's on the fallback. */
  function peersBehind(t) {
    return 'median of ' + t.count + ' mature peers' + (t.source === 'industry'
      ? ' of the ' + t.industry + ' industry' : ' on FMP\'s list');
  }

  /* A repriced row's market cap moved with the price at the share count it was read at (method
     6b.5), while its market-cap input keeps the one read: both show when they differ. */
  function movedCap(im, inputs) {
    var read = dataValue(inputs, 'market_cap');
    if (im.market_cap == null || read == null || im.market_cap === read) return null;
    return h('p', { className: 'caption' }, 'The market cap moved with the price: ' +
      dollars(im.market_cap) + ' at this price, ' + dollars(read) + ' as read');
  }

  /* The net cash a share (spec 9.4): (cash − debt) ÷ diluted shares. */
  function cashFloor(im) {
    return [
      ['Net cash a share', F.formatMoney(im.cash_floor), true],
      ['Cash', whole(im.cash), true],
      ['Less debt', whole(im.debt), true],
      ['Shares', plain(im.shares), true]
    ];
  }

  /* The caption reads the row's `below-net-cash` flag, the one test (method 6b.4): the market
     cap at or below the net cash, which is the price at or below the cash floor only when the
     market cap is the price times the diluted shares. */
  function belowFloor(r) {
    var below = r.flags.some(function (f) { return f.code === 'below-net-cash'; });
    if (!below) return null;
    return h('p', { className: 'caption' },
      'The price is covered by net cash: the market cap is at or below the cash less the debt');
  }

  /* The years the cash covers the trailing burn (spec 9.4); "not burning" when the trailing free
     cash flow is zero or above; none without the trailing cash flows, or without a cash figure,
     when the burn shows and the cover is unknown. */
  function burnCover(im) {
    var cover = im.burn_cover_years;
    if (cover === 'not burning') return [['Trailing burn', 'not burning', false]];
    if (cover == null && im.burn != null && im.cash_known === false) {
      return [
        ['Cash covers', 'unknown: no cash line on file', false],
        ['Burn a year', whole(im.burn), true]
      ];
    }
    if (cover == null) return [['Trailing burn', noted('—', 'no trailing cash flows'), true]];
    return [
      ['Cash covers', decimals(cover, 1) + ' years', true],
      ['Burn a year', whole(im.burn), true]
    ];
  }

  /* ---------------------------------------------------------------- the inputs */

  /* A date as it is; a timestamp in the reader's local time. */
  function when(iso) {
    if (!iso) return '—';
    var local = localIso(iso);
    return h('time', { dateTime: local, title: local }, F.formatDate(local));
  }

  /* A minus is U+2212; a negative that rounds to zero loses its sign. */
  function minus(s) { return /^-[0.,]*$/.test(s) ? s.slice(1) : s.replace(/^-/, '−'); }

  function decimals(v, dp) {
    return minus(Number(v).toLocaleString('en-US',
      { minimumFractionDigits: dp, maximumFractionDigits: dp }));
  }

  /* A count: whole numbers as they are (a year stays 2027), separated from 10,000 up. */
  function plain(v) {
    var n = Number(v);
    if (Number.isInteger(n) && Math.abs(n) < 10000) return minus(String(n));
    return decimals(n, Number.isInteger(n) ? 0 : 2);
  }

  /* A total in whole dollars, with separators: $5,900,000,000. */
  function dollars(v) { return (v < 0 ? '−$' : '$') + decimals(Math.abs(v), 0); }

  /* A total in whole dollars; an em dash for none. */
  function whole(v) { return v == null ? '—' : dollars(v); }

  /* A ratio of sales to capital, to two decimals with x: 1.38x; an em dash for none. */
  function times(v) { return v == null ? '—' : decimals(v, 2) + 'x'; }

  /* By unit: a price to cents, a total to whole dollars, a ratio to one decimal of a percent.
     A price and a total share the unit USD; a price is under a million. */
  function inputValue(i) {
    if (i.value == null) return '—';
    if (i.unit === 'USD a share') return F.formatMoney(i.value);
    if (i.unit === 'USD') return Math.abs(i.value) < 1e6 ? F.formatMoney(i.value) : dollars(i.value);
    if (i.unit === 'ratio') return F.formatPercent(i.value);
    return plain(i.value);
  }

  /* Each input on one row, its nine fields stacked so they fit the rail: the name, tag, kind and
     source, then the three dates in caption, and the value with its unit on the right. */
  function inputsTable(inputs) {
    return h('table', { className: 'fb-table app-inputs' },
      h('thead', null, h('tr', null,
        h('th', { className: 'label' }, 'Input'),
        h('th', { className: 'label fb-num' }, 'Value'))),
      h('tbody', null, inputs.map(function (i) {
        var p = i.provenance;
        return h('tr', { key: i.name },
          h('td', null,
            h('span', { className: 'app-line' },
              h('span', { className: 'figure-sm' }, i.name), ' ',
              h('code', { className: 'fb-tag figure-sm' }, i.tag)),
            h('span', { className: 'caption app-line' },
              (i.estimate_method ? i.kind + ' (' + i.estimate_method + ')' : i.kind) +
              ' · ' + p.source),
            i.note ? h('span', { className: 'caption app-muted app-line' }, i.note) : null,
            h('span', { className: 'caption app-muted app-line' },
              h('span', { className: 'app-nowrap' }, 'as of ', when(p.as_of)), ' · ',
              h('span', { className: 'app-nowrap' }, 'observed ', when(p.observed_at)), ' · ',
              h('span', { className: 'app-nowrap' }, 'entered ', when(p.entered_at)))),
          h('td', { className: 'fb-num' },
            h('span', { className: 'figure-sm app-line' }, inputValue(i)),
            h('span', { className: 'caption app-muted app-line' }, i.unit)));
      })));
  }

  /* ---------------------------------------------------------- the intermediates */

  /* A number's key says what it is. A key ending in one of these names a fraction, which reads
     as a percentage; so do the fractions those endings miss (the implied-growth maps, the price
     changes, the drawdown, the path steps, the growth rates, the growth share). A dollar amount
     or a count whose key happens to end the same way (value_by_roic, stable_growth, roic's years)
     does not. A map keyed by runway years or by ROIC values takes its own key's reading, and so
     does a bare value (runway_return's). */
  var PERCENT = /(_growth|_yield|_return|margin|roic|belief)$/;
  var ALSO_PERCENT = /^(implied_|change_|drawdown|path_steps$|growth_rates$|growth_share$)/;
  var NOT_PERCENT = /^(value_|stable_growth|years?$)/;
  /* Counts and years read whole. P/E multiples to one decimal with x. A figure a share (EPV, the
     value, EPS, the non-recurring gap, the 52-week prices, the value maps by runway and by ROIC,
     whatever the entry's key) reads to cents; a total (NOPAT, invested capital, net income,
     earnings, anything at a million or more) to whole dollars. Any other number to two
     decimals. */
  var COUNT = /^(years?|base_year|runway|fade_years|analysts|shares)$/;
  var MULTIPLE = /^pe_/;
  var PER_SHARE = /^(epv|value_per_share|stable_growth|nri_gap|ntm_eps.*|.*_per_share|.*_52w)$/;
  var PER_SHARE_GROUP = /^(eps$|value_by_)/;
  var TOTAL = /(_total|nopat|average_capital|net_income)$|^e_/;

  function figure(v, key, group) {
    if (isPercent(key, group)) return F.formatPercent(v);
    if (PER_SHARE_GROUP.test(group || '')) return F.formatMoney(v);  /* value_by_roic's runway */
    if (COUNT.test(key)) return plain(v);
    if (MULTIPLE.test(key)) return decimals(v, 1) + 'x';
    if (PER_SHARE.test(key)) return F.formatMoney(v);
    if (TOTAL.test(key) || Math.abs(v) >= 1e6) return dollars(v);
    return decimals(v, 2);
  }

  function isPercent(key, group) {
    if (NOT_PERCENT.test(key)) return false;
    if (PERCENT.test(key) || ALSO_PERCENT.test(key)) return true;
    return !!group && !NOT_PERCENT.test(group) && (PERCENT.test(group) || ALSO_PERCENT.test(group));
  }

  function isTable(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }

  /* One value as text: null an em dash, a number by its key, a list inline (a list of tables one
     table a line, its year first), a deeper table inline. */
  function shown(v, key, group) {
    if (v == null) return '—';
    if (typeof v === 'number') return figure(v, key, group);
    if (Array.isArray(v)) {
      if (!v.some(isTable)) return v.map(function (x) { return shown(x, key, group); }).join(', ');
      return v.map(function (x, n) {
        return h('span', { key: n, className: 'app-line' }, shown(x, key, group));
      });
    }
    if (isTable(v)) {
      return Object.keys(v).sort(function (a, b) { return (b === 'year') - (a === 'year'); })
        .map(function (k) { return k + ' ' + shown(v[k], k, key); }).join(' · ');
    }
    return String(v);
  }

  /* One group per top-level key: a table's entries, with a nested table flattened one level. EPV
     below zero capitalises a trailing loss, which also puts the growth share above 100%; its line
     says so, so the reader is not misled. */
  function intermediates(im) {
    return Object.keys(im).map(function (key) {
      var v = im[key];
      var rows = [];
      if (key === 'epv' && v < 0) {
        rows.push([key, noted(shown(v, key, null), 'negative: trailing earnings are a loss'),
          true]);
      } else if (!isTable(v)) {
        rows.push([key, shown(v, key, null), true]);
      } else {
        Object.keys(v).forEach(function (k) {
          if (!isTable(v[k])) return rows.push([k, shown(v[k], k, key), true]);
          Object.keys(v[k]).forEach(function (kk) {
            rows.push([k + '.' + kk, shown(v[k][kk], kk, k), true]);
          });
        });
      }
      return h('div', { key: key, className: 'app-group' },
        isTable(v) ? h('h4', { className: 'label app-group__head' }, key) : null,
        pairs(rows));
    });
  }

  render();
  load();
  reloadWatchlists();
})();
