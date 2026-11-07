/* The report page's charts (spec 2026-11-06 Tier 2, 18.4), loaded after report.js, which reads
   the series the sections cite and hands them here: ReportReader draws each section's charts
   under its heading and above its sentences (its `charts`, by the heading). In the design
   system's look (charts.md, CompanyReport.md): one measure per chart, two to a row, each on a
   raised panel with a BasisChip in its header, mechanical for the tables and the series and
   reviewed for a grid an agent's inputs move; every chart but a grid, its own twin, has its table
   twin behind the page's one table toggle, `tables`. The titles are the export's
   (reports/charts.py), so the page and its Markdown never differ: a part of Financial
   performance and health under its table's title, each chart by its row's name; a reading's grid
   by its read's title, the secondary valuation's grid by its table's; the price against the band
   by its table's; each P/E series by its column's in the year-end table. A cell with no value is
   left out, a gap, never a zero; a chart with no point shows its title and "No data on file.";
   a read the server refused shows its sentence, as it arrives. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var NO_DATA = 'No data on file.';
  var QUARTER_ENDS = { 1: '-03-31', 2: '-06-30', 3: '-09-30', 4: '-12-31' };

  /* Financial performance and health (18.4's table): the six tables in the export's order, each
     under its title (charts.TITLES), its charts by its rows, each titled by its row's name there
     (charts.row_name). Buybacks and dividends is one measure, the cash returned (`returned`). A
     lower net debt over EBITDA and a falling share count are the better ones: crossing zero, they
     take the diverging pair the other way round (`inverse`). */
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
  var BAND_TITLE = 'The price against the band by quarter';
  var GRID_TITLE = 'The grid of secondary valuation ';

  /* Each section's charts by its heading, as ReportReader places them; none before the series
     are read. */
  function draw(report, series, tables) {
    if (!series) return {};
    return {
      'Financial performance and health': financial(series.tables, tables),
      'Valuation': valuation(report, series.readings),
      'Price and multiples': price(series, tables)
    };
  }

  /* ------------------------------------------------------- the financial tables */

  /* The six parts, each its table's title over its charts; the server's sentence in their place
     when the tables did not load (no statements on file, say). */
  function financial(read, tables) {
    if (read.error) return refused('The financial tables', read.error);
    var body = read.body;
    var byName = {};
    body.tables.forEach(function (t) {
      var rows = {};
      t.rows.forEach(function (r) { rows[r.name] = r; });
      byName[t.name] = rows;
    });
    return h('div', { className: 'app-charts__parts' }, FINANCIAL.map(function (part) {
      var rows = byName[part.table] || {};
      return h(React.Fragment, { key: part.table },
        h('h5', { className: 'label app-charts__part' }, part.title),
        h('div', { className: 'app-charts' }, part.charts.map(function (c) {
          return c.hurdle ? spread(c, rows, tables) : bars(c, rows, body.currency, tables);
        })));
    }));
  }

  /* One row's columns, one measure (HistoryBars): a currency in the statements' currency, the
     EPS a share of it, a percentage as one, a multiple or a score bare. */
  function bars(c, rows, currency, tables) {
    var row = c.rows ? returned(rows[c.rows[0]], rows[c.rows[1]]) : rows[c.row];
    var series = row ? points(row) : [];
    var unit = row ? row.unit : null;
    var caption = unit === 'per-share' ? currency + ' a share' : undefined;
    return panel(c.title, series.length ? h(F.HistoryBars, {
      title: c.title, series: series, basis: 'mechanical', tableView: tables,
      unit: unit === 'currency' ? currency : caption,
      format: unit === 'percent' ? F.formatPercent : undefined,
      inverse: !!c.inverse
    }) : noData(c.title));
  }

  /* A row's cells as a chart's points, oldest first: a cell with no value is left out, a gap,
     never a zero (18.4). */
  function points(row) {
    return row.cells.map(function (cell) { return { period: cell.period, value: cell.value }; })
      .filter(function (p) { return p.value != null; });
  }

  /* The cash returned to holders a year, one measure: the buybacks and the dividends, which the
     cash flow signs as outflows, summed and turned; none where either is missing. */
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

  /* ROIC against the hurdle rate the returns table carries, the policy's r, both percentages on
     one axis with the gap filled (SpreadChart); a year missing either is left out. */
  function spread(c, rows, tables) {
    var roic = rows[c.row], hurdle = rows[c.hurdle];
    var series = !roic || !hurdle ? [] : roic.cells.map(function (cell, i) {
      return { period: cell.period, roic: cell.value, wacc: hurdle.cells[i].value };
    }).filter(function (p) { return p.roic != null && p.wacc != null; })
      .map(function (p) { return { period: p.period, roic: p.roic * 100, wacc: p.wacc * 100 }; });
    return panel(c.title, series.length ? h(F.SpreadChart, {
      title: c.title, subtitle: 'against the hurdle rate', series: series, basis: 'mechanical',
      tableView: tables
    }) : noData(c.title));
  }

  /* ------------------------------------------------------------------ the grids */

  /* Valuation (13.8, 11): each sensitivity reading the sections cite, in the order first cited,
     as its read words it, reviewed when the report rests on a review; then the grid of the
     secondary valuation the report rests on, reviewed, an agent's inputs. Each against the price
     of the report's snapshot. None without either. */
  function valuation(report, readings) {
    var a = report.appendixA;
    var drawn = readings.map(function (read, i) {
      return read.error ? panel('reading ' + i, refused('A sensitivity reading', read.error))
        : reading(read.body, a.snapshot.price, report.reviewId == null ? 'mechanical' : 'reviewed');
    });
    if (a.secondary && a.secondary.grid) drawn.push(secondaryGrid(a.secondary, a.snapshot.price));
    return drawn.length ? h('div', { className: 'app-charts' }, drawn) : null;
  }

  /* A reading's grid: its rows the first input's values and its columns the second's, a pair the
     engine valued none at without a fill, the pair in force ringed. */
  function reading(r, price, basis) {
    return panel('reading ' + r.id, h(F.SensitivityGrid, {
      title: r.title, rows: r.rowWords, cols: r.colWords, cells: r.cells, price: price,
      current: r.current ? { row: r.current[0] - 1, col: r.current[1] - 1 } : undefined,
      rowLabel: r.rowLabel, colLabel: r.colLabel, basis: basis
    }));
  }

  /* The secondary valuation's grid (spec 11): the rates across, the terminal growths down or, on
     the parts form, the shift in every part's, the valuation's own pair in the middle. */
  function secondaryGrid(s, price) {
    var g = s.grid;
    var title = GRID_TITLE + s.id;
    return panel(title, h(F.SensitivityGrid, {
      title: title, rows: g.rowWords, cols: g.cols.map(F.formatPercent), cells: g.cells,
      price: price, current: { row: 1, col: 1 },
      rowLabel: g.rowsAre === 'shifts' ? "Every part's terminal growth" : 'Terminal growth',
      colLabel: 'r', basis: 'reviewed'
    }));
  }

  /* ----------------------------------------------------------- price and multiples */

  /* The price against the band, the full width, then the two P/E series side by side. */
  function price(series, tables) {
    return h('div', { className: 'app-charts' },
      band(series.closes, series.band, tables), multiples(series.multiples, tables));
  }

  /* BandHistory: the five years of closes a quarter each, the quarter's last close, with the band
     in force at the quarter's end, the newest snapshot priced on or before it: none before the
     first snapshot, none on a refusal's. The past year's high and low in the subtitle. */
  function band(closes, history, tables) {
    var failed = closes.error || history.error;
    if (failed) return panel(BAND_TITLE, refused('The price history', failed), true);
    var list = closes.body.closes;
    if (!list.length) return panel(BAND_TITLE, noData(BAND_TITLE), true);
    var marks = history.body.points;
    var series = quarters(list).map(function (q) {
      var p = inForce(marks, q.end);
      return {
        period: q.period, price: q.close,
        fairLow: p ? p.fairLow : null, fairHigh: p ? p.fairHigh : null
      };
    });
    return panel(BAND_TITLE, h(F.BandHistory, {
      title: BAND_TITLE, subtitle: pastYear(list), series: series, basis: 'mechanical',
      tableView: tables
    }), true);
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
     log began. */
  function multiples(read, tables) {
    if (read.error) return panel('multiples', refused('The P/E history', read.error));
    var m = read.body;
    var forward = m.peForward;
    return [
      multiple('Trailing P/E', m.pe, m.pe ? byMonth(m.pe.points) : [],
        'the last P/E of each month against its ten-year average' +
          (m.peNote ? ' · ' + m.peNote : ''), tables),
      multiple('Forward P/E', forward, forward.points.map(function (p) {
        return { period: F.formatDate(p.day), value: p.value };
      }), forward.since ? 'since ' + F.formatDate(forward.since) : undefined, tables)
    ];
  }

  function multiple(title, found, series, subtitle, tables) {
    var drawn = series.some(function (p) { return p.value != null; });
    return panel(title, drawn ? h(F.MultipleHistory, {
      title: title, subtitle: subtitle, series: series, average: found.stats.avg10y.value,
      basis: 'mechanical', tableView: tables
    }) : noData(title));
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

  /* --------------------------------------------------------------------- the parts */

  /* A chart on its raised panel; the price chart takes the full width. */
  function panel(key, chart, wide) {
    return h('div', { key: key, className: wide ? 'app-chart app-chart--wide' : 'app-chart' },
      chart);
  }

  /* A chart with no point: its title and its basis, and that nothing is on file, not an empty
     plot. */
  function noData(title) {
    return h('figure', { className: 'fb-c' },
      h('figcaption', { className: 'fb-c__head' },
        h('span', { className: 'fb-c__title heading' }, title),
        h(F.BasisChip, { basis: 'mechanical', compact: true })),
      h('p', { className: 'caption app-muted' }, NO_DATA));
  }

  /* A read the server refused: its sentence, as it arrives. */
  function refused(what, sentence) {
    return h('p', { className: 'caption app-report__error' },
      what + ' did not load: ' + sentence + '.');
  }

  P.reportCharts = { draw: draw };
})();
