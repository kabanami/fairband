/* The company page's Financials tab (the Financials tab's design, 7), loaded after
   company_estimates.js: #company/<symbol>/financials, the three statements by fiscal year and by
   quarter, the revenue by product and by region, and the ratios by fiscal year, from the read's
   tables of periods and lines (GET /api/companies/{symbol}/page/financials). One panel the page's
   full width (7.2): a row of controls, at its left the five sub-tabs, at its right Millions and
   Billions, on every sub-tab but Ratios, and Annual and Quarterly, on the three statements, with
   Half-yearly in Quarterly's place for a company that reports twice a year (7.9); then the
   chart's place, where company_financials_chart.js draws the lines on the chart; then two
   captions on one line, what the table holds and how to pick a line; then the sub-tab's table, or
   Segments' two under their titles (7.3). A table has one column a period, oldest at the left,
   its head the period over the day and month its period ends, and the code of a column whose
   currency is not the tab's; its first column the lines' names, in place as the table scrolls
   sideways; a total, a line, a sub-line or a section head across the row; a table with no line
   draws its sentence. A figure is the read's, only formatted (7.7): an amount or a share count in
   millions or billions, never computed.

   The lines on the chart (7.4): a pick is {kind, table, key, slot}, a line known by its sub-tab,
   its table (null, or product or region on Segments) and its key, with its colour slot. A press
   on a row, a click or Enter or Space while it has the focus, charts its line alone; a row on the
   chart is marked. A section head takes no press. The tab opens on its company's Revenue alone
   (first), and on no line where it has none, when its chart's place stays empty.

   The state: the sub-tab and the period are kept in this script while the app is open, from one
   company to the next; the unit is kept in the browser's localStorage under
   fairband.financials.unit, read and written inside a try, Millions where it keeps nothing.
   Financials, the tab's component, keeps the view and the picks in its state, drawn keyed on the
   company of its answer, so another company's answer opens a new tab and drops the picks, and
   draws it with block, a pure builder of the answer, the view and the picks. The pieces are pure
   functions on FairbandPage.companyFinancials, for the tests, which read them in node, and
   draw.financials hangs on the company page's draw (company.js). */
(function () {
  'use strict';

  var h = React.createElement;
  var P = FairbandPage;
  var C = P.companyPage;

  /* The sub-tabs, each its id and its name. */
  var SUBTABS = [
    ['income', 'Income statement'], ['balance', 'Balance sheet'], ['cashflow', 'Cash flow'],
    ['segments', 'Segments'], ['ratios', 'Ratios']
  ];
  /* The units of the amounts, each its id and its name. */
  var SCALES = [['m', 'Millions'], ['b', 'Billions']];
  /* Segments' two tables, each its id in the answer and its title. */
  var SEGMENTS = [['product', 'Revenue by product'], ['region', 'Revenue by region']];
  /* A row's class by its kind; a line has none, a section head is drawn apart. */
  var KINDS = { total: 'is-total', sub: 'is-sub' };
  var UNIT_KEY = 'fairband.financials.unit';
  var PICK = 'press a line to chart it alone, or its + to add it to the chart';
  var DASH = '—';

  /* The sub-tab and the period a tab opens on: the last the reader chose while the app is open. */
  var kept = { kind: 'income', period: 'annual' };

  function ok(v) { return typeof v === 'number' && isFinite(v); }

  /* ------------------------------------------------------------------------------- the view */

  /* True for a sub-tab by fiscal year only: Segments and Ratios. */
  function yearly(kind) { return kind === 'segments' || kind === 'ratios'; }

  /* The view `view`, {kind, period, scale}, with `change` laid over it; a sub-tab by fiscal year
     only sets the period to annual, so the table always shows one period. */
  function step(view, change) {
    var next = Object.assign({}, view, change);
    if (yearly(next.kind)) next.period = 'annual';
    return next;
  }

  /* The tables of the sub-tab `kind` at `period`, 'annual' or 'quarter', each {id, title,
     table}: Segments' two, by product and by region, under their titles; any other sub-tab's
     one, with no id and no title, a statement's at the period, the ratios' by fiscal year. */
  function tables(answer, kind, period) {
    if (kind === 'segments') {
      return SEGMENTS.map(function (part) {
        return { id: part[0], title: part[1], table: answer.segments[part[0]] };
      });
    }
    var table = kind === 'ratios' ? answer.ratios : answer.statements[kind][period];
    return [{ id: null, title: null, table: table }];
  }

  /* ------------------------------------------------------------------------------ the picks */

  /* The line the tab opens on, as a pick at slot 0: the income statement's revenue, else the
     first line of its annual table, else the first line of the first table that has one, the
     sub-tabs in their order, each by fiscal year; null where no table has a line. */
  function first(answer) {
    var income = answer.statements.income.annual.rows;
    if (income.some(function (row) { return row.kind !== 'head' && row.key === 'revenue'; })) {
      return { kind: 'income', table: null, key: 'revenue', slot: 0 };
    }
    var found = null;
    SUBTABS.some(function (tab) {
      return tables(answer, tab[0], 'annual').some(function (item) {
        var row = item.table.rows.filter(function (r) { return r.kind !== 'head'; })[0];
        if (row) found = { kind: tab[0], table: item.id, key: row.key, slot: 0 };
        return !!row;
      });
    });
    return found;
  }

  /* The picks of the line `line`, {kind, table, key}, alone on the chart: it at slot 0. */
  function alone(line) {
    return [Object.assign({}, line, { slot: 0 })];
  }

  /* The pick among `picks` that is the line `line`, null where it is not on the chart. */
  function picked(picks, line) {
    return picks.filter(function (pick) {
      return pick.kind === line.kind && pick.table === line.table && pick.key === line.key;
    })[0] || null;
  }

  /* ---------------------------------------------------------------------- words and figures */

  /* The decimals of the table's amounts in millions: 1 where its largest amount in size is under
     a thousand million, so a small company's lines do not all read 0 or 3; else 0, and 0 for a
     table with no amount. Each table is judged by itself. */
  function digits(table) {
    var largest = 0;
    table.rows.forEach(function (row) {
      if (row.unit !== 'money') return;
      row.values.forEach(function (v) { if (ok(v)) largest = Math.max(largest, Math.abs(v)); });
    });
    return largest > 0 && largest < 1e9 ? 1 : 0;
  }

  /* A cell's text: the figure `value` of `row`, by its unit. An amount or a share count in
     millions, grouped, to `dp` decimals (digits), or under 'b' in billions to two; a dash for
     none and for 0. Per share and a plain ratio to two decimals; a percent to one, the dividend
     yield to two, as the Overview draws it; a multiple to one with x, a dash at 0; days to none.
     Below zero a minus, none where the figure rounds to zero (company.js's formatters). */
  function figure(row, value, scale, dp) {
    var unit = row.unit;
    if (unit === 'money' || unit === 'shares') {
      if (!ok(value) || value === 0) return DASH;
      return scale === 'b' ? C.decimal(value / 1e9, 2) : C.decimal(value / 1e6, dp);
    }
    if (unit === 'perShare') return C.decimal(value, 2);
    if (unit === 'percent') return C.percent(value, row.key === 'dividendYield' ? 2 : 1);
    if (unit === 'multiple') return C.multiple(value);
    if (unit === 'days') return C.count(value);
    return C.decimal(value, 2);
  }

  /* The first column's head, the unit of the table's figures in the tab's `currency`: USD,
     millions, except per share on the income statement; USD, millions on the other statements
     and Segments; billions under Billions; as each row says on Ratios. */
  function caption(kind, currency, scale) {
    if (kind === 'ratios') return 'as each row says';
    return currency + ', ' + (scale === 'b' ? 'billions' : 'millions') +
      (kind === 'income' ? ', except per share' : '');
  }

  /* The left caption, what the table holds: on a statement the last `count` fiscal years, or
     quarters, or half-years for a company whose `cadence` is half-yearly, the count the table's
     own, and the last fiscal year, quarter or half-year with no count for one; none for a count
     of none, a table with no line, whose sentence says so; Segments' and Ratios' own. */
  function note(kind, period, cadence, count) {
    if (kind === 'segments') return 'by fiscal year, as the company reports its segments';
    if (kind === 'ratios') {
      return 'by fiscal year; the same definitions as Key statistics on the Overview';
    }
    if (!count) return null;
    var what = period === 'annual' ? 'fiscal year'
      : cadence === 'half-yearly' ? 'half-year' : 'quarter';
    return count === 1 ? 'the last ' + what : 'the last ' + count + ' ' + what + 's';
  }

  /* A column's head, [period, day and month, code]: 2026 over 26 Sep, and the column's currency
     where it is not the tab's `currency`, else null. */
  function head(column, currency) {
    return [
      column.label, C.day(column.end).replace(/ \d{4}$/, ''),
      column.currency && column.currency !== currency ? column.currency : null
    ];
  }

  /* --------------------------------------------------------------------------- the unit kept */

  /* The unit the browser keeps: 'b' where it holds b, else 'm', and 'm' where it keeps nothing or
     its store throws. */
  function storedScale() {
    try {
      return window.localStorage.getItem(UNIT_KEY) === 'b' ? 'b' : 'm';
    } catch (e) {
      return 'm';
    }
  }

  /* Keeps the unit `scale` in the browser; where it keeps nothing, the unit lasts while the tab is
     open. Never throws. */
  function keepScale(scale) {
    try {
      window.localStorage.setItem(UNIT_KEY, scale);
    } catch (e) { /* no store */ }
  }

  /* ------------------------------------------------------------------------------- the block */

  /* The tab's panel on `answer` at `view`, {kind, period, scale}, with `picks` on the chart: the
     controls, the chart's place, the two captions and the sub-tab's tables. The chart's place
     holds the chart (company_financials_chart.js) where a line is picked and that script is
     loaded, else nothing. `on.view(change)` is called with the change a control asks for
     ({kind: 'ratios'}, {scale: 'b'}, {period: 'quarter'}), `on.picks(next)` with the picks a
     row's press asks for; neither is called while the block draws. */
  function block(answer, view, picks, on) {
    var found = tables(answer, view.kind, view.period);
    var unit = caption(view.kind, answer.currency, view.scale);
    var lead = found[0].table;
    var chart = P.companyFinancialsChart;
    return h('section', { className: 'app-company__panel app-fin', 'aria-label': 'Financials' },
      controls(answer.cadence, view, on),
      h('div', { className: 'app-fin__chart' }, picks.length && chart ? h(chart.view, {
        answer: answer, picks: picks, period: view.period, scale: view.scale
      }) : null),
      h('div', { className: 'app-fin__notes' },
        h('p', { className: 'caption app-fin__note' }, note(view.kind, view.period,
          answer.cadence, lead.rows.length ? lead.columns.length : 0)),
        h('p', { className: 'caption app-fin__note' }, PICK)),
      found.map(function (item) {
        return h(React.Fragment, { key: item.id || 'table' },
          item.title ? h('h3', { className: 'heading app-fin__title' }, item.title) : null,
          item.table.rows.length
            ? h('div', { className: 'app-fin__scroll' }, sheet(item.table, unit, answer.currency,
              view.scale, { kind: view.kind, table: item.id }, picks, on))
            : h('p', { className: 'body app-fin__none' }, 'No figures on file.'));
      }));
  }

  /* The row of controls: the sub-tabs, the open one selected; the units but on Ratios, no row of
     which is an amount; the periods but on a sub-tab by fiscal year only, the second Half-yearly
     for a company whose `cadence` is half-yearly. Each group is named. */
  function controls(cadence, view, on) {
    var periods = [['annual', 'Annual'],
      ['quarter', cadence === 'half-yearly' ? 'Half-yearly' : 'Quarterly']];
    return h('div', { className: 'app-fin__bar' },
      h('div', { className: 'app-fin__seg', role: 'tablist', 'aria-label': 'Statement' },
        SUBTABS.map(function (tab) {
          return h('button', {
            key: tab[0], type: 'button', role: 'tab', className: 'control app-fin__tab',
            'aria-selected': tab[0] === view.kind ? 'true' : 'false',
            onClick: function () { on.view({ kind: tab[0] }); }
          }, tab[1]);
        })),
      h('div', { className: 'app-fin__opts' },
        view.kind === 'ratios' ? null : choice('app-fin__scale', 'Unit of the amounts', SCALES,
          view.scale, function (id) { on.view({ scale: id }); }),
        yearly(view.kind) ? null : choice('app-fin__period', 'Period', periods, view.period,
          function (id) { on.view({ period: id }); })));
  }

  /* A switch named `label`: its buttons in a group, each of the class `name`, the one at
     `chosen` pressed, each calling `pick` with its id. */
  function choice(name, label, items, chosen, pick) {
    return h('div', { className: 'app-fin__seg', role: 'group', 'aria-label': label },
      items.map(function (item) {
        return h('button', {
          key: item[0], type: 'button', className: 'control ' + name,
          'aria-pressed': item[0] === chosen ? 'true' : 'false',
          onClick: function () { pick(item[0]); }
        }, item[1]);
      }));
  }

  /* A table of periods, the table `where`, {kind, table}, of its sub-tab: its head, the `unit`
     caption over the lines' names, then a column's head a period; then a row a line, its name,
     then its figures in `scale`, a dash in ink-faint; a section head one cell across every
     column, with no figure and no press. A line's row takes the focus and a press (line); one
     on the chart, among `picks`, is marked with its slot. */
  function sheet(table, unit, currency, scale, where, picks, on) {
    var dp = digits(table);
    var across = table.columns.length + 1;
    return h('table', { className: 'app-fin__table' },
      h('thead', null, h('tr', null,
        h('th', { scope: 'col', className: 'caption' }, unit),
        table.columns.map(function (column, i) {
          var words = head(column, currency);
          return h('th', { key: i, scope: 'col', className: 'figure-sm' }, words[0],
            h('span', { className: 'caption' }, words[1]),
            words[2] ? h('span', { className: 'caption app-fin__code' }, words[2]) : null);
        }))),
      h('tbody', null, table.rows.map(function (row, i) {
        if (row.kind === 'head') {
          return h('tr', { key: i, className: 'is-head' },
            h('th', { colSpan: across, className: 'label' }, h('span', null, row.label)));
        }
        var line = { kind: where.kind, table: where.table, key: row.key };
        var own = press(line, picked(picks, line), KINDS[row.kind], on);
        own.key = i;
        return h('tr', own,
          h('th', { scope: 'row', className: 'body' }, row.label),
          row.values.map(function (value, j) {
            var text = figure(row, value, scale, dp);
            return h('td', { key: j, className: 'figure' + (text === DASH ? ' is-nil' : '') },
              text);
          }));
      })));
  }

  /* A line's row's own props: its class, `kind`'s with is-on and its slot's where `pick`, the
     line's on the chart, is one; its focus; and its press, a click or Enter or Space, which
     calls `on.picks` with the line `line` alone. */
  function press(line, pick, kind, on) {
    var names = [kind, pick ? 'is-on is-s' + pick.slot : null].filter(Boolean).join(' ');
    function pressed() { on.picks(alone(line)); }
    return {
      className: names || undefined, tabIndex: 0, 'aria-selected': pick ? 'true' : 'false',
      onClick: pressed,
      onKeyDown: function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        pressed();
      }
    };
  }

  /* The tab: the block of `props.answer`, keeping its view, which opens at the sub-tab and the
     period kept while the app is open and at the unit the browser keeps, and its picks, which
     open on the company's first line alone, or on none. A control's change is laid over the view
     (step); the sub-tab and the period are kept for the next tab, and the unit, where it
     changed, in the browser. A row's press sets the picks. */
  function Financials(props) {
    var view = React.useState({ kind: kept.kind, period: kept.period, scale: storedScale() });
    var line = first(props.answer);
    var picks = React.useState(line ? alone(line) : []);
    return block(props.answer, view[0], picks[0], {
      view: function (change) {
        var next = step(view[0], change);
        kept = { kind: next.kind, period: next.period };
        if (next.scale !== view[0].scale) keepScale(next.scale);
        view[1](next);
      },
      picks: picks[1]
    });
  }

  /* The tab's function, draw.financials(answer, detail): the tab keyed on the company of its
     answer, so another company's answer opens a new one. */
  function financials(answer) {
    return h(Financials, { key: answer.symbol, answer: answer, symbol: answer.symbol });
  }

  /* What the page and the tests use. */
  P.companyFinancials = {
    SUBTABS: SUBTABS, yearly: yearly, step: step, tables: tables, first: first, alone: alone,
    digits: digits, figure: figure, caption: caption, note: note, head: head,
    storedScale: storedScale, keepScale: keepScale, block: block, Financials: Financials
  };
  C.draw.financials = financials;
})();
