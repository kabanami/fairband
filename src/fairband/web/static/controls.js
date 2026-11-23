/* The page's header, its status line and the Statistics view, loaded after app.js and finder.js.
   The header is the design system's AppHeader: the six views in the founder's order (Screen,
   Watchlists, Statistics, Methodology, Settings, Inbox; spec 2026-11-23 refresh experience, 4.6),
   then in its right slot the finder (finder.js) on every view but the Screen, the refresh
   controls and the engine stamp; the URL hash names the open view, and on the Watchlists view
   its list, whose table is the Screen's, shown under the list's head (spec 2026-11-22 7.3).
   Inbox carries the count of the open work items, read every thirty seconds while the page is
   shown (spec 2026-11-06 Tier 2, 18.5). Under the header, the status
   line: the running refresh's one run bar (the design system's RunProgress), or how the last one
   ended in one line, its calibration's breakdown behind Details ▾ (growth-routes spec 6.1); the
   company page draws the run bar and a notice alone, not the last refresh's line or Details ▾
   (the company page's design, the decision log of 2026-11-17). The page asks
   /api/refresh/current every 30 seconds while no refresh runs and every 2 seconds while one does,
   never while the page is hidden (spec 2026-11-23 refresh experience, 4.3). While a refresh runs,
   one Cancel stands where the Refresh buttons were and the stamp is gone; under a run of the
   whole screen the tables keep their old figures at ink-faint, and under a run of named companies
   nothing fades (4.1). A run of the whole screen, whoever started it, also locks the page under
   the refresh layer, its run bar and Cancel in a panel over a dark scrim: nothing under it
   answers, a change of the address is put back and Escape does nothing, until the run ends or,
   on a long run, the reader keeps reading (4.1). When any run ends, whoever started it, the rows
   load again, with the open drawer, the statistics when that view is open and the company page
   when the run covered its company; the figures the run changed are marked as they land, and
   after a run of the whole screen that ended done the status line counts them (4.2). The
   Statistics view, once named Groups, is one plain table from /api/statistics (spec 6.3; spec
   2026-11-23 refresh experience, 4.5), with no chart, each group's name a link that opens the
   Screen on the group; #statistics names it, and the old #groups opens it. The company
   page (company.js) is a
   panel no header view names: #company/<symbol> opens its Overview, #company/<symbol>/financials
   its Financials tab, #company/<symbol>/estimates its Estimates tab,
   #company/<symbol>/investor-relations its Investor relations tab, with a call (/2026Q4) or
   /filings after it, #company/<symbol>/research its Research tab on the company's latest report
   and #company/<symbol>/research/<id> on the report with that id (the company page's design,
   7.1; the Financials tab's design, 7.1; the Investor relations tab's design, 7.1; the Research
   tab's design, 7.1). The report page left (the Research tab's design, 9): its
   addresses, #report/<symbol> and #report/<symbol>/<id>, open the Research tab on the same
   report, the hash replaced by the tab's. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var POLL_MS = 2000;
  var IDLE_MS = 30000;
  var INBOX_MS = 30000;
  /* The kinds of a run of the whole screen where it names no company (spec 2026-11-23 refresh
     experience, 4.1), and the newest runs the refresh's state answers while none runs (4.3). */
  var WHOLE_KINDS = ['price', 'full', 'revalue'];
  var RECENT = 20;
  /* The refresh layer's words (4.1): its title by the run's kind, the id that labels the dialog,
     the sentence and what it goes on to say where Keep reading stands; the kinds of a long run,
     on which Keep reading stands, a whole revalue running for minutes as a full refresh does. */
  var LAYER_TITLES = { price: 'Refreshing prices', full: 'Refreshing all', revalue: 'Revaluing' };
  var LAYER_TITLE = 'app-layer-title';
  var LOCKED = 'The page is locked until the refresh ends.';
  var KEEP = ' Keep reading removes the lock; the refresh goes on.';
  var LONG_KINDS = ['full', 'revalue'];
  var OPEN = P.OPEN_STATES;
  var BY = { sector: 'Sector', industry: 'Industry', phase: 'Phase', cap: 'Cap band' };
  var RECOMPUTING = 'is-recomputing';
  var UNCLASSIFIED = 'unclassified'; /* the calibration's name for a company without a phase */
  /* The refusals the refresh writes for a company it failed, by the text they start with. */
  var FAILED_REASONS = ['data fetch failed', 'data fetch incomplete', 'valuation failed'];
  /* The server's stage names as the run bar's lowercase verb phrases (spec 4.3). */
  var STAGE_WORDS = {
    universe: 'reading the universe', deciles: 'ranking', fetch: 'fetching',
    rates: 'fetching exchange rates', backfill: 'reading stored statements', value: 'valuing',
    quotes: 'fetching prices', fx: 'quoting exchange rates', reprice: 'repricing',
    moat: 'reading the moat table', done: 'finishing'
  };

  /* The views in the header's order, each with its panel, a section of the page; then the company
     page's panel, which no header view names: the drawer's Company page and a ticker's link open
     it. */
  var VIEWS = ['screen', 'watchlists', 'statistics', 'methodology', 'settings', 'inbox', 'company'];
  /* The company page's tabs in the row's order, the Overview first: the tab of a hash that names
     none, or one the page does not know. */
  var COMPANY_TABS = ['overview', 'financials', 'estimates', 'investor-relations', 'research'];
  var panels = {};
  VIEWS.forEach(function (id) { panels[id] = document.getElementById(id); });
  var header = ReactDOM.createRoot(document.getElementById('header'));
  var bar = ReactDOM.createRoot(document.getElementById('controls'));
  var groupsRoot = ReactDOM.createRoot(panels.statistics);
  /* The refresh layer's mount, the body's child after main.app-page (index.html). */
  var layerMount = document.getElementById('layer');
  var layer = ReactDOM.createRoot(layerMount);
  var state = {
    tab: 'screen',
    by: 'sector',
    groups: null, groupsLoading: false, groupsError: null,
    running: null, /* the progress, while a refresh runs */
    last: null, /* the last refresh's record */
    notice: null, /* { text, caution }: what the last request came to */
    cancelAsked: false, /* Cancel was accepted: it stays disabled until the run ends */
    detailsOpen: false, /* the last refresh's Details ▾ menu is open */
    open: 0, /* the open work items, pending and claimed: the Inbox view's count */
    seen: null, /* the id of the newest refresh the rows were read under; null before an answer */
    ended: null, /* { id, kind, status }: the newest whole run the last follow took in, or null */
    changes: null, /* { id, kind, prices, values, fresh }: what the last whole run that ended done
                      changed on the rows, as the page counted it (onChanged), fresh for MARK_MS
                      after it was counted; or null */
    kept: null, /* the id of the run the reader kept reading under (Keep reading), or null */
    address: null, /* the address the page held as the last lock began (lockPage), which a change
                      of the address is put back to while the lock holds (fromHash) */
    statusFailed: false /* the last read of the refresh's state failed */
  };
  var shut = false; /* the page was locked at the last draw (lockPage) */
  var locks = 0; /* the locks so far: each draws a panel of its own (layerView) */
  var lastPanel = null; /* the panel the layer last drew, which it keeps as the lock lifts */
  var viewed = false; /* a view has opened (show) */
  var timer = null;
  var inboxTimer = null;
  var freshTimer = null; /* ends the count's freshness (onChanged) */
  var latestPoll = 0;
  var latestInbox = 0;
  var latestGroups = 0;
  var started = false; /* a refresh was started here and its end is not seen yet */

  /* ------------------------------------------------------------------ polling */

  /* The refresh's state (spec 2026-11-23 refresh experience, 4.3), read as the page loads, after
     each request (post), every 2 seconds while a run is alive and every 30 while none is; never
     while the page is hidden, and at once as it shows again. An answer with a run alive draws its
     bar; where it is the page's first answer, the rows were read under the run before, so the
     run's end is followed. An answer with none alive follows the runs that ended (followRuns).
     A read that fails keeps the run it knew, and so the lock, with Keep reading in the layer
     (keeps) until a read answers again (4.1). */
  function poll() {
    clearTimeout(timer);
    if (document.hidden) return;
    var request = ++latestPoll;
    P.getJson('/api/refresh/current')
      .then(function (body) {
        if (request !== latestPoll) return;
        var alive = state.running !== null; /* a run was alive at the answer before */
        state.statusFailed = false;
        if (state.notice && state.notice.fromPoll) state.notice = null; /* it answers again */
        state.running = body.refresh;
        if (body.refresh !== null) {
          state.detailsOpen = false; /* the run bar replaces the line */
          if (state.seen === null) state.seen = body.refresh.id - 1;
        } else {
          /* `shown` is the run the line, Details and the header's stamp describe: the last one,
             but for a moat write's revalue of one company, which the server passes over, so
             they stay about the last run of the whole screen (the founder, 2026-11-22). */
          state.last = body.shown;
          followRuns(body, alive);
        }
        timer = setTimeout(poll, body.refresh !== null ? POLL_MS : IDLE_MS);
        render();
      })
      .catch(function (err) {
        if (request !== latestPoll) return;
        /* Ask again all the same, so the buttons and the faded tables recover once the server
           answers: on a run's cycle while one was alive, else on the idle one. */
        var alive = state.running !== null || started;
        timer = setTimeout(poll, alive ? POLL_MS : IDLE_MS);
        state.statusFailed = true;
        notify('The refresh status did not load: ' + err.message + (alive
          ? '. The page asks again every 2 seconds.' : '. The page asks again every 30 seconds.'),
          true, true);
      });
  }
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) poll();
  });

  /* The runs an answer with none alive gives to follow, whoever started them (spec 2026-11-23
     refresh experience, 4.3): those of `recent` newer than state.seen, the run the rows were read
     under, but a run still running, which another process runs (the command-line tool) and whose
     end is followed when it comes. Where `recent` is full and does not reach back to the run after
     state.seen, runs are missing: they are followed as one run of the whole screen. The first
     answer follows none, since the rows the page read as it loaded hold them. Runs are followed
     where there are some, or a run was alive at the answer before (`alive`), or the page started
     one: the rows are read again, the open drawer, the statistics where that view shows, and the
     company page where a run covered its company (covers); a company page no run covered is left
     as it is, so its reader is not moved. state.ended is the newest whole run among them, else
     null. state.seen then stops before the oldest run still running, else at the last run. */
  function followRuns(body, alive) {
    var recent = body.recent || [];
    var first = state.seen === null;
    var runs = first ? [] : recent.filter(function (run) {
      return run.id > state.seen && run.status !== 'running';
    });
    var missing = !first && recent.length >= RECENT &&
      recent[recent.length - 1].id > state.seen + 1;
    var running = recent.filter(function (run) { return run.status === 'running'; });
    /* the oldest running is the last, `recent` being the newest first */
    state.seen = running.length ? running[running.length - 1].id - 1
      : body.last ? body.last.id : 0;
    if (!runs.length && !missing && !alive && !started) return;
    var ended = runs.filter(whole)[0];
    started = false;
    state.notice = null; /* the notice (already running, cancel asked) no longer holds */
    state.cancelAsked = false;
    state.ended = ended ? { id: ended.id, kind: ended.kind, status: ended.status } : null;
    P.reload(true);
    P.reloadDrawer(); /* its review, secondary valuation and item may have moved */
    if (state.tab === 'statistics') loadGroups();
    if (state.tab === 'company' && (missing || runs.some(covers))) P.onShow.company(true);
  }

  /* A run of the whole screen: a price refresh, a full refresh or a revalue, naming no company
     (spec 2026-11-23 refresh experience, 4.1). A scoped refresh and a revalue of named companies
     (an agent's, a moat write's) are not, nor a run whose kind the server cannot say yet. */
  function whole(run) {
    return run.symbols == null && WHOLE_KINDS.indexOf(run.kind) !== -1;
  }

  /* A run that ended covered the company page's company where it is a run of the whole screen or
     names the company (4.3). */
  function covers(run) {
    return whole(run) || (run.symbols || []).indexOf(P.company.symbol) !== -1;
  }

  /* The page is locked while a run of the whole screen is alive, whoever started it, but for the
     run the reader kept reading under (keepReading; spec 2026-11-23 refresh experience, 4.1). A
     run the server does not report alive, the command-line tool's, locks nothing, as it draws no
     bar. */
  function locked() {
    var run = state.running;
    return run !== null && whole(run) && state.kept !== run.id;
  }

  /* A notice under the status line; one from a failed poll clears when a poll answers. */
  function notify(text, caution, fromPoll) {
    state.notice = text ? { text: text, caution: caution, fromPoll: !!fromPoll } : null;
    render();
  }

  /* The header's Inbox count (spec 2026-11-06 Tier 2, 18.5): the work items read as the page
     loads and every thirty seconds after, whether a refresh runs or not, on a cycle of their own.
     Each read takes the write lock on the server, since it runs the expiry rule, and a full
     refresh writes all the while, so the cycle is slow and pauses while the page is hidden; shown
     again, the page reads at once. A watched company whose window ended counts on the next read
     without a reload, as does an item an agent or another view posted. While the Inbox view
     shows, its table follows each read too (onInbox). A failed read keeps the count it had; the
     next read comes all the same. */
  function pollInbox() {
    clearTimeout(inboxTimer);
    if (document.hidden) return;
    var request = ++latestInbox;
    P.getJson('/api/inbox')
      .then(function (body) {
        if (request !== latestInbox) return;
        countInbox(body.items);
        if (P.onInbox) P.onInbox(body.items);
      })
      .catch(function () { /* the count stays as it was */ })
      .then(function () {
        if (request === latestInbox) inboxTimer = setTimeout(pollInbox, INBOX_MS);
      });
  }
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) pollInbox();
  });

  /* The open items, pending and claimed, among an inbox read's items; the header draws again when
     the count moves. At 0 the header shows none. */
  function countInbox(items) {
    var open = items.filter(function (item) {
      return OPEN.indexOf(item.state) !== -1;
    }).length;
    if (open === state.open) return;
    state.open = open;
    render();
  }

  /* The Inbox view's own read, after its write, so the count matches the table it draws: a poll
     still in flight, which may predate the write, is dropped, and the next one comes thirty
     seconds on. */
  function inboxRead(items) {
    ++latestInbox;
    clearTimeout(inboxTimer);
    countInbox(items);
    inboxTimer = setTimeout(pollInbox, INBOX_MS);
  }

  /* A POST, then the status read at once. 409 and 503 have their own words; any other refusal
     (a 403, a 400) and a request that never arrived read in caution. */
  function post(url, body, onOk) {
    notify(null);
    P.api.post(url, body)
      .then(function (r) {
        if (r.status === 409) notify('A refresh is already running.', false);
        else if (r.status === 503) {
          notify('No refresh worker.', false);
        } else if (!r.ok) {
          var detail = r.body && r.body.detail ? String(r.body.detail) : 'no reason given';
          notify('The server refused the request: ' + detail + '.', true);
        } else if (onOk) onOk();
        poll();
      })
      .catch(function (err) {
        notify('The request did not reach the server: ' + err.message +
          '. Reload the page to try again.', true);
      });
  }

  function start(kind) {
    post('/api/refresh', { kind: kind }, function () { started = true; });
  }

  function cancel() {
    post('/api/refresh/cancel', {}, function () {
      state.cancelAsked = true;
      notify('Cancel asked: the refresh stops after the companies in flight.', false);
    });
  }

  /* ----------------------------------------------------------- the statistics */

  /* The Statistics view's groups by the grouping chosen (spec 2026-11-23 refresh experience,
     4.5); only the newest read lands. */
  function loadGroups() {
    var request = ++latestGroups;
    state.groupsLoading = true;
    render();
    P.getJson('/api/statistics?by=' + encodeURIComponent(state.by))
      .then(function (body) {
        if (request !== latestGroups) return;
        state.groups = body;
        state.groupsLoading = false;
        state.groupsError = null;
        render();
      })
      .catch(function (err) {
        if (request !== latestGroups) return;
        state.groupsLoading = false;
        state.groupsError = 'The statistics did not load: ' + err.message +
          '. Choose the grouping again to retry.';
        render();
      });
  }

  /* Opens a view: its panel shows and the others hide, the hash names it (the Screen has none)
     and its loader runs, the statistics' here and each later view's through P.onShow. A view the
     page does not know is the Screen. A section of the Methodology view stays in P.section for that
     view's script to scroll to; one named while the view is open runs its loader again
     (spec 2026-11-04 6). The company page takes a company's symbol, a tab and, on the Research
     tab, a report's id, `report`, on the Investor relations tab its word (keepCompany), kept in
     P.company for its script; without a symbol it is the Screen, and another symbol, tab or id
     while it is open runs its loader again; a change of tab or of id replaces the hash as a change
     of view does, so the browser's Back never steps through the tabs (the company page's design,
     7.1; the Research tab's design, 7.1). The watchlist page takes a list's id (keepList), kept
     in P.listId for its script, #watchlists/<id>; another id, or none, while it is open runs its
     loader again, which opens the list the id names, else the default or the first by name
     (watchlists.js; spec 2026-11-22 7.3). Its table and drawer are the Screen's (spec 2026-11-22
     6, approach A), so the Screen's panel shows under the page's own head there too, and the
     table is told which of the two views it draws (P.onList) once the panels show, since it reads
     the Screen's place from the scroller as it turns to the list and a hidden scroller reads
     none; no other view tells it, so it keeps its mode while hidden.
     A view shown closes the watchlist popup and the Notes box (FairbandPage.closePopups), which
     no press closes when the browser's Back or Forward moves the hash. Once a view has opened
     (viewed), fromHash holds the address while the page is locked (spec 2026-11-23 refresh
     experience, 4.1). */
  function show(tab, section, id, report) {
    viewed = true;
    if (VIEWS.indexOf(tab) === -1 || (tab === 'company' && !section)) tab = 'screen';
    var opened = state.tab !== tab;
    P.section = tab === 'methodology' && section ? section : null;
    var moved = tab === 'company' && keepCompany(section, id, report);
    var listed = tab === 'watchlists' && keepList(section);
    history.replaceState(null, '', tab === 'screen' ? location.pathname
      : '#' + tab + (P.section ? '/' + P.section : '') + (tab === 'company' ? companyPath() : '') +
        (tab === 'watchlists' && P.listId != null ? '/' + P.listId : ''));
    if (!opened && !P.section && !moved && !listed) return;
    state.tab = tab;
    state.detailsOpen = false; /* a view opened with no press, by Back or Forward, shuts it too */
    P.closePopups();
    VIEWS.forEach(function (id) {
      panels[id].hidden = id !== tab && !(id === 'screen' && tab === 'watchlists');
    });
    if (tab === 'screen' || tab === 'watchlists') P.onList(tab === 'watchlists');
    if (tab === 'statistics') loadGroups();
    if (P.onShow[tab]) P.onShow[tab]();
    render();
  }

  /* The list a hash names, kept in P.listId: the whole number its word spells, else null, the
     default list or the first by name (watchlists.js). True when it is not the id already
     kept. */
  function keepList(word) {
    var id = /^\d+$/.test(String(word)) ? Number(word) : null;
    var kept = P.listId;
    P.listId = id;
    return kept !== id;
  }

  /* The company a hash names, kept in P.company: the symbol decoded, as the links encode it, and
     upper-cased, as the store keeps it; the tab, the Overview for none or one the page does not
     know; and the tab's id: the report's, a whole number on the Research tab, else null, the
     company's latest report there; on the Investor relations tab its word, a call, the fiscal
     year and the quarter as 2026Q4, or filings, its Filings view, else null, the Earnings calls
     view on the newest call (the Investor relations tab's design, 7.1); null on any other tab.
     True when it is not the company, tab and id already kept. */
  function keepCompany(symbol, tab, id) {
    var name = symbol;
    try { name = decodeURIComponent(symbol); } catch (e) { /* a malformed escape stays as typed */ }
    var shown = COMPANY_TABS.indexOf(tab) === -1 ? COMPANY_TABS[0] : tab;
    var word = String(id);
    var company = {
      symbol: name.toUpperCase(), tab: shown,
      id: shown === 'research' && /^\d+$/.test(word) ? Number(word)
        : shown === 'investor-relations' && /^(filings|\d{4}Q[1-4])$/.test(word) ? word : null
    };
    var kept = P.company;
    P.company = company;
    return !kept || kept.symbol !== company.symbol || kept.tab !== company.tab ||
      kept.id !== company.id;
  }

  /* The kept company's part of the hash, the symbol encoded as the links encode it: /AAPL for the
     Overview, which names no tab, /AAPL/estimates, /AAPL/research/12 for a report's id, or
     /AAPL/investor-relations/2026Q4 and /AAPL/investor-relations/filings for the Investor
     relations tab's word. */
  function companyPath() {
    var tab = P.company.tab;
    var id = P.company.id;
    return '/' + encodeURIComponent(P.company.symbol) + (tab === COMPANY_TABS[0] ? '' : '/' + tab) +
      (id == null ? '' : '/' + id);
  }

  /* The view a hash names, on load and when a link changes it: #watchlists, the watchlist page
     on the default list, or the first by name, #watchlists/<id>, on the list with that id;
     #statistics, the Statistics view, and #groups, its old address, which a bookmark may still
     name, the hash replaced by the view's (spec 2026-11-23 refresh experience, 4.5);
     #methodology, #settings, #methodology/<section-id>, the Methodology view at that section;
     #company/<symbol>, the company page's Overview, #company/<symbol>/financials, its Financials
     tab, #company/<symbol>/estimates, its Estimates tab, #company/<symbol>/investor-relations,
     its Investor relations tab, #company/<symbol>/investor-relations/2026Q4 on that call and
     #company/<symbol>/investor-relations/filings on its Filings view, a word the tab cannot read
     put right to the tab alone, #company/<symbol>/research, its Research tab on the latest report,
     or #company/<symbol>/research/<id>, on that report. The report page's addresses, which a link
     or a bookmark may still name, #report/<symbol> and #report/<symbol>/<id>, open the Research
     tab on the same report, the company's latest where no id is given, the hash replaced by the
     tab's; #report with no symbol is the Screen, as show has it (the Research tab's design,
     7.1). While the page is locked, a change of the address (Back, Forward, a hash typed) shows
     nothing and is put back to the address the page held as the lock began (state.address,
     lockPage), whatever wrote it: show, or the watchlist page naming its list (spec 2026-11-23
     refresh experience, 4.1). The first view opens all the same where the lock began before it,
     as the page loads, and its address is the one held. */
  function fromHash() {
    if (locked() && viewed) {
      history.replaceState(null, '', state.address);
      return;
    }
    var parts = location.hash.slice(1).split('/');
    if (parts[0] === 'groups') parts[0] = 'statistics';
    if (parts[0] === 'report') show('company', parts[1], 'research', parts[2]);
    else show(parts[0], parts[1], parts[2], parts[3]);
    if (locked()) state.address = address();
  }

  /* The address the page holds: its path and its hash. */
  function address() { return location.pathname + location.hash; }

  function groupBy(event) {
    state.by = event.target.value;
    loadGroups();
  }

  /* ----------------------------------------------------------------- the text */

  function count(n) { return Number(n).toLocaleString('en-US'); }

  /* An engine phase name as the design system writes it: Mature growth. */
  function phaseName(name) { return F.PHASES[P.PHASE_NUMBER[name]] || name; }

  /* The run bar's props from the poll's refresh body. The server's counts are per stage and add up
     to the stage's symbols, so they make the total. In the universe and deciles stages the server
     reports every symbol done, yet none is fetched or valued: nothing is done, and the word says
     what is happening. An unknown stage name is shown as it is. */
  function runProps(r) {
    var total = r.done + r.failed + r.remaining;
    var stage = STAGE_WORDS[r.stage] || r.stage;
    if (r.stage === 'universe' || r.stage === 'deciles') {
      return { total: total, done: 0, failed: r.failed, stage: stage };
    }
    return { total: total, done: r.done, failed: r.failed, stage: stage };
  }

  /* The last refresh, from its kind (spec 6.1): full done 1 Nov 2026, 01:20 · 1,052 of 1,759
     valued, then · 3 failed when the run failed companies. A price refresh counts those
     repriced, and those skipped for want of a snapshot. A record without a calibration, a run
     that failed, was cancelled or was scoped, says its message instead. The finish reads in the
     reader's local time. While the line describes the whole run whose changes the page counted
     (state.changes), the count ends it, · 1,546 prices changed, in the tint a changed cell takes
     while the count is fresh (changed; spec 2026-11-23 refresh experience, 4.2). */
  function lastLine(last) {
    if (!last) return ['No refresh has run yet.'];
    var c = last.calibration;
    var finished = last.finishedAt ? P.localIso(last.finishedAt) : null;
    var when = finished ? h('time', {
      key: 'when', dateTime: finished, title: finished
    }, F.formatDate(finished)) : null;
    var line = [last.kind + ' ' + last.status + (when ? ' ' : ''), when];
    if (!c) return line.concat(last.message ? [' · ' + last.message] : [], changed(last));
    line = line.concat(c.repriced != null
      ? [' · ', count(c.repriced), ' of ', count(c.total), ' repriced']
      : [' · ', count(c.valued), ' of ', count(c.total), ' valued']);
    var failed = failedOf(c);
    if (failed > 0) line = line.concat([' · ', count(failed), ' failed']);
    if (c.skipped > 0) line = line.concat([' · ', count(c.skipped), ' skipped']);
    return line.concat(changed(last));
  }

  /* The count of what the run `last` changed, · and its words in a span, where the page counted
     it for that run; else nothing. The span takes the tint's class, fb-changed, only while the
     count is fresh, so the tint plays once, as the rows land, and not again when the line is
     drawn anew (back from the company page, which draws none). The words stand until the line
     describes another run, or the page is loaded again: they are kept nowhere else (4.2). */
  function changed(last) {
    var c = state.changes;
    if (!c || c.id !== last.id) return [];
    return [' · ', h('span', {
      key: 'changes', className: c.fresh ? 'fb-changed' : null
    }, changeWords(c))];
  }

  /* The count's words: 1,546 prices changed, 37 values changed, both where both moved; where
     none did, no price changed after a price refresh and no figure changed after another run. */
  function changeWords(c) {
    var p = c.prices ? count(c.prices) + (c.prices === 1 ? ' price changed' : ' prices changed')
      : null;
    var v = c.values ? count(c.values) + (c.values === 1 ? ' value changed' : ' values changed')
      : null;
    if (p && v) return p + ', ' + v;
    return p || v || (c.kind === 'price' ? 'no price changed' : 'no figure changed');
  }

  /* The companies a run failed. A price refresh's calibration counts them; a full refresh's or a
     revalue's does not, so they are its refusals of the three reasons the refresh itself writes
     (refresh/run.py): a fetch that failed, one a rate limit stopped, a valuation that raised. */
  function failedOf(c) {
    if (c.failed != null) return c.failed;
    return Object.keys(c.refused || {}).reduce(function (n, reason) {
      return FAILED_REASONS.some(function (head) { return reason.indexOf(head) === 0; })
        ? n + c.refused[reason] : n;
    }, 0);
  }

  /* Details ▾ beside the line of a full refresh or a revalue: in the bundle's sectioned menu (the
     Filters menu's markup), the companies a classifier check flagged; the phases in phase order,
     unclassified last, those with none left out; the refusals grouped by the text before their
     first colon, the most frequent first. A press outside it or Escape closes it (spec 6.3). */
  function detailsMenu(c) {
    var phases = Object.keys(c.phases || {})
      .filter(function (p) { return c.phases[p] > 0; })
      .sort(function (a, b) { return phaseOrder(a) - phaseOrder(b); });
    var reasons = {};
    Object.keys(c.refused || {}).forEach(function (reason) {
      var head = reason.split(':')[0];
      reasons[head] = (reasons[head] || 0) + c.refused[reason];
    });
    var refused = Object.keys(reasons)
      .sort(function (a, b) { return reasons[b] - reasons[a] || (a < b ? -1 : a > b ? 1 : 0); });
    return h('div', { className: 'fb-screen__cols app-details' },
      h(F.Button, {
        size: 'sm', onClick: function () { state.detailsOpen = !state.detailsOpen; render(); },
        'aria-expanded': state.detailsOpen ? 'true' : 'false'
      }, 'Details ▾'),
      state.detailsOpen ? h('div', { className: 'fb-menu fb-menu--filters' },
        h('div', { className: 'fb-menu__body' },
          menuSection('FLAGGED', h('div', { className: 'body app-details__row' },
            count(c.flagged) + ' flagged by a classifier check')),
          h('hr'),
          menuSection('PHASES', phases.length ? phases.map(function (p) {
            return detailsRow(p, p === UNCLASSIFIED ? 'Unclassified' : phaseName(p), c.phases[p]);
          }) : none()),
          h('hr'),
          menuSection('REFUSED', refused.length ? refused.map(function (reason) {
            return detailsRow(reason, reason, reasons[reason]);
          }) : none()))) : null);
  }

  function none() { return h('div', { className: 'body app-details__row app-muted' }, 'none'); }

  function menuSection(head, rows) {
    return h('div', { className: 'fb-menu__sec' },
      h('span', { className: 'fb-menu__h label' }, head), rows);
  }

  /* A word and its count, the count in mono. */
  function detailsRow(key, word, n) {
    return h('div', { key: key, className: 'app-details__row' },
      h('span', { className: 'body' }, word), h('span', { className: 'figure-sm' }, count(n)));
  }

  /* A phase's place in phase order; unclassified, and any name the page does not know, last. */
  function phaseOrder(name) { return P.PHASE_NUMBER[name] || 7; }

  /* ------------------------------------------------------------------ render */

  function render() {
    var alive = state.running !== null;
    var lock = locked();
    lockPage(lock);
    /* Every panel's tables fade while a run of the whole screen is alive, but the Methodology
       view's: its examples are figures as of a named date, not the running refresh's. The
       Research tab's appendixes keep theirs (index.html): they are the records of the snapshot
       the report rests on. A run of named companies fades nothing (spec 2026-11-23 refresh
       experience, 4.1). */
    var faded = alive && whole(state.running);
    VIEWS.forEach(function (id) {
      if (id !== 'methodology') panels[id].classList.toggle(RECOMPUTING, faded);
    });
    /* The stamp is the latest refresh's finish, whatever its status (the status line says how it
       ended; on a page of one company, only where it did not end done). While a run is alive, or
       before any refresh finished, there is none: an absent stamp, never a placeholder. */
    var ran = alive || !state.last ? null : state.last.finishedAt;
    header.render(h(F.AppHeader, {
      views: [{ id: 'screen', label: 'Screen' }, { id: 'watchlists', label: 'Watchlists' },
        { id: 'statistics', label: 'Statistics' }, { id: 'methodology', label: 'Methodology' },
        { id: 'settings', label: 'Settings' }, { id: 'inbox', label: 'Inbox', count: state.open }],
      /* the company page is no header view: none is marked while it shows */
      view: state.tab === 'company' ? '' : state.tab,
      onViewChange: show,
      engineRanAt: ran ? P.localIso(ran) : null,
      /* the right slot: the finder (finder.js) on every view but the Screen, whose table has a
         field of its own, then the refresh controls */
      children: [
        state.tab === 'screen' ? null : h(P.finder.view, { key: 'finder' }),
        actions(alive)
      ]
    }));
    /* The status line: during a run, the run bar, or the stage word alone while the stage reports
       a total of 0 (the component draws nothing for it); else how the last refresh ended. A div,
       since the bar is a block a p cannot hold. Details ▾ stands beside the line, outside the
       status region, when the calibration has a breakdown; the run bar keeps the full width.
       A page of one company, the company page, draws neither the last refresh's line nor
       Details ▾: both describe the universe, and the header's stamp says when the engine ran (the
       founder, 2026-11-17). A run's bar and a notice still draw there, since the header has
       neither, and so does the line of a run that did not end done: the stamp is that run's
       finish too, and would read as a fresh run over figures it did not renew. The status region
       stays, empty, so a run that starts is announced from a region the page already had. A bar
       that draws nothing takes no room. */
    var one = state.tab === 'company';
    var quiet = one && !(state.last && state.last.status !== 'done');
    var run = alive ? runProps(state.running) : null;
    var status = run ? [run.total > 0 ? h(F.RunProgress, runProps(state.running)) : run.stage]
      : quiet ? [] : lastLine(state.last);
    var c = !run && !one && state.last ? state.last.calibration : null;
    var details = c && c.phases ? detailsMenu(c) : null;
    var notice = state.notice;
    var bare = !status.length && !notice;
    bar.render(h('div', { className: 'app-bar' + (bare ? ' app-bar--bare' : '') },
      h('div', { className: details ? 'app-statusline' : null },
        h.apply(null, ['div', { className: 'caption app-status', role: 'status' }].concat(status)),
        details),
      notice ? h('p', {
        className: 'caption app-status' + (notice.caution ? ' app-status--caution' : '')
      }, notice.text) : null));
    layer.render(layerView(lock));
    if (state.tab === 'statistics') groupsRoot.render(groupsView());
  }

  /* -------------------------------------------------------------- the refresh layer */

  /* The refresh layer (spec 2026-11-23 refresh experience, 4.1): while the page is locked, a
     modal dialog over the whole page, the header included, labelled by its title, which names the
     run's kind. In its panel, the run bar as the status line draws it, or the stage word alone
     while the stage reports a total of 0; the sentence; the notice, where there is one; Cancel,
     which does what the header's does, disabled once asked; and Keep reading, where it stands
     (keeps). The panel itself takes the focus as the layer turns on (focusPanel), so a key pressed
     by reflex neither cancels the run nor lifts the lock; Tab reaches the buttons. Escape does
     nothing to it. Not locked, the layer is hidden from a screen reader and inert, and keeps the
     panel it last drew (lastPanel), so the scrim and the panel fade out together over 150 ms
     (index.html); before the first lock it holds none. Each lock draws a panel of its own, keyed
     by the count of locks, so the panel a lock draws mounts, and takes the focus, as it turns
     on. */
  function layerView(on) {
    if (!on) {
      return h('div', { className: 'app-layer', 'aria-hidden': 'true', inert: '' }, lastPanel);
    }
    var run = runProps(state.running);
    var keep = keeps(state.running);
    var notice = state.notice;
    lastPanel = h('div', {
      key: 'lock-' + locks, className: 'app-layer__panel', tabIndex: -1, ref: focusPanel
    },
      h('h2', { id: LAYER_TITLE, className: 'heading app-layer__title' },
        LAYER_TITLES[state.running.kind]),
      run.total > 0 ? h(F.RunProgress, run)
        : h('div', { className: 'caption app-layer__stage' }, run.stage),
      h('p', { className: 'caption app-layer__say' }, LOCKED + (keep ? KEEP : '')),
      notice ? h('p', {
        className: 'caption app-layer__notice' +
          (notice.caution ? ' app-layer__notice--caution' : '')
      }, notice.text) : null,
      h('div', { className: 'app-layer__buttons' },
        h(F.Button, {
          key: 'cancel', variant: 'quiet', size: 'sm', disabled: state.cancelAsked,
          onClick: cancel
        }, 'Cancel'),
        keep ? h(F.Button, {
          key: 'keep', variant: 'primary', size: 'sm', onClick: keepReading
        }, 'Keep reading') : null));
    return h('div', {
      className: 'app-layer is-on', role: 'dialog', 'aria-modal': 'true',
      'aria-labelledby': LAYER_TITLE
    }, lastPanel);
  }

  /* Keep reading stands on a long run, a full refresh or a revalue of the whole screen, and on
     any run while the last read of the refresh's state failed: the page cannot know then that the
     run goes on (the server restarts), and the reader is never held behind the layer (4.1). */
  function keeps(run) {
    return LONG_KINDS.indexOf(run.kind) !== -1 || state.statusFailed;
  }

  /* Keep reading lifts the lock for the run alive, on this page alone: the run goes on, and the
     page is as under a run today, the run bar in the status line, the tables faint and Cancel in
     the header. Another run locks the page again, and so does a reload: the choice is the page's
     own state (4.1). */
  function keepReading() {
    if (state.running) state.kept = state.running.id;
    render();
  }

  /* The panel's ref: the panel takes the focus as it is drawn, which is as the layer turns on.
     React calls it with the panel once, as the lock's panel mounts, after the layer has lost its
     inert, and with null as it goes. */
  function focusPanel(panel) {
    if (panel) panel.focus();
  }

  /* Locks the page or frees it (4.1). While it is locked, every child of the body but the layer's
     mount is inert: main.app-page and the mounts the scripts add beside it (the watchlist
     popup's, the Notes box's, the moat box's), so no pointer, key or focus reaches what is under
     the layer. It is set at each draw while locked, so a mount added under the lock is covered
     too, and taken off once as the lock lifts. As the lock turns on, the page's address is kept
     for the lock (state.address, which fromHash puts back), the lock is counted, so the layer
     draws a panel of its own, and the open popups close (FairbandPage.closePopups): they would
     stand under the layer, out of reach. */
  function lockPage(on) {
    if (on || shut) {
      Array.prototype.forEach.call(document.body.children, function (child) {
        if (child !== layerMount) child.inert = on;
      });
    }
    if (on && !shut) {
      state.address = address();
      locks += 1;
      P.closePopups();
    }
    shut = on;
  }

  /* Escape does nothing while the page is locked: the layer does not close, and nothing under it
     answers. Its default is prevented before any other listener runs, so the drawer, whose
     Escape gives way to one a control has acted on (app.js), stays open (4.1). */
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && locked()) event.preventDefault();
  }, true);

  /* A refresh button's words: the full ones, and the short ones index.html shows in their place
     below 400px, where the full ones no longer fit beside the lockup (B-82). The button names
     itself in full either way. */
  function label(full, short) {
    return [
      h('span', { key: 'l', className: 'app-actions__long' }, full),
      h('span', { key: 's', className: 'app-actions__short' }, short)
    ];
  }

  /* The refresh controls in the header, small: the two refreshes while no run is alive, else one
     Cancel in their place, disabled once a cancel was asked until the run ends. */
  function actions(alive) {
    var buttons = alive ? [
      h(F.Button, {
        key: 'cancel', variant: 'quiet', size: 'sm', disabled: state.cancelAsked, onClick: cancel
      }, 'Cancel')
    ] : [
      h(F.Button, {
        key: 'price', size: 'sm', 'aria-label': 'Refresh prices',
        onClick: function () { start('price'); }
      }, label('Refresh prices', 'Prices')),
      h(F.Button, {
        key: 'full', variant: 'primary', size: 'sm', 'aria-label': 'Refresh all',
        onClick: function () { start('full'); }
      }, label('Refresh all', 'Full'))
    ];
    return h('div', { key: 'actions', className: 'app-actions' }, buttons);
  }

  /* The Statistics view: the table of the groups last loaded; while others load, it stays,
     faded. Its figures read what the Screen shows, as rows.statistics_rows counts them: the
     row's shown phase and its own value, the reviewed one where Reviewed is filled, so a group's
     count is the Screen's under the group's filter (spec 2026-11-23 refresh experience, 4.5). */
  function groupsView() {
    var g = state.groups;
    var picker = h('label', { className: 'label app-by' }, 'Group by ',
      h('select', { className: 'control app-select', value: state.by, onChange: groupBy },
        Object.keys(BY).map(function (by) {
          return h('option', { key: by, value: by }, BY[by]);
        })));
    var body = null;
    if (state.groupsError) body = h('p', { className: 'body app-note' }, state.groupsError);
    else if (g && g.groups.length === 0) {
      body = h('p', { className: 'body app-note' }, 'No companies to group yet. Run a refresh.');
    } else if (g) body = groupsTable(g);
    return h('div', { className: state.groupsLoading ? 'app-groups is-loading' : 'app-groups' },
      h('div', { className: 'app-groups__bar' }, picker),
      body,
      g && g.groups.length ? h('p', { className: 'caption app-muted app-groups__note' },
        'The median and the share read the value the Screen shows, the reviewed one where a ' +
        'company has it, over the companies with a value; below value is a price in its ' +
        'Below or Well below band.') : null);
  }

  /* Each group's name is a link to the page's own path, whose press stays on the page and opens
     the Screen with the group's filter alone (FairbandPage.filterScreen, app.js); a group with no
     filter, none or unclassified, names a field its rows lack and is plain text (4.5). */
  function groupsTable(g) {
    function figure(v, text) {
      return h('td', { className: 'figure fb-num' + (v == null ? ' app-muted' : '') }, text);
    }
    function name(row) {
      var word = g.by === 'phase' ? phaseName(row.name) : row.name;
      return row.filter ? h('a', {
        className: 'app-link', href: location.pathname,
        onClick: function (event) { event.preventDefault(); P.filterScreen(row.filter); }
      }, word) : word;
    }
    return h('table', { className: 'fb-table app-groups__table' },
      h('thead', null, h('tr', null,
        h('th', { className: 'label' }, BY[g.by]),
        h('th', { className: 'label fb-num' }, 'Companies'),
        h('th', { className: 'label fb-num' }, 'Valued'),
        h('th', { className: 'label fb-num' }, 'Median price ÷ value'),
        h('th', { className: 'label fb-num' }, 'Below value'))),
      h('tbody', null, g.groups.map(function (row) {
        return h('tr', { key: row.name },
          h('td', { className: 'body' }, name(row)),
          figure(row.count, count(row.count)),
          figure(row.valued, count(row.valued)),
          figure(row.medianPriceToValue, F.formatPercent(row.medianPriceToValue)),
          figure(row.shareBelowValue, F.formatPercent(row.shareBelowValue)));
      })));
  }

  /* Details ▾ closes on a press or focus outside it and on Escape, as the screen's menus do. Each
     menu closes itself on a press or focus outside it, so opening one, by pointer or by keyboard,
     closes the others (spec 6.3). Registered once; each reads state.detailsOpen. */
  function closeDetailsOutside(event) {
    if (!state.detailsOpen) return;
    if (event.target instanceof Element && event.target.closest('.app-details')) return;
    state.detailsOpen = false;
    render();
  }
  document.addEventListener('pointerdown', closeDetailsOutside);
  document.addEventListener('focusin', closeDetailsOutside);
  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape' || !state.detailsOpen) return;
    state.detailsOpen = false;
    render();
  });

  /* What the later views use: show opens a view; each view registers its loader in onShow, and
     onShow[tab]() runs each time that view opens; section is the Methodology section a hash
     named; company is the company, the tab and the id the company page shows,
     { symbol, tab, id }, the id null but on a report of the Research tab and on a word of the
     Investor relations tab; listId is the list's id the address names, a number or null, which
     the watchlist page sets too as the reader chooses a list; running() is true
     while a refresh runs; followRefresh() follows a refresh another view started (the Settings
     view's revalue) as the header follows its own: the run bar while it runs, the rows loaded
     again when it ends; countInbox(items) hands the header the Inbox view's own read, so its
     count follows; the Inbox view sets onInbox(items), which each of the header's own reads
     calls; onChanged({ prices, values }), which the screen's reload calls as the rows a run's
     end read land, marked, keeps their count for the status line where the run followed was a
     run of the whole screen that ended done, fresh for MARK_MS, as the rows' marks are, then
     drawn once more without its tint (spec 2026-11-23 refresh experience, 4.2). */
  P.show = show;
  P.onShow = {};
  P.listId = null;
  P.section = null;
  P.company = null;
  P.running = function () { return state.running !== null; };
  P.followRefresh = function () { started = true; poll(); };
  P.countInbox = inboxRead;
  P.onChanged = function (counts) {
    var ended = state.ended;
    if (!ended || ended.status !== 'done') return;
    var changes = {
      id: ended.id, kind: ended.kind, prices: counts.prices, values: counts.values, fresh: true
    };
    state.changes = changes;
    clearTimeout(freshTimer);
    freshTimer = setTimeout(function () {
      freshTimer = null;
      changes.fresh = false;
      render();
    }, P.MARK_MS);
    render();
  };

  window.addEventListener('hashchange', fromHash);
  /* The first view opens once the page's later scripts have run and registered their loaders. */
  document.addEventListener('DOMContentLoaded', fromHash);

  render();
  poll();
  pollInbox();
})();
