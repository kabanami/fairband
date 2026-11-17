/* The screen page: fetches /api/screen and renders the design system's ScreenTable, and beside it
   the detail drawer of the row the reader opens (spec 6.4), fetched from /api/companies/{symbol}.
   No JSX and no build step: React.createElement against window.Fairband. The server sorts and the
   engine computes; this script asks for an order, remembers the chosen columns in the reader's
   order, narrows the loaded rows to the reader's find and filters and lays out what the engine
   produced, rounded for display only. Each row's watchlist mark opens a popup that puts the
   company on the reader's lists, from /api/watchlists (spec 2026-11-04 9.4); its ticker is a link
   to the company's page, and the rest of the row opens the drawer (the company page's design,
   12). The drawer is a short card under its bar, the company, its value and two buttons: Company
   page, which opens the company's page, and Request research, which posts a research request to
   the work inbox (the company page's design, 11; spec 2026-11-06 Tier 2, 18.2). Where launching
   is set up, a request also opens the window where Claude Code starts, and the line under the
   button follows its launch (spec 2026-11-16 agent launch, 10). At the bar's left, Notes opens a
   box of the company's notes, from /api/companies/{symbol}/notes, which takes a new one (the
   company page's design, 11.1); the company page's head draws it too. The header, the status
   line and the group view are controls.js, loaded after this script; it reaches the screen
   through window.FairbandPage. */
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
  /* A work item's two modes, as the inbox takes them (spec 2026-11-06 Tier 2, 8). */
  var REQUEST_MODES = ['valuation review', 'full report'];
  /* A work item's open states: work not yet done, which the header's Inbox count counts and the
     owner may decline (spec 2026-11-06 Tier 2, 8 and 18.5). */
  var OPEN_STATES = ['pending', 'claimed'];

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
    request: null, /* Request research of one company: { symbol, open, mode, note, error, … } */
    notes: null, /* { symbol, anchor, after, notes, loading, error } while a Notes box is open */
    noteDraft: null /* Add a note's draft, of one company: { symbol, text, error, posting } */
  };
  var latest = 0;
  var latestDetail = 0;

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
     where it is handed one (the company page's Watchlists ▾); closePopups, which closes the popup
     and the Notes box as controls.js shows a view; companyHref, the address a ticker links to,
     which a watchlist's table hands ScreenTable as the screen's does (the company page's design,
     12); researchHref, the address of a report, on the company page's Research tab (the Research
     tab's design, 7.1); the loaded rows (null until they load), the chosen columns, openRow,
     which opens a row's drawer, reloadDetail, which reads the drawer's company again after
     another view's write about it (the Inbox view's decline and a watchlist's Request research,
     spec 2026-11-06 Tier 2, 18.5 and 18.6), and reloadDrawer, which reads whichever company the
     drawer shows again when a run ends. controls.js adds show, onShow, section, openReport,
     running and countInbox, the Inbox view onInbox, and agents.js adds agents, the Settings
     view's Agents section; a view drawn from the rows or the lists sets onRender, which runs
     after each draw of the screen, so it draws again as they load and change (the company page's
     runs the Watchlists view's, set before it, then its own). A report's parts after its sections
     (report_parts.js, 18.4) draw with this script's parts: the inputs table, a table of figures
     by year, an input's figure in its unit, the secondary valuation's rows and path, the guidance
     table, the phase evidence, pairs, a date, a total in a currency, an exchange rate and a
     count; the line that says what the figures are in (currencyLine) is the drawer's. The company
     page (company.js; the company page's design, 7) draws its head with the logo, the phase
     numbers, the moat stamp (moatStamp), the Notes control as the drawer's bar draws it
     (notesControl, 11.1) and Request research with a request of its own (asking), whose
     following of a launch the page stops as it starts to read another company (stopLaunch) and
     starts as its read lands (followItem), opens the watchlists popup under its head's button
     (watch) on the company's row or, the lists loaded, on the company alone (rows, watchlists),
     and says when it turns to another company (notesShown), so a note drafted on another goes;
     its Fairband value block (company_overview.js, 8.2) draws the meter, the four levels under it
     in the screen's words (levelRows), the basis chip of the band they draw (bandBasis) and the
     local day of its report (localIso); its Research tab (company_research.js, the Research tab's
     design) numbers a report's cites by its references (footnotes), its value card (7.5) writes
     the meter's gap as every meter does (gapText), and its Records (company_research_records.js,
     7.10) a guidance record's figures and a store word as the guidance table writes them
     (guided, words). The Inbox view's row (inbox.js, B-210) keeps
     a request for each pending item too, posts its launch (openLaunch) and draws the line's
     words (launchWords) from the item the line is drawn from (lineItem). The header's finder
     (finder.js) finds the rows the Screen's field finds (finds). The drawer with its bar
     (drawer), its parts (sections), the Notes box (notesBox), the open item's line (launchLine),
     an input's value (inputValue), a figure a share in a currency (money) and a logo's ground
     (logoGround) are here for the tests, which read them in node (tests/web/page.mjs). */
  window.FairbandPage = {
    reload: load, api: api, refusal: refusal, refusalDetail: refusalDetail, getJson: getJson,
    localIso: localIso, following: following,
    PHASE_NUMBER: PHASE_NUMBER, OPEN_STATES: OPEN_STATES,
    find: find, finds: finds,
    watchlists: function () { return state.watchlists; },
    reloadWatchlists: reloadWatchlists,
    watch: watch, closePopups: closePopups,
    companyHref: companyHref, researchHref: researchHref,
    rows: function () { return state.rows; },
    columns: function () { return state.columns; },
    openRow: openRow, reloadDetail: reloadDetail, reloadDrawer: reloadDrawer,
    meter: meter, gapText: gapText, levelRows: levelRows, bandBasis: bandBasis,
    inputsTable: inputsTable, figuresTable: figuresTable, inputFigure: inputFigure,
    inputValue: inputValue,
    secondaryRows: secondaryRows, secondaryPath: secondaryPath, guidanceTable: guidanceTable,
    guided: guided, words: words,
    phaseEvidence: phaseEvidence, pairs: pairs, when: when, whole: whole, money: money,
    rate: rate, plain: plain,
    footnotes: footnotes, asking: asking, requestResearch: requestResearch,
    launchLine: launchLine, launchWords: launchWords, lineItem: lineItem,
    openLaunch: openLaunch, stopLaunch: stopLaunch, followItem: followItem,
    currencyLine: currencyLine, logo: logo, logoGround: logoGround, moatStamp: moatStamp,
    notesControl: notesControl, notesBox: notesBox, notesShown: notesShown,
    drawer: drawer, sections: sections
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
     (the local-offset ISO in datetime), and its report's time likewise, so the coverage mark's
     title gives the local date; watched when the company is on a list, which fills its mark. */
  function localRow(r) {
    var row = Object.assign({}, r, { watched: (r.watchlists || []).length > 0 });
    if (r.covered) row.covered = Object.assign({}, r.covered, { at: localIso(r.covered.at) });
    return r.enteredAt ? Object.assign(row, { enteredAt: localIso(r.enteredAt) }) : row;
  }

  /* The address a row's ticker links to in the screen's table and in a watchlist's
     (ScreenTable's companyHref): the company's page, the symbol encoded as the drawer's Company
     page encodes it (spec 2026-11-16 company page, 12). */
  function companyHref(row) {
    return '#company/' + encodeURIComponent(row.ticker);
  }

  /* The address of a report (the Research tab's design, 7.1): the company page's Research tab on
     the report `id`, the symbol encoded as companyHref encodes it, #company/AAPL/research/12, or
     #company/AAPL/research, the company's latest report, where no id is given. The Inbox view's
     link to an item's report, the Overview's link to the latest and the tab's reports on file
     name it; it is here, in the first script, so each of them finds it whatever its own place. */
  function researchHref(symbol, id) {
    return '#company/' + encodeURIComponent(symbol) + '/research' + (id == null ? '' : '/' + id);
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
     faded, until the new one lands. */
  function open(row) {
    var d = state.drawer;
    if (d && d.symbol === row.ticker && !d.error) return;
    /* the company the drawer showed no longer follows its launch (spec 2026-11-16 agent launch,
       10), whether the new one's read lands or fails, and the drawer turning to another company
       drops a note drafted on another (notesShown) */
    if (state.request && state.request.symbol !== row.ticker) stopLaunch(state.request);
    if (!d || d.symbol !== row.ticker) notesShown(row.ticker);
    var request = ++latestDetail;
    state.drawer = { symbol: row.ticker, body: d && d.body, loading: true, error: null };
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

  /* Whether a text, trimmed and in lower case, finds a row: its ticker starts with the text, or
     its name holds it. The Screen's field and the header's finder (finder.js) share it. */
  function finds(r, needle) {
    return r.ticker.toLowerCase().indexOf(needle) === 0 ||
      (r.name || '').toLowerCase().indexOf(needle) !== -1;
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
      var found = !needle || finds(r, needle);
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

  /* onWatch: a mark opens its popup, closing a Notes box, or closes it when the popup is its own.
     The popup opens under `mark` where one is given, the company page's Watchlists ▾ (the company
     page's design, 7.2), else under the mark the click landed on. */
  function watch(row, mark) {
    var anchor = mark || pressedMark;
    if (!anchor || (state.watch && state.watch.anchor === anchor)) {
      closeWatch();
      return;
    }
    closeNotes();
    state.watch = {
      symbol: row.ticker, anchor: anchor, ids: membersOf(row.ticker, row), name: '', error: null
    };
    renderWatch();
  }

  function closeWatch() {
    state.watch = null;
    renderWatch();
  }

  /* A view is shown (controls.js, show): the watchlist popup and the Notes box close, so neither
     stays drawn over a view the browser's Back or Forward, or a link, opened with no press. */
  function closePopups() {
    if (state.watch) closeWatch();
    if (state.notes) closeNotes();
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
     the mark sits low in the window (place); it follows the mark as the page scrolls and closes
     when the mark is gone (its row narrowed away) or hidden. It stands at the end of the page,
     away from the mark, so focus moves into it as it opens. */
  function WatchMenu(props) {
    var w = props.watch;
    var ref = React.useRef(null);
    React.useLayoutEffect(function () {
      if (!w.anchor.getClientRects().length) { /* gone, or its view hidden */
        closeWatch();
        return;
      }
      place(ref.current, w.anchor);
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

  /* A popup fixed under its control, `anchor`, or over it when the control sits low in the
     window, from the control's left edge and inside the window: the watchlist popup and the
     Notes box. */
  function place(menu, anchor) {
    var rect = anchor.getBoundingClientRect();
    var style = menu.style;
    var below = rect.bottom < window.innerHeight * 0.6;
    style.left = Math.max(0, Math.min(rect.left, window.innerWidth - menu.offsetWidth)) + 'px';
    style.top = below ? rect.bottom + 4 + 'px' : 'auto';
    style.bottom = below ? 'auto' : window.innerHeight - rect.top + 4 + 'px';
  }

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
        companyHref: companyHref,
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
    renderNotes();
    var page = window.FairbandPage;
    if (page.onRender) page.onRender();
  }

  /* ------------------------------------------------------------------ the drawer */

  /* The drawer of `d`, { symbol, body, loading, error }. Its bar: Notes for the drawer's company at
     its left (notesControl, the company page's design, 11.1), with the count of its notes while
     the drawer holds its detail and none while the drawer turns to it or its read failed, a note
     taken reading the detail again (reread); Close at its right. Under the bar the company's
     parts (sections), a failed read's sentence, or the ticker alone while the first read is
     out. */
  function drawer(d) {
    var content;
    if (d.error) content = note(d.error);
    else if (d.body) content = sections(d.body);
    else content = h('h2', { className: 'ticker app-drawer__ticker' }, d.symbol);
    return h('aside', { className: 'app-drawer', 'aria-label': 'Detail for ' + d.symbol },
      h('div', { className: 'app-drawer__bar' },
        notesControl(d.symbol, d.body && !d.loading ? d.body.noteCount : null,
          reread(d.symbol)),
        h(F.Button, { variant: 'quiet', size: 'sm', onClick: close }, 'Close')),
      h('div', { className: d.loading ? 'app-drawer__body is-loading' : 'app-drawer__body' },
        content));
  }

  /* The drawer under its bar, form A (the company page's design, 11), in this order and nothing
     else: the head, the logo, the ticker, the phase badge, the moat stamp (moatStamp), the name
     and, for a company in another currency or an ADR, the line that says what its figures are in
     (currencyLine, spec 2026-11-10 7.4); one caption, the sector and the industry (sectorLine);
     the company brief whole, which the page's style cuts at six lines; the value band, the meter
     and under it the four levels in the screen's words (levelRows), or where the meter draws no
     band a refused row's sentence in its place; then Company page, a link to the company page,
     and Request research with its menu, the server's refusal under it and the open item's line.
     The rest of what a company has is on its page. */
  function sections(body) {
    var r = body.result;
    var phase = PHASE_NUMBER[r.phase.phase];
    var sector = sectorLine(body.company);
    var rows = levelRows(body);
    var ask = asked(r.symbol);
    return [
      h('header', { key: 'head', className: 'app-drawer__head' },
        logo(body, 'app-drawer__logo'),
        h('h2', { className: 'ticker app-drawer__ticker' }, r.symbol),
        phase ? h(F.PhaseBadge, { phase: phase, size: 'sm' }) : null,
        moatStamp(body),
        body.company && body.company.name
          ? h('p', { className: 'body app-drawer__name' }, body.company.name) : null,
        currencyLine(body) ? h('p', { className: 'caption app-muted app-drawer__currency' },
          currencyLine(body)) : null),
      sector ? h('p', { key: 'sector', className: 'caption app-muted app-drawer__sector' }, sector)
        : null,
      body.brief ? h('p', { key: 'brief', className: 'body app-drawer__brief' }, body.brief)
        : null,
      rows ? h('section', { key: 'band', className: 'app-drawer__band' }, meter(body),
        pairs(rows.map(function (row) { return [row[0], row[1], true]; })))
        : r.refusal ? h('section', { key: 'band', className: 'app-drawer__band' },
          h('p', { className: 'body app-refusal' }, r.refusal)) : null,
      h('div', { key: 'actions', className: 'app-drawer__actions' },
        h(F.Button, { variant: 'primary', href: '#company/' + encodeURIComponent(r.symbol) },
          'Company page'),
        requestResearch(ask, body.item, render, reread(r.symbol), body.launchReady))
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
     meter draws (meter). The review's where it counts and has a value, on a valued row (spec
     2026-11-06 Tier 2, 18.1 and 18.2, plan 3) or a refused one; else a valued row's own, the
     snapshot's; else a refused row's secondary valuation's; null where the meter draws no band.
     The engine's own levels stay on the snapshot and in the report's Appendix A. */
  function levelRows(body) {
    var r = body.result;
    var v = body.review;
    var s = body.secondary;
    var band = isReviewed(body) || isReviewBanded(body)
      ? Object.assign({ value: v.value }, v.levels)
      : isValued(r) ? {
        value: r.value, buy: r.levels.buy, fairLow: r.levels.fair_low,
        fairHigh: r.levels.fair_high, trim: r.levels.trim
      } : isBanded(body) ? Object.assign({ value: s.valuePerShare }, s.levels) : null;
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

  /* A report's references, [{ n, ref, source }], as ReportReader's footnotes, ref → n (spec 13.1):
     the report page numbers a cite by the full report's list. */
  function footnotes(references) {
    var marks = {};
    (references || []).forEach(function (e) { marks[e.ref] = e.n; });
    return marks;
  }

  /* ----------------------------------------------------------- the drawer's requests */

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

  /* The company the drawer shows read again in place when a run ends (controls.js), since a run
     may follow its review, post its expiry item or drop an override (method 14.6). */
  function reloadDrawer() {
    var d = state.drawer;
    if (!d) return;
    reloadDetail(d.symbol);
  }

  /* ------------------------------------------------------------------- the notes */

  /* Notes (the company page's design, 11.1). The box has a root of its own at the end of the page,
     as the watchlist popup has, so it opens over the drawer and over the company page's head. */
  var notesMount = document.body.appendChild(document.createElement('div'));
  var notesRoot = ReactDOM.createRoot(notesMount);
  var latestNotes = 0;

  /* The Notes control of a company, `symbol`, in the quiet button's look: the word Notes, followed
     by `count`, the company's notes, when it has one or more (Notes 3). The drawer's bar draws it
     at its left and the company page's head before Watchlists ▾. A click opens the box under it
     (openNotes); `after` reads the view's company again once a note is taken, so the count
     follows. */
  function notesControl(symbol, count, after) {
    return h(F.Button, {
      variant: 'quiet', size: 'sm', className: 'app-notes-open',
      onClick: function (event) { openNotes(symbol, event.currentTarget, after); }
    }, count ? 'Notes ' + count : 'Notes');
  }

  /* A Notes control's click: the box opens under the control, `anchor`, with the company's draft
     (drafted), and reads the company's notes; the watchlist popup closes, so one box stands at a
     time. A click on the control whose box is open closes it. */
  function openNotes(symbol, anchor, after) {
    if (state.notes && state.notes.anchor === anchor) {
      closeNotes();
      return;
    }
    closeWatch();
    drafted(symbol);
    state.notes = {
      symbol: symbol, anchor: anchor, after: after, notes: null, loading: true, error: null
    };
    readNotes();
  }

  function closeNotes() {
    latestNotes++;
    state.notes = null;
    renderNotes();
  }

  /* The open box's notes, read: newest first, as the read gives them (store.research,
     notes_for). While the read is out the box shows what it holds, faded; a failed read's message
     takes the list's place. A read that lands after the box closed, or after a later read began,
     is dropped. */
  function readNotes() {
    var box = state.notes;
    var request = ++latestNotes;
    box.loading = true;
    renderNotes();
    getJson('/api/companies/' + encodeURIComponent(box.symbol) + '/notes')
      .then(function (body) {
        if (request !== latestNotes) return;
        box.notes = body.notes;
        box.error = null;
        box.loading = false;
        renderNotes();
      }, function (err) {
        if (request !== latestNotes) return;
        box.error = err.message;
        box.loading = false;
        renderNotes();
      });
  }

  function renderNotes() {
    notesRoot.render(state.notes ? h(NotesBox, { box: state.notes }) : null);
  }

  /* The box, fixed under its control as the watchlist popup is (place), or over it when the
     control sits low in the window; it follows the control as the page scrolls and closes when
     the control is gone (the drawer closed) or hidden (its view left). Focus moves into its field
     as it opens. */
  function NotesBox(props) {
    var box = props.box;
    var ref = React.useRef(null);
    React.useLayoutEffect(function () {
      if (!box.anchor.getClientRects().length) { /* gone, or its view hidden */
        closeNotes();
        return;
      }
      place(ref.current, box.anchor);
    });
    React.useEffect(function () {
      ref.current.querySelector('textarea').focus();
    }, [box.anchor]);
    return notesBox(Object.assign({}, box, { draft: drafted(box.symbol) }), ref);
  }

  /* The Notes box of `box`, { symbol, notes, loading, error, draft }, in the bundle's menu style as
     the watchlist popup draws it. Its list: the company's notes in their order, newest first,
     each its text as written and under it its principal chip, with its principal, its actor and
     its time in the reader's offset, which the chip draws as the day; No notes yet. where the
     read holds none, and nothing before the first read lands; while a read is out what the box
     holds, faded; a failed read's sentence in the list's place. The list scrolls under 240px.
     Under it Add a note as Details had it: the field, named for the company, holding the draft,
     Add a note, disabled for an empty draft and while the note is posted (postNote), then the
     server's sentence on a refusal, the text kept. `ref` is the box's own (NotesBox). */
  function notesBox(box, ref) {
    var draft = box.draft;
    var named = 'A note on ' + box.symbol;
    var listed = null;
    if (box.error) {
      listed = h('p', { className: 'caption app-notes-box__failed' },
        'The notes did not load: ' + box.error + '. Open Notes again to retry.');
    } else if (box.notes && box.notes.length) {
      listed = h('ul', { className: 'app-list app-notes-box__list' }, box.notes.map(function (n) {
        return h('li', { key: n.id },
          h('p', { className: 'body app-notes-box__text' }, n.text),
          h('div', { className: 'app-notes-box__chip' },
            h(F.PrincipalChip, { principal: n.principal, actor: n.actor, at: localIso(n.at) })));
      }));
    } else if (box.notes) {
      listed = h('p', { className: 'body app-muted app-notes-box__none' }, 'No notes yet.');
    }
    return h('div', {
      ref: ref, className: 'fb-menu fb-menu--filters app-notes-box', role: 'group',
      'aria-label': 'Notes'
    },
      h('div', {
        className: 'fb-menu__body app-notes-box__body' + (box.loading ? ' is-loading' : '')
      }, listed),
      h('div', { className: 'fb-menu__foot' },
        h('form', {
          className: 'app-notes-box__new',
          onSubmit: function (event) { event.preventDefault(); postNote(box.symbol); }
        },
          h('textarea', {
            className: 'control app-field app-notes-box__field', rows: 3, value: draft.text,
            placeholder: named, 'aria-label': named,
            onChange: function (event) { draft.text = event.target.value; renderNotes(); }
          }),
          h(F.Button, {
            type: 'submit', size: 'sm', disabled: draft.posting || !draft.text.trim()
          }, 'Add a note')),
        draft.error ? h('p', { className: 'caption app-notes-box__error' }, draft.error) : null));
  }

  /* The box closes on a press or focus outside it and its control, and on Escape, which hands
     focus back to the control, as the watchlist popup does; the drawer's own Escape sees the box,
     a menu, and waits. It follows its control when anything scrolls and when the window
     resizes. */
  function closeNotesOutside(event) {
    var box = state.notes;
    if (!box || !(event.target instanceof Node)) return;
    if (notesMount.contains(event.target) || box.anchor.contains(event.target)) return;
    closeNotes();
  }
  document.addEventListener('pointerdown', closeNotesOutside);
  document.addEventListener('focusin', closeNotesOutside);
  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape' || !state.notes) return;
    var anchor = state.notes.anchor;
    closeNotes();
    if (anchor.isConnected) anchor.focus();
  });
  document.addEventListener('scroll', function () { if (state.notes) renderNotes(); }, true);
  window.addEventListener('resize', function () { if (state.notes) renderNotes(); });

  /* Add a note's draft of a company, `symbol`: kept as its box closes, until the drawer or the
     company page turns to another company (notesShown) or a box opens on another. */
  function drafted(symbol) {
    if (!state.noteDraft || state.noteDraft.symbol !== symbol) {
      state.noteDraft = { symbol: symbol, text: '', error: null, posting: false };
    }
    return state.noteDraft;
  }

  /* A view turns to a company, `symbol`: the drawer as it opens another (open), the company page
     as it is asked for another (company.js). A note drafted on another company goes, and so does
     a box open on another. */
  function notesShown(symbol) {
    if (state.noteDraft && state.noteDraft.symbol !== symbol) state.noteDraft = null;
    if (state.notes && state.notes.symbol !== symbol) closeNotes();
  }

  /* Add a note, from the open box: the note, as the owner, with the request header every page
     write carries; a refusal shows the server's sentence under the field (refusalDetail), the
     text kept. Taken, the field clears, a box still open on the company reads its notes again,
     so the new one is first, and the box's `after` reads the view's company again, so its
     control's count follows: the drawer's detail (reloadDetail) or the company page's own
     read; a control made without one reads nothing more. */
  function postNote(symbol) {
    var box = state.notes;
    var draft = drafted(symbol);
    var text = draft.text.trim();
    if (!text || draft.posting) return;
    draft.posting = true;
    draft.error = null;
    renderNotes();
    api.post('/api/companies/' + encodeURIComponent(symbol) + '/notes', { text: text })
      .then(function (r) {
        if (!r.ok) throw new Error(refusalDetail(r));
        draft.text = '';
        if (state.notes && state.notes.symbol === symbol) readNotes();
        if (box.after) box.after();
      })
      .catch(function (err) { draft.error = err.message; })
      .then(function () {
        draft.posting = false;
        renderNotes();
      });
  }

  /* --------------------------------------------- the parts the report page draws too */

  /* An override's or a bridge line's value in its input's unit (overrides.TAGS): a word as it
     is, a multiple to two decimals with x, any other figure as the inputs table reads its unit. */
  function inputFigure(v, unit) {
    if (typeof v === 'string') return v;
    return unit === 'multiple' ? times(v) : inputValue({ value: v, unit: unit });
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
     which the report page reads from Appendix A, whose record naming none is in the report's
     snapshot's currency. */
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

  /* A store word in a reader's words: target_margin is target margin. */
  function words(name) { return String(name).replace(/_/g, ' '); }

  /* The band meter's gap text, beside the word's chip in its head (spec 2026-11-06 Tier 2, 18.2
     item 2, plan 4): price ÷ value over the value's name `of` in one form, "0.82 × the reviewed
     value"; '' where there is no ratio (a row valued before the designation), which draws none. */
  function gapText(ratio, edges, of) {
    return ratio == null ? '' : ratioFigure(ratio, edges) + ' × ' + of;
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

  /* [label, value, numeric] rows as a two-column list; numbers in mono, words in sans. */
  function pairs(rows) {
    return h('dl', { className: 'app-pairs' }, rows.map(function (row) {
      return h(React.Fragment, { key: row[0] },
        h('dt', { className: 'caption' }, row[0]),
        h('dd', { className: row[2] ? 'figure-sm' : 'body' }, row[1]));
    }));
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

  /* A result's classifier evidence, a row a reading, for the report page's Appendix A
     (18.4). */
  function phaseEvidence(p) {
    return pairs(evidence(p, PHASE_NUMBER[p.phase]));
  }

  /* -------------------------------------------------------------------- the head */

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

  /* The drawer's caption under its head (the company page's design, 11): the universe row's
     sector and industry, joined by a middle dot; the parts it has, '' without either. */
  function sectorLine(company) {
    return [company && company.sector, company && company.industry]
      .filter(function (part) { return !!part; }).join(' · ');
  }

  /* -------------------------------------------------------- a table of figures by year */

  /* A row a year from year 1, a column for each [head, the figures by year, their format]. Wider
     than its column, the table scrolls on its own, by keyboard too: its box takes focus. */
  function figuresTable(columns) {
    return h('div', { className: 'app-scroll', tabIndex: 0 },
      h('table', { className: 'fb-table app-figures' },
        h('thead', null, h('tr', null,
          h('th', { className: 'label fb-num' }, 'Year'),
          columns.map(function (c) {
            return h('th', { key: c[0], className: 'label fb-num' }, c[0]);
          }))),
        h('tbody', null, columns[0][1].map(function (_, t) {
          return h('tr', { key: t },
            h('td', { className: 'fb-num figure-sm' }, plain(t + 1)),
            columns.map(function (c) {
              return h('td', { key: c[0], className: 'fb-num figure-sm' }, c[2](c[1][t]));
            }));
        }))));
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
     the drawer and of the report page, from the company read:
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

  /* Each input on one row, its nine fields stacked so they fit a narrow column: the name, tag,
     kind and source, then the three dates in caption, and the value with its unit on the right. */
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

  render();
  load();
  reloadWatchlists();
})();
