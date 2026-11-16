/* The company page (the company page's design, 7), loaded after charts.js: a view at
   #company/<symbol>, its Overview, and #company/<symbol>/estimates, its Estimates tab. Above the
   head, the link back to the screen, as on the report page. The head stands on every tab: at its
   left the logo, the name, the ticker, the phase badge, the moat stamp and one caption line, the
   exchange, the sector and the industry; at its right the latest snapshot's price, the day's
   change where the stored quote is that price's, the day of the close, then the watchlists
   control and Request research. Under it the tabs' row: Overview and Estimates, and Research, a
   link to the report page, the data date of the open tab at the row's right end. Under the row the
   open tab's blocks, which the later scripts hang on companyPage.draw by tab; nothing is drawn
   there while a tab's function is missing. The head reads the company's detail, as the drawer and
   the report page do; each tab its own read of the store, which carries the head's quote too. The
   parts the blocks are built from, a panel, a list of names and figures, a group, a small table,
   and the formatters of their figures (14.1), are on FairbandPage.companyPage with the head and
   the tabs' row, for those scripts and for the tests, which read them in node. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  /* The two tabs the page reads, each its read's path and its name; Research is a link. */
  var TABS = [['overview', 'Overview'], ['estimates', 'Estimates']];

  var mount = document.getElementById('company');
  var root = ReactDOM.createRoot(mount);
  var state = {
    symbol: null, /* the company whose page is shown */
    tab: 'overview', /* the tab shown */
    detail: null, /* GET /api/companies/{symbol}: the head */
    answers: {}, /* the shown company's tab reads, by tab, as they landed */
    failed: null, /* the shown tab's read failed: the sentence drawn under the tabs */
    error: null, /* the detail's read failed: the server's sentence, drawn in the head's place */
    loading: false,
    request: null /* Request research for the page's company (FairbandPage.asking) */
  };
  var latest = 0;

  /* The page FairbandPage.company names (7.1, 7.5). Another company, or the tab shown asked for
     again (the view opened again, or a request's post ended), reads the detail, then the tab's
     read, and drops what the page held of the other tab; another tab of the company shown reads
     only that tab, and one it read already is shown at once. The page shown stays, faded, until
     the new one lands, and the latest read wins, so a read that lands after the reader moved to
     another company or tab is dropped. A read of another company stops the following of the
     request of the company shown before it starts, and the page follows the open item's launch
     as the detail lands (FairbandPage.followItem), as the report page does. A tab's read that
     fails draws its sentence under the tabs; the detail's draws the server's sentence and the
     link back. */
  function load() {
    var want = P.company;
    var request = ++latest;
    var held = !!state.detail && !state.error && state.symbol === want.symbol;
    if (held && want.tab !== state.tab && state.answers[want.tab]) {
      state.tab = want.tab;
      state.failed = null;
      state.loading = false;
      render();
      return;
    }
    var whole = !held || want.tab === state.tab;
    var company = '/api/companies/' + encodeURIComponent(want.symbol);
    if (state.request && state.request.symbol !== want.symbol) P.stopLaunch(state.request);
    state.loading = true;
    render();
    (whole ? read(company) : Promise.resolve(state.detail))
      .then(function (detail) {
        return read(company + '/page/' + want.tab).then(function (answer) {
          return { detail: detail, answer: answer, failed: null };
        }, function (err) {
          return {
            detail: detail, answer: null,
            failed: 'The company\'s data did not load: ' + err.message +
              '. Open the page again to retry.'
          };
        });
      })
      .then(function (found) {
        if (request !== latest) return;
        if (whole) state.answers = {};
        if (found.answer) state.answers[want.tab] = found.answer;
        state.symbol = want.symbol;
        state.tab = want.tab;
        state.detail = found.detail;
        state.failed = found.failed;
        state.error = null;
        state.loading = false;
        if (whole) P.followItem(asked(want.symbol), found.detail.item, render, load);
        render();
      })
      .catch(function (err) {
        if (request !== latest) return;
        state.symbol = want.symbol;
        state.tab = want.tab;
        state.detail = null;
        state.answers = {};
        state.failed = null;
        state.error = err.message;
        state.loading = false;
        render();
      });
  }

  function render() {
    root.render(page());
  }

  /* The link back, then the head, the tabs' row and the open tab; the detail's failure in the
     head's place; while the first read is out, the ticker as the hash names it. */
  function page() {
    var d = state.detail;
    var className = state.loading ? 'app-company is-loading' : 'app-company';
    if (state.error) {
      return h('div', { className: className }, back(), note(state.error));
    }
    if (!d) {
      return h('div', { className: className }, back(),
        h('h2', { className: 'ticker' }, P.company.symbol));
    }
    var answer = state.answers[state.tab] || null;
    return h('div', { className: className },
      back(),
      head(d, answer && answer.quote),
      tabs(state.symbol, state.tab, answer && answer.dataDate),
      tabBody(answer, d));
  }

  /* The way back: the Screen, as the report page's link opens it. */
  function back() {
    return h('p', { className: 'app-company__back' },
      h('a', {
        className: 'app-link', href: '#',
        onClick: function (event) { event.preventDefault(); P.show('screen'); }
      }, 'Back to the screen'));
  }

  /* Under the tabs' row: the tab's failed read in one sentence (7.5), else its blocks, drawn by
     the function a later script hangs on draw for the tab, on its answer and the detail, once
     both are in; nothing while either is missing. */
  function tabBody(answer, d) {
    if (state.failed) return note(state.failed);
    var drawn = P.companyPage.draw[state.tab];
    return answer && drawn ? drawn(answer, d) : null;
  }

  function note(text) { return h('p', { className: 'body app-note' }, text); }

  /* ------------------------------------------------------------------ the head */

  /* The head on every tab (7.2), from the company's detail `d`, and `quote`, the open tab's
     stored quote, null before its answer is in. Left: the logo on the drawer's tile at 40px
     (FairbandPage.logo), the name, the ticker, the phase badge, the moat stamp
     (FairbandPage.moatStamp), and one caption line, the exchange, the sector and the industry of
     the universe row, the parts it has. Right: the latest snapshot's price in figure-lg, in US
     dollars, the day's change, and the day of its close; then the watchlists control, which
     opens the screen's popup for this company under itself, and Request research, the report
     page's: its menu, its line and the following of its launch, with a request kept for the
     page's company. */
  function head(d, quote) {
    var r = d.result;
    var c = d.company || {};
    var phase = P.PHASE_NUMBER[r.phase.phase];
    var line = [c.exchange, c.sector, c.industry].filter(Boolean).join(' · ');
    return h('header', { className: 'app-company__head' },
      h('div', { className: 'app-company__id' },
        P.logo(d, 'app-company__logo'),
        h('div', { className: 'app-company__names' },
          h('div', { className: 'app-company__line' },
            c.name ? h('h1', { className: 'title app-company__name' }, c.name) : null,
            h('span', { className: 'ticker' }, r.symbol),
            phase ? h(F.PhaseBadge, { phase: phase, size: 'sm' }) : null,
            P.moatStamp(d)),
          line ? h('p', { className: 'caption app-company__sub' }, line) : null)),
      h('div', { className: 'app-company__side' },
        h('div', { className: 'app-company__quote' },
          h('p', { className: 'figure-lg' }, money(dollars(r.price))),
          change(r.price, quote),
          r.price_date
            ? h('p', { className: 'caption app-company__at' }, 'close ' + day(r.price_date))
            : null),
        h('div', { className: 'app-company__actions' },
          h(F.Button, {
            onClick: function (event) { P.watch({ ticker: r.symbol }, event.currentTarget); }
          }, 'Watchlists ▾'),
          P.requestResearch(asked(r.symbol), d.item, render, load, d.launchReady))));
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

  /* Request research's state for the page's company, kept until the page shows another. */
  function asked(symbol) {
    if (!state.request || state.request.symbol !== symbol) state.request = P.asking(symbol);
    return state.request;
  }

  /* ------------------------------------------------------------------ the tabs */

  /* The tabs' row (7.3, 7.4): Overview and Estimates, the open one selected, each opening through
     FairbandPage.show, which replaces the hash; Research, a link to the report page, the symbol
     encoded as the report page's links encode it; and at the row's right end the data date of
     the open tab's read, none without one. */
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
      h('a', {
        className: 'control app-company__tab', href: '#report/' + encodeURIComponent(symbol)
      }, 'Research'),
      dataDate ? h('p', { className: 'caption app-company__asof' }, 'data ' + day(dataDate))
        : null);
  }

  /* ---------------------------------------------------------- the blocks' parts */

  /* A block: its title in its head, with `right`, a caption or a control, at the head's right
     end, then `children`. */
  function panel(title, right, children) {
    return h('section', { key: title, className: 'app-company__panel' },
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

  /* A small table of figures: its head's cells in label, then its rows, each led by its name. */
  function table(head, rows) {
    return h('table', { className: 'app-company__table' },
      h('thead', null, h('tr', null, head.map(function (cell, i) {
        return h('th', { key: i, className: 'label' }, cell);
      }))),
      h('tbody', null, rows.map(function (row, i) {
        return h('tr', { key: i }, row.map(function (cell, j) {
          return h('td', { key: j, className: j ? 'figure' : 'body app-company__rowname' }, cell);
        }));
      })));
  }

  /* ------------------------------------------------------------- the figures */

  /* The figures' words (14.1). A money figure is { value, currency } as the reads give it, in US
     dollars with `$` and in another currency with its code in `$`'s place; a missing figure is an
     em dash, and so is a multiple at exactly 0. */
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

  /* Money to cents: $356.27, TWD 120.00, −$1.20. */
  function money(m) {
    if (!m || !ok(m.value)) return '—';
    return minus(unit(m) + fixed(Math.abs(m.value), 2), m.value);
  }

  /* A large amount, compact: $5.18T, TWD 4.94T, $478.8B; a bare count, a number not money, with
     no mark: 14.53B, 39.1M, 167,000. */
  function big(m) {
    var isMoney = m !== null && typeof m === 'object';
    var v = isMoney ? m.value : m;
    if (!ok(v)) return '—';
    var a = Math.abs(v);
    var size = a >= 1e12 ? fixed(a / 1e12, 2) + 'T'
      : a >= 1e9 ? fixed(a / 1e9, a >= 1e11 ? 1 : 2) + 'B'
        : a >= 1e6 ? fixed(a / 1e6, 1) + 'M' : fixed(a, 0);
    return minus((isMoney ? unit(m) : '') + size, v);
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

  /* A day: 13 Nov 2026. */
  function day(iso) { return iso ? F.formatDate(String(iso).slice(0, 10)) : '—'; }

  /* A count, grouped: 167,000. */
  function count(n) { return ok(n) ? minus(fixed(Math.abs(n), 0), n) : '—'; }

  /* -------------------------------------------------------------------- the reads */

  /* A read whose refusal is the server's sentence, as it arrives. The page's reads are plain
     GETs: none calls a vendor. */
  function read(url) {
    return fetch(url).then(function (response) {
      return response.ok ? response.json() : refused(response);
    });
  }

  function refused(response) {
    return response.json().catch(function () { return null; }).then(function (body) {
      throw new Error(body && typeof body.detail === 'string' ? body.detail
        : 'the server answered ' + response.status);
    });
  }

  /* What the tabs' scripts and the tests use: the head, the tabs' row, a panel, a list of names
     and figures, a group, a small table and the formatters; and draw, which each tab's script
     fills with its tab's function, draw.overview(answer, detail) and draw.estimates(answer,
     detail), each returning the tab's element. */
  P.companyPage = {
    head: head, tabs: tabs, panel: panel, kv: kv, group: group, table: table,
    money: money, big: big, percent: percent, points: points, signed: signed,
    multiple: multiple, day: day, count: count,
    draw: {}
  };
  P.onShow.company = load;
})();
