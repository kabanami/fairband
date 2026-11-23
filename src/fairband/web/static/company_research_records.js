/* The company page's Research tab, its Records view (the Research tab's design, 7.10), loaded
   after company_research.js, whose tab calls it as it draws: the company's records on file,
   whatever report wrote them, from the tab's read's `records` (GET
   /api/companies/{symbol}/page/research). One panel a kind, in the design's order: Kill criteria,
   Guidance, Overrides, Notes, Reviews, Secondary valuations, News items, Findings and Ledger; each
   its name and its count over a table of its records, newest first as the read serves them, the
   news items by their date, newest first, as the news card orders them; "None on file." where it
   holds none. The judgments have no panel: a judgment belongs to its report, whose Key judgments
   panel draws it. The ledger holds the company's newest twenty rows, and its head says so with
   the count on file, "the newest 20 of 192", where more are on file than it draws. A press on a
   review's row draws its bridge under it, the design system's ValueBridge from the mechanical
   value to the review's, each line under its label with its figures in its input's unit, as the
   read gives them, or the review's refusal where it has no value; a second press closes it.

   It draws the stored records and the read's fields and computes no figure: money a share by
   Fairband.formatMoney, an input's figure by FairbandPage.inputFigure, a guidance record's as the
   guidance table writes them (FairbandPage.guided, in the record's currency), a finding's in its
   unit and currency, a day by companyPage.day, a time by FairbandPage.when; a figure a record
   lacks is a dash. It writes nothing: no override, no kill criterion's state, no note.

   What the tab and the tests use, on FairbandPage.researchRecords: panels(records), the nine
   panels as plain data, which the tests read in node, each { name, count, note, heads, rows }, a
   row { key, cells } and a review's its `bridge` too, ValueBridge's props or { refusal }, a cell
   { text, kind } with `at`, a time's instant, `href`, a link's address, or `designation`, the
   word's code; count(records), the rows the panels draw, the count beside Records in the bar; and
   draw(records, open, press), the view, the review `open` names with its bridge under it, a press
   on a review's row handed to press(id). */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var C = P.companyPage;

  var NONE = 'None on file.';
  var DASH = '—';
  var WEB = /^https?:\/\//i; /* an address a headline links to, as the news card's */

  /* -------------------------------------------------------------------------------- the cells */

  /* A cell of `text` drawn as `kind`: text, the record's words; muted, its words in ink-muted;
     figure, a figure set right; when, a day or a period in ink-muted; stamp, a state in an
     outlined stamp; input, an override's input as its tag; designation and refusal, a review's
     word or its refusal. */
  function cell(text, kind, more) {
    var c = { text: text == null || text === '' ? DASH : String(text), kind: kind };
    return more ? Object.assign(c, more) : c;
  }

  /* A time, the instant `at`, as FairbandPage.when writes it: its day and its hour in the
     reader's local time. */
  function time(at) {
    return cell(at ? F.formatDate(P.localIso(at)) : DASH, 'when', at ? { at: at } : null);
  }

  /* The day of a time, `at`, in the reader's local time, or of a date as it is. */
  function day(at) { return cell(C.day(P.localIso(at)), 'when'); }

  function money(v) { return cell(F.formatMoney(v), 'figure'); }

  /* ------------------------------------------------------------------------------- the panels */

  /* The nine panels of `records` (module comment), in the design's order. */
  function panels(records) {
    var r = records || {};
    var ledger = r.ledger || [];
    return [
      panel('Kill criteria', ['State', 'The thesis is wrong if', 'Set', 'Moved, and why'],
        r.killCriteria, criterion),
      panel('Guidance', ['Metric', 'Period', 'Range', 'Midpoint', 'Basis', 'Call of', 'State'],
        r.guidance, guidance),
      panel('Overrides', ['Input', 'From', 'To', 'State', 'The reason'], r.overrides, override),
      panel('Notes', ['When', 'The note'], r.notes, note),
      panel('Reviews',
        ['When', 'Value', 'Mechanical value', 'Overrides inside', 'Price vs value, or the refusal'],
        r.reviews, reviewOf(r.reviews)),
      panel('Secondary valuations', ['When', 'Form', 'Value a share', 'The reason'],
        r.secondaryValuations, secondary),
      panel('News items', ['Date', 'Headline', 'What happened'], newest(r.newsItems), news),
      panel('Findings', ['As of', 'Period', 'Figure', 'The words', 'Source'], r.findings, finding),
      panel('Ledger', ['When', 'Kind', 'What was written', 'By'], ledger, entry,
        r.ledgerCount > ledger.length
          ? 'the newest ' + C.count(ledger.length) + ' of ' + C.count(r.ledgerCount) : null)
    ];
  }

  /* A panel of `list`'s records, each a row by `row`, its count the rows it draws, and the words
     its head adds, `more`, where given. */
  function panel(name, heads, list, row, more) {
    var rows = (list || []).map(function (record) { return row(record); });
    return { name: name, count: rows.length, note: more || null, heads: heads, rows: rows };
  }

  /* The news items by their date, newest first, the newer record first on a day. */
  function newest(items) {
    return (items || []).slice().sort(function (a, b) {
      return a.date < b.date ? 1 : a.date > b.date ? -1 : b.id - a.id;
    });
  }

  /* A kill criterion: its state, its text, the day it was set and, once it moved, that day with
     its reason. */
  function criterion(k) {
    var moved = k.stateAt
      ? C.day(P.localIso(k.stateAt)) + (k.stateReason ? ': ' + k.stateReason : '') : null;
    return {
      key: k.id,
      cells: [cell(k.state, 'stamp'), cell(k.text, 'text'), day(k.at), cell(moved, 'muted')]
    };
  }

  /* A guidance record: its metric in words, its period, its range and its midpoint as the
     guidance table writes them in the record's currency, one figure where the range is a point,
     its basis, its call's day, and current or superseded, today's state. */
  function guidance(g) {
    var guided = function (v) { return P.guided(v, g.metric, g.currency); };
    var range = g.low === g.high ? guided(g.low) : guided(g.low) + ' to ' + guided(g.high);
    return {
      key: g.id,
      cells: [
        cell(P.words(g.metric), 'text'), cell(g.period, 'when'), cell(range, 'figure'),
        cell(guided(g.midpoint), 'figure'), cell(g.basis, 'muted'), day(g.asOf),
        cell(g.supersededBy == null ? 'current' : 'superseded', 'stamp')
      ]
    };
  }

  /* An override: its input, from and to in its unit, its state and its reason. */
  function override(o) {
    return {
      key: o.id,
      cells: [
        cell(o.tag, 'input'), cell(P.inputFigure(o.old, o.unit), 'figure'),
        cell(P.inputFigure(o['new'], o.unit), 'figure'), cell(o.state, 'stamp'),
        cell(o.reason, 'muted')
      ]
    };
  }

  function note(n) {
    return { key: n.id, cells: [time(n.at), cell(n.text, 'text')] };
  }

  /* The row builder of the company's reviews (review), each given the time its review was made:
     a copy a refresh carried onto a newer snapshot (its madeId) keeps the bridge of the made
     review, with the mechanical value of that day (spec 2026-11-23 held reviewed value, 5.2 and
     5.7), so its bridge names the made review's day; a made review's is its own. */
  function reviewOf(reviews) {
    var madeAt = {};
    (reviews || []).forEach(function (r) { if (r.madeId == null) madeAt[r.id] = r.createdAt; });
    return function (r) { return review(r, madeAt[r.madeId] || r.createdAt); };
  }

  /* A review: when, its value and the mechanical value it starts from, the count of the
     overrides inside it, and its word against the price it was stored at, or its refusal; with
     its bridge, ValueBridge's props, its first line naming the day of the mechanical value, the
     local day of `madeAt`, or its refusal where it has no value. */
  function review(r, madeAt) {
    var said = r.value == null && r.refusal ? cell(r.refusal, 'refusal')
      : r.designation ? cell(F.DESIGNATION[r.designation] || r.designation, 'designation',
        { designation: r.designation })
        : cell(null, 'text');
    return {
      key: r.id,
      cells: [
        time(r.createdAt), money(r.value), money(r.mechanicalValue),
        cell(C.count((r.overrideIds || []).length), 'figure'), said
      ],
      bridge: r.value == null ? { refusal: r.refusal || DASH } : {
        mechanical: r.mechanicalValue, reviewed: r.value, hero: false,
        mechanicalDay: madeAt ? P.localIso(madeAt).slice(0, 10) : undefined,
        overrides: (r.bridge || []).map(function (line) {
          return {
            tag: line.label, from: P.inputFigure(line.old, line.unit),
            to: P.inputFigure(line['new'], line.unit),
            delta: line.delta == null ? undefined : line.delta,
            principal: line.principal, actor: line.actor, reason: line.reason
          };
        })
      }
    };
  }

  function secondary(s) {
    return {
      key: s.id,
      cells: [time(s.createdAt), cell(s.form, 'text'), money(s.valuePerShare),
        cell(s.reason, 'muted')]
    };
  }

  /* A news item: its date, its headline, a link where its source is a web address, and what
     happened. */
  function news(n) {
    var web = WEB.test(String(n.source || ''));
    return {
      key: n.id,
      cells: [day(n.date), cell(n.headline, 'text', web ? { href: n.source } : null),
        cell(n.text, 'muted')]
    };
  }

  /* A finding: the day it describes, its period, its figure in its unit and currency, its words
     and the kind of its source. */
  function finding(f) {
    return {
      key: f.id,
      cells: [
        day(f.asOf), cell(f.period, 'when'), cell(figure(f.value, f.unit, f.currency), 'figure'),
        cell(f.text, 'text'), cell(f.source ? f.source.kind : null, 'muted')
      ]
    };
  }

  /* A finding's figure in its unit, as a cite of it reads (reports.check.shown): an amount in
     whole units of `code` and a figure a share to cents, $ for USD and the code before the number
     otherwise; a percent of a fraction to one decimal; a multiple to two with x; years to one; a
     score to two; a count whole. A dash for none. */
  function figure(v, unit, code) {
    if (v == null) return DASH;
    if (unit === 'currency') return P.whole(v, code);
    if (unit === 'per-share') return P.money(v, code);
    if (unit === 'percent') return F.formatPercent(v);
    if (unit === 'multiple') return C.decimal(v, 2) + 'x';
    if (unit === 'years') return C.decimal(v, 1) + ' years';
    if (unit === 'score') return C.decimal(v, 2);
    return C.count(v);
  }

  /* A ledger row: when, its kind, its summary, and who wrote it, an agent by its model. */
  function entry(e) {
    return {
      key: e.id,
      cells: [time(e.at), cell(P.words(e.kind), 'text'), cell(e.summary, 'text'),
        cell(e.actor || e.principal, 'muted')]
    };
  }

  /* The rows the nine panels of `records` draw: the count beside Records in the bar. */
  function count(records) {
    return panels(records).reduce(function (n, p) { return n + p.count; }, 0);
  }

  /* ------------------------------------------------------------------------------ the drawing */

  var CELLS = {
    text: 'body', muted: 'body app-research__muted', figure: 'figure-sm fb-num',
    when: 'body app-research__when', stamp: null, input: 'figure-sm', designation: null,
    refusal: 'body app-refusal'
  };

  /* The view: the nine panels in two columns, a panel with records across both, the review
     `open` names with its bridge under its row, a press on a review's row handed to press(id). */
  function draw(records, open, press) {
    return h('div', { className: 'app-research__records' }, panels(records).map(function (p) {
      return drawPanel(p, open, press || function () {});
    }));
  }

  /* A panel: its name and its count, the ledger's note at its right, over its table, or "None on
     file." */
  function drawPanel(p, open, press) {
    return h('section', {
      key: p.name,
      className: 'app-research__panel' + (p.rows.length ? ' app-research__panel--full' : '')
    },
      h('header', { className: 'app-research__panelhead' },
        h('h2', { className: 'heading app-research__title' }, p.name, ' ',
          h('span', { className: 'figure-sm app-research__n' }, C.count(p.count))),
        p.note ? h('span', { className: 'caption app-research__headnote' }, p.note) : null),
      p.rows.length ? table(p, open, press)
        : h('p', { className: 'body app-research__empty' }, NONE));
  }

  /* A panel's table: its heads, a figure's set right, then a row a record, a review's a press
     that opens or closes its bridge in a row under it. */
  function table(p, open, press) {
    var kinds = p.rows[0].cells.map(function (c) { return c.kind; });
    return h('div', { className: 'app-research__scroll' },
      h('table', { className: 'app-research__table' },
        h('thead', null, h('tr', null, p.heads.map(function (name, i) {
          return h('th', {
            key: i, scope: 'col', className: 'label' + (kinds[i] === 'figure' ? ' fb-num' : '')
          }, name);
        }))),
        h('tbody', null, [].concat.apply([], p.rows.map(function (row) {
          return row.bridge ? reviewRows(row, p.heads.length, open === row.key, press)
            : [h('tr', { key: row.key }, row.cells.map(drawCell))];
        })))));
  }

  /* A review's row, a press on it, or on its time's button with the keyboard, handed to press;
     and where it is `on`, its bridge in a row under it across the table. */
  function reviewRows(row, width, on, press) {
    var cells = row.cells.map(drawCell);
    var first = row.cells[0];
    cells[0] = h('td', { key: 0, className: CELLS[first.kind] },
      h('button', {
        type: 'button', className: 'app-research__open', 'aria-expanded': on ? 'true' : 'false'
      }, content(first)));
    var drawn = [h('tr', {
      key: row.key, className: 'app-research__review' + (on ? ' is-open' : ''),
      onClick: function () { press(row.key); }
    }, cells)];
    if (on) {
      drawn.push(h('tr', { key: 'bridge-' + row.key, className: 'app-research__bridge' },
        h('td', { colSpan: width }, bridge(row.bridge))));
    }
    return drawn;
  }

  /* The bridge of a review with a value, or its refusal in the bridge's place. */
  function bridge(b) {
    if (b.refusal !== undefined) return h('p', { className: 'body app-refusal' }, b.refusal);
    return h(F.ValueBridge, b);
  }

  function drawCell(c, i) {
    return h('td', { key: i, className: CELLS[c.kind] }, content(c));
  }

  /* What a cell holds: a time as FairbandPage.when writes it, a link, a stamp, the review's word
     in its band's chip, or its text. */
  function content(c) {
    if (c.at) return P.when(c.at);
    if (c.href) return h('a', { href: c.href, target: '_blank', rel: 'noopener' }, c.text);
    if (c.kind === 'stamp') return h('span', { className: 'label app-research__stamp' }, c.text);
    if (c.kind === 'designation') {
      return h('span', {
        className: 'fb-designation fb-designation--' + c.designation + ' label'
      }, c.text);
    }
    return c.text;
  }

  P.researchRecords = { panels: panels, count: count, draw: draw };
})();
