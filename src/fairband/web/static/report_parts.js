/* A report's parts after its sections (spec 2026-11-06 Tier 2, 13.1 and 18.4), loaded after
   methodology.js and before report.js, for the report page (report.js) and the company page's
   Research tab (company_research.js), which draw them alike (the Research tab's design, 7.8 and
   9): the references those numbers name, Appendix A, the audit of the records the report rests
   on, and Appendix B, the glossary, both as the server generates them; and Download .md, the
   report's Markdown saved as a file. Each is a pure builder of the report, apart from the
   download, which fetches; app.js's parts come through window.FairbandPage. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  /* An override inside the report's review whose step gives no effect: the review refused. */
  var NO_EFFECT = 'No effect to show: the review it is inside has no value';

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
     report rests on; every input, as the inputs table draws one; the review's bridge;
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

  /* An Appendix A input as the inputs table reads a result's: its provenance's source
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

  /* The secondary valuation (spec 11): its form, its value a share and its levels; for a
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

  /* Appendix A's classifier evidence as phaseEvidence reads a result's phase. */
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

  /* ------------------------------------------------------------------ the controls */

  /* Download .md: the report's Markdown (spec 13.6) fetched and saved as a file; a refusal is
     handed to `failed` as one sentence with the server's, which the caller draws under its line. */
  function download(report, failed) {
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
        failed('The Markdown did not download: ' + err.message + '.');
      });
  }

  /* A refusal as the server's sentence, as it arrives. */
  function refused(response) {
    return response.json().catch(function () { return null; }).then(function (body) {
      throw new Error(body && typeof body.detail === 'string' ? body.detail
        : 'the server answered ' + response.status);
    });
  }

  function none(text) { return h('p', { className: 'caption app-muted' }, text); }

  /* What the report page and the Research tab draw: the references, Appendix A and Appendix B of
     a report, each its element, and download(report, failed); and Appendix A's overrides and its
     Snapshot line, which the node tests read (tests/web/test_report_reader.py), as charts.js
     hangs its helpers, also as reportAppendix, their name before this script. */
  P.reportParts = {
    references: references, appendixA: appendixA, appendixB: appendixB, download: download,
    overrides: overrides, snapshotLine: snapshotLine
  };
  P.reportAppendix = { overrides: overrides, snapshotLine: snapshotLine };
})();
