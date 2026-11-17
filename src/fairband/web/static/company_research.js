/* The company page's Research tab (the Research tab's design, 7), loaded after
   company_research_text.js: #company/<symbol>/research, the company's latest report, and
   #company/<symbol>/research/<id>, the report with that id, from the tab's read
   (GET /api/companies/{symbol}/page/research), which carries the report shown whole and the
   company's reports on file. It draws and writes nothing else: no override, no kill criterion's
   state, no note and no Request research, which the head has.

   Under the tabs' row, the bar (7.2): Report and Records, the tab's two views, Records with the
   count of the rows its panels draw; in the Report view the report's line, its stance in the
   Stance column's chip, faded once its validity ended, its mode, its revision, its date and time,
   who wrote it, valid until and, for a valuation review, the full report it reuses; at its right
   Footnote marks and Download .md; under it a valuation review's note that it reuses none and the
   Markdown's refusal. In the Records view the line's sentence, and under the bar the company's
   records on file (7.10), which company_research_records.js draws (FairbandPage.researchRecords,
   loaded after this script and called as the tab draws). Then, in the Report view, the section
   list at the left (7.3): the report's headings, the three parts kept closed, References with
   their count, and the reports on file, the one shown marked, each other a link to its address;
   the name of the section in view marked as the app marks a selection, where the browser can
   tell which is in view, else the first. A press on a name scrolls to its panel and opens it
   where it is closed. At the right, a panel a section (7.4): its heading, then the rows its
   layout gives (FairbandPage.researchText.lay), each block drawn by the design system's reader
   (Fairband.reportText.draw), and the cards beside its first run of text, the named blocks its
   layout makes cards and the records' cards the tab hands it by heading. Then the references,
   Appendix A and Appendix B (7.8), each closed, each opened drawing what the report page draws
   (FairbandPage.reportParts). A company with no report draws "No report yet." alone.

   The cards by heading (7.4 rules 1 and 6 to 10): Summary, the report's call (7.5), its value,
   the design system's meter whole and the levels in words; Valuation, each grid the report cites
   and the secondary valuation's, then Changes to Fairband's inputs (7.6); Price and multiples,
   the price against the band and the two P/E; Recent news, the sources on file, newest first;
   Risks and kill criteria, the kill criteria; Key judgments, one card a judgment in a row under
   the text. A card draws the read's fields and stored records, and computes no figure. The
   charts (7.9) are the report page's (FairbandPage.reportCharts) with no panel of their own: in
   Financial performance and health a paragraph stands beside its group's charts and a group no
   paragraph names in a row of its own (rule 3); the last earnings call opens with its three
   charts by quarter (rule 4); those of a pair and of the quarters' row drawn smaller.

   The series the charts read (8.2) are read as the report page reads them, each on its own after
   the report lands, each with the request header: the financial tables, the multiples history,
   five years of closes, the band's history and each sensitivity reading the references name.
   They are kept by the report's id outside the tab, read when a report's answer lands, again
   when a new answer of the same report lands (the charts drawn staying until their new series
   land), never when the tab is only drawn again; each landing draws the page again
   (FairbandPage.companyPage.redraw), so a series of a report no longer shown changes nothing
   drawn, and one of an older run of the reads is dropped. A section's text is drawn at once; a
   chart waits for its series; a read the server refused draws its sentence in the chart's place.

   A cited number (7.7) is the design system's cite: the CSS gives it the text's colour and its
   [n] shows while Footnote marks is on, the choice kept in the browser's localStorage under
   fairband.research.marks, read and written inside a try, off where it keeps nothing. Its source,
   the reference's number and its words (source), shows in one box of the tab's own on hover and
   on keyboard focus, each cite made focusable; the cite's own title, its ref, is taken off as the
   box shows, so the browser shows no second one.

   Research, the tab's component, keeps the view, the marks, the section in view, the Markdown's
   refusal and the review whose bridge Records draws in its state, drawn keyed on the company of
   its answer, so another report of the company keeps them and another company opens a new tab.
   The pieces are pure builders on FairbandPage.research, for the tests, which read them in node,
   and draw.research hangs on the company page's draw (company.js). */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var C = P.companyPage;

  var MARKS_KEY = 'fairband.research.marks';
  var RECORDS = 'The company\'s records on file, from any report.';
  var EXPIRED = 'The value of this report is past the date it was valid until';
  var CLOSED = ['research-refs', 'research-a', 'research-b']; /* the closed parts' panels */
  var CITE_TITLE = /^traces to /; /* the start of the bundle's title of a cite, before its ref */
  var SMALL = 120; /* the charts' height in a pair and in the quarters' row (7.9) */
  var EARNINGS = 'The last earnings call';
  var UNDER = ['Key judgments']; /* the headings whose cards stand in a row under the text */
  var NO_CHANGE = 'The report changes no input, so its value is the mechanical value.';
  var KEPT_STATE =
    'A criterion keeps its state after the report: an agent marks it when the event happens.';
  var JUDGED = {
    phase: 'Phase', moat: 'Moat', belief: 'Belief', roic: 'Return on new capital',
    target_margin: 'Target margin'
  };
  var WEB = /^https?:\/\//i; /* an address the news card links to */
  var HELD = {}; /* the series of each report shown, by its id, { of, got } (series) */

  /* A section's panel's id, from its index in the report: research-s1 for the first. */
  function panelId(index) { return 'research-s' + (index + 1); }

  /* ---------------------------------------------------------------------------- the marks kept */

  /* Whether the browser keeps Footnote marks on: true where it holds 1, else false, and false
     where it keeps nothing or its store throws. */
  function storedMarks() {
    try {
      return window.localStorage.getItem(MARKS_KEY) === '1';
    } catch (e) {
      return false;
    }
  }

  /* Keeps Footnote marks `on` in the browser, 1 or 0; where it keeps nothing, the choice lasts
     while the tab is open. Never throws. */
  function keepMarks(on) {
    try {
      window.localStorage.setItem(MARKS_KEY, on ? '1' : '0');
    } catch (e) { /* no store */ }
  }

  /* -------------------------------------------------------------------------------- the bar */

  /* The bar (7.2) on `answer` in the view `view`, 'report' or 'records', Footnote marks `marks`
     on or off, Records with the count of the rows its panels draw (company_research_records.js).
     `act` holds what it draws with and what its controls call: `today`, the detail's day, against
     which the report's validity has ended; `failed`, the Markdown's refusal or null; view(next),
     marks() and download(). Under it, in the Report view, a valuation review's note that it
     reuses no full report, and the Markdown's refusal. */
  function bar(answer, view, marks, act) {
    var report = answer.report;
    var shown = view === 'report';
    var count = P.researchRecords.count(answer.records);
    return h('div', { className: 'app-research__top' },
      h('div', { className: 'app-research__bar' },
        h('div', {
          className: 'app-research__views', role: 'tablist', 'aria-label': 'What the tab shows'
        }, viewButton('report', 'Report', view, act),
          viewButton('records', 'Records', view, act, count)),
        !shown ? h('p', { className: 'caption app-research__line' }, RECORDS)
          : report ? line(answer, act.today) : null,
        shown && report ? h('div', { className: 'app-research__actions' },
          h(F.Button, {
            size: 'sm', className: 'app-research__marks', 'aria-pressed': marks ? 'true' : 'false',
            onClick: act.marks
          }, 'Footnote marks'),
          h(F.Button, { size: 'sm', className: 'app-research__download', onClick: act.download },
            'Download .md')) : null),
      shown && report && report.mode === 'valuation review' && report.reusesFullReportOf == null
        ? h('p', { className: 'caption app-research__note' }, 'No full report to reuse.') : null,
      shown && act.failed ? h('p', { className: 'caption app-research__error' }, act.failed)
        : null);
  }

  /* One of the bar's two views, selected where it is `view`, with the count `n` after its name
     where given. */
  function viewButton(id, words, view, act, n) {
    return h('button', {
      key: id, type: 'button', role: 'tab', className: 'control app-research__view',
      'aria-selected': id === view ? 'true' : 'false',
      onClick: function () { act.view(id); }
    }, words, n == null ? null : h('span', { className: 'figure-sm app-research__n' }, C.count(n)));
  }

  /* The report's line: its stance in the Stance column's chip, faded with the report page's
     title where the window of the snapshot it rests on ended before `today`; its mode; its
     revision; its date and time; who wrote it; valid until; and the full report a valuation
     review reuses, by that report's date. */
  function line(answer, today) {
    var report = answer.report;
    var until = report.appendixA.snapshot.validUntil;
    var expired = until < today;
    var reused = reusedOn(answer);
    return h('div', { className: 'app-research__line' },
      h('span', {
        className: 'fb-stance fb-stance--' + report.stance +
          (expired ? ' fb-stance--expired' : '') + ' label',
        title: expired ? EXPIRED : null
      }, report.stance),
      h('span', { className: 'label app-research__mode' }, report.mode),
      h('span', { className: 'figure-sm' }, 'revision ' + report.revision),
      h('span', { className: 'caption' }, P.when(report.createdAt)),
      h(F.PrincipalChip, { principal: report.principal, actor: report.actor }),
      h('span', { className: 'caption' }, 'valid until ' + C.day(until)),
      reused ? h('span', { className: 'caption' }, 'reuses the full report of ' + C.day(reused))
        : null);
  }

  /* When the full report a valuation review reuses was written, in the reader's local time, from
     the company's reports on file; null where it reuses none, or none on file is it. */
  function reusedOn(answer) {
    var id = answer.report.reusesFullReportOf;
    var found = answer.reports.filter(function (r) { return r.id === id; })[0];
    return id != null && found ? P.localIso(found.createdAt) : null;
  }

  /* ------------------------------------------------------------------------------- the list */

  /* The section list (7.3) of `answer`'s report, the name of the panel `shown` marked: the
     report's headings, the three parts kept closed, then the reports on file. */
  function list(answer, shown) {
    var report = answer.report;
    var names = report.sections.map(function (s, i) {
      return link(panelId(i), s.heading, null, shown);
    });
    var kept = [
      link(CLOSED[0], 'References', report.references.length, shown),
      link(CLOSED[1], 'Appendix A', null, shown),
      link(CLOSED[2], 'Appendix B', null, shown)
    ];
    return h('nav', { className: 'app-research__list', 'aria-label': 'The report\'s sections' },
      group('The report', h('ul', { className: 'app-research__links' }, names)),
      group('Kept closed', h('ul', { className: 'app-research__links' }, kept)),
      group('Reports on file · ' + C.count(answer.reports.length),
        h('ul', { className: 'app-research__files' }, answer.reports.map(function (r) {
          return h('li', { key: r.id }, file(r, report.id, answer.symbol));
        }))));
  }

  function group(title, body) {
    return h('div', { key: title, className: 'app-research__group' },
      h('p', { className: 'label app-research__grouphead' }, title), body);
  }

  /* A name in the list: a press scrolls to its panel `id` and opens it where it is closed (go);
     `n`, a count after the name where given; marked where it is the panel `shown`. */
  function link(id, name, n, shown) {
    return h('li', { key: id },
      h('button', {
        type: 'button', className: 'control app-research__link' + (id === shown ? ' is-on' : ''),
        'aria-current': id === shown ? 'true' : null,
        onClick: function () { go(id); }
      },
        h('span', null, name),
        n == null ? null : h('span', { className: 'figure-sm app-research__n' }, C.count(n))));
  }

  /* The panel `id` brought into view, opened where it is a closed part. */
  function go(id) {
    var target = document.getElementById(id);
    if (!target) return;
    if (target.tagName === 'DETAILS') target.open = true;
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /* A report on file: its date and its revision over its mode and its stance; the one shown,
     `shownId`, marked and no link, each other a link to its address on the tab. */
  function file(r, shownId, symbol) {
    var mode = String(r.mode);
    var words = [
      h('span', { key: 'when', className: 'control' },
        C.day(P.localIso(r.createdAt)) + ', revision ' + r.revision),
      h('span', { key: 'what', className: 'caption app-research__what' },
        mode.charAt(0).toUpperCase() + mode.slice(1) + ', ' + r.stance)
    ];
    if (r.id === shownId) {
      return h('span', { className: 'app-research__file is-on', 'aria-current': 'page' }, words);
    }
    return h('a', { className: 'app-research__file', href: C.researchHref(symbol, r.id) }, words);
  }

  /* ---------------------------------------------------------------------------- the sections */

  /* The panel of `s`, the report's section at `index` (7.4): its heading, then the rows its
     layout gives under the report's stance, and its cards, the named blocks the layout makes
     cards and those `cards` holds for its heading, in a column beside its first run of text, or
     after its rows where it has none; no column where it has no card. Under Key judgments the
     cards `cards` holds stand after the rows instead. The charts read the series `landed` holds
     (series): the financial tables' beside the paragraphs of Financial performance and health,
     a refusal's sentence once, in the first place a chart stands; the quarters' as the first row
     of the last earnings call. */
  function section(s, index, report, cards, landed) {
    var laid = P.researchText.lay(s.heading, s.parts, report.stance);
    var footnotes = P.footnotes(report.references);
    var tables = (landed || {}).tables;
    var held = Object.prototype.hasOwnProperty.call(cards, s.heading) ? cards[s.heading] : [];
    var under = UNDER.indexOf(s.heading) >= 0;
    var aside = laid.cards.map(function (b, i) {
      return labelled(b, footnotes, i, 'app-research__card');
    }).concat(under ? [] : held);
    var charts = tables ? {
      small: P.reportCharts.groupCharts(tables, SMALL), whole: P.reportCharts.groupCharts(tables)
    } : null;
    var firstCharts = -1; /* the first row of charts, where a refusal's sentence stands */
    laid.rows.some(function (r, i) {
      if (r.kind === 'pair' || r.kind === 'groups') firstCharts = i;
      return firstCharts >= 0;
    });
    var rows = laid.rows.map(function (r, i) {
      return row(r, footnotes, i, charts, i === firstCharts);
    });
    if (aside.length) {
      var side = h('div', { key: 'cards', className: 'app-research__cards' }, aside);
      var first = laid.rows.map(function (r) { return r.kind; }).indexOf('run');
      if (first < 0) rows.push(side);
      else {
        rows[first] = h('div', { key: 'split', className: 'app-research__split' }, rows[first],
          side);
      }
    }
    var quarters = s.heading === EARNINGS && tables ? quarterRow(tables) : null;
    if (quarters) rows.unshift(quarters);
    if (under) rows = rows.concat(held);
    return h('section', {
      key: panelId(index), id: panelId(index), className: 'app-research__sec'
    },
      h('h2', { className: 'heading app-research__title' }, s.heading),
      h('div', { className: 'app-research__body' }, rows));
  }

  /* A row of the layout under `key` (company_research_text.js, lay); a pair and a row of groups
     with the `charts` of the financial tables, null before they land, and the refusal's sentence
     where the row is the `first` to stand charts. */
  function row(r, footnotes, key, charts, first) {
    if (r.kind === 'run') return run(r.blocks, footnotes, key);
    if (r.kind === 'wide') return wide(r.block, footnotes, key);
    if (r.kind === 'columns') return columns(r.blocks, footnotes, key);
    if (r.kind === 'pair') return pair(r, footnotes, key, charts && charts.small, first);
    if (r.kind === 'groups') return groups(r, key, charts && charts.whole, first);
    if (r.kind === 'sides') return sides(r.sides, footnotes, key);
    return null;
  }

  /* Text at the reading width: the blocks in their order. */
  function run(blocks, footnotes, key) {
    return h('div', { key: key, className: 'app-research__run' }, blocks.map(function (b, i) {
      return block(b, footnotes, i);
    }));
  }

  /* A wide table across the panel, its whole width where a cell is long. */
  function wide(b, footnotes, key) {
    var full = P.researchText.isLong(b);
    return h('div', {
      key: key, className: 'app-research__wide' + (full ? ' app-research__wide--full' : '')
    }, block(b, footnotes, 0));
  }

  /* Named lists side by side. */
  function columns(blocks, footnotes, key) {
    return h('div', { key: key, className: 'app-research__columns' }, blocks.map(function (b, i) {
      return block(b, footnotes, i);
    }));
  }

  /* A paragraph beside the charts of its group (rule 3): the paragraph at the reading width, as a
     run draws it, and the group's charts of `drawn` (groupCharts, drawn smaller), none before
     they land; where the tables did not load, the sentence in the `first` pair alone. */
  function pair(r, footnotes, key, drawn, first) {
    var charts = !drawn ? null : drawn.refused ? (first ? drawn.refused : null) : drawn[r.group];
    return h('div', { key: key, className: 'app-research__pair' },
      run([r.block], footnotes, 'text'),
      h('div', { key: 'charts', className: 'app-research__minis' }, charts));
  }

  /* The charts of the groups no paragraph names, alone, in a row at their own height (rule 3);
     nothing before they land; where the tables did not load, the sentence where the row is the
     `first` to stand charts. */
  function groups(r, key, drawn, first) {
    if (!drawn || (drawn.refused && !first)) return null;
    var charts = drawn.refused || [].concat.apply([], r.groups.map(function (g) {
      return drawn[g];
    }));
    return h('div', { key: key, className: 'app-research__minis app-research__minis--all' },
      charts);
  }

  /* The last earnings call's first row (rule 4): its three charts by quarter, drawn smaller, or
     the sentence of the tables' refusal; none on an answer without the quarters. */
  function quarterRow(tables) {
    var drawn = P.reportCharts.quarterCharts(tables, SMALL);
    return drawn ? h('div', { key: 'quarters', className: 'app-research__minis' }, drawn) : null;
  }

  /* Two columns, each its block under its label. */
  function sides(list, footnotes, key) {
    return h('div', { key: key, className: 'app-research__sides' }, list.map(function (s, i) {
      return h('div', { key: i, className: 'app-research__side' },
        h('p', { className: 'label app-research__name' }, s.label),
        block(s.block, footnotes, 'text'));
    }));
  }

  /* A block under `key`: a named block under its name, any other as the design system's reader
     draws it. */
  function block(b, footnotes, key) {
    if (b.kind === 'named') return labelled(b, footnotes, key, 'app-research__named');
    return F.reportText.draw(b, footnotes, key);
  }

  /* A named block, `b`, of the class `className`: its name, a line of pieces the reader draws,
     over its body. */
  function labelled(b, footnotes, key, className) {
    return h('div', { key: key, className: className },
      h('div', { className: 'label app-research__name' },
        F.reportText.draw({ kind: 'p', items: [b.name] }, footnotes, 'name')),
      F.reportText.draw(b.body, footnotes, 'body'));
  }

  /* -------------------------------------------------------------------------------- the cards */

  /* The cards of each heading (7.4 rules 1 and 6 to 10) for `answer`'s report, the company's
     `detail` and the series `landed` holds; a card with nothing to draw is left out. */
  function cardsOf(answer, detail, landed) {
    var report = answer.report;
    var of = answer.ofReport || {};
    var cards = {
      'Summary': [valueCard(answer.call, detail)],
      'Valuation': charted(P.reportCharts.gridCharts(report, landed.readings || []))
        .concat([changesCard(report)]),
      'Price and multiples': charted(P.reportCharts.priceCharts(landed)),
      'Recent news': [newsCard(of.newsItems)],
      'Risks and kill criteria': [killCard(of.killCriteria)],
      'Key judgments': [judgmentCards(report)]
    };
    Object.keys(cards).forEach(function (k) { cards[k] = cards[k].filter(Boolean); });
    return cards;
  }

  /* Charts as cards in a section's column, each chart's own head its name. */
  function charted(charts) {
    return charts.map(function (chart, i) {
      return h('div', { key: 'chart' + i, className: 'app-research__card app-research__chart' },
        chart);
    });
  }

  /* A card under `key` of the class `className`: its name and, at the right of it, the word on
     what it holds where it has one, over its body, and a line under it where it has one. */
  function card(key, className, name, note, body, foot) {
    return h('div', { key: key, className: 'app-research__card ' + className },
      h('p', { className: 'app-research__head' },
        h('span', { className: 'label' }, name),
        note == null ? null : h('span', { className: 'caption app-research__headnote' }, note)),
      body,
      foot ? h('p', { className: 'caption app-research__foot' }, foot) : null);
  }

  /* The report's call (7.5) on the read's `call`, today's figures from the company's `detail`:
     what the value rests on in its head; the value a share and its kind; the design system's
     meter on the value, its four levels and the snapshot's price, whole; the levels in words;
     the caption. With no value, the refusal's sentence and no meter; with no price or no
     levels, no meter. None without a call. */
  function valueCard(call, detail) {
    if (!call) return null;
    var body = call.value == null
      ? [call.refusal ? h('p', { key: 'refusal', className: 'body app-refusal' }, call.refusal)
        : null]
      : [valueFigure(call), meter(call, detail), levels(call.levels)];
    return card('call', 'app-research__call', 'The report\'s call', pricedOn(call), body,
      callFoot(call, detail));
  }

  /* "on the data of" its day, then "priced that day" or "priced" and the price's day; the data's
     day alone where the snapshot has no price. */
  function pricedOn(call) {
    var data = 'on the data of ' + C.day(call.dataDate);
    if (call.priceDate == null) return data;
    return data + (call.priceDate === call.dataDate ? ', priced that day'
      : ', priced ' + C.day(call.priceDate));
  }

  function valueFigure(call) {
    return h('div', { key: 'value', className: 'app-research__value' },
      h('span', { className: 'caption app-research__faint' }, 'Value a share'),
      h('span', { className: 'app-research__figure' },
        h('span', { className: 'figure-lg' }, F.formatMoney(call.value)),
        h('span', { className: 'label app-research__kind' },
          call.note ? call.basis + ', ' + call.note : call.basis)));
  }

  /* BandMeter on the call's value, its levels and the snapshot's price, the read's word and its
     gap in every meter's words (FairbandPage.gapText) on the detail's edges; none without a
     price or the levels. */
  function meter(call, detail) {
    var l = call.levels;
    if (call.price == null || !l) return null;
    return h(F.BandMeter, {
      key: 'meter', low: l.fairLow, high: l.fairHigh, price: call.price, fairValue: call.value,
      buyLevel: l.buy, trimLevel: l.trim, designation: call.designation, showScale: false,
      gap: P.gapText(call.priceToValue, detail ? detail.designationEdges : null, valueName(call)),
      hero: false
    });
  }

  /* The name the gap gives the value: the secondary valuation, the reviewed value or the
     mechanical value. */
  function valueName(call) {
    if (call.note === 'secondary valuation') return 'the secondary valuation';
    return call.basis === 'reviewed' ? 'the reviewed value' : 'the mechanical value';
  }

  /* The three levels in words, each by its zone's colour; none without levels. */
  function levels(l) {
    if (!l) return null;
    return h('ul', { key: 'levels', className: 'caption app-research__levels' },
      level('buy', 'buy below ', F.formatMoney(l.buy)),
      level('fair', 'close to the value ',
        F.formatMoney(l.fairLow) + ' to ' + F.formatMoney(l.fairHigh)),
      level('trim', 'trim above ', F.formatMoney(l.trim)));
  }

  function level(zone, words, figure) {
    return h('li', { key: zone, className: 'app-research__level app-research__level--' + zone },
      words, h('span', { className: 'figure-sm' }, figure));
  }

  /* The caption: valid until; today's value and price, the detail's; and, where the report's
     value is a review's and its snapshot has a mechanical value, that value. */
  function callFoot(call, detail) {
    var said = ['Valid until ' + C.day(call.validUntil) + '.'];
    var now = today(detail);
    if (now) said.push(now);
    if (call.basis === 'reviewed' && call.note == null && call.mechanicalValue != null) {
      said.push('The mechanical value was ' + F.formatMoney(call.mechanicalValue) + '.');
    }
    return said.join(' ');
  }

  /* Today's value and price from the company's detail: the review's value, reviewed, where it
     carries a review with a value, else the snapshot's, mechanical, and the snapshot's price;
     null where it has no value or no price. */
  function today(detail) {
    var r = detail && detail.result;
    if (!r) return null;
    var reviewed = !!detail.review && detail.review.value != null;
    var value = reviewed ? detail.review.value : r.value;
    if (value == null || r.price == null) return null;
    return 'Today the ' + (reviewed ? 'reviewed' : 'mechanical') + ' value is ' +
      F.formatMoney(value) + ' and the price ' + F.formatMoney(r.price) + '.';
  }

  /* Changes to Fairband's inputs (7.6): for a report on a review, a line a change in the bridge's
     order, its label, its figures before and after in its input's unit and its effect on the
     value a share, signed, or its refusal; for one with none, that it changes no input, where
     its snapshot has a mechanical value for that to be. */
  function changesCard(report) {
    var a = report.appendixA;
    var lines = a.bridge ? a.bridge.lines : [];
    var units = {};
    a.overrides.forEach(function (o) { units[o.id] = o.unit; });
    var body = lines.length
      ? h('ul', { className: 'app-research__recs' }, lines.map(function (line, i) {
        return change(line, units[line.overrideId], i);
      }))
      : a.snapshot.value != null ? h('p', { className: 'body app-research__muted' }, NO_CHANGE)
        : null;
    return card('changes', 'app-research__changes', 'Changes to Fairband\'s inputs',
      lines.length ? C.count(lines.length) : 'none', body);
  }

  function change(line, unit, key) {
    return h('li', { key: key, className: 'app-research__rec' },
      h('span', { className: 'app-research__rechead' },
        h('span', { className: 'body app-research__label' }, line.label),
        line.delta == null ? null
          : h('span', { className: 'figure-sm app-research__effect' },
            (line.delta > 0 ? '+' : '') + F.formatMoney(line.delta) + ' a share')),
      h('span', { className: 'figure-sm app-research__change' },
        P.inputFigure(line.old, unit) + ' → ' + P.inputFigure(line.new, unit)),
      line.refusal ? h('span', { className: 'caption app-refusal' }, line.refusal) : null);
  }

  /* Kill criteria (rule 9): how many are open of all, each with its state, the day of that
     state, its text and its state's reason, then that a state outlives the report; none for a
     report with no criterion. */
  function killCard(criteria) {
    if (!criteria || !criteria.length) return null;
    var open = criteria.filter(function (k) { return k.state === 'open'; }).length;
    return card('kill', 'app-research__kill', 'Kill criteria',
      C.count(open) + ' open of ' + C.count(criteria.length),
      h('ul', { className: 'app-research__recs' }, criteria.map(criterion)), KEPT_STATE);
  }

  function criterion(k) {
    return h('li', { key: k.id, className: 'app-research__rec' },
      h('span', { className: 'app-research__rechead' },
        h('span', { className: 'label app-research__stamp' }, k.state),
        h('span', { className: 'caption app-research__since' },
          'since ' + C.day(P.localIso(k.stateAt || k.at)))),
      h('span', { className: 'body' }, k.text),
      k.stateReason ? h('span', { className: 'body app-research__reason' }, k.stateReason)
        : null);
  }

  /* The sources on file (rule 8): the news items with their count, newest first, each with its
     date, its address's host and its headline, a link where the address is a web address; none
     for a report with no item. */
  function newsCard(items) {
    if (!items || !items.length) return null;
    var newest = items.slice().sort(function (a, b) {
      return a.date < b.date ? 1 : a.date > b.date ? -1 : b.id - a.id;
    });
    return card('news', 'app-research__news', 'The sources on file', C.count(items.length),
      h('ul', { className: 'app-research__recs' }, newest.map(newsItem)));
  }

  function newsItem(n) {
    var web = WEB.test(String(n.source || ''));
    var host = web ? hostOf(n.source) : '';
    return h('li', { key: n.id, className: 'app-research__rec' },
      h('span', { className: 'app-research__rechead' },
        h('span', { className: 'figure-sm app-research__date' }, C.day(n.date)),
        host ? h('span', { className: 'caption app-research__host' }, host) : null),
      web ? h('a', {
        className: 'body app-research__headline', href: n.source, target: '_blank',
        rel: 'noopener'
      }, n.headline) : h('span', { className: 'body app-research__headline' }, n.headline));
  }

  /* A web address's host without www.; '' where the browser cannot read it. */
  function hostOf(address) {
    try {
      return new URL(address).hostname.replace(/^www\./, '');
    } catch (e) {
      return '';
    }
  }

  /* The judgments (rule 10): one card a judgment in a row, its name, "stands", or "changed"
     where it names an override, and its decision; none for a report with no judgment. */
  function judgmentCards(report) {
    var list = report.judgments || [];
    if (!list.length) return null;
    return h('div', { key: 'judged', className: 'app-research__judged' }, list.map(function (j) {
      var changed = j.overrideId != null;
      return h('div', { key: j.id, className: 'app-research__card' },
        h('span', { className: 'app-research__rechead' },
          h('span', { className: 'heading app-research__judgment' },
            JUDGED[j.judgment] || j.judgment),
          h('span', {
            className: 'label app-research__stamp' + (changed ? ' app-research__stamp--on' : '')
          }, changed ? 'changed' : 'stands')),
        h('span', { className: 'body app-research__decision' }, j.decision));
    }));
  }

  /* ------------------------------------------------------------------------------- the series */

  /* What has landed of the series `report`'s charts read (8.2), held in `held` by the report's
     id, { of, got }: the report the reads were started for and what has landed. The reads start
     when the tab is handed a report it has not read them for: the first time, and again when a
     new answer of the tab's read lands for the same report (a new report object: after a
     refresh ends, after a note is taken), as the report page reads them at every landing; what
     landed before stays drawn until each new series takes its place. Drawn again with the same
     answer, it starts no read and gives what has landed. */
  function series(report, held) {
    var kept = Object.prototype.hasOwnProperty.call(held, report.id) ? held[report.id] : null;
    if (!kept || kept.of !== report) {
      kept = held[report.id] = { of: report, got: kept ? kept.got : {} };
      readSeries(report, held);
    }
    return kept.got;
  }

  /* The report's series, each on its own, its body or the server's sentence why not, as the
     report page reads them: the six financial tables, the multiples history, the closes of the
     five years, the band's history and each sensitivity reading the references name, once, in
     the order first cited, the company's own. Each lands under the report's id, so one of a
     report no longer shown changes nothing drawn, taking the place of the one before it, and the
     page draws again; one of an older run of the reads, landing after a newer run started, is
     dropped. */
  function readSeries(report, held) {
    var id = report.id;
    var company = '/api/companies/' + encodeURIComponent(report.symbol);
    var land = function (key) {
      return function (got) {
        var kept = held[id];
        if (kept.of !== report) return; /* a newer run of the reads started: the latest wins */
        var next = {};
        Object.keys(kept.got).forEach(function (k) { next[k] = kept.got[k]; });
        next[key] = got;
        kept.got = next;
        C.redraw();
      };
    };
    settle(read(company + '/financial-tables')).then(land('tables'));
    settle(read(company + '/multiples-history')).then(land('multiples'));
    settle(read(company + '/price-history?years=5')).then(land('closes'));
    settle(read(company + '/band-history')).then(land('band'));
    Promise.all(cited(report.references).map(function (n) {
      return settle(read('/api/sensitivities/' + n));
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

  /* A read whose refusal is the server's sentence, as it arrives. Every read carries the request
     header: the server refuses without it a read that may call a vendor, the multiples
     history's, so no other site's page can spend a vendor's quota. */
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

  /* --------------------------------------------------------------------------- the closed parts */

  /* The references, Appendix A and Appendix B (7.8), each a panel closed until the reader opens
     it, its head its name and one line, each opened drawing what the report page draws. */
  function closed(report) {
    return [
      fold(CLOSED[0], 'References',
        report.references.length + ' sources, one for each cited number',
        P.reportParts.references(report)),
      fold(CLOSED[1], 'Appendix A', 'the audit of the records the report rests on',
        P.reportParts.appendixA(report)),
      fold(CLOSED[2], 'Appendix B', 'the glossary, ' + report.appendixB.length + ' terms',
        P.reportParts.appendixB(report))
    ];
  }

  function fold(id, name, note, body) {
    return h('details', { key: id, id: id, className: 'app-research__sec app-research__closed' },
      h('summary', { className: 'app-research__summary' },
        h('span', { className: 'heading' }, name),
        h('span', { className: 'caption app-research__gloss' }, note)),
      h('div', { className: 'app-research__fold' }, body));
  }

  /* -------------------------------------------------------------------------- a cited number */

  /* The words of the box of a cite of `ref` (7.7): its reference's number and its source,
     "[3] FMP income statement, revenue, fiscal 2026"; null for a ref `references` lack. */
  function source(ref, references) {
    var key = String(ref).trim();
    var found = (references || []).filter(function (e) {
      return String(e.ref).trim() === key;
    })[0];
    return found ? '[' + found.n + '] ' + found.source : null;
  }

  /* The box of a cite's source, for the tab drawn in `root`, whose references `refs.current`
     holds: one element of its own at the page's end, shown over a cite under the pointer or with
     the focus, under it where there is no room above, hidden as the pointer or the focus leaves
     it and as anything scrolls. A cite's own title is taken off as it shows, kept as its
     data-ref. Gives what takes the box and its listeners away. */
  function follow(root, refs) {
    if (!root) return undefined;
    var box = document.createElement('div');
    box.className = 'app-research__tip';
    box.setAttribute('role', 'tooltip');
    box.hidden = true;
    document.body.appendChild(box);
    function citeOf(event) {
      return event.target instanceof Element ? event.target.closest('.fb-cite') : null;
    }
    function hide() { box.hidden = true; }
    function show(event) {
      var cite = citeOf(event);
      if (!cite) { hide(); return; }
      if (cite.hasAttribute('title')) {
        cite.setAttribute('data-ref', cite.getAttribute('title').replace(CITE_TITLE, ''));
        cite.removeAttribute('title');
      }
      var words = source(cite.getAttribute('data-ref'), refs.current);
      if (!words) { hide(); return; }
      box.textContent = words;
      box.hidden = false;
      var at = cite.getBoundingClientRect();
      var size = box.getBoundingClientRect();
      var above = at.top - size.height - 6;
      box.style.left = Math.max(8, Math.min(at.left, window.innerWidth - size.width - 8)) + 'px';
      box.style.top = (above < 8 ? at.bottom + 6 : above) + 'px';
    }
    root.addEventListener('mouseover', show);
    root.addEventListener('mouseleave', hide);
    root.addEventListener('focusin', show);
    root.addEventListener('focusout', hide);
    document.addEventListener('scroll', hide, true);
    return function () {
      root.removeEventListener('mouseover', show);
      root.removeEventListener('mouseleave', hide);
      root.removeEventListener('focusin', show);
      root.removeEventListener('focusout', hide);
      document.removeEventListener('scroll', hide, true);
      box.remove();
    };
  }

  /* Each cite drawn in `root` takes the keyboard's focus, so its box shows on focus too. */
  function focusable(root) {
    if (!root) return;
    Array.prototype.forEach.call(root.querySelectorAll('.fb-cite:not([tabindex])'), function (c) {
      c.tabIndex = 0;
    });
  }

  /* Which panel of the tab drawn in `root` is in view, handed to `mark` as it changes, where the
     browser has an IntersectionObserver: the first of those in the band near the top of the
     window. Gives what stops watching. */
  function watch(root, mark) {
    if (!root || !window.IntersectionObserver) return undefined;
    var panels = Array.prototype.slice.call(root.querySelectorAll('.app-research__sec'));
    var seen = {};
    var spy = new window.IntersectionObserver(function (entries) {
      entries.forEach(function (e) { seen[e.target.id] = e.isIntersecting; });
      var on = panels.filter(function (p) { return seen[p.id]; })[0];
      if (on) mark(on.id);
    }, { rootMargin: '-8% 0px -70% 0px' });
    panels.forEach(function (p) { spy.observe(p); });
    return function () { spy.disconnect(); };
  }

  /* ---------------------------------------------------------------------------------- the tab */

  /* The tab on `props.answer` and the company's `props.detail`: the bar, then in the Report view
     the list and the panels with their cards and charts, the report's series read as it is drawn
     (series), or "No report yet."; in the Records view the company's records on file
     (FairbandPage.researchRecords). It keeps the view, Report at first; Footnote marks, as the
     browser keeps them; the panel in view, the first at first; the Markdown's refusal, with the
     report it is of, so another report draws none; and the review whose bridge Records draws,
     none at first, a press on its row again closing it. */
  function Research(props) {
    var answer = props.answer;
    var report = answer.report;
    var view = React.useState('report');
    var marks = React.useState(storedMarks());
    var shown = React.useState(panelId(0));
    var failed = React.useState(null);
    var opened = React.useState(null);
    var root = React.useRef(null);
    var refs = React.useRef(null);
    refs.current = report ? report.references : [];
    React.useEffect(function () { return follow(root.current, refs); }, []);
    React.useEffect(function () { focusable(root.current); });
    React.useEffect(function () {
      return watch(root.current, shown[1]);
    }, [report ? report.id : null, view[0]]);
    var act = {
      today: props.detail ? props.detail.today : null,
      failed: failed[0] && report && failed[0].id === report.id ? failed[0].text : null,
      view: function (next) { view[1](next); },
      marks: function () {
        keepMarks(!marks[0]);
        marks[1](!marks[0]);
      },
      download: function () {
        var id = report.id;
        failed[1](null);
        P.reportParts.download(report, function (text) { failed[1]({ id: id, text: text }); });
      }
    };
    var drawn = view[0] === 'report' && report;
    var landed = drawn ? series(report, HELD) : null;
    var cards = drawn ? cardsOf(answer, props.detail, landed) : null;
    var open = function (id) { opened[1](opened[0] === id ? null : id); };
    return h('div', {
      ref: root, className: 'app-research' + (marks[0] ? ' app-research--marks' : '')
    },
      bar(answer, view[0], marks[0], act),
      view[0] !== 'report' ? P.researchRecords.draw(answer.records, opened[0], open)
        : report ? h('div', { className: 'app-research__layout' },
          list(answer, shown[0]),
          h('div', { className: 'app-research__main' },
            report.sections.map(function (s, i) { return section(s, i, report, cards, landed); }),
            closed(report)))
          : h('p', { className: 'body app-research__none' }, 'No report yet.'));
  }

  /* The tab's function, draw.research(answer, detail): the tab keyed on the company of its
     answer, so another company's answer opens a new one. */
  function research(answer, detail) {
    return h(Research, { key: answer.symbol, answer: answer, detail: detail });
  }

  /* What the page and the tests use. */
  P.research = {
    bar: bar, list: list, section: section, closed: closed, source: source,
    storedMarks: storedMarks, keepMarks: keepMarks, Research: Research,
    valueCard: valueCard, changesCard: changesCard, killCard: killCard, newsCard: newsCard,
    judgmentCards: judgmentCards, series: series
  };
  C.draw.research = research;
})();
