/* The report's charts (spec 2026-11-06 Tier 2, 18.4), which the company page's Research tab
   draws (the Research tab's design, 7.4 rules 3, 4, 6 and 7, and 7.9), loaded after
   report_parts.js: the tab reads the series the sections cite and hands them here, and lays out
   the lists it is given. groupCharts gives the charts of Financial performance and health by
   their table's name, each group with its title, quarterCharts the last earnings call's three
   charts by quarter with theirs, gridCharts the grids of Valuation and priceCharts the charts of
   Price and multiples, the first two at the height the tab asks for. In the design system's look
   (charts.md): one measure per chart, each with a BasisChip in its header, mechanical for the
   tables and the series and reviewed for a grid an agent's inputs move, each with no raised panel
   of its own, on its section's panel; no chart has a table, the hover giving a point's figures
   (spec 2026-11-16 company page, 8.4 and 13). The titles are the export's (reports/charts.py),
   so the page and its Markdown never differ: a group of Financial performance and health by its
   table's title, each of its charts by its row's name there; the quarters by the export's title
   for them, By quarter; a reading's grid by its read's title, the secondary valuation's grid by
   its table's; the price against the band by its table's; each P/E series by its column's in
   the year-end table. A cell with no value is left out, a gap, never a zero; a chart with no
   point shows its title and "No data on file."; a read the server refused shows its sentence in
   the chart's place, as it arrives. A ROIC year on average invested capital at or below zero,
   whose figure has the wrong sign and no meaning, is left out of the ROIC chart, and a line under
   the chart names the years and why (B-8; the export's table writes the note in the cell).

   Past the fiscal year (spec 2026-11-15 6.5, 6.6): a chart's bars stand under its table's
   columns, the tooltip naming each by the label the server gives its column.
   The trailing twelve months stand after the fiscal years in grey, marked "to date", and the
   analysts' estimates after them as outlines, marked by their period ("2026E"); under a chart
   with such a bar one line says which is which. The last earnings call's charts run by
   quarter. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var NO_DATA = 'No data on file.';
  var QUARTER_ENDS = { 1: '-03-31', 2: '-06-30', 3: '-09-30', 4: '-12-31' };
  var SHORT_LOG = 5; /* the fewest forward readings drawn as a line (13.7) */

  /* Financial performance and health (18.4's table): the six tables in the export's order, each
     under its title there (charts.TITLES), its charts by its rows, each titled by its row's name
     there (charts.row_name). Buybacks and dividends is one measure, the cash returned
     (`returned`). A lower net debt over EBITDA and a falling share count are the better ones:
     crossing zero, they take the diverging pair the other way round (`inverse`). */
  var FINANCIAL = [
    { table: 'growth', title: 'Growth and profitability', charts: [
      { row: 'revenue', title: 'Revenue' },
      { row: 'operating_margin', title: 'Operating margin' },
      { row: 'eps', title: 'EPS' }
    ] },
    { table: 'cash_flow', title: 'Cash flow', charts: [
      { row: 'free_cash_flow', title: 'Free cash flow' },
      { row: 'stock_compensation_to_revenue', title: 'Stock compensation to revenue' }
    ] },
    { table: 'solvency', title: 'Balance sheet and solvency', charts: [
      { row: 'net_debt_to_ebitda', title: 'Net debt to EBITDA', inverse: true },
      { row: 'interest_coverage', title: 'Interest coverage' }
    ] },
    { table: 'returns', title: 'Returns on capital', charts: [
      { row: 'roic', title: 'ROIC', hurdle: 'hurdle_rate' }
    ] },
    { table: 'capital_allocation', title: 'Capital allocation', charts: [
      { rows: ['buybacks', 'dividends'], title: 'Buybacks and dividends' },
      { row: 'share_count_change', title: 'Share count change', inverse: true }
    ] },
    { table: 'quality', title: 'Quality scores', charts: [
      { row: 'altman_z', title: "Altman's Z″" },
      { row: 'piotroski_f', title: "Piotroski's F" }
    ] }
  ];
  /* The last earnings call (spec 2026-11-15 6.5): the quarters table under its title in the
     export (charts.QUARTERS_TITLE), its charts by its rows, each titled by its row's name there,
     run by quarter. */
  var QUARTERS_TITLE = 'By quarter';
  var QUARTERLY = { table: 'quarters', title: QUARTERS_TITLE, by: 'quarter', charts: [
    { row: 'revenue', title: 'Revenue' },
    { row: 'operating_margin', title: 'Operating margin' },
    { row: 'eps', title: 'EPS' }
  ] };
  var BAND_TITLE = 'The price against the band by quarter';
  var GRID_TITLE = 'The grid of secondary valuation ';
  /* The tick under the trailing twelve months' bar, and the line's sentence for the estimates'
     (6.6), before its full stop: their cells' note follows it after a comma where they carry one,
     the EPS's basis (the whole-branch review's I2). */
  var TO_DATE = 'to date';
  var OUTLINED = 'Outlined: analysts\' estimates';

  /* ------------------------------------------------------- the financial tables */

  /* The financial tables of the read's body by their names. */
  function tablesByName(body) {
    var byName = {};
    body.tables.forEach(function (t) { byName[t.name] = t; });
    return byName;
  }

  /* A part's charts, each set as `look` sets it, from its table's rows and columns; with no
     table, every chart with "No data on file.". */
  function chartsOf(part, table, currency, look) {
    var rows = {};
    if (table) table.rows.forEach(function (r) { rows[r.name] = r; });
    var columns = table ? table.columns : null;
    return part.charts.map(function (c) {
      return c.hurdle ? spread(c, rows, look) : bars(c, rows, columns, part.by, currency, look);
    });
  }

  /* One row's bars, one measure (HistoryBars): a currency in the statements' currency, the EPS a
     share of it, a percentage as one, a multiple or a score bare. Run by the part's `by`, a
     quarter; else by period where a bar is the trailing twelve months or an estimate, with the
     line that says which under the chart, and by fiscal year where none is (6.6). Set as `look`
     sets it, at its height, where it gives none the bundle's. */
  function bars(c, rows, columns, by, currency, look) {
    var row = c.rows ? returned(rows[c.rows[0]], rows[c.rows[1]]) : rows[c.row];
    var series = row ? points(row, columns) : [];
    if (!series.length) return look.wrap(c.title, noData(c.title));
    var unit = row.unit;
    var caption = unit === 'per-share' ? currency + ' a share' : undefined;
    var line = kindsLine(series); /* a point carries its column's kind and label */
    return look.wrap(c.title, h(React.Fragment, null,
      h(F.HistoryBars, {
        title: c.title, series: series, basis: 'mechanical',
        unit: unit === 'currency' ? currency : caption,
        format: unit === 'percent' ? F.formatPercent : undefined,
        inverse: !!c.inverse, by: by || (line ? 'period' : undefined), height: look.height
      }),
      line ? h('p', { className: 'caption app-muted' }, line) : null));
  }

  /* A row's cells as a chart's points, oldest first, each under its column of the table's
     `columns`: its tick (`period`) the year for a fiscal year, "to date" for the trailing twelve
     months, an estimate's period ("2026E") and a quarter's short name ("Q3 26"); its `kind`,
     `trailing` or `estimate`, none otherwise; its `label`, the column's, which the tooltip reads;
     and its cell's `note` where the cell has one, which the line under the chart reads. A cell
     with no value is left out, a gap, never a zero (18.4). On a table served without columns, an
     older answer, a point is its cell's period and value. */
  function points(row, columns) {
    var under = {};
    (columns || []).forEach(function (column) { under[column.period] = column; });
    return row.cells.map(function (cell) {
      var column = Object.prototype.hasOwnProperty.call(under, cell.period)
        ? under[cell.period] : null;
      if (!column) return { period: cell.period, value: cell.value };
      var p = { period: tick(column), value: cell.value, label: column.label };
      if (column.kind === 'trailing' || column.kind === 'estimate') p.kind = column.kind;
      if (cell.note) p.note = cell.note;
      return p;
    }).filter(function (p) { return p.value != null; });
  }

  /* The tick under a column's bar: "to date" for the trailing twelve months, a quarter's short
     name, and the period otherwise, a fiscal year's ("2025") or an estimate's ("2026E"). */
  function tick(column) {
    if (column.kind === 'trailing') return TO_DATE;
    return column.kind === 'quarter' ? quarterTick(column) : column.period;
  }

  /* A quarter's tick, the quarter and the last two digits of its fiscal year, "Q3 26" for
     `2026-Q3`; a period the store names otherwise (a half-year, `2026-H1`) takes the column's
     label, its year shortened so where the label ends in one ("H1 26"), else as it is. */
  function quarterTick(column) {
    var named = /^\d\d(\d\d)-(Q[1-4])$/.exec(column.period);
    if (named) return named[2] + ' ' + named[1];
    return column.label.replace(/(^|\D)\d\d(\d\d)$/, '$1$2');
  }

  /* The line under a chart with a bar that is not a fiscal year, from its columns' kinds and
     labels, or its points', which carry them: "Grey: the 12 months to 30 Sep 2026. Outlined:
     analysts' estimates.", the first sentence alone without an estimate and the second alone
     without the trailing twelve months; none with neither (6.6). Where an estimate point carries
     its cell's note, the second sentence says it after a comma, in the cell's words: "Outlined:
     analysts' estimates, on the analysts' own basis, which can leave out items the reported EPS
     includes." (the EPS's, tables.ANALYSTS_BASIS). */
  function kindsLine(columns) {
    var trailing = columns.filter(function (c) { return c.kind === 'trailing'; })[0];
    var estimates = columns.filter(function (c) { return c.kind === 'estimate'; });
    var noted = estimates.filter(function (c) { return c.note; })[0];
    var said = trailing ? ['Grey: the ' + trailing.label + '.'] : [];
    if (estimates.length) said.push(OUTLINED + (noted ? ', ' + noted.note : '') + '.');
    return said.length ? said.join(' ') : null;
  }

  /* The cash returned to holders a period, one measure: the buybacks and the dividends, which
     the cash flow signs as outflows, summed and turned, each under its cells' period, so the
     trailing twelve months keep their column; none where either is missing. */
  function returned(buybacks, dividends) {
    if (!buybacks || !dividends) return null;
    return {
      unit: 'currency',
      cells: buybacks.cells.map(function (cell, i) {
        var paid = dividends.cells[i].value;
        var value = cell.value == null || paid == null ? null : -(cell.value + paid);
        return { period: cell.period, value: value };
      })
    };
  }

  /* ROIC against the hurdle rate the returns table carries, the policy's r (restated into the
     reporting currency on a company in another currency, as its ROIC is in it), both percentages
     on one axis with the gap filled (SpreadChart); a year missing either is left out. Set as
     `look` sets it. */
  function spread(c, rows, look) {
    var drawn = roicPoints(rows[c.row], rows[c.hurdle]);
    if (!drawn.series.length) return look.wrap(c.title, noData(c.title, drawn.left));
    return look.wrap(c.title, h(React.Fragment, null,
      h(F.SpreadChart, {
        title: c.title, subtitle: 'against the hurdle rate', series: drawn.series,
        basis: 'mechanical', height: look.height, hurdleLabel: 'Hurdle rate'
      }),
      drawn.left ? h('p', { className: 'caption app-muted' }, drawn.left) : null));
  }

  /* The ROIC chart's points, percentages, a year missing either figure left out; and `left`, the
     sentence for the years left out because the ROIC cell carries a note: average invested
     capital at or below zero, on which the figure has the wrong sign and no meaning, or at
     exactly zero is none (method 16.5), "Fiscal 2024 and 2025 are not drawn: <the note>.",
     none without such a year. */
  function roicPoints(roic, hurdle) {
    var cells = !roic || !hurdle ? [] : roic.cells.map(function (cell, i) {
      return { period: cell.period, roic: cell.value, wacc: hurdle.cells[i].value,
        note: cell.note };
    });
    var noted = cells.filter(function (p) { return p.note; });
    var series = cells.filter(function (p) {
      return p.roic != null && p.wacc != null && !p.note;
    }).map(function (p) { return { period: p.period, roic: p.roic * 100, wacc: p.wacc * 100 }; });
    return { series: series, left: noted.length ? notDrawn(noted) : null };
  }

  function notDrawn(noted) {
    var years = noted.map(function (p) { return p.period; });
    var listed = years.length === 1 ? years[0]
      : years.slice(0, -1).join(', ') + ' and ' + years[years.length - 1];
    return 'Fiscal ' + listed + (years.length === 1 ? ' is' : ' are') + ' not drawn: ' +
      noted[0].note + '.';
  }

  /* ------------------------------------------------------------------ the grids */

  /* Valuation (13.8, 11): each sensitivity reading the sections cite, in the order first cited,
     as its read words it, reviewed when the report rests on a review, a reading the server
     refused its sentence in its place; then the grid of the secondary valuation the report rests
     on, reviewed, an agent's inputs. Each against the price of the report's snapshot, each set
     as `look` sets it. None without either. */
  function grids(report, readings, look) {
    var a = report.appendixA;
    var drawn = readings.map(function (read, i) {
      return read.error ? look.wrap('reading ' + i, refused('A sensitivity reading', read.error))
        : reading(read.body, a.snapshot.price, report.reviewId == null ? 'mechanical' : 'reviewed',
          look);
    });
    if (a.secondary && a.secondary.grid) {
      drawn.push(secondaryGrid(a.secondary, a.snapshot.price, look));
    }
    return drawn;
  }

  /* A reading's grid: its rows the first input's values and its columns the second's, a pair the
     engine valued none at without a fill, the pair in force ringed. */
  function reading(r, price, basis, look) {
    return look.wrap('reading ' + r.id, h(F.SensitivityGrid, {
      title: r.title, rows: r.rowWords, cols: r.colWords, cells: r.cells, price: price,
      current: r.current ? { row: r.current[0] - 1, col: r.current[1] - 1 } : undefined,
      rowLabel: r.rowLabel, colLabel: r.colLabel, basis: basis
    }));
  }

  /* The secondary valuation's grid (spec 11): the rates across, the terminal growths down or, on
     the parts form, the shift in every part's, the valuation's own pair in the middle. */
  function secondaryGrid(s, price, look) {
    var g = s.grid;
    var title = GRID_TITLE + s.id;
    return look.wrap(title, h(F.SensitivityGrid, {
      title: title, rows: g.rowWords, cols: g.cols.map(F.formatPercent), cells: g.cells,
      price: price, current: { row: 1, col: 1 },
      rowLabel: g.rowsAre === 'shifts' ? "Every part's terminal growth" : 'Terminal growth',
      colLabel: 'r', basis: 'reviewed'
    }));
  }

  /* ----------------------------------------------------------- price and multiples */

  /* BandHistory: the five years of closes a quarter each, the quarter's last close, with the band
     in force at the quarter's end, the newest snapshot priced on or before it: none before the
     first snapshot, none on a refusal's. The past year's high and low in the subtitle. When the
     band's history did not load, the price alone, with the server's sentence under it. Set as
     `look` sets it. */
  function band(closes, history, look) {
    if (closes.error) {
      return look.wrap(BAND_TITLE, refused('The price history', closes.error));
    }
    var list = closes.body.closes;
    if (!list.length) return look.wrap(BAND_TITLE, noData(BAND_TITLE));
    var marks = history.error ? [] : history.body.points;
    var series = quarters(list).map(function (q) {
      var p = inForce(marks, q.end);
      return {
        period: q.period, price: q.close,
        fairLow: p ? p.fairLow : null, fairHigh: p ? p.fairHigh : null
      };
    });
    return look.wrap(BAND_TITLE, [
      h(F.BandHistory, {
        key: 'chart', title: BAND_TITLE, subtitle: pastYear(list), series: series,
        basis: 'mechanical'
      }),
      history.error ? refused('The band\'s history', history.error, 'refused') : null
    ]);
  }

  /* The closes a calendar quarter each, oldest first: its last close and its end. */
  function quarters(closes) {
    var out = [];
    var at = {};
    closes.forEach(function (c) {
      var year = c.date.slice(0, 4);
      var q = Math.floor((Number(c.date.slice(5, 7)) - 1) / 3) + 1;
      var period = 'Q' + q + ' ' + year;
      if (!Object.prototype.hasOwnProperty.call(at, period)) {
        at[period] = out.length;
        out.push({ period: period, end: year + QUARTER_ENDS[q] });
      }
      out[at[period]].close = c.close.value;
    });
    return out;
  }

  /* The newest band-history point priced on or before the day; none before the first. */
  function inForce(marks, day) {
    var found = null;
    marks.forEach(function (p) { if (p.day <= day) found = p; });
    return found;
  }

  /* The highest and the lowest close of the year to the newest. */
  function pastYear(closes) {
    var newest = closes[closes.length - 1].date;
    var since = (Number(newest.slice(0, 4)) - 1) + newest.slice(4);
    var year = closes.filter(function (c) { return c.date >= since; })
      .map(function (c) { return c.close.value; });
    return 'Past year: high ' + F.formatMoney(Math.max.apply(null, year)) +
      ', low ' + F.formatMoney(Math.min.apply(null, year));
  }

  /* The P/E against its own history (13.7), each series against its average over the ten years
     on file, its subtitle saying which: the trailing one a point a month, with the read's note on
     it, the server's sentence, when it has one; the forward one a point a day logged, since the
     log began, once the log holds five readings (SHORT_LOG). A forward log of fewer is no chart:
     its newest reading as a figure and since when the log is kept (shortLog), no line and no
     average. A trailing series with no point says why in the server's words when it sends them,
     the series' note ("the series could not be read") or the read's; a forward log with none,
     that nothing is on file. Each set as `look` sets it. */
  function multiples(read, look) {
    if (read.error) return look.wrap('multiples', refused('The P/E history', read.error));
    var m = read.body;
    var forward = m.peForward;
    var logged = forward.points.filter(function (p) { return p.value != null; });
    return [
      multiple('Trailing P/E', m.pe, m.pe ? byMonth(m.pe.points) : [],
        'the last P/E of each month against its ten-year average' +
          (m.peNote ? ' · ' + m.peNote : ''), (m.pe && m.pe.note) || m.peNote, look),
      0 < logged.length && logged.length < SHORT_LOG ? look.wrap('forward', shortLog(forward)) :
        multiple('Forward P/E', forward, forward.points.map(function (p) {
          return { period: F.formatDate(p.day), value: p.value };
        }), forward.since ? 'since ' + F.formatDate(forward.since) : undefined, undefined, look)
    ];
  }

  function multiple(title, found, series, subtitle, why, look) {
    var drawn = series.some(function (p) { return p.value != null; });
    return look.wrap(title, drawn ? h(F.MultipleHistory, {
      title: title, subtitle: subtitle, series: series, average: found.stats.avg10y.value,
      basis: 'mechanical'
    }) : noData(title, why));
  }

  /* A forward log too short to draw (13.7): its title and its basis, as a chart's head; its
     newest reading as a figure, on its day, in MultipleHistory's end label's form ("17.5x"); and
     since when the log is kept. */
  function shortLog(forward) {
    var logged = forward.points.filter(function (p) { return p.value != null; });
    var newest = logged[logged.length - 1];
    var sentence =
      'logged since ' + F.formatDate(forward.since) + '; a reading is added at each price refresh';
    return h('figure', { className: 'fb-c' },
      h('figcaption', { className: 'fb-c__head' },
        h('span', { className: 'fb-c__title heading' }, 'Forward P/E'),
        h(F.BasisChip, { basis: 'mechanical', compact: true })),
      h('p', { className: 'figure' },
        newest.value.toFixed(1) + 'x on ' + F.formatDate(newest.day)),
      h('p', { className: 'caption app-muted' }, sentence));
  }

  /* The trailing series a point a month, the month's last P/E, from the first month on file to
     the last; a month with none, a loss's, is null, a gap in the line. */
  function byMonth(marks) {
    if (!marks.length) return [];
    var last = {};
    marks.forEach(function (p) { last[p.day.slice(0, 7)] = p.value; });
    var out = [];
    var year = Number(marks[0].day.slice(0, 4));
    var month = Number(marks[0].day.slice(5, 7));
    var end = marks[marks.length - 1].day.slice(0, 7);
    for (;;) {
      var key = year + '-' + (month < 10 ? '0' : '') + month;
      out.push({
        period: F.formatDate(key + '-01').replace(/^\d+ /, ''),
        value: Object.prototype.hasOwnProperty.call(last, key) ? last[key] : null
      });
      if (key === end) return out;
      month += 1;
      if (month > 12) { month = 1; year += 1; }
    }
  }

  /* ------------------------------------------------------------- the exports */

  /* Rule 3 (the Research tab's design, 7.4, 7.9): each group by its table's name, from growth to
     quality, { title, charts }: its title, the export's, which the tab draws over a row of groups
     and not beside a paragraph, whose lead word names the group; and its charts, each with no
     panel, at `height` where given. The server's sentence alone, { refused }, when the tables
     did not load. */
  function groupCharts(read, height) {
    if (read.error) return { refused: refused('The financial tables', read.error) };
    var look = { wrap: bare, height: height };
    var byName = tablesByName(read.body);
    var drawn = {};
    FINANCIAL.forEach(function (part) {
      drawn[part.table] = {
        title: part.title,
        charts: chartsOf(part, byName[part.table], read.body.currency, look)
      };
    });
    return drawn;
  }

  /* Rule 4: the three charts by quarter, { title, charts }: the export's title for them, By
     quarter, and the charts, each with no panel, at `height` where given. The server's sentence
     alone, { refused }, when the tables did not load; none on an answer from before the quarters
     were served. */
  function quarterCharts(read, height) {
    if (read.error) return { refused: refused('The figures by quarter', read.error) };
    var body = read.body;
    if (!body.quarters) return null;
    return {
      title: QUARTERLY.title,
      charts: chartsOf(QUARTERLY, body.quarters, body.currency, { wrap: bare, height: height })
    };
  }

  /* Rule 6: Valuation's grids, each with no panel. */
  function gridCharts(report, readings) {
    return grids(report, readings, { wrap: bare });
  }

  /* Rule 7: the price against the band once the closes and the band's history have landed, then
     the trailing and the forward P/E once the multiples history has, or its sentence; each with
     no panel. */
  function priceCharts(series) {
    var look = { wrap: bare };
    var drawn = series.closes && series.band ? [band(series.closes, series.band, look)] : [];
    return series.multiples ? drawn.concat(multiples(series.multiples, look)) : drawn;
  }

  /* --------------------------------------------------------------------- the parts */

  /* A chart with no panel of its own, on the panel of its section. */
  function bare(key, chart) {
    return h('div', { key: key, className: 'app-charts__chart' }, chart);
  }

  /* A chart with no point: its title and its basis, and that nothing is on file, or the
     server's sentence why when it sent one, not an empty plot. */
  function noData(title, why) {
    return h('figure', { className: 'fb-c' },
      h('figcaption', { className: 'fb-c__head' },
        h('span', { className: 'fb-c__title heading' }, title),
        h(F.BasisChip, { basis: 'mechanical', compact: true })),
      h('p', { className: 'caption app-muted' }, why || NO_DATA));
  }

  /* A read the server refused: its sentence, as it arrives. */
  function refused(what, sentence, key) {
    return h('p', { key: key, className: 'caption app-report__error' },
      what + ' did not load: ' + sentence + '.');
  }

  /* What the Research tab and the tests use: the four exports, and the points of the ROIC chart,
     of a row and the line under a chart, which the tests read in node. */
  P.reportCharts = {
    groupCharts: groupCharts, quarterCharts: quarterCharts, gridCharts: gridCharts,
    priceCharts: priceCharts, roicPoints: roicPoints, points: points, kindsLine: kindsLine
  };
})();
