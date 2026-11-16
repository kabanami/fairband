/* The screen page: fetches /api/screen and renders the design system's ScreenTable, and beside it
   the detail drawer of the row the reader opens (spec 6.4), fetched from /api/companies/{symbol}.
   No JSX and no build step: React.createElement against window.Fairband. The server sorts and the
   engine computes; this script asks for an order, remembers the chosen columns in the reader's
   order, narrows the loaded rows to the reader's find and filters and lays out what the engine
   produced, rounded for display only. Each row's watchlist mark opens a popup that puts the
   company on the reader's lists, from /api/watchlists (spec 2026-11-04 9.4). The drawer leads with
   the valuation and the agents' report and puts the rest behind Details ▾; without a report it
   posts a research request to the work inbox, and Details takes the owner's notes (spec 2026-11-06
   Tier 2, 18.2 and 18.3). Where launching is set up, a request also opens the window where Claude
   Code starts, and the line under the button follows its launch (spec 2026-11-16 agent launch,
   10). The header, the status line and the group view are controls.js, loaded after this script;
   it reaches the screen through window.FairbandPage. */
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
  /* A work item's open states: work not yet done, which the header's Inbox count counts and the
     owner may decline (spec 2026-11-06 Tier 2, 8 and 18.5). */
  var OPEN_STATES = ['pending', 'claimed'];
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
     view also renames and deletes; the promise gives the status and the parsed body, null when
     the answer is not JSON (a 500's plain text), so the refusal names the status. */
  function send(method, url, body) {
    return fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json', 'X-Fairband-Request': '1' },
      body: JSON.stringify(body || {})
    }).then(function (response) {
      return response.json().catch(function () { return null; }).then(function (json) {
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

  /* Whether the page reads a launch again (spec 2026-11-16 agent launch, 7.4 and 10): while it is
     opening, opened or started, under LAUNCH_FOLLOW_S seconds after it was made by the server's
     clock, and, for a work item's launch, while the item is pending, past overdue too, since a
     claim may still arrive. A test waits for no claim: its launch is read again while it is
     opening or opened and not overdue, and once it has started only while it is under
     TEST_STARTED_S seconds old, so that a Claude Code that ends at once shows. No launch is not
     read. The Settings page's Test and the request button both follow a launch by it. */
  var LAUNCH_FOLLOW_S = 600;
  var TEST_STARTED_S = 60;
  function following(launch) {
    if (!launch || ['opening', 'opened', 'started'].indexOf(launch.state) === -1) return false;
    if (!(launch.ageSeconds < LAUNCH_FOLLOW_S)) return false;
    if (launch.test) {
      return launch.state === 'started' ? launch.ageSeconds < TEST_STARTED_S : !launch.overdue;
    }
    return launch.itemState === 'pending';
  }

  /* What controls.js uses: the screen's reload when a refresh ends, the write helpers and a refused
     write's sentence and its reason (refusalDetail), the GET helper, the local-time helper, whether
     a launch is followed (following), the phase numbers and a work item's open states; and the
     later views, find, the lists (null until they load), their reload, which settles once they are
     in, and watch, the marks' onWatch, which opens the popup, under the element it is handed
     where it is handed one (the company page's Watchlists ▾); the loaded rows (null until they
     load), the chosen columns, openRow, which opens a row's drawer, reloadDetail, which reads the
     drawer's company again after another view's write about it (the Inbox view's decline and a
     watchlist's Request research, spec 2026-11-06 Tier 2, 18.5 and 18.6), and reloadDrawer, which
     reads whichever company the drawer shows again when a run ends. controls.js adds show, onShow,
     section, running and countInbox, the Inbox view onInbox, agents.js adds agents, the Settings
     view's Agents section, and methodology.js adds methodologySection, which the drawer's link
     reads; a view drawn from the rows or the lists sets onRender, which runs after each draw of the
     screen, so it draws again as they load and change (the company page's runs the Watchlists
     view's, set before it, then its own). The report page (report.js, 18.4) draws with
     the drawer's own parts: the meter, the inputs table, a table of figures by year, an input's
     figure in its unit, the secondary valuation's rows and path, the guidance table, the phase
     evidence, pairs, a date, a total, a figure a share and a rate in a currency, a count, the line
     that says what the figures are in (currencyLine), a report's footnote numbers, and Request
     research with a request of its own (asking), whose following of a launch the page stops as it
     starts to read another company (stopLaunch) and starts as its read lands (followItem). The
     company page (company.js; the company page's design, 7) draws its head with the logo, the
     phase numbers, the moat stamp (moatStamp) and Request research as the report page keeps it,
     and opens the watchlists popup under its head's button (watch) on the company's row or, the
     lists loaded, on the company alone (rows, watchlists); its Fairband value block
     (company_overview.js, 8.2) draws the meter, the four levels under it in the screen's words
     (levelRows), the basis chip of the band they draw (bandBasis) and the local day of its
     report (localIso). The Inbox view's row (inbox.js, B-210) keeps a request for each pending
     item too, posts its launch
     (openLaunch) and draws the line's words (launchWords) from the item the line is drawn from
     (lineItem). The open item's line (launchLine), the drawer's route sections, the charge's
     rows, an input's value, the intermediates, the flags it lists and Details' findings are here
     for the tests, which read them in node (tests/web/page.mjs). */
  window.FairbandPage = {
    reload: load, api: api, refusal: refusal, refusalDetail: refusalDetail, getJson: getJson,
    localIso: localIso, following: following,
    PHASE_NUMBER: PHASE_NUMBER, OPEN_STATES: OPEN_STATES,
    find: find,
    watchlists: function () { return state.watchlists; },
    reloadWatchlists: reloadWatchlists,
    watch: watch,
    rows: function () { return state.rows; },
    columns: function () { return state.columns; },
    openRow: openRow, reloadDetail: reloadDetail, reloadDrawer: reloadDrawer,
    meter: meter, levelRows: levelRows, bandBasis: bandBasis,
    inputsTable: inputsTable, figuresTable: figuresTable, inputFigure: inputFigure,
    inputValue: inputValue,
    secondaryRows: secondaryRows, secondaryPath: secondaryPath, guidanceTable: guidanceTable,
    phaseEvidence: phaseEvidence, pairs: pairs, when: when, whole: whole, money: money,
    rate: rate, plain: plain,
    footnotes: footnotes, asking: asking, requestResearch: requestResearch,
    launchLine: launchLine, launchWords: launchWords, lineItem: lineItem,
    openLaunch: openLaunch, stopLaunch: stopLaunch, followItem: followItem,
    chargeRows: chargeRows, matureRoute: matureRoute, revenueRoute: revenueRoute,
    declineRoute: declineRoute, startUpRoute: startUpRoute, intermediates: intermediates,
    briefLine: briefLine, firstSentence: firstSentence, currencyLine: currencyLine,
    logo: logo, logoGround: logoGround, moatStamp: moatStamp,
    drawerFlags: drawerFlags, findingsList: findingsList
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
    /* the company the drawer showed no longer follows its launch (spec 2026-11-16 agent launch,
       10), whether the new one's read lands or fails */
    if (state.request && state.request.symbol !== row.ticker) stopLaunch(state.request);
    var request = ++latestDetail;
    state.drawer = { symbol: row.ticker, body: d && d.body, loading: true, error: null };
    if (state.detailsOpen) readResearch(row.ticker);
    render();
    getJson('/api/companies/' + encodeURIComponent(row.ticker))
      .then(function (body) {
        if (request !== latestDetail) return;
        landed(row.ticker, body);
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

  /* The drawer closes, and its company's request no longer follows its launch. */
  function close() {
    latestDetail++;
    if (state.request) stopLaunch(state.request);
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
     designation unless the value in its Reviewed column lends one (spec 2026-11-06 Tier 2, 18.1,
     plan 3), the server's word, never derived here; a row without a published report has no
     stance, the agent's word (18.1). The row's phase is already the menu's number (the server
     maps the engine's phase name through PHASE_NUMBER), and its cap band is the menu's id once
     lower-cased (Mega is mega); small never matches, the universe's floor being $2 bn. A row on
     any chosen watchlist matches; Clean keeps the valued rows whose quality warnings count 0: a
     refusal or a placeholder has no value to be cheap on, so it is never clean (spec 2026-11-04
     9.4, 9.5). The count is the server's: the review's flags where a review fills the row, else
     the snapshot's (spec 2026-11-13 8a). Valued is the engine's word, the Mechanical column: a
     refused row's fair value may be its review's or its secondary valuation's (plan 3), and a row
     the engine refused is not clean, whatever a review made of it. */
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
        (!filters.cleanOnly || (r.flagCount === 0 && r.mechanical != null));
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

  /* onWatch: a mark opens its popup, or closes it when the popup is its own. The popup opens under
     `mark` where one is given, the company page's Watchlists ▾ (the company page's design, 7.2),
     else under the mark the click landed on. */
  function watch(row, mark) {
    var anchor = mark || pressedMark;
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

  /* A refused write's sentence, led by the write's own head, with the server's reason as it
     arrived (refusalDetail); null for a write it took. The popup's, and every later view's
     through FairbandPage. */
  function refusal(head, r) {
    if (r.ok) return null;
    return head + ': ' + refusalDetail(r) + '.';
  }

  /* A refused write's reason: the server's sentence as it arrived, or its status when it sent
     none. */
  function refusalDetail(r) {
    return r.body && typeof r.body.detail === 'string' ? r.body.detail
      : 'the server answered ' + r.status;
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
     head, with one line on the company under its name (B-149: the sector and industry, then the
     first sentence of the company brief, briefLine), and for a company in another currency or an
     ADR the line that says what its figures are in (currencyLine, spec 2026-11-10 7.4); the
     meter with its levels and the route's lines under it, the review's band and levels where the
     review counts and has a value, the mechanical value named in its caption (plan 3), or in its
     place the refusal, as before; the
     stance line when a report exists, the report's word in the row's chip classes, faded once
     the window of the snapshot it rests on has expired, then who published it and when; the
     report's Summary, its first section, then Open the report, a link to the report page; then
     Request research with its menu, the server's refusal under it and the open item's line, with
     or without a report (plan 4: the founder found none on a company with a report); then
     Details ▾, a disclosure over everything else (details). */
  function sections(body) {
    var r = body.result;
    var im = r.intermediates;
    var phase = PHASE_NUMBER[r.phase.phase];
    var valued = isValued(r);
    var growth = r.route === 'revenue-growth';
    var report = body.report;
    var reviewBanded = isReviewBanded(body);
    var banded = isBanded(body);
    var ask = asked(r.symbol);
    return [
      h('header', { key: 'head', className: 'app-drawer__head' },
        logo(body, 'app-drawer__logo'),
        h('h2', { className: 'ticker app-drawer__ticker' }, r.symbol),
        phase ? h(F.PhaseBadge, { phase: phase, size: 'sm' }) : null,
        body.company && body.company.name
          ? h('p', { className: 'body app-drawer__name' }, body.company.name) : null,
        briefLine(body.company, body.brief)
          ? h('p', { className: 'caption app-muted app-drawer__brief' },
            briefLine(body.company, body.brief)) : null,
        currencyLine(body) ? h('p', { className: 'caption app-muted app-drawer__currency' },
          currencyLine(body)) : null),
      valued ? section('band', null, meter(body),
        levels(drawnLevels(body)),
        h('p', { className: 'caption app-muted' }, ROUTES[r.route] || r.route),
        youngGrowth(im.failure_probability),
        crossCheck(im.growth_route, im.currency),
        growth ? discountedAt(r.inputs) : null) : null,
      /* A refused row shows in the screen's Reviewed column (spec 2026-11-06 Tier 2, 11 and
         18.1) the value of its review on the latest snapshot, else of its secondary valuation
         there, so the drawer draws that value's band against the price, its word at today's
         price, and the refusal stays under it: the review's when it has a value (the ruling of
         2026-11-08), else the secondary's (the ruling of 2026-11-07). A refused row with neither
         has the refusal alone. */
      reviewBanded ? section('review-band', null, meter(body)) : null,
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
        'e_trailing' in im ? crossCheck(im.growth_route, im.currency) : null) : null,
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
        : null,
      section('request', null,
        requestResearch(ask, body.item, render, reread(r.symbol), body.launchReady)),
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
     the report page draw it. The head beside the price says the word and price ÷ value over the
     value's name in one form, "0.82 × the reviewed value", and the caption only what the head
     does not (18.2 item 2, plan 4): a valued row whose review on the latest snapshot has a value,
     the review's band, its word and ratio at today's price over the reviewed value, its caption
     the mechanical value in words, as the row's band and levels follow the reviewed value (plan
     3); else a valued row's mechanical band against the price, its word and ratio over the
     mechanical value; a refused row whose review on the latest snapshot has a value, the
     review's band, the reviewed marker on the value itself, its word and ratio at today's price
     over the reviewed value, the bundle's caption "reviewed" and the value (the ruling of
     2026-11-08); else a refused row whose secondary valuation counts on the latest snapshot, the
     secondary's band, its word and ratio at today's price over the secondary valuation (the
     ruling of 2026-11-07); else none. The scale is off: the drawer names the levels under it.
     `hero` false sets the meter's price in figure, under the report page's one headline figure;
     the drawer passes none. */
  function meter(body, hero) {
    var r = body.result;
    var review = body.review;
    var secondary = body.secondary;
    if (isValued(r)) {
      if (isReviewed(body)) {
        return h(F.BandMeter, {
          low: review.levels.fairLow, high: review.levels.fairHigh, price: r.price,
          fairValue: review.value, buyLevel: review.levels.buy, trimLevel: review.levels.trim,
          designation: review.designation, showScale: false,
          gap: gapText(review.priceToValue, body.designationEdges, 'the reviewed value'),
          caption: 'mechanical ' + F.formatMoney(r.value), hero: hero
        });
      }
      return h(F.BandMeter, {
        low: r.levels.fair_low, high: r.levels.fair_high, price: r.price, fairValue: r.value,
        buyLevel: r.levels.buy, trimLevel: r.levels.trim, designation: r.designation,
        showScale: false,
        gap: gapText(r.price_to_value, body.designationEdges, 'the mechanical value'), hero: hero
      });
    }
    if (isReviewBanded(body)) {
      return h(F.BandMeter, {
        low: review.levels.fairLow, high: review.levels.fairHigh, price: r.price,
        fairValue: review.value, buyLevel: review.levels.buy, trimLevel: review.levels.trim,
        designation: review.designation, reviewedValue: review.value, showScale: false,
        gap: gapText(review.priceToValue, body.designationEdges, 'the reviewed value'), hero: hero
      });
    }
    if (!isBanded(body)) return null;
    return h(F.BandMeter, {
      low: secondary.levels.fairLow, high: secondary.levels.fairHigh, price: r.price,
      fairValue: secondary.valuePerShare, buyLevel: secondary.levels.buy,
      trimLevel: secondary.levels.trim, designation: secondary.designation, showScale: false,
      gap: gapText(secondary.priceToValue, body.designationEdges, 'the secondary valuation'),
      hero: hero
    });
  }

  /* A row the engine valued: a value, its levels and a price to draw them against. */
  function isValued(r) {
    return r.value != null && r.levels != null && r.price != null;
  }

  /* A valued row whose review, which the detail carries only while it counts on the latest
     snapshot, has a value and its levels: its meter and the levels named under it are the
     review's, as the screen row's band and levels are (spec 2026-11-06 Tier 2, 18.1 and 18.2,
     plan 3). */
  function isReviewed(body) {
    var v = body.review;
    return isValued(body.result) && !!v && v.value != null && !!v.levels;
  }

  /* The levels a valued row's meter draws, in the shape levels() reads (spec 2026-11-06 Tier 2,
     18.1 and 18.2, plan 3): the review's where it counts and has a value, the margin's moat the
     one its moat override sets, as the review's levels read the reviewed moat (method 14.5); else
     the engine's. The engine's own levels stay on the snapshot and in the report's Appendix A. */
  function drawnLevels(body) {
    var r = body.result;
    var v = body.review;
    if (!isReviewed(body)) return r;
    var moat = (v.bridge || []).filter(function (line) { return line.tag === 'moat.class'; })[0];
    return {
      value: v.value,
      levels: {
        buy: v.levels.buy, fair_low: v.levels.fairLow, fair_high: v.levels.fairHigh,
        trim: v.levels.trim
      },
      intermediates: { moat: moat ? moat.new : r.intermediates.moat }
    };
  }

  /* A refused row whose review, which the detail carries only while it counts on the latest
     snapshot, has a value, its levels, and a price to draw them against: its meter is the
     review's, as the row's Reviewed cell and the report page's headline show that value. */
  function isReviewBanded(body) {
    var r = body.result;
    var v = body.review;
    return !isValued(r) && !!r.refusal && !!v && v.value != null && !!v.levels &&
      r.price != null;
  }

  /* A refused row whose review has no value there and whose secondary valuation, which the detail
     carries only while it counts on the latest snapshot, has levels, and a price to draw them
     against: its meter is the secondary's. */
  function isBanded(body) {
    var r = body.result;
    var s = body.secondary;
    var v = body.review;
    return !isValued(r) && !!r.refusal && !(v && v.value != null) && !!s && !!s.levels &&
      r.price != null;
  }

  /* The four levels under the meter in the screen's words, as [name, text] pairs (the company
     page's design, 8.2 and 11): Fair value, Buy level, Fair band and Trim level of the value the
     meter draws (meter). On a valued row the review's where it counts and has a value, else the
     snapshot's (drawnLevels); on a refused row the review's band or the secondary valuation's
     that the meter draws; null where the meter draws no band. */
  function levelRows(body) {
    var d = isValued(body.result) ? drawnLevels(body) : null;
    var v = body.review;
    var s = body.secondary;
    var band = d ? {
      value: d.value, buy: d.levels.buy, fairLow: d.levels.fair_low,
      fairHigh: d.levels.fair_high, trim: d.levels.trim
    } : isReviewBanded(body) ? Object.assign({ value: v.value }, v.levels)
      : isBanded(body) ? Object.assign({ value: s.valuePerShare }, s.levels) : null;
    if (!band) return null;
    return [
      ['Fair value', F.formatMoney(band.value)],
      ['Buy level', F.formatMoney(band.buy)],
      ['Fair band', F.formatMoney(band.fairLow) + ' – ' + F.formatMoney(band.fairHigh)],
      ['Trim level', F.formatMoney(band.trim)]
    ];
  }

  /* The basis of the band the meter draws (meter) and the four levels name (levelRows), by the
     branch they take: reviewed where they draw a review's band, on a valued row or a refused one,
     or a secondary valuation's; else mechanical, the engine's band or none. */
  function bandBasis(body) {
    return isReviewed(body) || isReviewBanded(body) || isBanded(body) ? 'reviewed' : 'mechanical';
  }

  /* The flags the drawer lists, { flags, reviewed } (spec 2026-11-13 8a): the review's, which the
     detail carries only while the review counts on the latest snapshot, where it has a value and
     its flags, as the screen row's Flags and Warnings read them; else the snapshot's. reviewed
     says they are the review's. */
  function drawerFlags(body) {
    var v = body.review;
    if (v && v.value != null && v.flags) return { flags: v.flags, reviewed: true };
    return { flags: body.result.flags, reviewed: false };
  }

  /* A report's references, [{ n, ref, source }], as ReportReader's footnotes, ref → n (spec 13.1):
     the drawer's Summary and the report page number a cite alike, by the full report's list. */
  function footnotes(references) {
    var marks = {};
    (references || []).forEach(function (e) { marks[e.ref] = e.n; });
    return marks;
  }

  /* Details (spec 2026-11-06 Tier 2, 18.3), in order: About, the company brief whole (B-149),
     the stored profile's description; the review, its bridge from the mechanical value when it
     has a value, each line under its input's label, or its refusal; the secondary valuation; the
     overrides, each a record, read-only; the guidance on file; the latest report's judgments;
     the kill criteria; the news items; the notes, with Add a note; the findings; the company's
     ledger rows; then what the drawer showed before Details, in its order, the inputs led by the
     line that says what the figures are in (currencyLine), and the flags, the review's under a
     line that says so where the review has a value (drawerFlags, spec 2026-11-13 8a). The review
     and the secondary come with the detail; the rest is its own read (readResearch). A list with
     nothing in it is left out, but for the notes, which carry the owner's field. The money
     figures of the records are in the company's reporting currency (spec 2026-11-10 7.3 and
     7.6), but a finding's and a guidance record's, each in its own currency (spec 2026-11-15
     9.5); the head's value and levels and the secondary valuation's value a share in USD. */
  function details(body) {
    var r = body.result;
    var im = r.intermediates;
    var code = body.currency; /* the reporting currency, a record's that names none */
    var phase = PHASE_NUMBER[r.phase.phase];
    var growth = r.route === 'revenue-growth';
    var estimates = r.inputs.filter(function (i) { return i.kind === 'estimate'; });
    var review = body.review;
    var secondary = body.secondary;
    var flagged = drawerFlags(body);
    var found = state.research && state.research.symbol === r.symbol ? state.research : null;
    var rs = found && found.body;
    var draft = drafted(r.symbol);
    return h('div', { key: 'details', className: 'app-drawer__details' },
      body.brief ? section('about', 'About',
        h('p', { className: 'body' }, body.brief)) : null,
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
          note: isReviewed(body) ? mechanicalLevels(r.levels) : undefined
        })) : null,
      review && review.refusal ? section('review', 'Review',
        h('p', { className: 'body app-refusal' }, review.refusal)) : null,
      secondary ? block('app-secondary', 'Secondary valuation',
        notFallback(body) ? h('p', { className: 'caption app-muted' }, notFallback(body)) : null,
        pairs(secondaryRows(secondary)),
        secondaryPath(secondary, code),
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
             effect; a step that refused, its refusal (a later step may still value the review);
             outside one (no review there, after a revalue, or one that refused) its Result row
             says so instead. */
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
            resultNote: effect === undefined ? (line && line.refusal) || NO_EFFECT : undefined
          });
        })) : null,
      rs && rs.guidance.length ? block('app-guidance', 'Guidance on file',
        guidanceTable(rs.guidance.map(function (g) {
          return Object.assign({}, g, {
            state: g.supersededBy == null ? 'current' : 'superseded by record ' + g.supersededBy,
            citedBy: citedBy(rs.overrides, g.id)
          });
        }), code)) : null,
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
        findingsList(rs.findings, code)) : null,
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
      /* Only the two mature routes write the charge, and a row they refuse for a value at or
         below zero keeps it without a route: the reader most needs it there. */
      'charge' in im ? matureRoute(r) : null,
      /* A Decline row refused for a value at or below zero keeps its figures but has no route,
         and a Start-up row is always a refusal with its figures: each draws from the
         intermediates only its route writes. */
      'runoff_path' in im ? declineRoute(r) : null,
      'requirement' in im ? startUpRoute(r) : null,
      section('inputs', 'Inputs',
        currencyLine(body) ? h('p', { className: 'caption app-muted' }, currencyLine(body)) : null,
        inputsTable(r.inputs)),
      section('intermediates', 'Intermediate results', intermediates(r.intermediates)),
      section('flags', 'Flags',
        flagged.reviewed
          ? h('p', { className: 'caption app-muted' }, 'The review\'s flags.') : null,
        flagged.flags.length ? h('ul', { className: 'app-list' },
          flagged.flags.map(function (f) {
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
     report on a company with a report as on one without (the founder asked for a full report on
     the second run), and no note. Its launch (spec 2026-11-16 agent launch, 10): the menu's box
     Open Claude Code ticked (`launch`); no launch's post in flight (`opening`); no launch
     followed (`followed`, the launch as the page last read it); no timer (`timer`, held from the
     moment a read of the followed launch is due until its answer lands); no failed read of it in
     a row (`misses`); and the count of the following's stops (`round`), so a read or a post begun
     before a stop is dropped. */
  function asking(symbol) {
    return {
      symbol: symbol, open: false, mode: 'full report', note: '', error: null, posting: false,
      launch: true, opening: false, followed: null, timer: null, misses: 0, round: 0
    };
  }

  /* Request research (spec 18.2), as the drawer and the report page show it with or without a
     report (18.4): the button, disabled while an item is open or a launch's post is in flight,
     its menu, the server's refusal under it and the open item's line. `ask` is the view's request
     (asking), `redraw` draws the view again and `after` runs once a post ends, taken or refused,
     so the view reads its company again and the open item's line follows; `ready` is the detail
     read's launchReady, whether launching is set up (spec 2026-11-16 agent launch, 10). */
  function requestResearch(ask, item, redraw, after, ready) {
    return h(React.Fragment, null,
      h('div', { className: 'app-request' },
        h(F.Button, {
          disabled: !!item || ask.opening,
          'aria-expanded': ask.open ? 'true' : 'false',
          onClick: function () { toggleRequest(ask, redraw); }
        }, 'Request research'),
        ask.open ? h(RequestMenu, { ask: ask, redraw: redraw, after: after, ready: ready }) : null),
      ask.error ? h('p', { className: 'caption app-request__error' }, ask.error) : null,
      requested(ask, item, redraw, after, ready));
  }

  function toggleRequest(ask, redraw) {
    ask.open = !ask.open;
    ask.error = null;
    redraw();
  }

  /* Request research's menu (spec 18.2), in the bundle's menu style as Details ▾ draws it: the
     mode, a radio each, the note line, where launching is set up the box Open Claude Code (spec
     2026-11-16 agent launch, 10), then Post. It opens under its button from the button's left
     edge, focus on the chosen mode; Post, or Enter in the note line, sends it. A press or focus
     outside the button and its menu closes it, as the screen's menus close, and so does Escape,
     which hands focus back to the button; the listeners last as long as the menu, and the
     drawer's own Escape, registered first, sees the menu open and waits. */
  function RequestMenu(props) {
    var ask = props.ask;
    var redraw = props.redraw;
    var after = props.after;
    var ready = props.ready;
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
      onSubmit: function (event) { event.preventDefault(); postRequest(ask, redraw, after, ready); }
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
            placeholder: 'The request in your words, one line',
            onChange: function (event) { ask.note = event.target.value; redraw(); }
          })),
        ready ? h('div', { className: 'fb-menu__sec app-request__launch' },
          h('label', { className: 'fb-menu__row control' },
            h('input', {
              type: 'checkbox', checked: ask.launch,
              onChange: function () { ask.launch = !ask.launch; redraw(); }
            }),
            h('span', null, 'Open Claude Code'))) : null),
      h('div', { className: 'fb-menu__foot' },
        h(F.Button, { type: 'submit', size: 'sm', disabled: ask.posting }, 'Post')));
  }

  /* Post: the item, as the owner (no identity headers), with the request header every page write
     carries. The menu closes; a refusal, a second open item's 409 among them, shows the server's
     sentence under the button as it arrives, the note kept for another try. A post taken where
     launching is set up and Open Claude Code is ticked posts the item's launch (openLaunch), which
     runs `after` once its own post ends, unless the request was stopped (stopLaunch: the drawer
     closed or turned to another company) while the item's post was in flight; otherwise `after`
     runs, so the view reads its company again and the open item's line follows. */
  function postRequest(ask, redraw, after, ready) {
    if (ask.posting) return;
    ask.posting = true;
    ask.error = null;
    redraw();
    var posted = null;
    var round = ask.round;
    api.post('/api/inbox', { symbol: ask.symbol, mode: ask.mode, note: ask.note.trim() })
      .then(function (r) {
        if (!r.ok) throw new Error(r.body && r.body.detail ? String(r.body.detail)
          : 'the server answered ' + r.status);
        ask.note = '';
        posted = r.body.id;
      })
      .catch(function (err) { ask.error = err.message; })
      .then(function () {
        ask.posting = false;
        ask.open = false;
        if (posted !== null && ready && ask.launch && round === ask.round) {
          openLaunch(ask, posted, redraw, after);
        } else {
          after();
        }
      });
  }

  /* The open item's line under Request research, until the item is done or declined (launchLine
     of lineItem). A failure's line is in the request's error style. After its text, where
     launching is set up, the row's button, Open Claude Code or Open again, which posts a launch
     for the item. */
  function requested(ask, item, redraw, after, ready) {
    var line = launchLine(lineItem(ask, item), ready);
    if (!line) return null;
    return h('p', {
      className: line.failed ? 'caption app-request__error' : 'caption app-requested'
    },
      line.text,
      ready && line.action ? h(F.Button, {
        size: 'sm', variant: 'quiet', className: 'app-request__open',
        onClick: function () { openLaunch(ask, item.id, redraw, after); }
      }, line.action === 'open' ? 'Open Claude Code' : 'Open again') : null);
  }

  /* The item a request's line is drawn from: one with an opening launch while a launch's post is
     in flight, whatever the item's launch, before the item is read again too; else the item, with
     the launch the page follows in place of its own where it is that item's. */
  function lineItem(ask, item) {
    if (ask.opening) return { state: 'pending', launch: { state: 'opening' } };
    return item && ask.followed && ask.followed.itemId === item.id
      ? Object.assign({}, item, { launch: ask.followed }) : item;
  }

  /* The open item's line (spec 2026-11-16 agent launch, 10) from the item and its newest launch,
     as { text, failed, action }: its words (launchWords) after the word Requested, a failure's
     sentence whole. No item has no line. */
  function launchLine(item, ready) {
    var words = launchWords(item, ready);
    if (!words || words.failed) return words;
    return { text: 'Requested · ' + words.text, failed: false, action: words.action };
  }

  /* What the line says of the item and its newest launch, as { text, failed, action }: a claim
     whatever the launch; a pending item with no launch with the action 'open' where launching is
     set up (`ready`); a failure's sentence, and the two overdue ones, in the error style with the
     action 'again'; the others with none. No item has no words. The Inbox view's row, whose
     state cell says the item's state, shows them without the word Requested (B-210). */
  function launchWords(item, ready) {
    if (!item) return null;
    var launch = item.launch;
    if (item.state === 'claimed') return said('claimed by ' + item.claimedBy);
    if (!launch) return { text: 'pending', failed: false, action: ready ? 'open' : null };
    if (launch.state === 'opening') return said('opening a window…');
    if (launch.state === 'opened' && !launch.overdue) {
      return said('the window opened, Claude Code is starting…');
    }
    if (launch.state === 'opened') {
      return failure('The window opened, but nothing in it reported after 90 seconds. ' +
        'Check the window.');
    }
    if (launch.state === 'started' && !launch.overdue) {
      return said('Claude Code started, not claimed yet');
    }
    if (launch.state === 'started') {
      return failure('Claude Code started, but no agent claimed this request after 90 ' +
        'seconds. Check the window.');
    }
    if (launch.state === 'ended') {
      return failure('Claude Code ended before it claimed this request (exit code ' +
        launch.exitCode + ').');
    }
    if (launch.stage === 'window') {
      return failure('Could not open the window: ' + launch.detail + '. Check Settings, Agents.');
    }
    return failure('The window opened, but Claude Code did not start: ' + launch.detail +
      '. Check Settings, Agents.');
  }

  function said(text) { return { text: text, failed: false, action: null }; }

  function failure(text) { return { text: text, failed: true, action: 'again' }; }

  /* Open Claude Code, Open again, and a post taken with the box ticked: the item's launch,
     posted as the owner with the request header. Any following stops first, and while the post
     is in flight, up to the window command's 15 seconds, the line is the opening one. A 201 is
     the launch, which the page then follows; a 409, the item no longer pending or a launch for it
     in flight, shows no error, since the company read again draws the claim or that launch; any
     other refusal's sentence is the request's error, and a post that fails on the network says
     that the window was not opened and why. Either way `after` runs once the post ends, so the
     view reads its company again with the item and its launch; a request stopped meanwhile
     (stopLaunch) follows nothing. */
  function openLaunch(ask, itemId, redraw, after) {
    if (ask.opening) return;
    stopLaunch(ask);
    ask.followed = null;
    ask.opening = true;
    ask.error = null;
    redraw();
    var round = ask.round;
    api.post('/api/launches', { itemId: itemId })
      .then(function (r) {
        if (r.ok) ask.followed = r.body;
        else if (r.status !== 409) ask.error = refusalDetail(r);
      }, function (err) {
        ask.error = 'The window was not opened: ' + err.message + '.';
      })
      .then(function () {
        ask.opening = false;
        after();
        if (round === ask.round) followLaunch(ask, redraw, after);
      });
  }

  /* How long after an answer the page reads a followed launch again; how many reads in a row
     may fail before the following stops; and the words a failed read's sentence starts with. */
  var LAUNCH_READ_MS = 2000;
  var LAUNCH_MISSES = 30;
  var UNREAD = 'The launch could not be read: ';

  /* The page follows the request's launch (spec 2026-11-16 agent launch, 10): while it is
     followed (following), it is read again LAUNCH_READ_MS after the last answer and the view is
     drawn with each answer, with one timer for a request. Once an answer is no longer followed,
     the item claimed or no longer open, the launch failed or ended, or ten minutes past its
     making, the following ends and `after` runs once, so the view reads its company again and the
     line draws the claim or the failure. An answer from before a stop (stopLaunch) is dropped. A
     read that fails does not end the following: the next read runs LAUNCH_READ_MS later, and the
     request's error says the launch could not be read and that the page tries again, until a read
     succeeds and clears that sentence (unread). The LAUNCH_MISSES-th failed read in a row ends
     the following: `after` runs once, and the sentence says to reload the page. */
  function followLaunch(ask, redraw, after) {
    var launch = ask.followed;
    if (ask.timer !== null || !following(launch)) return;
    var round = ask.round;
    ask.timer = setTimeout(function () {
      getJson('/api/launches/' + launch.id).then(function (got) {
        if (round !== ask.round) return;
        ask.timer = null;
        ask.misses = 0;
        unread(ask);
        ask.followed = got;
        if (following(got)) followLaunch(ask, redraw, after);
        else after();
        redraw();
      }, function (err) {
        if (round !== ask.round) return;
        ask.timer = null;
        ask.misses++;
        if (ask.misses < LAUNCH_MISSES) {
          ask.error = UNREAD + err.message + '. Trying again.';
          followLaunch(ask, redraw, after);
        } else {
          ask.error = UNREAD + err.message + '. Reload the page.';
          after();
        }
        redraw();
      });
    }, LAUNCH_READ_MS);
  }

  /* The request's error goes where it is a failed read's sentence (followLaunch), and no other. */
  function unread(ask) {
    if (ask.error && ask.error.indexOf(UNREAD) === 0) ask.error = null;
  }

  /* The request's following stops: its timer is cleared, its count of failed reads goes back to
     none, and its round moves on, so a read begun before the stop is dropped when it lands, and a
     post begun before it (the item's or its launch's) follows nothing. The drawer stops it as it
     closes and as it turns to another company, the report page as it starts to read another
     company. */
  function stopLaunch(ask) {
    ask.round++;
    if (ask.timer !== null) clearTimeout(ask.timer);
    ask.timer = null;
    ask.misses = 0;
  }

  /* A view's read of its company has landed, with its open item or none. The launch the request
     follows goes once the read holds no open item, another item or a newer launch of it, and
     once no following runs, since the read is then the newer. Then, where no following runs and
     no launch's post is in flight, an open item whose launch is followed (following) starts the
     following, and a failed read's sentence goes (unread): a view that loads while a launch is in
     flight follows it. */
  function followItem(ask, item, redraw, after) {
    var held = ask.followed;
    if (held && (ask.timer === null || !item || held.itemId !== item.id ||
        (item.launch && item.launch.id > held.id))) {
      stopLaunch(ask);
      ask.followed = null;
    }
    if (ask.timer !== null || ask.opening || !item || !following(item.launch)) return;
    unread(ask);
    ask.followed = item.launch;
    followLaunch(ask, redraw, after);
  }

  /* The drawer's company read has landed: the drawer shows it, and its request follows the open
     item's launch (followItem). */
  function landed(symbol, body) {
    state.drawer = { symbol: symbol, body: body, loading: false, error: null };
    followItem(asked(body.result.symbol), body.item, render, reread(body.result.symbol));
  }

  /* The drawer's `after` for a company's request: its detail read again. */
  function reread(symbol) {
    return function () { reloadDetail(symbol); };
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
        landed(symbol, body);
      })
      .catch(function () { /* the drawer keeps what it shows */ })
      .then(render);
  }

  /* The company the drawer shows read again when a run ends (controls.js), since a run may
     follow its review, post its expiry item or drop an override (method 14.6): the detail in
     place, and Details' records while Details is open. */
  function reloadDrawer() {
    var d = state.drawer;
    if (!d) return;
    if (state.detailsOpen) readResearch(d.symbol);
    reloadDetail(d.symbol);
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

  /* The bridge's note: the engine's own levels, the snapshot's, which the meter and the levels
     named under it no longer show where they draw the review's (spec 2026-11-06 Tier 2, 18.1 and
     18.2, plan 3); none on a refused row, where the engine has no levels. */
  function mechanicalLevels(l) {
    if (!l) return undefined;
    return 'Mechanical levels: margin of safety ' + F.formatMoney(l.buy) + ' · fair band ' +
      F.formatMoney(l.fair_low) + ' – ' + F.formatMoney(l.fair_high) + ' · trim ' +
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
     a total in whole units of `code`, the reporting currency (spec 2026-11-10 7.6), with its note
     under it; on the drivers form the drivers in words, the rates as percentages. */
  function secondaryPath(s, code) {
    if (s.form === 'parts') {
      return h('ul', { className: 'app-list app-secondary__path' }, s.parts.map(function (p, i) {
        return h('li', { key: i },
          h('span', { className: 'app-line' },
            h('span', { className: 'body' }, p.name), ' ',
            h('span', { className: 'figure-sm' }, whole(p.value, code))),
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
     growth rate as a percent, any other a total in whole units. A point is one figure. The money
     figures are in `code`, the record's currency (spec 2026-11-10 7.3, spec 2026-11-15 9.5). */
  var GUIDED_PERCENT = ['operating_margin', 'revenue_growth', 'eps_growth'];

  function guided(v, metric, code) {
    if (metric === 'eps') return money(v, code);
    if (GUIDED_PERCENT.indexOf(metric) !== -1) return F.formatPercent(v);
    return whole(v, code);
  }

  function guidedRange(g, code) {
    if (g.low === g.high) return guided(g.low, g.metric, code);
    return guided(g.low, g.metric, code) + ' – ' + guided(g.high, g.metric, code);
  }

  /* The guidance on file (spec 18.3, and Appendix A's, 18.4): each record's metric, period and
     basis, its call's date and its state in words, the overrides citing it, then its range and
     midpoint in the metric's unit, a money figure in the record's own currency, `g.currency`,
     `$` for USD and the code before the number otherwise, else in `code`, the reporting currency
     (spec 2026-11-15 9.5). Each record brings its state, the ids citing it and its currency,
     which Details reads from the research records and the report page from Appendix A, whose
     record naming none is in the report's snapshot's currency. */
  function guidanceTable(guidance, code) {
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
            h('span', { className: 'figure-sm app-line' }, guidedRange(g, g.currency || code)),
            h('span', { className: 'caption app-muted app-line' },
              'midpoint ' + guided(g.midpoint, g.metric, g.currency || code))));
      })));
  }

  /* Details' findings (spec 18.3): each with its date and period, its text and its figure, its
     source and who wrote it; a money figure in the finding's own currency, `f.currency`, else in
     `code`, the reporting currency (spec 2026-11-15 9.5). */
  function findingsList(findings, code) {
    return h('ul', { className: 'app-list' }, findings.map(function (f) {
      return h('li', { key: f.id },
        h('span', { className: 'caption app-line' }, 'as of ', when(f.asOf),
          f.period ? ' · ' + f.period : null),
        h('p', { className: 'body' }, f.text, f.value != null ? h('span',
          { className: 'figure-sm' }, ' ' + findingFigure(f.value, f.unit, f.currency || code))
          : null),
        h('p', { className: 'caption app-muted app-source' }, f.source.kind + ' ',
          h('code', { className: 'fb-tag figure-sm' }, f.source.ref),
          f.source.note ? ' — ' + f.source.note : null),
        h('p', { className: 'app-chipline' },
          h(F.PrincipalChip, { principal: f.principal, actor: f.actor, at: localIso(f.at) })));
    }));
  }

  /* A finding's value in its unit (store.research.UNITS), a total or a figure a share in `code`,
     the finding's currency, `$` for USD and the code before the number otherwise. */
  function findingFigure(v, unit, code) {
    if (unit === 'currency') return whole(v, code);
    if (unit === 'per-share') return money(v, code);
    if (unit === 'percent') return F.formatPercent(v);
    if (unit === 'multiple') return times(v);
    return plain(v);
  }

  /* A store word in a reader's words: target_margin is target margin. */
  function words(name) { return String(name).replace(/_/g, ' '); }

  /* The band meter's gap text, beside the word's chip in its head (spec 2026-11-06 Tier 2, 18.2
     item 2, plan 4): price ÷ value over the value's name `of` in one form, "0.82 × the reviewed
     value"; '' where there is no ratio (a row valued before the designation), which draws none. */
  function gapText(ratio, edges, of) {
    return ratio == null ? '' : ratioFigure(ratio, edges) + ' × ' + of;
  }

  /* Why a secondary valuation on file is not the row's fallback (spec 2026-11-06 Tier 2, 11, plan
     3): the route values the company, or the review on the latest snapshot does, as Appendix A
     says of a report; null where it is the fallback. */
  function notFallback(body) {
    if (body.result.value != null) return 'not the fallback: the route values the company';
    var v = body.review;
    if (v && v.value != null) return 'not the fallback: the review values the company';
    return null;
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
     is off: in the drawer's rail these names would run into each other. `r` is the meter's
     levels (drawnLevels): the review's where its band is drawn, else the engine's. */
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
     among the intermediates. The route computes it in `code`, the reporting currency. */
  function crossCheck(g, code) {
    if (!g || g.value_per_share == null) return null;
    return h('p', { className: 'caption app-muted' }, 'Growth-route cross-check: ' +
      money(g.value_per_share, code) + ' (implied growth ' + F.formatPercent(g.implied_growth) +
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

  /* ------------------------------------------- the Mature Growth and Mature Stable routes */

  /* The route of a mature phase, for a refused row, which has none. */
  var MATURE = { 'Mature Growth': 'mature-growth', 'Mature Stable': 'mature-stable' };

  /* The company's logo before its ticker (B-203), in the drawer's head and the report page's:
     an image of the detail read's `logo`, the address of the logo read, which the server names
     where the stored profile names a logo and fetches once; nothing without one. The ticker and
     the name stand beside it, so its alt is empty. The tile holds its place unseen until the
     image loads (logoLoaded), since the first read waits on the server's fetch and an empty
     white tile would flash meanwhile; an image that does not load hides itself and gives its
     place up. Its key is the address: the drawer's next company draws a new element, not one an
     earlier load marked. `className` is the head's own class; the report page's sets a larger
     size. */
  function logo(body, className) {
    if (!body.logo) return null;
    return h('img', {
      key: body.logo, className: 'app-logo ' + className, src: body.logo, alt: '',
      onLoad: logoLoaded,
      onError: function (event) { event.target.hidden = true; }
    });
  }

  var LOGO_SAMPLE = 64;

  /* A logo's image has loaded: the tile takes the ground the image needs, then shows
     (is-loaded). The tile is white unless the logo's marks are light where they meet its clear
     ground (logoGround), when it is dark (is-on-dark). A blank image is hidden like one that did
     not load. Where the browser gives no pixels the tile stays white. */
  function logoLoaded(event) {
    var image = event.target;
    var pixels = logoPixels(image);
    var ground = pixels ? logoGround(pixels, LOGO_SAMPLE) : 'white';
    if (ground === 'blank') { image.hidden = true; return; }
    if (ground === 'dark') image.classList.add('is-on-dark');
    image.classList.add('is-loaded');
  }

  /* The image's pixels, drawn LOGO_SAMPLE a side on a canvas: red, green, blue and alpha a
     pixel, row by row. The logo read is this page's own origin, so the canvas may be read. Null
     where the browser draws or gives none. */
  function logoPixels(image) {
    try {
      var canvas = document.createElement('canvas');
      canvas.width = LOGO_SAMPLE;
      canvas.height = LOGO_SAMPLE;
      var context = canvas.getContext('2d');
      context.drawImage(image, 0, 0, LOGO_SAMPLE, LOGO_SAMPLE);
      return context.getImageData(0, 0, LOGO_SAMPLE, LOGO_SAMPLE).data;
    } catch (error) {
      return null;
    }
  }

  /* The ground a logo needs (B-206), from its pixels (`data`, `size` a side). Many of FMP's
     logos are white marks on a clear ground, drawn for a dark page: on a white tile they are a
     plain white square. So the ground is read where the marks meet the clear pixels. A pixel at
     least half opaque is a mark's, any other is clear; a mark's pixel beside a clear one, left,
     right, above or below, is an edge pixel; one is light at a luma of 0.85 or more. 'dark'
     where more than half of the edge is light; 'white' otherwise, and for an image with no
     clear pixel beside a mark, which brings its own ground; 'blank' for an image with no mark,
     clear all over or light all over, as FMP holds for some companies. White lettering inside a
     coloured shape meets no clear pixel, so the shape's edge decides. */
  function logoGround(data, size) {
    function clear(x, y) {
      return x >= 0 && y >= 0 && x < size && y < size && data[4 * (y * size + x) + 3] < 128;
    }
    var marks = 0;
    var light = 0;
    var edge = 0;
    var lightEdge = 0;
    for (var y = 0; y < size; y += 1) {
      for (var x = 0; x < size; x += 1) {
        var i = 4 * (y * size + x);
        if (data[i + 3] < 128) continue;
        var luma = (0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]) / 255;
        var isLight = luma >= 0.85;
        var isEdge = clear(x - 1, y) || clear(x + 1, y) || clear(x, y - 1) || clear(x, y + 1);
        marks += 1;
        if (isLight) light += 1;
        if (isEdge) edge += 1;
        if (isEdge && isLight) lightEdge += 1;
      }
    }
    if (marks === 0 || (edge === 0 && light === marks)) return 'blank';
    return lightEdge > edge / 2 ? 'dark' : 'white';
  }

  /* The moat stamp after the phase badge (the company page's design, 7.2): the detail's `moat`,
     the moat class in force, the review's where a review counts, else the snapshot's, in the
     stamp's words. An outlined label in ink-muted with no fill, since the phase colours mean the
     phase alone. A row with no value has no moat, and no stamp. */
  var MOAT_WORDS = { Wide: 'WIDE MOAT', Narrow: 'NARROW MOAT', None: 'NO MOAT' };

  function moatStamp(body) {
    var words = MOAT_WORDS[body.moat];
    return words ? h('span', { className: 'label app-moat' }, words) : null;
  }

  /* The head's one line on the company (B-149): the universe row's sector and industry, then
     the first sentence of the company brief, the stored profile's description, joined by middle
     dots; the parts it has, nothing without any. The full brief is behind Details, under About,
     and whole on the report page. */
  function briefLine(company, brief) {
    var parts = [];
    if (company && company.sector) parts.push(company.sector);
    if (company && company.industry) parts.push(company.industry);
    var first = firstSentence(brief);
    if (first) parts.push(first);
    return parts.join(' · ');
  }

  /* The words a period follows without ending a sentence, as the live briefs have them: "KKR &
     Co. Inc.", "Eaton Corp. PLC", "Dr. Reddy's", "St. Louis". */
  var ABBREVIATIONS = ['co', 'corp', 'inc', 'ltd', 'st', 'dr', 'mr', 'mrs', 'ms', 'mt', 'jr', 'sr'];

  /* The first sentence of a text: to the first period that white space and a capital letter
     follow, where the word before the period is more than one letter, holds no period of its
     own and is not one of ABBREVIATIONS, so "Apple Inc. designs", "the U.S. The", "Plan B. The"
     and "St. Joe" do not end it; the whole text, trimmed, without such a period. */
  function firstSentence(text) {
    var s = (text == null ? '' : String(text)).trim();
    var ends = /\.\s+(?=[A-Z])/g;
    var found;
    while ((found = ends.exec(s)) !== null) {
      var word = s.slice(0, found.index).split(/\s+/).pop();
      if (word.length > 1 && word.indexOf('.') === -1 &&
          ABBREVIATIONS.indexOf(word.toLowerCase()) === -1) {
        return s.slice(0, found.index + 1);
      }
    }
    return s;
  }

  /* A row on its earnings path (method 4.8, 5 and 6), valued or refused for a value at or below
     zero: the charge, in words (spec 2026-11-09 12), then the count under shares.committed, under
     the route's name, a refused row's by its phase. The figures behind it are among the
     intermediates. */
  function matureRoute(r) {
    return section('mature', ROUTES[r.route || MATURE[r.phase.phase]],
      annualAnchor(r.intermediates.anchor, r.intermediates.currency),
      group('charge', 'Charge', pairs(chargeRows(r.intermediates))),
      shareCount(r.intermediates));
  }

  /* A mature route's count in force under shares.committed (spec 2026-11-14 4), with the
     committed shares it holds: the route's section has no count of its own, so the group shows
     only under the override. */
  function shareCount(im) {
    if (!('shares_committed' in im)) return null;
    return group('shares', 'Share count',
      pairs([['Shares', plain(im.shares), true]].concat(committedShares(im))));
  }

  /* Year 1 on a thin NTM window, the periods' sum corrected by the annual consensus of the last
     fiscal year the window reaches (spec 2026-11-13 9a): "Year 1 from the periods, corrected by
     the annual consensus of fiscal 2027: +$0.12 a share.", the correction signed, in `code`, the
     row's currency; nothing on the window's periods, on a Mature Stable row, or on an anchor
     stored before method 1.4. */
  function annualAnchor(anchor, code) {
    var gap = anchor && anchor.source === 'annual' ? anchor.annual : null;
    if (!isTable(gap) || typeof gap.correction !== 'number') return null;
    return h('p', { className: 'caption' }, 'Year 1 from the periods, corrected by the annual ' +
      'consensus of fiscal ' + gap.fiscal_year + ': ' + (gap.correction > 0 ? '+' : '') +
      money(gap.correction, code) + ' a share.');
  }

  /* The charge's rows (spec 2026-11-09 6.2 and 6.3): the return each year's reinvestment pays
     at; the growth it pays for in years 2 and 3 beside the earnings growth, or on a Mature Stable
     row the terminal growth in every year; and the newest year's marginal return and the
     five-year marginal return at a constant margin (method 4.6), each shown and never used,
     when there is one. Where the measure was below the hurdle rate and the charge
     read the return without goodwill (method 4.6 rule 5), both measures follow: the one below
     the hurdle rate, then the same measure on capital without goodwill and intangibles, or the
     words for a business with no capital without them. The return by year shows the start. */
  function chargeRows(im) {
    var c = im.charge, rr = im.runway_return || {};
    var organic = rr.used === 'without-goodwill' ? rr.without_goodwill : null;
    var rows = [
      ['Return by year', returnByYear(c.return_by_year, c.hold_years, im.charge_off === true),
        false],
      ['Growth the charge pays for', 'stable_growth' in im
        ? F.formatPercent(c.growth_by_year[c.growth_by_year.length - 1]) +
          ' a year, the terminal growth'
        : paidFor(c, im.growth_rates), false]
    ];
    if (rr.one_year != null) {
      rows.push(['Newest year\'s marginal return', F.formatPercent(rr.one_year), true]);
    }
    if (rr.constant_margin != null) {
      rows.push(['Five-year return at a constant margin', F.formatPercent(rr.constant_margin),
        true]);
    }
    if (organic) {
      rows.push(['Return with goodwill',
        F.formatPercent(rr.marginal_usable ? rr.marginal : rr.three_year) +
        ', below the hurdle rate', true]);
      rows.push(organic.measure == null
        ? ['Return without goodwill', 'no capital without goodwill', false]
        : ['Return without goodwill', F.formatPercent(organic.measure), true]);
    }
    return rows;
  }

  /* The return by year from its ends and the hold (method 4.8): years 1 to N - 1 uncharged when
     the charge is off (4.6 rule 4; the row's charge_off, never the measure's word, since a
     return.runway override charges a row whose measure was off); one figure when both ends read
     the same; with no hold, a straight line from year 1; with the hold at N - 1 or more, held to
     year N - 1, the shape before method 1.0; else held through the hold, then a straight line to
     year N. The line falls, or rises where an override starts it below the terminal return, so
     the words say neither. */
  function returnByYear(returns, hold, off) {
    var n = returns.length, first = F.formatPercent(returns[0]);
    var end = F.formatPercent(returns[n - 1]), last = end + ' in year ' + n;
    if (n === 1) return last;
    if (off) return 'no charge in years 1 to ' + (n - 1) + ', then ' + last;
    if (first === end) return first + ' in every year';
    if (hold === 0) return 'from ' + first + ' in year 1 to ' + last;
    if (hold >= n - 1) return first + ' through year ' + (n - 1) + ', then ' + last;
    return first + ' through year ' + hold + ', then to ' + last;
  }

  /* Years 2 and 3's growth the charge pays for beside the earnings growth as the path resolved
     it, and where each year's comes from (method 4.8, spec 2026-11-14 6.3): the consensus revenue
     step, an agent's override of it, or the year's earnings growth, where the consensus gives no
     revenue step or a thin one; one phrase for both years where they come from one place. */
  function paidFor(c, earnings) {
    var h = c.growth_by_year, source = stepSources(c);
    var paid = F.formatPercent(h[0]) + ' then ' + F.formatPercent(h[1]);
    var against = ', against earnings of ' + F.formatPercent(earnings[0]) + ' then ' +
      F.formatPercent(earnings[1]);
    var both = source[0] === source[1] ? source[0] : null;
    if (both === 'consensus') return paid + ' on revenue' + against;
    if (both === 'agent') return paid + ' on revenue from overrides' + against;
    if (both === 'none') {
      return paid + ', the earnings growth: years 2 and 3 have no revenue consensus';
    }
    return paid + against + ': ' + [0, 1].map(function (k) {
      if (source[k] === 'thin') return 'year ' + (k + 2) + thinStep(c.revenue_steps_found[k]);
      return 'year ' + (k + 2) + STEP_FROM[source[k]];
    }).join(', ');
  }

  /* Each year's source, as the charge records it; on a result stored before it was recorded,
     from the steps the charge read: a step the consensus's, none the earnings growth. */
  function stepSources(c) {
    return c.revenue_step_source || c.revenue_steps.map(function (step) {
      return step == null ? 'none' : 'consensus';
    });
  }

  /* What a year's growth is, by its source, after "year 2". */
  var STEP_FROM = {
    consensus: ' is on revenue',
    agent: ' is on revenue from an override',
    none: ' has no revenue consensus and takes its earnings growth'
  };

  /* A thin year (spec 2026-11-14 6.2): its consensus revenue step as found, above the most read
     on fewer revenue analysts than the analyst minimum, or no count, is not read. The drawer
     holds neither limit, so the words name them without figures. */
  function thinStep(step) {
    return ' has too few analysts on file for a revenue consensus as high as ' +
      F.formatPercent(step) + ' and takes its earnings growth';
  }

  /* ---------------------------------------------------- the revenue growth route */

  /* A row valued on the revenue DCF (growth-routes spec 5): the ten years, the peers that set
     the target margin, the sales-to-capital, the terminal and the bridge to equity, then the two
     solves at the price, so the arithmetic reproduces from the drawer. */
  function revenueRoute(r) {
    var im = r.intermediates;
    var code = im.currency;
    var held = heldYears(ruleValue(r.inputs, 'high_growth_years'));
    return section('revenue', ROUTES[r.route],
      group('years', 'Ten years', yearsTable(im)),
      group('peers', 'Target margin', peersTable(im.target_margin.peers),
        pairs(peerSummary(im.target_margin))),
      group('capital', 'Sales-to-capital', pairs(salesToCapital(im.sales_to_capital))),
      group('bridge', 'Terminal and bridge to equity', pairs([
        ['Terminal return', F.formatPercent(im.terminal_roic), true],
        ['Year-10 NOPAT, fully taxed', whole(im.terminal_nopat, code), true],
        ['Terminal value', whole(im.terminal_value, code), true],
        ['Firm value', whole(im.firm_value, code), true],
        ['Less debt', whole(im.debt, code), true]
      ].concat(lessMinority(im), [
        ['Plus cash', whole(im.cash, code), true],
        ['Equity', whole(im.equity, code), true],
        ['Shares', plain(im.shares), true]
      ], committedShares(im), [
        ['Value a share', money(im.value_per_share, code), true]
      ])), sheetPeriod(im)),
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

  /* Whether the revenue-growth, Decline or Start-up row takes a minority interest off the owners'
     claim (spec 2026-11-13 13): above zero only, so a company with none, and a result stored
     before method 1.4, reads as before. */
  function hasMinority(im) { return im.minority_interest > 0; }

  /* The minority interest's row, after the debt, where there is one; none where there is not. */
  function lessMinority(im) {
    return hasMinority(im)
      ? [['Less minority interest', whole(im.minority_interest, im.currency), true]] : [];
  }

  /* The committed shares' row, right after the count, which holds them (spec 2026-11-14 4): an
     agent's shares.committed, on any of the five routes; none without the override. */
  function committedShares(im) {
    return 'shares_committed' in im ? [['Committed shares',
      noted(plain(im.shares_committed), 'in the shares above'), true]] : [];
  }

  /* The newest balance sheet the debt, the cash and the minority interest were read from (spec
     2026-11-13 12.2), under their rows: "Balance sheet of fiscal 2026 Q3."; nothing without a
     sheet, or on a result stored before method 1.4. */
  function sheetPeriod(im) {
    var sheet = im.balance_sheet;
    if (!sheet || !sheet.label) return null;
    return h('p', { className: 'caption' }, 'Balance sheet of ' + sheet.label + '.');
  }

  /* The implied growth is held from year 4 to the last high-growth year, the row's RULE input;
     null when the row has none, and the label then says only where the hold starts. */
  function heldYears(last) {
    if (last == null) return null;
    if (last === 4) return 'year 4';
    return last === 5 ? 'years 4 and 5' : 'years 4 to ' + last;
  }

  /* One row a year: the revenue, the margin, EBIT, tax, NOPAT, the reinvestment and the free cash
     flow, totals to whole units of the row's currency. On the dollar ramp the margin is each
     year's operating income over its revenue, the income moving in dollars (method 5a.4), or in
     the currency of a row in another, and its head says so. */
  function yearsTable(im) {
    var ramp = im.margin_path.ramp === 'dollars'
      ? 'ramp in ' + (foreign(im.currency) ? im.currency : 'dollars') : null;
    var total = wholeIn(im.currency);
    return figuresTable([
      ['Revenue', im.revenue_by_year, total],
      ['Margin', im.margin_path.by_year, F.formatPercent, ramp],
      ['EBIT', im.ebit_by_year, total],
      ['Tax', im.tax_by_year, total],
      ['NOPAT', im.nopat_by_year, total],
      ['Reinvestment', im.reinvestment_by_year, total],
      ['Free cash flow', im.fcff_by_year, total]
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
     it but the decline rate at the price. Its money figures are in the row's currency. */
  function declineRoute(r) {
    var im = r.intermediates;
    return section('decline', ROUTES.decline,
      group('runoff', 'Run-off', runoffTable(im), pairs(runoffSummary(im))),
      group('margin', 'Normalized margin', pairs(normalizedMargin(im.margin))),
      group('rating', 'Rating', pairs(rating(im.rating, im.currency))),
      group('floor', 'Floor and distress', pairs(floorAndDistress(im)), sheetPeriod(im),
        weighting(im)),
      group('altman', 'Altman Z″', altmanZ(im.altman_z)),
      group('piotroski', 'Piotroski F', piotroskiF(im.piotroski_f)));
  }

  /* A fall in revenue releases the capital it needed, recovered in part; a rise reinvests in
     full; each in the year of the change, so no year has both (spec 10.4). */
  function runoffTable(im) {
    var total = wholeIn(im.currency);
    return figuresTable([
      ['Revenue', im.revenue_by_year, total],
      ['EBIT', im.ebit_by_year, total],
      ['NOPAT', im.nopat_by_year, total],
      ['Release', im.release_by_year, total],
      ['Reinvestment', im.reinvestment_by_year, total],
      ['Free cash flow', im.fcff_by_year, total]
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
      ['Terminal value', noted(whole(im.terminal_value, im.currency), 'flat'), true],
      ['Firm value', whole(im.firm_value, im.currency), true]
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
     no π, the note saying which. EBIT and the interest are in `code`, the row's currency. */
  function rating(g, code) {
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
      ['EBIT at the normalized margin', whole(g.ebit, code), true],
      ['Interest expense, trailing', whole(g.interest, code), true],
      ['Coverage', times(g.coverage), true],
      [pi, F.formatPercent(g.pi), true]
    ];
  }

  /* The firm value to the going-concern value a share; the net current asset value a share, which
     floors it when above zero and above it (spec 10.6): no floor without one or at or below zero,
     and above zero a floor that binds or does not; the distress-sale value a share. A minority
     interest comes off all three (spec 2026-11-13 13): its row follows the debt, and the floor's
     row and the distress-sale value's words name it. Committed shares follow the count. */
  function floorAndDistress(im) {
    var ncav = im.ncav_per_share, code = im.currency, minority = hasMinority(im);
    var floor = ncav == null || ncav <= 0 ? 'no floor'
      : im.floored_per_share > im.going_concern_per_share ? 'the floor binds'
        : 'the floor does not bind';
    return [['Less debt', whole(im.debt, code), true]].concat(lessMinority(im), [
      ['Plus cash', whole(im.cash, code), true],
      ['Shares', plain(im.shares), true]
    ], committedShares(im), [
      ['Going concern a share', money(im.going_concern_per_share, code), true],
      [minority ? 'NCAV less minority interest, a share' : 'NCAV a share',
        noted(money(ncav, code), floor), true],
      ['Distress-sale value a share', noted(money(im.distress_per_share, code),
        F.formatPercent(im.distress_sale_fraction) + ' of firm value + cash − debt' +
        (minority ? ' − minority interest' : '')), true]
    ]);
  }

  /* The value a share (spec 10.7): the floored value weighted against the distress-sale value at
     π, or the floored value alone when π is unavailable. */
  function weighting(im) {
    var pi = im.pi.value, code = im.currency;
    var floored = money(im.floored_per_share, code);
    if (pi == null) {
      return h('p', { className: 'caption' }, 'π unavailable: the value is the floored value, ' +
        floored);
    }
    return h('p', { className: 'caption' },
      h('span', { className: 'app-line' }, 'value = floored × (1 − π) + distress × π'),
      h('span', { className: 'app-line' }, '= ' + floored + ' × (1 − ' + F.formatPercent(pi) +
        ') + ' + money(im.distress_per_share, code) + ' × ' + F.formatPercent(pi) + ' = ' +
        money(im.value_per_share, code)));
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
     cash covers the burn. Its money figures are in the row's currency. */
  function startUpRoute(r) {
    var im = r.intermediates;
    return section('start-up', ROUTES['start-up'],
      group('requirement', 'Revenue the price needs',
        requirement(im.requirement, im.currency, hasMinority(im)), movedCap(im, r.inputs)),
      group('floor', 'Cash floor', pairs(cashFloor(im)), sheetPeriod(im), belowFloor(r)),
      group('burn', 'Burn cover', pairs(burnCover(im))));
  }

  /* The year-10 revenue at which the straight ramp from today's revenue and operating income to
     the target margin is worth the enterprise value the price implies (spec 9.2), and the ramp,
     totals in `code`, the row's currency; or the reason the requirement is not computed. Where
     the row has a `minority` interest, the enterprise value adds it (spec 2026-11-13 13), and its
     words say so. */
  function requirement(req, code, minority) {
    var target = req.target_margin, s = req.sales_to_capital;
    var total = wholeIn(code);
    var rows = req.reason ? [['Not computed', req.reason, false]]
      : [['Year-10 revenue', total(req.revenue_y10), true]];
    if (!req.reason && req.revenue_0 > 0) {
      rows.push(['Against today', h(React.Fragment, null,
        decimals(req.revenue_y10 / req.revenue_0, 1),
        h('span', { className: 'caption' }, ' × the trailing revenue')), true]);
    }
    rows = rows.concat([
      ['Trailing revenue', total(req.revenue_0), true],
      ['Enterprise value at the price', enterpriseValue(req.ev_price, total, minority), true],
      ['Target margin', target == null ? '—'
        : noted(F.formatPercent(target.value), peersBehind(target)), true],
      ['Sales-to-capital', s == null ? '—' : noted(times(s.value), 'mature peers\' median'), true]
    ]);
    return h(React.Fragment, null, pairs(rows), req.path ? figuresTable([
      ['Revenue', req.path.revenue, total],
      ['EBIT', req.path.ebit, total],
      ['NOPAT', req.path.nopat, total],
      ['Reinvestment', req.path.reinvestment, total],
      ['Free cash flow', req.path.fcff, total]
    ]) : null, req.path ? pairs([
      ['Terminal value', total(req.terminal_value), true],
      ['Terminal return', F.formatPercent(req.terminal_roic), true]
    ]) : null);
  }

  /* The enterprise value the price implies, `total` its format: at or below zero, net cash
     covers the price; with a `minority` interest, the words name the sum, which adds it. */
  function enterpriseValue(ev, total, minority) {
    var covered = ev != null && ev <= 0 ? 'net cash covers the price' : null;
    if (minority && ev != null) {
      var sum = 'market cap + debt + minority interest − cash';
      return noted(total(ev), covered ? sum + '; ' + covered : sum);
    }
    return covered ? noted(total(ev), covered) : total(ev);
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
      dollars(im.market_cap, im.currency) + ' at this price, ' + dollars(read, im.currency) +
      ' as read');
  }

  /* The net cash a share (spec 9.4; method 6b.4): (cash − debt − minority interest) ÷ diluted
     shares, with any committed shares, the minority interest's row only where there is one and
     the committed shares' only under the override. */
  function cashFloor(im) {
    var code = im.currency;
    return [
      ['Net cash a share', money(im.cash_floor, code), true],
      ['Cash', whole(im.cash, code), true],
      ['Less debt', whole(im.debt, code), true]
    ].concat(lessMinority(im), [
      ['Shares', plain(im.shares), true]
    ], committedShares(im));
  }

  /* The caption reads the row's `below-net-cash` flag, the one test (method 6b.4): the market
     cap at or below the net cash, cash less debt and any minority interest, which is the price
     at or below the cash floor only when the market cap is the price times the diluted shares. */
  function belowFloor(r) {
    var below = r.flags.some(function (f) { return f.code === 'below-net-cash'; });
    if (!below) return null;
    return h('p', { className: 'caption' },
      'The price is covered by net cash: the market cap is at or below the cash less the debt' +
      (hasMinority(r.intermediates) ? ' and the minority interest' : ''));
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
        ['Burn a year', whole(im.burn, im.currency), true]
      ];
    }
    if (cover == null) return [['Trailing burn', noted('—', 'no trailing cash flows'), true]];
    return [
      ['Cash covers', decimals(cover, 1) + ' years', true],
      ['Burn a year', whole(im.burn, im.currency), true]
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

  /* Whether `code`, a figure's currency, is one other than USD: such a figure takes its code
     before the number, a USD one, or one with none named, `$` as before (spec 2026-11-10 7.4). */
  function foreign(code) { return !!code && code !== 'USD'; }

  /* A figure in a currency other than USD: the code before the number, to `dp` decimals,
     SEK 837.14, −SEK 800,000,000. */
  function coded(v, code, dp) {
    return (v < 0 ? '−' : '') + code + ' ' + decimals(Math.abs(v), dp);
  }

  /* A total in whole dollars, with separators: $5,900,000,000; in another currency `code`,
     whole units with its code: SEK 800,000,000. */
  function dollars(v, code) {
    return foreign(code) ? coded(v, code, 0) : (v < 0 ? '−$' : '$') + decimals(Math.abs(v), 0);
  }

  /* A total in whole units of `code`, USD when none; an em dash for none. */
  function whole(v, code) { return v == null ? '—' : dollars(v, code); }

  /* whole, in `code`, as a table's column format (figuresTable). */
  function wholeIn(code) { return function (v) { return whole(v, code); }; }

  /* A figure a share to cents: $104.64, or in another currency `code` SEK 837.14; an em dash for
     none. */
  function money(v, code) {
    if (!foreign(code)) return F.formatMoney(v);
    return v == null || isNaN(Number(v)) ? '—' : coded(Number(v), code, 2);
  }

  /* An exchange rate, units of a currency a US dollar: to two decimals, four below one, so a
     euro's 0.8612 keeps its figures (32.96, 8.00, 0.8612). */
  function rate(v) { return decimals(v, Math.abs(v) < 1 ? 4 : 2); }

  /* The ADR ratio, ordinary shares per ADS: a number of shares, to four decimals at most (5,
     1.5, 0.3333). */
  function shares(v) {
    return minus(Number(v).toLocaleString('en-US', { maximumFractionDigits: 4 }));
  }

  /* A ratio of sales to capital, to two decimals with x: 1.38x; an em dash for none. */
  function times(v) { return v == null ? '—' : decimals(v, 2) + 'x'; }

  /* By unit: a price to cents, a total to whole units, a ratio to one decimal of a percent. A
     price and a total share the unit USD; a price is under a million. On a row in another
     currency a money input's unit is the code, SEK or SEK a share (spec 2026-11-10 7.4), and it
     reads with the code; the rate, `<code> per USD`, reads as a rate; the ADR ratio, ordinary
     shares per ADS, as a number of shares, though its unit is `ratio`. */
  var CODE = /^[A-Z]{3}$/;
  var CODE_A_SHARE = /^([A-Z]{3}) a share$/;
  var PER_USD = / per USD$/;

  function inputValue(i) {
    var unit = i.unit || '';
    var share = CODE_A_SHARE.exec(unit);
    if (i.value == null) return '—';
    if (i.name === 'adr_ratio') return shares(i.value);
    if (PER_USD.test(unit)) return rate(i.value);
    if (share) return money(i.value, share[1]);
    if (CODE.test(unit)) {
      return Math.abs(i.value) < 1e6 ? money(i.value, unit) : dollars(i.value, unit);
    }
    if (unit === 'ratio') return F.formatPercent(i.value);
    return plain(i.value);
  }

  /* What a company's figures are in (spec 2026-11-10 6.2, 7.4 and 10), the line under the head of
     the drawer and of the report page and at the head of Details' inputs, from the company read:
     the reporting currency, the ordinary shares an ADS stands for, and the rate its value was
     translated at, "Reports in TWD; one ADS is five ordinary shares; valued at TWD 32.96 per
     USD". The report page (`perAds`) adds that every figure a share is per ADS. A company in USD
     that is no ADR, and has no ratio on file, has none: ''. */
  function currencyLine(body, perAds) {
    var code = body.currency || 'USD';
    var listed = !!body.isAdr || body.adrRatio != null;
    if (!foreign(code) && !listed) return '';
    var parts = ['Reports in ' + code];
    if (listed) {
      parts.push(adsWords(body.adrRatio));
      if (perAds) parts.push('every per-share figure here is per ADS');
    }
    if (foreign(code) && body.fxRate != null) {
      parts.push('valued at ' + code + ' ' + rate(body.fxRate) + ' per USD');
    }
    return parts.join('; ');
  }

  /* The ordinary shares an ADS stands for, by the ADR ratio: "one ADS is five ordinary shares",
     "three ADSs are one ordinary share" for a ratio of a third; a ratio within 1% of a whole
     number reads as that number, in words up to ten. */
  var NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
    'nine', 'ten'];

  function adsWords(ratio) {
    if (ratio == null) return 'the ADR ratio is not on file';
    if (ratio < 1 && nearWhole(1 / ratio)) {
      return counted(Math.round(1 / ratio)) + ' ADSs are one ordinary share';
    }
    var n = nearWhole(ratio) ? Math.round(ratio) : ratio;
    return 'one ADS is ' + counted(n) + ' ordinary share' + (n === 1 ? '' : 's');
  }

  function nearWhole(x) { return Math.abs(x - Math.round(x)) <= 0.01 * x; }

  function counted(n) {
    return Number.isInteger(n) && n <= 10 ? NUMBER_WORDS[n] : shares(n);
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
     changes, the drawdown, the path steps, the growth rates, the growth share, the charge's
     revenue steps as read and as found). A dollar amount or a count whose key happens to end the
     same way (value_by_roic, stable_growth, roic's years) does not. A map keyed by runway years
     or by ROIC values takes its own key's reading, and so does a bare value (runway_return's).
     The inflation differential is a fraction too. */
  var PERCENT = /(_growth|_yield|_return|margin|roic|belief)$/;
  var ALSO_PERCENT =
    /^(implied_|change_|drawdown|path_steps$|growth_rates$|growth_share$|inflation_differential$)/;
  var REVENUE_STEPS = /^revenue_steps(_found)?$/;  /* spec 2026-11-14 6.3 */
  var NOT_PERCENT = /^(value_|stable_growth|years?$)/;
  /* Counts and years read whole, the committed shares too. P/E multiples to one decimal with x. A
     figure a share (EPV, the value, the value in the reporting currency, EPS, the non-recurring
     gap, the one-time item in the NTM consensus, the 52-week prices, the value maps by runway and
     by ROIC, whatever the entry's key) reads to cents; a total (NOPAT, invested capital, net
     income, earnings, the trailing stock pay and the minority interest, nil or not, anything at a
     million or more) to whole units. The rate reads as a rate. Any other number to two
     decimals. */
  var COUNT = /^(years?|base_year|runway|fade_years|analysts|shares|shares_committed)$/;
  var MULTIPLE = /^pe_/;
  var PER_SHARE =
    /^(epv|value_per_share|value_in_currency|stable_growth|nri_gap|ntm_eps.*|.*_per_share|.*_52w)$/;
  var ONE_TIME = /^ntm_nri$/;  /* spec 2026-11-14 5 */
  var PER_SHARE_GROUP = /^(eps$|value_by_)/;
  var TOTAL = /(_total|nopat|average_capital|net_income|sbc_ttm|minority_interest)$|^e_/;
  /* The NTM anchor's correction by the annual consensus (spec 2026-11-13 9a): the fiscal year
     whole and the window's share of its periods plain; the sum of the window's periods, the
     year's annual EPS, the sum of its periods and the correction a share. */
  var ANCHOR_PLAIN = /^(fiscal_year|share)$/;
  var ANCHOR_PER_SHARE = /^(periods_sum|eps|year_sum|correction)$/;
  /* On a row in another currency every money figure is in it (spec 2026-11-10 7.2) but the price
     facts, read from the USD closes, and the peers' market caps, which rank the peers. */
  var USD_GROUPS = /^(price_facts|peers)$/;

  /* A number by its key, a money figure in `code`, the row's reporting currency. */
  function figure(v, key, group, code) {
    var own = USD_GROUPS.test(group || '') ? null : code;
    if (key === 'fx_rate') return rate(v);
    if (isPercent(key, group)) return F.formatPercent(v);
    if (PER_SHARE_GROUP.test(group || '')) return money(v, own);  /* value_by_roic's runway */
    if (ANCHOR_PLAIN.test(key)) return plain(v);
    if (ANCHOR_PER_SHARE.test(key)) return money(v, own);
    if (COUNT.test(key)) return plain(v);
    if (MULTIPLE.test(key)) return decimals(v, 1) + 'x';
    if (PER_SHARE.test(key) || ONE_TIME.test(key)) return money(v, own);
    if (TOTAL.test(key) || Math.abs(v) >= 1e6) return dollars(v, own);
    return decimals(v, 2);
  }

  function isPercent(key, group) {
    if (NOT_PERCENT.test(key)) return false;
    if (PERCENT.test(key) || ALSO_PERCENT.test(key) || REVENUE_STEPS.test(key)) return true;
    return !!group && !NOT_PERCENT.test(group) && (PERCENT.test(group) || ALSO_PERCENT.test(group));
  }

  function isTable(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }

  /* One value as text: null an em dash, a number by its key, a list inline (a list of tables one
     table a line, its year first), a deeper table inline; a money figure in `code`. */
  function shown(v, key, group, code) {
    if (v == null) return '—';
    if (typeof v === 'number') return figure(v, key, group, code);
    if (Array.isArray(v)) {
      if (!v.some(isTable)) {
        return v.map(function (x) { return shown(x, key, group, code); }).join(', ');
      }
      return v.map(function (x, n) {
        return h('span', { key: n, className: 'app-line' }, shown(x, key, group, code));
      });
    }
    if (isTable(v)) {
      return Object.keys(v).sort(function (a, b) { return (b === 'year') - (a === 'year'); })
        .map(function (k) { return k + ' ' + shown(v[k], k, key, code); }).join(' · ');
    }
    return String(v);
  }

  /* One group per top-level key: a table's entries, with a nested table flattened one level, an
     empty table left out (a margin record with no year). EPV below zero capitalises a trailing
     loss, which also puts the growth share above 100%; its line says so, so the reader is not
     misled. The money figures are in the row's currency, its `currency`, USD on a row that names
     none. A nested table reads by its own key, except the margin record's (`margin_history`'s
     `operating` and `net`), which reads as a margin: its medians percentages, its years whole. */
  function intermediates(im) {
    var code = im.currency;
    return Object.keys(im).map(function (key) {
      var v = im[key];
      var rows = [];
      if (isTable(v) && !Object.keys(v).length) return null;
      if (key === 'epv' && v < 0) {
        rows.push([key, noted(shown(v, key, null, code), 'negative: trailing earnings are a loss'),
          true]);
      } else if (!isTable(v)) {
        rows.push([key, shown(v, key, null, code), true]);
      } else {
        Object.keys(v).forEach(function (k) {
          if (!isTable(v[k])) return rows.push([k, shown(v[k], k, key, code), true]);
          var group = key === 'margin_history' ? 'margin' : k;
          Object.keys(v[k]).forEach(function (kk) {
            rows.push([k + '.' + kk, shown(v[k][kk], kk, group, code), true]);
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
