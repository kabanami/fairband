/* The report page (spec 2026-11-06 Tier 2, 18.4), loaded after controls.js: a view at
   #report/<symbol>, the company's latest published report, and #report/<symbol>/<id>, a revision,
   in the design system's CompanyReport order. The head: the ticker, the name, the phase badge and
   the page's one headline figure, the reviewed value where the review on the latest snapshot has
   one, else the mechanical, with the price beside it; the meter as the drawer draws it. Above the
   reader, the report's stance, mode, date, writer and revision, Download .md, the page's one table
   toggle and the other revisions by number and by date and time. Then ReportReader with every
   section, each cited number followed by its footnote number (13.1) and the charts of the
   sections that have them above their sentences (18.4), the references those numbers name,
   Appendix A, the audit of the records the report rests on, and Appendix B, the glossary, both
   as the server generates them; a link back to the screen. The page shows Request research with
   or without a report, as the drawer has it: under the revisions line, or under the head, the
   meter and "No report yet." for a company with none. The drawer's own parts come through
   window.FairbandPage; the head and the meter read the company's detail, as the drawer does, and
   the rest the report. The charts read the series the sections cite once the report is in, and
   charts.js draws them. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  /* An override inside the report's review whose step gives no effect: the review refused. */
  var NO_EFFECT = 'No effect to show: the review it is inside has no value';

  var panel = document.getElementById('report');
  var root = ReactDOM.createRoot(panel);
  var state = {
    symbol: null, /* the company whose page is shown */
    detail: null, /* GET /api/companies/{symbol}: the head and the meter */
    reports: null, /* the company's revisions, newest first, without their sections */
    report: null, /* the report shown, whole; null for a company with none */
    loading: false,
    error: null,
    tables: false, /* the page's one table toggle (CompanyReport): every chart's table view */
    series: null, /* the series the charts read (readSeries), each by its key as it lands */
    request: null, /* Request research for the page's company (FairbandPage.asking) */
    downloadError: null
  };
  var latest = 0;

  /* The page FairbandPage.report names: the company's detail and its revisions, then the revision
     the hash names, else the latest. The page shown stays, faded, until the new one lands, and the
     latest read wins. A revision of another company is refused, so the page never shows one
     company's report under another's head. A read of another company stops the following of the
     request of the company shown before it starts, so a read that fails leaves none running, and
     the page starts a request of its own as the read lands; each read that lands goes to
     FairbandPage.followItem, so the page follows the open item's launch while it is in flight
     (spec 2026-11-16 agent launch, 10). */
  function load() {
    var want = P.report;
    var request = ++latest;
    var company = '/api/companies/' + encodeURIComponent(want.symbol);
    if (state.request && state.request.symbol !== want.symbol) P.stopLaunch(state.request);
    state.loading = true;
    render();
    Promise.all([read(company), read(company + '/reports')])
      .then(function (got) {
        var listed = got[1].reports;
        var id = want.id != null ? want.id : listed.length ? listed[0].id : null;
        return (id == null ? Promise.resolve(null) : read('/api/reports/' + id))
          .then(function (report) { return { detail: got[0], reports: listed, report: report }; });
      })
      .then(function (found) {
        if (request !== latest) return;
        var report = found.report;
        if (report && report.symbol !== want.symbol) {
          throw new Error('report ' + report.id + ' is ' + report.symbol + '\'s, not ' +
            want.symbol + '\'s');
        }
        if (state.symbol !== want.symbol) state.request = P.asking(want.symbol);
        if (!report || !state.report || state.report.id !== report.id) state.series = null;
        state.symbol = want.symbol;
        state.detail = found.detail;
        state.reports = found.reports;
        state.report = report;
        state.loading = false;
        state.error = null;
        state.downloadError = null;
        P.followItem(state.request, found.detail.item, render, load);
        render();
        if (report) readSeries(report, request);
      })
      .catch(function (err) {
        if (request !== latest) return;
        state.loading = false;
        state.error = 'The report page for ' + want.symbol + ' did not load: ' + err.message + '.';
        render();
      });
  }

  function render() {
    root.render(page());
  }

  /* The series the report's charts read (spec 18.4), each on its own, its body or the server's
     sentence why not: the six financial tables, the multiples history, the closes of the five
     years, the band's history and each sensitivity reading the sections cite, once, in the order
     first cited, the company's own. Each lands in state.series as it settles and the page draws
     again, so the charts of the local reads never wait for the multiples history, whose trailing
     series may wait on GuruFocus. The charts of the same report stay as they are until their new
     series land; the latest read wins. */
  function readSeries(report, request) {
    var company = '/api/companies/' + encodeURIComponent(report.symbol);
    var land = function (key) {
      return function (got) {
        if (request !== latest) return;
        var next = {};
        Object.keys(state.series || {}).forEach(function (k) { next[k] = state.series[k]; });
        next[key] = got;
        state.series = next;
        render();
      };
    };
    settle(read(company + '/financial-tables')).then(land('tables'));
    settle(read(company + '/multiples-history')).then(land('multiples'));
    settle(read(company + '/price-history?years=5')).then(land('closes'));
    settle(read(company + '/band-history')).then(land('band'));
    Promise.all(cited(report.references).map(function (id) {
      return settle(read('/api/sensitivities/' + id));
    })).then(function (got) {
      land('readings')(got.filter(function (r) {
        return r.error || r.body.symbol === report.symbol;
      }));
    });
  }

  /* A read as its body, or the server's sentence why not. */
  function settle(reading) {
    return reading.then(function (body) { return { body: body }; },
      function (err) { return { error: err.message }; });
  }

  /* The ids of the sensitivity readings the references name, once each, in the order first
     cited, as the export reads them. */
  function cited(references) {
    var ids = [];
    references.forEach(function (e) {
      var found = /^sensitivity:(\d+)(\/|$)/.exec(String(e.ref).trim());
      if (found && ids.indexOf(found[1]) === -1) ids.push(found[1]);
    });
    return ids;
  }

  /* CompanyReport's order: the head, the company brief (B-149), the meter, then the report with
     the line above it and Request research under that line (plan 4), its references and its
     appendixes; without a report, a note and Request research. The link back closes it. */
  function page() {
    var d = state.detail;
    var report = state.report;
    var shown;
    if (state.error) shown = h('p', { className: 'body app-note' }, state.error);
    else if (!d) shown = h('h2', { className: 'ticker app-report__ticker' }, P.report.symbol);
    else {
      shown = [head(d), brief(d), band(d)].concat(report ? [
        meta(d, report), reader(report), references(report), appendixA(report), appendixB(report)
      ] : [noReport(d)]);
    }
    return h('div', { className: state.loading ? 'app-report is-loading' : 'app-report' },
      shown, back());
  }

  /* ----------------------------------------------------------------- the head */

  /* The company's logo where it has one (FairbandPage.logo, B-203), the ticker, the name and the
     phase badge, and under them, for a company in another currency or an ADR, what its figures
     are in (FairbandPage.currencyLine, spec 2026-11-10 6.2 and 7.4:
     "Reports in TWD; one ADS is five ordinary shares; every per-share figure here is per ADS;
     valued at TWD 32.96 per USD"); then the one headline figure, the page's only figure-lg
     (CompanyReport's one hero), and the price beside it in figure, both in US dollars. */
  function head(d) {
    var r = d.result;
    var phase = P.PHASE_NUMBER[r.phase.phase];
    var value = headline(d);
    return h('header', { key: 'head', className: 'app-report__head' },
      h('div', { className: 'app-report__id' },
        P.logo(d, 'app-report__logo'),
        h('h2', { className: 'ticker app-report__ticker' }, r.symbol),
        d.company && d.company.name
          ? h('p', { className: 'title app-report__name' }, d.company.name) : null,
        phase ? h(F.PhaseBadge, { phase: phase }) : null,
        P.currencyLine(d, true) ? h('p', { className: 'caption app-muted app-report__currency' },
          P.currencyLine(d, true)) : null),
      h('div', { className: 'app-report__figures' },
        value ? h(F.ValueCell, {
          value: value.value, basis: value.basis, emphasis: 'strong', align: 'left'
        }) : null,
        value && value.note ? h('span', { className: 'caption app-muted' }, value.note) : null,
        h('span', { className: 'app-report__price' },
          h('span', { className: 'caption app-muted' }, 'price '),
          h('span', { className: 'figure' }, F.formatMoney(r.price)))));
  }

  /* The headline: the reviewed value where the review on the latest snapshot has one, else the
     mechanical value; on a refused row whose secondary valuation counts, its value a share above
     zero, as the screen's Reviewed column shows it (18.1) and the meter draws its band, its basis
     reviewed, an agent's inputs inside, and named; none on a refused row without one. */
  function headline(d) {
    var r = d.result;
    var s = d.secondary;
    if (d.review && d.review.value != null) return { value: d.review.value, basis: 'reviewed' };
    if (r.value != null) return { value: r.value, basis: 'mechanical' };
    if (s && s.valuePerShare > 0) {
      return { value: s.valuePerShare, basis: 'reviewed', note: 'secondary valuation' };
    }
    return null;
  }

  /* The company brief (B-149) under the head: the stored profile's description, whole, as the
     drawer shows it under About; nothing without one. */
  function brief(d) {
    return d.brief ? h('p', { key: 'brief', className: 'body app-report__brief' }, d.brief)
      : null;
  }

  /* The meter as the drawer draws it (FairbandPage.meter), its price in figure under the head's
     one figure-lg; a refused row's refusal under it, as the drawer has it in the meter's place.
     Above it, what the price needs when it is well above the value (FairbandPage.priceNeeds,
     method 4.11). */
  function band(d) {
    var r = d.result;
    return h('section', { key: 'band', className: 'app-report__band' },
      P.priceNeeds(d),
      P.meter(d, false),
      r.refusal ? h('p', { className: 'body app-refusal' }, r.refusal) : null);
  }

  /* --------------------------------------------------------- the line above it */

  /* Above the reader (18.4): the report's stance in the drawer's chip classes, faded once the
     window of the snapshot it rests on has ended (rows.window_ended's rule), its title then saying
     so in the register's words (spec 2026-11-15 7); its mode, its date,
     who wrote it and its revision; Download .md and the page's one table toggle. Under it, that a
     valuation review has no full report to reuse, when it has none; the other revisions by number
     and by date and time; Request research, the drawer's own with this page's request, as on a
     company with no report (plan 4); a download's refusal. */
  function meta(d, report) {
    var expired = report.appendixA.snapshot.validUntil < d.today;
    return h('div', { key: 'meta', className: 'app-report__meta' },
      h('div', { className: 'app-report__line' },
        h('span', {
          className: 'fb-stance fb-stance--' + report.stance +
            (expired ? ' fb-stance--expired' : '') + ' label',
          title: expired ? 'The value of this report is past the date it was valid until' : null
        }, report.stance),
        h('span', { className: 'label app-report__mode' }, report.mode),
        h('span', { className: 'caption' }, P.when(report.createdAt)),
        h(F.PrincipalChip, { principal: report.principal, actor: report.actor }),
        h('span', { className: 'figure-sm' }, 'revision ' + report.revision),
        h('span', { className: 'app-report__actions' },
          h(F.Button, { size: 'sm', onClick: download }, 'Download .md'),
          h(F.Button, {
            size: 'sm', variant: 'quiet', onClick: toggleTables,
            'aria-pressed': state.tables ? 'true' : 'false'
          }, 'Tables'))),
      report.mode === 'valuation review' && report.reusesFullReportOf == null
        ? h('p', { className: 'caption app-report__note' }, 'No full report to reuse.') : null,
      revisions(report),
      P.requestResearch(state.request, d.item, render, load, d.launchReady),
      state.downloadError
        ? h('p', { className: 'caption app-report__error' }, state.downloadError) : null);
  }

  /* The company's other revisions by number and by date and time, newest first, each a link to
     its page: those after the one shown, when it is an earlier revision, then those before it. */
  function revisions(report) {
    var listed = state.reports || [];
    var later = listed.filter(function (r) { return r.revision > report.revision; });
    var earlier = listed.filter(function (r) { return r.revision < report.revision; });
    if (!later.length && !earlier.length) return null;
    return h('p', { className: 'caption app-report__revisions' },
      later.length ? dated('Later revisions: ', report, later) : null,
      later.length && earlier.length ? ' · ' : null,
      earlier.length ? dated('Earlier revisions: ', report, earlier) : null);
  }

  /* A group's title, then its links joined by a middle dot, as the page's captions join, since
     each link's own text holds commas (plan 4). */
  function dated(title, report, list) {
    return h(React.Fragment, null, title, list.map(function (r, i) {
      return h(React.Fragment, { key: r.id }, i ? ' · ' : null, revisionLink(report, r));
    }));
  }

  /* A revision's link, named by its number and its date and time in the reader's local time
     ("revision 1, 8 Nov 2026, 07:24"), since two revisions on one day read the same by date
     alone (18.4, plan 4). P.when gives the time as its element, so it follows the text as a
     child, not joined to it. */
  function revisionLink(report, r) {
    return h('a', {
      className: 'app-link', href: '#report/' + encodeURIComponent(report.symbol) + '/' + r.id
    }, 'revision ' + r.revision + ', ', P.when(r.createdAt));
  }

  /* ------------------------------------------------------------------ the report */

  /* Every section, each cited number followed by its footnote number in the references (13.1),
     and the charts of the sections that have them under their headings (18.4, charts.js); the
     line under the title says what the report rests on in the reader's words, the data's date,
     the price's, the end of the validity window and, for a valuation review, the date of the full
     report it reuses, and names no record, whose ids Appendix A gives (spec 2026-11-15 7). The
     appendixes follow on the page, so the reader's own pointer to them is off. */
  function reader(report) {
    var s = report.appendixA.snapshot;
    return h(F.ReportReader, {
      key: 'reader',
      mode: report.mode, state: 'published', revision: 'revision ' + report.revision,
      cites: {
        dataDate: s.dataDate, priceDate: s.priceDate, validUntil: s.validUntil,
        reusesFullReportOf: reusedDate(report)
      },
      sections: report.sections, footnotes: P.footnotes(report.references), appendixes: false,
      charts: P.reportCharts.draw(report, state.series, state.tables)
    });
  }

  /* The day of the full report a valuation review reuses, from the company's revisions. */
  function reusedDate(report) {
    var reused = (state.reports || []).filter(function (r) {
      return r.id === report.reusesFullReportOf;
    })[0];
    return reused ? P.localIso(reused.createdAt).slice(0, 10) : undefined;
  }

  /* The references, once, after the last section and before Appendix A (13.1): each numbered in
     the order it is first cited, [n], and its source in words, the ref in its title. */
  function references(report) {
    var refs = report.references;
    return h('section', { key: 'refs', className: 'app-report__panel' },
      h('h3', { className: 'title' }, 'References'),
      refs.length ? h('ol', { className: 'app-report__notes body' }, refs.map(function (e) {
        return h('li', { key: e.n, title: e.ref },
          h('span', { className: 'figure-sm app-report__n' }, '[' + e.n + ']'), ' ', e.source);
      })) : none('No references.'));
  }

  /* ------------------------------------------------------------- the appendixes */

  /* Appendix A, the audit, as the server generates it from the records (13.1): the snapshot the
     report rests on; every input, as the drawer's inputs table draws one; the review's bridge;
     the overrides inside the review; the secondary valuation; the guidance on file; the checks
     that ran; the versions; the classifier's evidence. */
  function appendixA(report) {
    var a = report.appendixA;
    var s = a.snapshot;
    return h('section', { key: 'a', className: 'app-report__panel' },
      h('h3', { className: 'title' }, 'Appendix A'),
      part('Snapshot', snapshotLine(s),
        s.refusal ? h('p', { className: 'body app-refusal' }, s.refusal) : null),
      part('Inputs', P.inputsTable(a.inputs.map(input))),
      part('Bridge', bridge(a)),
      part('Overrides', a.overrides.length ? overrides(a) : none('None.')),
      part('Secondary valuation', secondary(a)),
      part('Guidance on file', a.guidance.length
        ? P.guidanceTable(a.guidance, a.snapshot.currency) : none('None.')),
      part('Checks that ran', h('ul', { className: 'app-list' }, a.checks.map(function (c) {
        return h('li', { key: c.check },
          h('span', { className: 'label' }, c.check),
          h('p', { className: 'body' }, c.rule));
      }))),
      part('Versions', versions(a.versions)),
      part('Classifier evidence', P.phaseEvidence(classifier(a.classifier))));
  }

  /* One part of an appendix under its heading. */
  function part(title) {
    return h.apply(null, ['section', { key: title, className: 'app-report__part' },
      h('h4', { className: 'heading' }, title)].concat(Array.prototype.slice.call(arguments, 1)));
  }

  /* The snapshot: its id, its data date, its price date, the end of its window, its price and its
     value a share, and on a company in another currency the reporting currency its money figures
     are in, last; the export's Appendix A opens with the same line, but for its thousands
     separator from $1,000 up (render.py, `_snapshot_line`; method 16.6). */
  function snapshotLine(s) {
    var code = s.currency && s.currency !== 'USD' ? s.currency : null;
    return h('p', { className: 'body' },
      'Snapshot ', h('span', { className: 'figure-sm' }, s.id),
      ' · data ', P.when(s.dataDate), ' · priced ', P.when(s.priceDate),
      ' · valid until ', P.when(s.validUntil),
      ' · price ', h('span', { className: 'figure-sm' }, F.formatMoney(s.price)),
      ' · value ', h('span', { className: 'figure-sm' }, F.formatMoney(s.value)),
      code ? ' · in ' + code : null);
  }

  /* An Appendix A input as the drawer's inputs table reads a result's: its provenance's source
     and its three dates; a date input's note, its date as an ISO day (the next earnings date), in
     words, as the page writes its dates and the export that note (spec 2026-11-15 7). */
  function input(i) {
    var day = i.unit === 'date' && /^\d{4}-\d{2}-\d{2}$/.test(String(i.note));
    return {
      name: i.name, value: i.value, unit: i.unit, tag: i.tag, kind: i.kind,
      estimate_method: i.estimateMethod, note: day ? F.formatDate(i.note) : i.note,
      provenance: {
        source: i.source, as_of: i.asOf, observed_at: i.observedAt, entered_at: i.enteredAt
      }
    };
  }

  /* The review's bridge from the mechanical value (spec 10.4) when the review has a value: each
     line under its input's label, from and to in the input's unit, with its override's reason and
     writer; else its refusal. Without a review the mechanical value is the value, when the
     snapshot has one; a refused snapshot has none. */
  function bridge(a) {
    var b = a.bridge;
    if (!b) {
      return none(a.snapshot.value == null ? 'No review.'
        : 'No review: the value is the mechanical one.');
    }
    if (b.reviewedValue == null) {
      return h('p', { className: 'body app-refusal' }, b.refusal || 'The review has no value.');
    }
    var by = byId(a.overrides);
    return h(F.ValueBridge, {
      mechanical: b.mechanicalValue, reviewed: b.reviewedValue, hero: false,
      overrides: b.lines.map(function (line) {
        var o = by[line.overrideId] || {};
        return {
          tag: line.label,
          from: P.inputFigure(line.old, o.unit), to: P.inputFigure(line.new, o.unit),
          delta: line.delta == null ? undefined : line.delta,
          principal: o.principal, actor: o.actor, reason: o.reason
        };
      }),
      note: 'Review ' + b.reviewId
    });
  }

  function byId(records) {
    var found = {};
    records.forEach(function (o) { found[o.id] = o; });
    return found;
  }

  /* The overrides inside the review, each a record, read-only: no one adds or drops an override
     here (spec 3). Each is applied; its effect is its step in the bridge when the review has a
     value, with the reviewed value and the end of the snapshot's window; else its step's refusal,
     or that the review has no value. One the review applied at a figure other than the one
     entered, because a split fell between (method 14.6), shows the review's pair in force, both on
     the new basis, with the words of the scaling under the record as the server sends them
     ("entered as $30.00 a share before the 2-for-1 split of 27 Jan 2027"); any other its stored
     pair (spec 2026-11-15 8). */
  function overrides(a) {
    var b = a.bridge;
    return a.overrides.map(function (o) {
      var line = b ? b.lines.filter(function (l) { return l.overrideId === o.id; })[0] : null;
      var effect = line && line.delta != null && b.reviewedValue != null ? line.delta : undefined;
      var pair = o.inForce || o;
      return h(React.Fragment, { key: o.id },
        h(F.OverrideRecord, {
          tag: o.tag, from: P.inputFigure(pair.old, o.unit), to: P.inputFigure(pair.new, o.unit),
          lifetime: o.lifetime, period: o.period, reason: o.reason, evidence: o.evidence,
          principal: o.principal, actor: o.actor,
          state: 'applied',
          effect: effect,
          reviewed: effect === undefined ? undefined : b.reviewedValue,
          validUntil: effect === undefined ? undefined : a.snapshot.validUntil,
          resultNote: effect === undefined ? (line && line.refusal) || NO_EFFECT : undefined
        }),
        o.rescaled ? h('p', { className: 'caption app-report__entered' }, o.rescaled) : null);
    });
  }

  /* The secondary valuation (spec 11): its form and value a share as Details lists them; for a
     company in another currency, the rate it ran at (spec 2026-11-10 7.6), its totals being in the
     currency and its value a share in US dollars; the walk to equity, the agent's reason, its
     drivers in words or its parts, then its projection year by year. Without one, the server's
     sentence why, as it arrives, or none. */
  function secondary(a) {
    var s = a.secondary;
    if (!s) return none(a.noSecondary || 'None.');
    var code = s.currency;
    return h(React.Fragment, null,
      P.pairs(P.secondaryRows(s).concat(
        code !== 'USD' ? [['Rate', code + ' ' + P.rate(s.fxRate) + ' per USD', true]] : [],
        [
          ['Firm value', P.whole(s.firmValue, code), true],
          ['Less debt', P.whole(s.debt, code), true],
          ['Plus cash', P.whole(s.cash, code), true],
          ['Equity', P.whole(s.equity, code), true],
          ['Shares', P.plain(s.shares), true],
          ['Debt and cash from', s.debtSource + ', ' + s.cashSource, false]
        ])),
      s.reason ? h('p', { className: 'body' }, s.reason) : null,
      P.secondaryPath(s, code),
      s.form === 'drivers' ? projection(s, code) : partsYears(s, code));
  }

  /* The drivers form's projection: a row a year, the revenue, EBIT, NOPAT, reinvestment, free cash
     flow and its present value, totals in whole units of `code`; then the terminal. */
  function projection(s, code) {
    var p = s.projection;
    var total = function (v) { return P.whole(v, code); };
    if (!p) return null;
    return h(React.Fragment, null,
      P.figuresTable([
        ['Revenue', column(p.years, 'revenue'), total],
        ['EBIT', column(p.years, 'ebit'), total],
        ['NOPAT', column(p.years, 'nopat'), total],
        ['Reinvestment', column(p.years, 'reinvestment'), total],
        ['FCFF', column(p.years, 'fcff'), total],
        ['PV', column(p.years, 'pv'), total]
      ]),
      P.pairs([
        ['Trailing revenue', total(p.trailingRevenue), true],
        ['Terminal return', F.formatPercent(p.terminalReturn), true],
        ['Terminal free cash flow', total(p.terminalFcff), true],
        ['Terminal value at year ' + s.drivers.years, total(p.terminal), true],
        ['Its present value', total(p.terminalPv), true]
      ]));
  }

  /* The parts form: each part's free cash flow and its present value a year, then its terminal,
     totals in whole units of `code`. */
  function partsYears(s, code) {
    var total = function (v) { return P.whole(v, code); };
    return s.parts.map(function (p, i) {
      return h('div', { key: i, className: 'app-group' },
        h('h5', { className: 'label app-group__head' }, p.name),
        P.figuresTable([
          ['FCFF', column(p.years, 'fcff'), total],
          ['PV', column(p.years, 'pv'), total]
        ]),
        P.pairs([
          ['Terminal growth', F.formatPercent(p.terminalGrowth), true],
          ['Terminal value', total(p.terminal), true],
          ['Its present value', total(p.terminalPv), true]
        ]));
    });
  }

  function column(years, key) {
    return years.map(function (y) { return y[key]; });
  }

  /* The versions the report's records were made under. */
  function versions(v) {
    var named = ['Method ' + v.method, 'policy ' + v.policy, 'settings ' + v.settingsHash];
    if (v.review) named.push('review ' + v.review);
    if (v.secondary) named.push('secondary ' + v.secondary);
    return h('p', { className: 'caption app-muted' }, named.join(' · '));
  }

  /* Appendix A's classifier evidence as the drawer's Phase evidence reads a result's phase. */
  function classifier(c) {
    return {
      phase: c.phase, reason: c.reason, growth_3y: c.growth3Y, growth_word: c.growthWord,
      growth_decile: c.growthDecile, margin: c.margin, margin_slope: c.marginSlope,
      margin_direction: c.marginDirection, fcf_sign: c.fcfSign, dickinson: c.dickinson,
      checks: c.checks.map(function (word) { return { word: word }; })
    };
  }

  /* Appendix B, the glossary (13.1): the terms the sections use, each with its meaning. */
  function appendixB(report) {
    var b = report.appendixB;
    return h('section', { key: 'b', className: 'app-report__panel' },
      h('h3', { className: 'title' }, 'Appendix B'),
      b.length ? h('dl', { className: 'app-report__glossary' }, b.map(function (t) {
        return h(React.Fragment, { key: t.term },
          h('dt', { className: 'heading' }, t.term),
          h('dd', { className: 'body' }, t.meaning));
      })) : none('No terms used.'));
  }

  /* The way back: the Screen, as its header view opens it. */
  function back() {
    return h('p', { className: 'app-report__back' },
      h('a', {
        className: 'app-link', href: '#',
        onClick: function (event) { event.preventDefault(); P.show('screen'); }
      }, 'Back to the screen'));
  }

  /* -------------------------------------------------------------- without a report */

  /* A company with no published report (18.4): a note and Request research, the drawer's own,
     with this page's request; posted, the page reads the company again, so the open item's line
     follows. */
  function noReport(d) {
    return h('section', { key: 'none', className: 'app-report__none' },
      h('p', { className: 'body app-note' }, 'No report yet.'),
      P.requestResearch(state.request, d.item, render, load, d.launchReady));
  }

  /* ------------------------------------------------------------------ the controls */

  /* Download .md: the report's Markdown (spec 13.6) fetched and saved as a file; a refusal shows
     the server's sentence under the line. */
  function download() {
    var report = state.report;
    state.downloadError = null;
    render();
    fetch('/api/reports/' + report.id + '/markdown')
      .then(function (response) { return response.ok ? response.blob() : refused(response); })
      .then(function (blob) {
        var link = document.createElement('a');
        var url = URL.createObjectURL(blob);
        link.href = url;
        link.download = report.symbol + '-revision-' + report.revision + '.md';
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 0);
      })
      .catch(function (err) {
        state.downloadError = 'The Markdown did not download: ' + err.message + '.';
        render();
      });
  }

  /* The page's one table toggle (CompanyReport): it flips every chart to its table and back, and
     says whether it is on. */
  function toggleTables() {
    state.tables = !state.tables;
    render();
  }

  /* -------------------------------------------------------------------- the reads */

  /* A read whose refusal is the server's sentence, as it arrives. Every read carries the request
     header, as the page's writes do: the server refuses without it a read that may call a vendor,
     the multiples history's (D11, B-109), so no other site's page can spend GuruFocus's quota. */
  function read(url) {
    return fetch(url, { headers: { 'X-Fairband-Request': '1' } }).then(function (response) {
      return response.ok ? response.json() : refused(response);
    });
  }

  function refused(response) {
    return response.json().catch(function () { return null; }).then(function (body) {
      throw new Error(body && typeof body.detail === 'string' ? body.detail
        : 'the server answered ' + response.status);
    });
  }

  function none(text) { return h('p', { className: 'caption app-muted' }, text); }

  /* Appendix A's overrides and its Snapshot line, which the node tests read
     (tests/web/test_report_reader.py), as charts.js hangs its helpers. */
  P.reportAppendix = { overrides: overrides, snapshotLine: snapshotLine };
  P.onShow.report = load;
})();
