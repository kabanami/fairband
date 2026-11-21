/* The company page (the company page's design, 7), loaded after charts.js: a view at
   #company/<symbol>, its Overview, #company/<symbol>/financials, its Financials tab (the
   Financials tab's design, 7.1), #company/<symbol>/estimates, its Estimates tab,
   #company/<symbol>/investor-relations, its Investor relations tab, with a call (/2026Q4) or its
   Filings view (/filings) after it (the Investor relations tab's design, 7.1), and
   #company/<symbol>/research, its Research tab on the company's latest report, or
   #company/<symbol>/research/<id> on the report with that id (the Research tab's design, 7.1).
   No link leads back to the screen: the header's Screen view does (the decision log of
   2026-11-17). The head stands on every tab: at its left the logo, the name, the ticker, the
   phase badge, the moat stamp, the chip of the owner's or an agent's class and the control of
   the class (spec 2026-11-19 8.8), and one caption line, the exchange, the sector and the
   industry; at its right the latest snapshot's price, the day's change where the stored quote is
   that price's, the day of the close, then Notes, the watchlists control and Request research.
   Under it the tabs' row: Overview, Financials, Estimates, Investor relations and Research, the
   data date of the open tab at the row's right end.
   Under the row the open tab's blocks, which the later scripts hang on companyPage.draw by tab;
   nothing is drawn there while a tab's function is missing. The head reads the company's
   detail, as the drawer does; each tab its own read of the store, which carries the head's
   quote too; and the Overview, where its stored news is stale, one read of the news
   pass-through after it draws them, which may call a vendor (10.5), as the Research tab's read
   of the multiples history may (company_research.js) and the Investor relations tab's reads of
   a call's transcript and of an older year of filings (readVendor).
   The parts the blocks are built from, a panel, a list of names and figures, a group, a small
   table, and the formatters of their figures (14.1), are on FairbandPage.companyPage with the
   head and the tabs' row, for those scripts and for the tests, which read them in node. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  /* The five tabs the page reads, each its read's path and its name. */
  var TABS = [['overview', 'Overview'], ['financials', 'Financials'], ['estimates', 'Estimates'],
    ['investor-relations', 'Investor relations'], ['research', 'Research']];
  /* The tab whose id is a word the page draws and never reads: the Investor relations tab's call
     or view (the Investor relations tab's design, 7.1). */
  var WORDED = 'investor-relations';

  var mount = document.getElementById('company');
  var root = ReactDOM.createRoot(mount);
  var state = {
    symbol: null, /* the company whose page is shown */
    tab: 'overview', /* the tab shown */
    id: null, /* the report the Research tab shows, by its id, null for the latest; the word the
                 Investor relations tab shows; null elsewhere */
    report: null, /* the key (keyOf) of the report the Research tab showed last of the company
                     shown, kept while another tab shows; null before the tab showed one */
    detail: null, /* GET /api/companies/{symbol}: the head */
    answers: {}, /* the shown company's tab reads, by tab and report (keyOf), as they landed */
    failed: null, /* the shown tab's read failed: the sentence drawn under the tabs */
    error: null, /* the detail's read failed: the server's sentence, drawn in the head's place */
    loading: false,
    whole: false, /* the read out reads the detail too: the tabs held may be older than it */
    reading: null, /* the company, tab and id the read out reads ({ symbol, tab, id }, as
                      FairbandPage.company named them, or as a change of the Investor relations
                      tab's word alone moved them since: redrawn), before it is shown */
    request: null /* Request research for the page's company (FairbandPage.asking) */
  };
  var latest = 0;

  /* The key a tab's answer is held under, of `at`, { tab, id }: the tab, and for a report the
     Research tab names by its id, research/<id>, so each report read is a tab of its own. The
     Investor relations tab's word is no part of it: the tab's one answer is drawn on every word.
     Null for no `at`. */
  function keyOf(at) {
    if (!at) return null;
    return at.id == null || at.tab === WORDED ? at.tab : at.tab + '/' + at.id;
  }

  /* The page FairbandPage.company names (7.1, 7.5). Another company, or the tab shown asked for
     again (the view opened again, a request's post ended, a note was taken in the head's Notes box,
     or a refresh ended while the page shows, controls.js), or the tab whose read is out, not yet
     shown, asked for again, reads the detail, then the tab's read, and drops what the page held of
     the other tab, so the head and the tab draw the run's figures; another tab of the company shown
     reads only that tab, and one it read already is shown at once, but while a read of the detail
     is out, which that tab may be older than, it reads the detail and the tab, so a reread a
     refresh's end started is never dropped for the figures of before the run. A report of the
     Research tab is a tab of its own (keyOf): another report reads the tab with that report's id,
     ?report=<id>, and one read already is shown at once. The page shown stays, faded, until the
     new one lands, and the latest read wins, so a read that lands after the reader moved to
     another company, tab or report is dropped. A read of another company stops the following of
     the request of the company shown before it starts, and drops a note drafted on another company
     (FairbandPage.notesShown), and again as it lands or fails while the page shows, so a Notes box
     opened from the faded head of the company before it closes as the page turns; one that lands
     after the reader left the view leaves the notes alone, so a Notes box open in the drawer keeps
     its draft; a read of the company shown keeps its draft; every landing follows the open item's
     launch again (shown). A tab's read that fails draws its sentence under the tabs; the detail's
     draws its own (failure) alone. An Overview's read that lands draws its stored news,
     then asks for newer news where they are stale (newer); a tab held is shown with what it holds
     and asks nothing. The panel goes back to its top as the page turns to another company, and as
     the Research tab turns to another report than it showed last, another id or the latest after
     an id, read or held (the Research tab's design, 7.3), since its section list stays in view
     while the report scrolls; the same report read again, another tab, and the same report on
     coming back keep the reader's place. The Investor relations tab's word is the page's own: the
     tab's read takes no query, and a change of the word alone reads nothing (redrawn). */
  function load() {
    var want = P.company;
    var key = keyOf(want);
    if (redrawn(want, key)) return;
    var request = ++latest;
    var held = !!state.detail && !state.error && state.symbol === want.symbol;
    if (want.tab === 'research' && state.symbol === want.symbol && state.report != null &&
      state.report !== key) {
      mount.scrollTop = 0;
    }
    if (held && key !== keyOf(state) && state.answers[key] && !state.whole) {
      state.tab = want.tab;
      state.id = want.id;
      if (want.tab === 'research') state.report = key;
      state.failed = null;
      state.loading = false;
      state.reading = null;
      shown();
      return;
    }
    var whole = !held || key === keyOf(state) || key === keyOf(state.reading) || state.whole;
    var company = '/api/companies/' + encodeURIComponent(want.symbol);
    if (state.request && state.request.symbol !== want.symbol) P.stopLaunch(state.request);
    if (state.symbol !== want.symbol) P.notesShown(want.symbol);
    /* The panel stays shown from one company to the next (the header's finder, the browser's
       Back): the next page opens at its head, not at the depth the reader left. */
    if (state.symbol !== want.symbol) mount.scrollTop = 0;
    state.whole = whole;
    state.reading = want;
    state.loading = true;
    render();
    (whole ? read(company) : Promise.resolve(state.detail))
      .then(function (detail) {
        /* a report's id alone travels, ?report=<id>; the Investor relations tab's word never */
        var query = key === want.tab ? '' : '?report=' + want.id;
        return read(company + '/page/' + want.tab + query)
          .then(function (answer) {
            return { detail: detail, answer: answer, failed: null };
          }, function (err) {
            return { detail: detail, answer: null, failed: failure(err, want.tab === 'research') };
          });
      })
      .then(function (found) {
        if (request !== latest) return;
        var at = state.reading; /* want, or its word as a change of it alone moved it (redrawn) */
        state.whole = false;
        state.reading = null;
        if (whole) state.answers = {};
        if (found.answer) state.answers[key] = found.answer;
        if (state.symbol !== want.symbol && !mount.hidden) P.notesShown(want.symbol);
        if (state.symbol !== want.symbol) state.report = null;
        if (want.tab === 'research') state.report = key;
        state.symbol = want.symbol;
        state.tab = want.tab;
        state.id = at.id;
        state.detail = found.detail;
        state.failed = found.failed;
        state.error = null;
        state.loading = false;
        shown();
        if (want.tab === 'overview' && found.answer) newer(want.symbol, found.answer);
      })
      .catch(function (err) {
        if (request !== latest) return;
        /* the read out, or, where the landing cleared it and then threw (a tab's function, the
           following of the item, newer news), the address it was asked for */
        var at = state.reading || want;
        state.whole = false;
        state.reading = null;
        if (state.symbol !== want.symbol && !mount.hidden) P.notesShown(want.symbol);
        if (state.symbol !== want.symbol) state.report = null;
        if (want.tab === 'research') state.report = key;
        state.symbol = want.symbol;
        state.tab = want.tab;
        state.id = at.id;
        state.detail = null;
        state.answers = {};
        state.failed = null;
        state.error = failure(err, true);
        state.loading = false;
        render();
      });
  }

  /* A change of the Investor relations tab's word alone, its call or its view, which the page
     draws and never reads (the Investor relations tab's design, 7.1; `want` the address asked
     for, `key` its key): true where it is drawn with no read, so load reads nothing. Where the
     tab's own read of the company is out (a refresh's end, the tab asked for from another), that
     read lands on the new word, and the tab, where the page shows it, is drawn on it at once,
     still faded. Else, where the page shows the tab of the company and holds its answer, the
     answer is drawn again on the new word at once, and a read of another tab out is dropped, as
     a tab held is shown at once (load); but not while a read of the detail is out, which the
     answer held may be older than: load reads the detail and the tab. False for every other
     change, and for the same word asked for again (a refresh's end, a note taken), which load
     reads whole. */
  function redrawn(want, key) {
    if (want.tab !== WORDED) return false;
    var out = state.reading;
    if (out && out.symbol === want.symbol && keyOf(out) === key) {
      if (out.id === want.id) return false;
      state.reading = want;
      if (state.symbol === want.symbol && state.tab === want.tab) state.id = want.id;
      render();
      return true;
    }
    if (!state.detail || state.error || state.symbol !== want.symbol || state.tab !== want.tab ||
      state.id === want.id || !state.answers[key] || state.whole) return false;
    ++latest; /* a read of another tab out lands late, and is dropped */
    state.id = want.id;
    state.failed = null;
    state.loading = false;
    state.reading = null;
    shown();
    return true;
  }

  /* The page shows the company's detail it holds, as a read lands or a tab read before is shown
     again. The page's request for the company (FairbandPage.asking) is made as the company's
     first read lands, and kept until the page shows another; at every landing it follows the
     open item's launch (FairbandPage.followItem), so a following that a read of another company
     stopped starts again when the reader comes back before it lands. */
  function shown() {
    if (!state.request || state.request.symbol !== state.symbol) {
      state.request = P.asking(state.symbol);
    }
    P.followItem(state.request, state.detail.item, render, load);
    render();
  }

  /* Newer news (10.5), once for each read of the Overview that lands: where the stored news of
     its `answer` is stale, older than the refresh's reuse window or none, the page has drawn them
     at once, and now asks the pass-through (freshNews) at the answer's limit. Its stories take the
     stored ones' place in the answer the page holds; a refusal keeps the stored ones and sets the
     news' note, the server's sentence, which News draws in its head. An answer that lands when
     the page no longer holds the answer it was asked for, the reader gone to another company or
     the company read anew, is dropped; on another tab of the company the answer is still held,
     and the stories land in it. */
  function newer(symbol, answer) {
    var news = answer.news;
    if (!news.stale) return;
    freshNews(symbol, news.limit).then(function (stories) {
      return { stories: stories, note: null };
    }, function (err) {
      return { stories: news.stories, note: err.message };
    }).then(function (got) {
      if (state.answers.overview !== answer) return;
      state.answers.overview = Object.assign({}, answer, { news: Object.assign({}, news, got) });
      render();
    });
  }

  /* What a failed read draws (7.5): the Words table's sentence with the read's message, which
     says to open the page again; but for a 404 of a read whose refusal is final, `asIs` true, the
     server's own sentence as it arrives, since opening the page again would not help: the
     detail's, a company with no snapshot (no snapshot for <symbol>), and the Research tab's, a
     report of another company or of none, or no page data (the Research tab's design, 7.1). Any
     other tab's 404 is no page data for <symbol> in the Words table's sentence. */
  function failure(err, asIs) {
    if (asIs && err.status === 404) return err.message;
    return 'The company\'s data did not load: ' + err.message + '. Open the page again to retry.';
  }

  function render() {
    root.render(page());
  }

  /* The head, the tabs' row and the open tab; the detail's failure in the head's place; while
     the first read is out, the ticker as the hash names it. */
  function page() {
    var d = state.detail;
    var className = state.loading ? 'app-company is-loading' : 'app-company';
    if (state.error) {
      return h('div', { className: className }, note(state.error));
    }
    if (!d) {
      return h('div', { className: className },
        h('h2', { className: 'ticker' }, P.company.symbol));
    }
    var answer = state.answers[keyOf(state)] || null;
    return h('div', { className: className },
      head(d, answer && answer.quote),
      tabs(state.symbol, state.tab, answer && asOf(answer)),
      tabBody(answer, d));
  }

  /* Under the tabs' row: the tab's failed read in one sentence (7.5), else its blocks, drawn by
     the function a later script hangs on draw for the tab, on its answer, the detail and the id
     the page shows (the Investor relations tab's word), once the answer and the detail are in;
     nothing while either is missing. */
  function tabBody(answer, d) {
    if (state.failed) return note(state.failed);
    var drawn = P.companyPage.draw[state.tab];
    return answer && drawn ? drawn(answer, d, state.id) : null;
  }

  /* The open tab's data date, at the row's right end (7.4): its answer's, unless the tab's script
     works its own out, a function it hangs on dataDate for the tab, called on the answer and the
     id the page shows, as the Investor relations tab's, whose two views each count their own
     answers (its design, 7.6). A tab whose later reads land after its answer draws the page
     again (redraw), and the date with it. */
  function asOf(answer) {
    var dated = P.companyPage.dataDate[state.tab];
    return dated ? dated(answer, state.id) : answer.dataDate;
  }

  function note(text) { return h('p', { className: 'body app-note' }, text); }

  /* ------------------------------------------------------------------ the head */

  /* The head on every tab (7.2), from the company's detail `d`, and `quote`, the open tab's
     stored quote, null before its answer is in. Left: the logo on the drawer's tile at 40px
     (FairbandPage.logo), the name, the ticker, the phase badge, the moat stamp
     (FairbandPage.moatStamp), the chip where the class is the owner's or an agent's
     (FairbandPage.moatChip) and the control that opens the moat box under it, which, once a write
     is taken, reads the page again (FairbandPage.moatControl, load; spec 2026-11-19 8.8); and one
     caption line, the exchange, the sector and the industry of the universe row, the parts it
     has. Right: the latest snapshot's price in figure-lg, in US dollars, the day's change, and
     the day of its close; then Notes with the count of the
     company's notes (FairbandPage.notesControl, 11.1), whose box opens under it and, once a note
     is taken, reads the page again (load); the watchlists control, which opens the screen's
     popup for this company under itself, on the row watchRow gives, disabled without one; and
     Request research, the drawer's: its menu, its line and the following of its launch, with
     the request the page keeps for its company (shown), or, where it keeps none for it, as in
     the tests, which draw a head with no read, a new one it keeps nowhere. */
  function head(d, quote) {
    var r = d.result;
    var c = d.company || {};
    var phase = P.PHASE_NUMBER[r.phase.phase];
    var line = [c.exchange, c.sector, c.industry].filter(Boolean).join(' · ');
    var row = watchRow(r.symbol, P.rows(), P.watchlists());
    var ask = state.request && state.request.symbol === r.symbol ? state.request
      : P.asking(r.symbol);
    return h('header', { className: 'app-company__head' },
      h('div', { className: 'app-company__id' },
        P.logo(d, 'app-company__logo'),
        h('div', { className: 'app-company__names' },
          h('div', { className: 'app-company__line' },
            c.name ? h('h1', { className: 'title app-company__name' }, c.name) : null,
            h('span', { className: 'ticker' }, r.symbol),
            phase ? h(F.PhaseBadge, { phase: phase, size: 'sm' }) : null,
            P.moatStamp(d), P.moatChip(d), P.moatControl(d, load)),
          line ? h('p', { className: 'caption app-company__sub' }, line) : null)),
      h('div', { className: 'app-company__side' },
        h('div', { className: 'app-company__quote' },
          h('p', { className: 'figure-lg' }, money(dollars(r.price))),
          change(r.price, quote),
          r.price_date
            ? h('p', { className: 'caption app-company__at' }, 'close ' + day(r.price_date))
            : null),
        h('div', { className: 'app-company__actions' },
          P.notesControl(r.symbol, d.noteCount, load),
          h(F.Button, {
            disabled: !row,
            onClick: function (event) { P.watch(row, event.currentTarget); }
          }, 'Watchlists ▾'),
          P.requestResearch(ask, d.item, render, load, d.launchReady))));
  }

  /* The row the watchlists popup opens on (FairbandPage.watch). A box ticked or a list added
     writes the company's whole set of lists, so the popup opens only on its true memberships:
     the screen's row of the company, which carries the lists it is on, where the loaded `rows`
     hold it; else the company alone where the `lists` have loaded, which the popup reads its
     memberships from; else none, and the control waits, disabled, for either to land. */
  function watchRow(symbol, rows, lists) {
    var found = (rows || []).filter(function (row) { return row.ticker === symbol; })[0];
    if (found) return { ticker: symbol, watchlists: found.watchlists };
    return lists ? { ticker: symbol } : null;
  }

  /* The day's change and its percent, each with its sign and in the text's own colour (14.1),
     from the stored quote (10.4); drawn only where the quote's price is the snapshot's `price`,
     so the change is that price's, and where the quote has both. */
  function change(price, quote) {
    if (!quote || !ok(price) || quote.price !== price || !ok(quote.change) ||
        !ok(quote.changePercent)) return null;
    return h('p', { className: 'figure app-company__change' },
      signed(money(dollars(Math.abs(quote.change))), quote.change) + ' (' +
      signed(points(Math.abs(quote.changePercent), 2), quote.changePercent) + ')');
  }

  /* ------------------------------------------------------------------ the tabs */

  /* The tabs' row (7.3, 7.4; the Research tab's design, 7.1; the Investor relations tab's design,
     7.1): Overview, Financials, Estimates, Investor relations and Research, the open one
     selected, each opening through FairbandPage.show, which replaces the hash, Investor relations
     on its Earnings calls view and Research on the company's latest report; and at the row's
     right end the data date of the open tab (asOf), none without one. */
  function tabs(symbol, tab, dataDate) {
    return h('nav', { className: 'app-company__tabs' },
      h('div', { className: 'app-company__tablist', role: 'tablist' },
        TABS.map(function (t) {
          return h('button', {
            key: t[0], type: 'button', role: 'tab', className: 'control app-company__tab',
            'aria-selected': t[0] === tab ? 'true' : 'false',
            onClick: function () { P.show('company', symbol, t[0]); }
          }, t[1]);
        })),
      dataDate ? h('p', { className: 'caption app-company__asof' }, 'data ' + day(dataDate))
        : null);
  }

  /* ---------------------------------------------------------- the blocks' parts */

  /* A block: its title in its head, with `right`, a caption or a control, at the head's right
     end, then `children`; `modifier`, where given, a class of its own beside the block's. */
  function panel(title, right, children, modifier) {
    return h('section', {
      key: title, className: 'app-company__panel' + (modifier ? ' ' + modifier : '')
    },
      h('header', { className: 'app-company__panelhead' },
        h('h2', { className: 'heading app-company__paneltitle' }, title), right || null),
      children);
  }

  /* Rows of a name and a figure, `[name, value, isText]`: the value in figure, or in body where
     it is text. */
  function kv(rows) {
    return h('div', { className: 'app-kv' }, rows.map(function (row) {
      return h('div', { key: row[0], className: 'app-kv__row' },
        h('span', { className: 'body app-kv__k' }, row[0]),
        h('span', { className: (row[2] ? 'body' : 'figure') + ' app-kv__v' }, row[1]));
    }));
  }

  /* A group of rows under its title in label, upper case (14.1). */
  function group(title, rows) {
    return h('div', { key: title, className: 'app-company__group' },
      h('h3', { className: 'label app-company__grouptitle' }, title), kv(rows));
  }

  /* A small table of figures: its head's cells in label, then its rows, each led by its name, its
     figures in `type`, figure unless told (figure-sm, for a table in a narrow column). */
  function table(head, rows, type) {
    return h('table', { className: 'app-company__table' },
      h('thead', null, h('tr', null, head.map(function (cell, i) {
        return h('th', { key: i, className: 'label' }, cell);
      }))),
      h('tbody', null, rows.map(function (row, i) {
        return h('tr', { key: i }, row.map(function (cell, j) {
          return h('td', {
            key: j, className: j ? type || 'figure' : 'body app-company__rowname'
          }, cell);
        }));
      })));
  }

  /* ------------------------------------------------------------- the figures */

  /* The figures' words (14.1). A money figure is { value, currency } as the reads give it, in US
     dollars with `$` and in another currency with its code in `$`'s place, its amount written as
     the design system writes it, so the page's money reads as the meter's beside it; a missing
     figure is an em dash, and so is a multiple at exactly 0. */
  function ok(v) { return typeof v === 'number' && isFinite(v); }

  /* `v` to `dp` decimals, grouped in threes. */
  function fixed(v, dp) {
    return v.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
  }

  /* A minus, U+2212, before `text`, the figure's size, where `v` is below zero and the text is
     not zero at its precision. */
  function minus(text, v) { return v < 0 && /[1-9]/.test(text) ? '−' + text : text; }

  function dollars(v) { return { value: v, currency: 'USD' }; }

  /* The mark before a money figure's number: `$`, or another currency's code and a space. */
  function unit(m) { return m.currency && m.currency !== 'USD' ? m.currency + ' ' : '$'; }

  /* Money to cents with no thousands separator, as the design system writes an amount
     (Fairband.formatMoney, which the meter, the drawer and the screen write), its `$` the
     currency's mark: $356.27, $1495.16, TWD 1495.16, −$1.20. */
  function money(m) {
    if (!m || !ok(m.value)) return '—';
    return minus(unit(m) + Math.abs(m.value).toFixed(2), m.value);
  }

  /* The compact scales, largest first: the least amount each draws, its divisor, its decimals and
     its letter. Billions take one decimal from a hundred billion, two below. */
  var SCALES = [
    [1e12, 1e12, 2, 'T'], [1e11, 1e9, 1, 'B'], [1e9, 1e9, 2, 'B'], [1e6, 1e6, 1, 'M'], [0, 1, 0, '']
  ];

  /* A large amount, compact: $5.18T, TWD 4.94T, $478.8B; a bare count, a number not money, with
     no mark: 14.53B, 39.1M, 167,000. The scale is the amount's, one up where the amount rounded
     at it reaches the next scale's least, so none reads as a thousand of the scale below it:
     999.96 billion is 1.00T, not 1,000.0B, and 999.94 billion stays 999.9B. */
  function big(m) {
    var isMoney = m !== null && typeof m === 'object';
    var v = isMoney ? m.value : m;
    if (!ok(v)) return '—';
    var a = Math.abs(v);
    var i = 0;
    while (a < SCALES[i][0]) i++;
    while (i > 0 && scaled(a, SCALES[i]) >= SCALES[i - 1][0] / SCALES[i][1]) i--;
    var s = SCALES[i];
    return minus((isMoney ? unit(m) : '') + fixed(a / s[1], s[2]) + s[3], v);
  }

  /* The amount `a` at `scale`, rounded to its decimals as fixed rounds them. */
  function scaled(a, scale) {
    return Number(fixed(a / scale[1], scale[2]).replace(/,/g, ''));
  }

  /* A fraction as a percent, to one decimal unless told: 0.4879 is 48.8%. */
  function percent(x, digits) {
    return ok(x) ? minus(fixed(Math.abs(x) * 100, digits == null ? 1 : digits) + '%', x) : '—';
  }

  /* A percent as given, to one decimal unless told: 88.42 is 88.4%. */
  function points(x, digits) {
    return ok(x) ? minus(fixed(Math.abs(x), digits == null ? 1 : digits) + '%', x) : '—';
  }

  /* A change's sign before `text`, its size: + above zero, − below; none where the text is zero
     at its precision, or a dash. */
  function signed(text, x) {
    if (!/[1-9]/.test(text)) return text;
    return (x > 0 ? '+' : x < 0 ? '−' : '') + text;
  }

  /* A multiple to one decimal: 39.3x; a dash at exactly 0. */
  function multiple(x) { return ok(x) && x !== 0 ? minus(fixed(Math.abs(x), 1) + 'x', x) : '—'; }

  /* A plain number to `dp` decimals, grouped: 1.18, 11.9, −0.42; its zero is a zero. */
  function decimal(x, dp) { return ok(x) ? minus(fixed(Math.abs(x), dp), x) : '—'; }

  /* A day: 13 Nov 2026. */
  function day(iso) { return iso ? F.formatDate(String(iso).slice(0, 10)) : '—'; }

  /* A count, grouped: 167,000. */
  function count(n) { return ok(n) ? minus(fixed(Math.abs(n), 0), n) : '—'; }

  /* -------------------------------------------------------------------- the reads */

  /* A read whose refusal is the server's sentence, as it arrives, with the answer's status, by
     which the detail's 404 keeps its own sentence (failure); `init`, where given, the fetch's
     options. The page's own reads, the detail and each tab's, are plain GETs: none calls a
     vendor. */
  function read(url, init) {
    return fetch(url, init).then(function (response) {
      return response.ok ? response.json() : refused(response);
    });
  }

  /* A tab's read that may call a vendor (the Investor relations tab's design, 8.2: a call's
     transcript, an older year of filings): read with the header a write carries, without which
     the server refuses it, as the Research tab's reads and newer news carry it. */
  function readVendor(url) {
    return read(url, { headers: { 'X-Fairband-Request': '1' } });
  }

  function refused(response) {
    return response.json().catch(function () { return null; }).then(function (body) {
      var error = new Error(body && typeof body.detail === 'string' ? body.detail
        : 'the server answered ' + response.status);
      error.status = response.status;
      throw error;
    });
  }

  /* Newer news (10.5): the news pass-through's stories (GET /api/vendor/news/{symbol}), the
     symbol encoded as the page's reads encode it, at `limit`. A read that may call a vendor, so
     it carries the header a write carries, as the Research tab's reads do, without which the
     server refuses it. Its payload's stories in the overview read's shape
     (newsStories); a refusal is the server's sentence (refused), and a payload that is not a
     list, FMP's error body, which the pass-through answers and stores as unusable, or an answer
     that is not JSON at all, a sentence of its own. */
  function freshNews(symbol, limit) {
    var url = '/api/vendor/news/' + encodeURIComponent(symbol) + '?limit=' + limit;
    return fetch(url, { headers: { 'X-Fairband-Request': '1' } }).then(function (response) {
      if (!response.ok) return refused(response);
      return response.json().catch(function () { return null; });
    }).then(function (body) {
      if (!body || !Array.isArray(body.payload)) throw new Error('the answer held no stories');
      return newsStories(body.payload);
    });
  }

  /* A news payload's stories as the overview read shapes them (vendors/page_fmp.py, stories):
     each object row in its order, newest first as FMP gives them; its day, the first ten
     characters of publishedDate where they are an ISO date; its title; its publisher, else its
     site; its address, kept whatever its scheme (News makes a link only of a web address). Each
     text stripped, and null where it is empty or not a text. */
  function newsStories(payload) {
    return payload.filter(function (row) {
      return row !== null && typeof row === 'object' && !Array.isArray(row);
    }).map(function (row) {
      var published = words(row.publishedDate);
      return {
        day: published && /^\d{4}-\d{2}-\d{2}/.test(published) ? published.slice(0, 10) : null,
        title: words(row.title),
        publisher: words(row.publisher) || words(row.site),
        url: words(row.url)
      };
    });
  }

  /* A text, stripped; null where it is empty or not a text. */
  function words(raw) {
    return typeof raw === 'string' && raw.trim() ? raw.trim() : null;
  }

  /* What the tabs' scripts and the tests use: the head, the tabs' row, a panel, a list of names
     and figures, a group, a small table and the formatters; readVendor(url), a tab's read that
     may call a vendor; redraw(), which draws the page again with what it holds, for a tab
     whose own reads land after its answer; draw, which each tab's script fills with its tab's
     function, draw.overview(answer, detail), draw.financials(answer, detail),
     draw.estimates(answer, detail), draw['investor-relations'](answer, detail, id) and
     draw.research(answer, detail), each returning the tab's element, `id` the id the page shows,
     the Investor relations tab's word; and dataDate, where a tab's script hangs the function that
     works out its data date, dataDate['investor-relations'](answer, id) (asOf). The read of newer
     news (freshNews), the row the watchlists popup opens on and a failed read's sentence are here
     for the tests. */
  P.companyPage = {
    head: head, tabs: tabs, panel: panel, kv: kv, group: group, table: table,
    money: money, big: big, percent: percent, points: points, signed: signed,
    multiple: multiple, decimal: decimal, day: day, count: count,
    watchRow: watchRow, failure: failure, freshNews: freshNews, readVendor: readVendor,
    redraw: render, draw: {}, dataDate: {}
  };
  P.onShow.company = load;

  /* The page draws again after each draw of the screen while it shows, as the Watchlists view
     does: the screen draws as its rows and the lists land, and the watchlists control waits on
     them (watchRow). The view's redraw set before this script, the Watchlists view's, still
     runs. */
  var before = P.onRender;
  P.onRender = function () {
    if (before) before();
    if (!mount.hidden && P.company) render();
  };
})();
