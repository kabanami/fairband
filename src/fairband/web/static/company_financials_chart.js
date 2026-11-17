/* The Financials tab's chart (the Financials tab's design, 7.4 to 7.7 and 7.9), loaded after
   company_financials.js, whose tab draws it in its chart's place, above the captions, with the
   lines the reader picked, up to four, at the tab's period and unit. Each pick is a series of its
   line's table at the period. A line by fiscal year only, a segment or a ratio, is off by
   quarter, and so is a statement's line the quarterly table lacks: an off line draws nothing.
   The chart stands on the union of the drawn lines' periods, known by their labels, in order of
   the day each ends, so a line with no figure for a period draws no mark there.

   The head of one line: its name, its newest figure in figure-lg as its table writes it, then the
   newest period and the plot's unit in words; of one line that is off, its name and why. The head
   of several: a label a line, drawn or off, in their order, each its swatch, a square for bars
   and a round dot for a line, its name, its figure at the newest period or, faded, why it is off,
   and a x that takes it off; then the newest period. The labels are the chart's legend. Where no
   line draws, the plot's place holds the sentence that says so.

   The lines of one unit share a plot and its scale; each other unit takes a plot of its own under
   it, in the order the units were first picked, 160px high alone, 120px each of two, 100px each
   of three and 90px each of four; with several lines each plot states its unit at its top left.
   The periods' labels stand once, under the last plot, every second or every third left out,
   from the newest back, where they would touch. An amount, a per-share figure or a share count is
   bars from a zero baseline: one line's at most 44px wide and 72% of the period's width, two to
   four lines' side by side in their order, each at most 28px and 2px apart, together within 72%
   of the period's width; rounded 4px at the data end and square at the baseline; with one line
   picked its figure below zero in chart-neg-3, and with several picked, drawn or off, every bar
   in its line's colour, as its label is. Any other unit is a 2px line on a scale that fits its
   figures, broken at a gap, a lone figure between gaps a dot, its newest point an end marker
   10px across ringed in surface-raised. A figure draws no mark where its table writes a dash
   (none, or an amount, a share count or a multiple of exactly 0), where it is a bar of 0, or
   where it is an amount or a per-share figure in another currency than the tab's; no scale is
   built from such a figure, and a plot with no figure draws its frame, its baseline. A plot's
   scale in four clean steps, three under 150px, widened by a step where it would be flat; the
   ticks bare and compact at its right (company_chart.js's steps and figures), monospaced in
   ink-faint; the zero line in border, the others in chart-grid, solid.

   The pointer over the plots, or the arrow keys, Home and End while they have the focus, pick a
   period (company_chart.js's keyed). One line drawn: a box over its mark with the period and the
   figure. Several: a box beside the period, on the side with room, with the period, then a row a
   line drawn, its swatch, its name and its figure. A figure in another currency is led by its
   code. The other periods' bars fade; where a line plot is drawn a crosshair runs through every
   plot and each line's point takes a marker. Escape, the pointer leaving and a loss of focus
   clear it. Nothing animates and no table twins the chart. A mark, a label and a box's row carry
   their line's colour slot as a class, is-s0 to is-s3, which the page's CSS paints chart-1 to
   chart-4; no text wears a series colour. The pieces are pure functions of the answer, the
   picks, the period, the unit and the width, on FairbandPage.companyFinancialsChart for the tab
   and the tests, which read them in node; view, the component, keeps the period picked and the
   width it measures, and puts the focus on the next label's x, or on the plot, after a x takes
   its line off. */
(function () {
  'use strict';

  var h = React.createElement;
  var P = FairbandPage;
  var F = P.companyFinancials;
  var K = P.companyChart;

  /* The chart's frame, as the mockup draws it: the width drawn at before one is measured and the
     least it is drawn at; the left margin; the right margin, the ticks' room; the room above a
     plot, for its unit's words; a plot's height by the number of plots; the room under a plot
     over the next one's; and the room under the last plot for the periods' labels. */
  var WIDTH = 900;
  var LEAST = 280;
  var LEFT = 6;
  var RIGHT = 58;
  var TOP = 18;
  var HEIGHTS = [160, 120, 100, 90];
  var BETWEEN = 8;
  var BOTTOM = 22;
  var BAR_MAX = 44; /* a lone line's bar, at most */
  var BAR_SOME = 28; /* a bar among several of a period, at most */
  var GAP = 2; /* between the bars of a period */
  var BAR_SHARE = 0.72; /* of its period's width, at most */
  var RADIUS = 4; /* a bar's corners at its data end */
  var CHAR = 6.6; /* a monospaced 11px character's width, near enough to keep labels apart */
  var TIP_CHAR = 7.2; /* a monospaced 12px character's, the box's figure-sm */
  var NAME_CHAR = 7; /* an 11px character's of a line's name in the box, at the widest */
  var TIP_ROOM = 46; /* a box's row beyond its words: its swatch, its gaps, padding and border */
  var DASH = '—';
  var OWN = { money: true, perShare: true }; /* the units in the tab's currency */
  var WORDS = { percent: 'percent', multiple: 'multiple', ratio: 'ratio', days: 'days' };
  var COMPACT = [[1e12, 'T'], [1e9, 'B'], [1e6, 'M'], [1e3, 'K'], [1, '']];
  var KEYS = { ArrowLeft: true, ArrowRight: true, Home: true, End: true };
  var READ = 'The left and right arrow keys read each period.';
  var TAKE = 'Take off the chart';
  var NONE = 'These lines have figures by fiscal year only. Choose Annual, or press a line in ' +
    'the table.';

  function ok(v) { return typeof v === 'number' && isFinite(v); }

  /* A coordinate as a path writes it, to two decimals. */
  function px(v) { return Math.round(v * 100) / 100; }

  /* ------------------------------------------------------------------------------ the series */

  /* The table and the row of the line `pick` at `period`, {table, row}; null where its table
     there has no such line. */
  function lineAt(answer, pick, period) {
    var found = F.tables(answer, pick.kind, period).filter(function (item) {
      return item.id === pick.table;
    })[0];
    var row = found ? found.table.rows.filter(function (r) {
      return r.kind !== 'head' && r.key === pick.key;
    })[0] : null;
    return row ? { table: found.table, row: row } : null;
  }

  /* The series of `picks` at `period`, 'annual' or 'quarter', one a pick in their order, each
     {pick, slot, name, unit, form, off, columns, at, digits}: its name on the chart and its unit,
     its form by its unit (companyFinancials.form), bars for money, per share and a share count
     and a line for the rest; why it is off, null where it draws: by year only for a segment or a
     ratio by quarter, no figures by quarter for a statement's line the quarterly table lacks,
     both read by fiscal year; its table's columns; `at`, each column's label to {value,
     currency}, its figure and the column's currency; its table's decimals
     (companyFinancials.digits). A statement's line its annual table lacks, which its quarterly
     one holds, stands on the annual columns with no figure; a pick no table holds has no
     series. */
  function series(answer, picks, period) {
    var out = [];
    picks.forEach(function (pick) {
      var yearly = F.yearly(pick.kind);
      var off = yearly && period === 'quarter' ? 'by year only' : null;
      var found = lineAt(answer, pick, yearly ? 'annual' : period);
      if (!found && !yearly && period === 'quarter') {
        found = lineAt(answer, pick, 'annual');
        if (found) off = 'no figures by quarter';
      }
      var named = found || lineAt(answer, pick, 'quarter');
      if (!named) return;
      var table = found ? found.table : F.tables(answer, pick.kind, period)[0].table;
      var at = {};
      if (found) {
        table.columns.forEach(function (column, i) {
          at[column.label] = { value: found.row.values[i], currency: column.currency };
        });
      }
      out.push({
        pick: pick, slot: pick.slot, name: named.row.name, unit: named.row.unit,
        form: F.form(named.row.unit), off: off, columns: table.columns, at: at,
        digits: F.digits(table)
      });
    });
    return out;
  }

  /* The periods the series `drawn` stand on: the union of their columns, known by their labels,
     each {label, end}, in order of the day each ends, a label's first column giving its day. */
  function periods(drawn) {
    var seen = Object.create(null);
    var out = [];
    drawn.forEach(function (s) {
      s.columns.forEach(function (column) {
        if (seen[column.label]) return;
        seen[column.label] = true;
        out.push({ label: column.label, end: column.end });
      });
    });
    return out.sort(function (a, b) {
      return a.end < b.end ? -1 : a.end > b.end ? 1 : a.label < b.label ? -1 : 1;
    });
  }

  /* A plot's unit in words, in the tab's `currency` and the unit of the amounts `scale`: USD,
     millions; USD a share; millions of shares; percent, multiple, ratio, days. */
  function unitWords(unit, currency, scale) {
    var size = scale === 'b' ? 'billions' : 'millions';
    if (unit === 'money') return currency + ', ' + size;
    if (unit === 'perShare') return currency + ' a share';
    if (unit === 'shares') return size + ' of shares';
    return WORDS[unit] || '';
  }

  /* --------------------------------------------------------------------------- the figures */

  /* True where `cell`, {value, currency}, of the series `s` holds a figure: one its table does
     not write as a dash (companyFinancials.figure: none, or an amount, a share count or a
     multiple of exactly 0). */
  function figured(cell, s) {
    return !!cell && F.figure({ unit: s.unit, key: s.pick.key }, cell.value, 'm', 0) !== DASH;
  }

  /* True where `code`, a column's currency, is not the tab's `currency` for a line in `unit`, an
     amount or a per-share figure; a share count, a percent, a multiple, a ratio and days are
     drawn whatever the column's currency (7.9). */
  function foreign(unit, code, currency) {
    return !!OWN[unit] && !!code && code !== currency;
  }

  /* True where the cell `cell` of the series `s` draws a mark in a tab in `currency`: a figure,
     in the tab's currency where its unit is, and not a bar of 0. */
  function marked(cell, s, currency) {
    return figured(cell, s) && !foreign(s.unit, cell.currency, currency) &&
      !(s.form === 'bars' && cell.value === 0);
  }

  /* The text of the cell `cell` of the series `s` in `scale`, as its table writes it, with the
     code and a space before a figure in another currency than the tab's `currency`; a dash for
     no figure. */
  function said(s, cell, scale, currency) {
    if (!figured(cell, s)) return DASH;
    var text = F.figure({ unit: s.unit, key: s.pick.key }, cell.value, scale, s.digits);
    return foreign(s.unit, cell.currency, currency) ? cell.currency + ' ' + text : text;
  }

  /* -------------------------------------------------------------------------- the geometry */

  /* The scale of the figures `values` of a plot of `form` in about `count` clean steps,
     {step, from, to}, its ends `from` and `to` steps from zero: a bar plot's holds zero, a line
     plot's fits its figures. Where its ends would meet, a flat line or no figure, it is widened
     by a step (a bar plot's upwards from zero), so nothing divides by zero. */
  function scale(values, form, count) {
    var lo = values.length ? Math.min.apply(null, values) : 0;
    var hi = values.length ? Math.max.apply(null, values) : 0;
    if (form === 'bars') { lo = Math.min(0, lo); hi = Math.max(0, hi); }
    var step = K.niceStep(hi > lo ? hi - lo : Math.abs(hi), count);
    var from = Math.floor(lo / step + 1e-9);
    var to = Math.ceil(hi / step - 1e-9);
    if (to <= from) {
      if (form !== 'bars') from -= 1;
      to += 1;
    }
    return { step: step, from: from, to: to };
  }

  /* The ticks' texts of a plot in `unit` on the scale `sc`, from its foot up, bare and compact:
     an amount or a share count in thousands, millions, billions or trillions by the plot's
     largest tick (0B, 200B; 0M, 50M), a percent with %, a multiple with x, a per-share figure, a
     plain ratio and days as plain numbers, each to the decimals its step needs
     (companyChart.decimals and bare). */
  function tickTexts(unit, sc) {
    var size = Math.max(Math.abs(sc.from), Math.abs(sc.to)) * sc.step;
    var by = 1;
    var after = '';
    if (unit === 'money' || unit === 'shares') {
      var found = COMPACT.filter(function (c) { return size >= c[0]; })[0] || [1, ''];
      by = 1 / found[0];
      after = found[1];
    } else if (unit === 'percent') {
      by = 100;
      after = '%';
    } else if (unit === 'multiple') {
      after = 'x';
    }
    var dp = K.decimals(sc.step * by);
    var out = [];
    for (var k = sc.from; k <= sc.to; k++) out.push(K.bare(k * sc.step * by, dp) + after);
    return out;
  }

  /* A bar of the figure `v` from the baseline at `base` to `end`, at `x`, `width` wide: its box
     and its path, square at the baseline and rounded at its data end, at least 1px tall. */
  function bar(x, width, base, end, v) {
    var d = v > 0 ? 1 : -1;
    if (Math.abs(end - base) < 1) end = base - d;
    var r = Math.min(RADIUS, Math.abs(end - base), width / 2);
    var turn = end + d * r;
    return {
      x: x, y: Math.min(base, end), width: width, height: Math.abs(end - base),
      d: 'M' + px(x) + ' ' + px(base) + 'V' + px(turn) +
        'Q' + px(x) + ' ' + px(end) + ' ' + px(x + r) + ' ' + px(end) +
        'H' + px(x + width - r) +
        'Q' + px(x + width) + ' ' + px(end) + ' ' + px(x + width) + ' ' + px(turn) +
        'V' + px(base) + 'Z'
    };
  }

  /* The plot of the series `lines`, of one unit, in their order, each with its cells a period, on
     the periods at `xs`, each `band` wide, its top at `top` and `height` high, in a tab in
     `currency`, `lone` where one line is picked (geometry): its unit, its form, its top and its
     height; its ticks from its foot up, in four steps from 150px high and three under it, each
     its y, its text and whether it is the zero line, its frame its baseline alone where it has no
     figure to scale; the y of its baseline, or of its scale's end nearer zero; and its series,
     each with its bars, a period's bars side by side about its middle in the lines' order, or its
     line's path, its lone figures' dots and its end marker, and each period's mark's top, null
     where it draws none. */
  function plotOf(lines, xs, band, top, height, currency, lone) {
    var form = lines[0].form;
    var values = [];
    lines.forEach(function (s) {
      s.cells.forEach(function (cell) { if (marked(cell, s, currency)) values.push(cell.value); });
    });
    var sc = scale(values, form, height >= 150 ? 4 : 3);
    var lo = sc.from * sc.step;
    var hi = sc.to * sc.step;
    function y(v) { return top + (hi - v) / (hi - lo) * height; }
    var texts = tickTexts(lines[0].unit, sc);
    var ticks = [];
    for (var k = sc.from; k <= sc.to; k++) {
      if (values.length || k === 0) {
        ticks.push({
          y: Math.round(y(k * sc.step)) + 0.5, text: values.length ? texts[k - sc.from] : null,
          zero: k === 0
        });
      }
    }
    var count = lines.length;
    var width = count === 1 ? Math.min(band * BAR_SHARE, BAR_MAX)
      : Math.max(1, Math.min(BAR_SOME, (band * BAR_SHARE - GAP * (count - 1)) / count));
    var group = count * width + GAP * (count - 1);
    var shaped = lines.map(function (s, q) {
      var bars = [];
      var dots = [];
      var path = '';
      var end = null;
      var points = s.cells.map(function (cell, i) {
        return marked(cell, s, currency) ? { i: i, x: xs[i], y: y(cell.value) } : null;
      });
      var tops = points.map(function (p, i) {
        if (!p) return null;
        if (form === 'bars') {
          var v = s.cells[i].value;
          var b = bar(xs[i] - group / 2 + q * (width + GAP), width, y(0), p.y, v);
          bars.push(Object.assign(b, { i: i, neg: lone && v < 0 }));
          return b.y;
        }
        var before = i > 0 && points[i - 1];
        var after = i < points.length - 1 && points[i + 1];
        if (!before && !after) dots.push(p);
        else path += (before ? 'L' : 'M') + px(p.x) + ' ' + px(p.y);
        end = p;
        return p.y;
      });
      if (end && dots[dots.length - 1] === end) dots.pop();
      return Object.assign({}, s, { bars: bars, path: path, dots: dots, end: end, tops: tops });
    });
    return {
      unit: lines[0].unit, form: form, top: top, height: height, ticks: ticks,
      base: y(Math.min(Math.max(0, lo), hi)), series: shaped
    };
  }

  /* The periods' labels: one a period, at its x, where there is room; where they would touch,
     every second, or every third, counted from the newest back, so the newest stays. Each
     {i, x, text, anchor}, anchored so that it stays inside the svg `width` wide. */
  function labels(cols, xs, band, width) {
    var widest = Math.max.apply(null, cols.map(function (c) { return c.label.length; }));
    var every = Math.max(1, Math.ceil((widest * CHAR + 10) / band));
    var out = [];
    cols.forEach(function (c, i) {
      if ((cols.length - 1 - i) % every) return;
      var half = c.label.length * CHAR / 2;
      var anchor = xs[i] - half < 0 ? 'start' : xs[i] + half > width ? 'end' : 'middle';
      out.push({ i: i, x: xs[i], text: c.label, anchor: anchor });
    });
    return out;
  }

  /* The chart of the series `drawn`, in their order, at `width` (the width drawn at before one is
     measured where it is none, and never under the least), in the tab's `currency`, in the svg's
     units, `lone` where one line is picked, so that the chart's head is that line's and not the
     labels, and its bars below zero take the negative colour; with two or more lines picked,
     drawn or off, every bar keeps its line's colour, as its label does. Null where no series
     draws or they stand on no period. Its width and height, its plots' left edge and width, each
     period's `band` and x, at the middle of its band; its periods and their labels; and its
     plots, one a unit in the order the units first come, each holding its unit's series, one
     under the other, of one height by their number, each with its room above it. */
  function geometry(drawn, width, currency, lone) {
    var cols = periods(drawn);
    if (!drawn.length || !cols.length) return null;
    var W = Math.max(LEAST, ok(width) && width > 0 ? width : WIDTH);
    var plotWidth = W - LEFT - RIGHT;
    var band = plotWidth / cols.length;
    var xs = cols.map(function (c, i) { return LEFT + band * (i + 0.5); });
    var units = [];
    var byUnit = Object.create(null);
    drawn.forEach(function (s) {
      if (!byUnit[s.unit]) {
        byUnit[s.unit] = [];
        units.push(s.unit);
      }
      byUnit[s.unit].push(Object.assign({}, s, {
        cells: cols.map(function (c) { return s.at[c.label] || null; })
      }));
    });
    var high = HEIGHTS[Math.min(units.length, HEIGHTS.length) - 1];
    var plots = units.map(function (unit, k) {
      return plotOf(byUnit[unit], xs, band, TOP + k * (high + BETWEEN + TOP), high, currency,
        !!lone);
    });
    var last = plots[plots.length - 1];
    return {
      width: W, height: last.top + last.height + BOTTOM, left: LEFT, plotWidth: plotWidth,
      band: band, currency: currency, periods: cols, xs: xs, labels: labels(cols, xs, band, W),
      plots: plots
    };
  }

  /* The period under `x`, in the svg's units, of the chart `g`. */
  function nearest(g, x) {
    var i = Math.floor((x - g.left) / g.band);
    return Math.max(0, Math.min(g.periods.length - 1, i));
  }

  /* What the hover shows for the period `i` of the chart `g`, in `scale`; null for no period,
     one the chart lacks, and a period where no line drawn has a figure. Of one line drawn,
     {i, x, y, left, text}: the period's label and the line's figure as its table writes it, with
     the code before a figure in another currency; centred on the period's x, kept inside the
     chart (`left`, its left edge, its width reckoned from its text), and standing over `y`, the
     top of its bar, a little over its line's point, or its baseline where the figure draws no
     mark. Of several, {i, x, y, left, right, label, rows}: the period's label, then a row a line
     drawn, plot by plot, each {slot, form, name, text}, its figure written as one line's; at the
     first plot's top `y`, beside the period: at its right, its left edge at `left`, where the
     box's width, reckoned from its words, has room there; else at its left, its right edge
     `right` from the chart's; else, with room on neither side, against the chart's right edge,
     never past its left. The other of `left` and `right` is null. */
  function box(g, i, scale) {
    if (!g || !ok(i) || i < 0 || i >= g.periods.length) return null;
    var all = [];
    g.plots.forEach(function (p) { all = all.concat(p.series); });
    if (!all.some(function (s) { return figured(s.cells[i], s); })) return null;
    if (all.length === 1) return boxOfOne(g, all[0], i, scale);
    var rows = all.map(function (s) {
      return {
        slot: s.slot, form: s.form, name: s.name, text: said(s, s.cells[i], scale, g.currency)
      };
    });
    var wide = TIP_ROOM + Math.max.apply(null, rows.map(function (row) {
      return row.name.length * NAME_CHAR + row.text.length * TIP_CHAR;
    }));
    var x = g.xs[i];
    var after = x + g.band / 2 + 4;
    var before = x - g.band / 2 - 4;
    var left = after + wide <= g.width ? after : before - wide >= 0 ? null
      : Math.max(0, g.width - wide);
    return {
      i: i, x: x, y: g.plots[0].top, left: left, right: left === null ? g.width - before : null,
      label: g.periods[i].label, rows: rows
    };
  }

  /* The box of the period `i` of the one line `s` drawn on the chart `g`, in `scale` (box). */
  function boxOfOne(g, s, i, scale) {
    var text = g.periods[i].label + ' · ' + said(s, s.cells[i], scale, g.currency);
    var wide = text.length * TIP_CHAR + 18;
    var x = g.xs[i];
    var y = s.tops[i] === null ? g.plots[0].base : s.tops[i] - (s.form === 'line' ? 8 : 0);
    return {
      i: i, x: x, y: y, left: Math.max(0, Math.min(g.width - wide, x - wide / 2)), text: text
    };
  }

  /* ----------------------------------------------------------------------------- the block */

  /* The chart of `picks` on `answer` at `period` in the unit of the amounts `scale`, the period
     `at` picked (null: none, and so is one the chart lacks), drawn at `width`: its head, the one
     line's (head) or the labels of several (legend), then its plots, or, where no line draws,
     the sentence in their place; null where no table holds a pick. `on` holds the refs the
     plots' wrapper and the labels' list take, `pick(i)`, called with the period the pointer or a
     key picks, null to clear it, and `drop(pick)`, called with the pick whose x is pressed; none
     of them is called while it draws. */
  function block(answer, picks, period, scale, at, width, on) {
    var all = series(answer, picks, period);
    var drawn = all.filter(function (s) { return s.off === null; });
    var several = all.length > 1;
    var g = geometry(drawn, width, answer.currency, !several);
    if (!all.length || (!g && drawn.length)) return null;
    var picked = g && ok(at) && at >= 0 && at < g.periods.length ? at : null;
    return h(React.Fragment, null,
      several ? legend(g, all, scale, answer.currency, on) : head(g, all[0], scale),
      g ? plot(g, picked, box(g, picked, scale), scale, several, on)
        : h('p', { className: 'caption app-fin__blank' }, NONE));
  }

  /* The head of the chart of one line `s`: its name, its newest figure in figure-lg, at the
     chart's newest period, and that period and the plot's unit in words; of a line that is off,
     its name and why. */
  function head(g, s, scale) {
    if (s.off) {
      return h('div', { className: 'app-fin__chead' },
        h('h2', { className: 'heading' }, s.name),
        h('p', { className: 'caption app-fin__unit' }, s.off));
    }
    var newest = g.periods[g.periods.length - 1];
    return h('div', { className: 'app-fin__chead' },
      h('h2', { className: 'heading' }, s.name),
      h('p', { className: 'figure-lg' }, said(s, s.at[newest.label], scale, g.currency)),
      h('p', { className: 'caption app-fin__unit' },
        newest.label + ', ' + unitWords(s.unit, g.currency, scale)));
  }

  /* The head of the chart `g` of several lines `all`, in a tab in `currency`: a label a line, in
     their order, drawn or off, each wearing its slot, its swatch, its name, its figure at the
     chart's newest period as its table writes it, the code before a figure in another currency,
     or, faded, why it is off, and a x that calls `on.drop` with its pick; then the caption of the
     newest period, none where no line draws. */
  function legend(g, all, scale, currency, on) {
    var newest = g ? g.periods[g.periods.length - 1].label : null;
    return h('div', { className: 'app-fin__chead' },
      h('ul', { className: 'app-fin__legend', ref: on ? on.legend : null }, all.map(function (s) {
        return h('li', {
          key: s.pick.kind + ' ' + s.pick.table + ' ' + s.pick.key,
          className: 'control app-fin__label is-s' + s.slot + (s.off ? ' is-off' : '')
        },
          swatch(s),
          h('span', null, s.name),
          s.off ? h('span', { className: 'caption' }, s.off)
            : h('span', { className: 'figure-sm' }, said(s, s.at[newest], scale, currency)),
          h('button', {
            type: 'button', className: 'app-fin__x', 'aria-label': TAKE, title: TAKE,
            onClick: function () { on.drop(s.pick); }
          }, '×'));
      })),
      newest ? h('p', { className: 'caption app-fin__unit' }, 'figures for ' + newest) : null);
  }

  /* The swatch of `s`, a series or a box's row, in the colour of the slot its label or row wears:
     a square for bars, a round dot for a line. */
  function swatch(s) {
    return h('span', {
      className: 'app-fin__key' + (s.form === 'line' ? ' app-fin__key--round' : '')
    });
  }

  /* The plots' wrapper, which takes the focus and the keys, named by what it draws and how the
     keys read it, and holds the svg and, with a period picked that has a figure, its box `tip`.
     The svg holds the plots, each its frame, with its unit in words at its top left where
     `several` lines are picked, and its marks; the periods' labels under the last; and what the
     period picked draws over them. The pointer over the svg picks the period under it, the svg's
     width scaled to the units it draws in; leaving the svg or the wrapper's focus clears it. */
  function plot(g, at, tip, scale, several, on) {
    var names = [];
    g.plots.forEach(function (p) {
      p.series.forEach(function (s) {
        names.push(s.name + ' in ' + unitWords(s.unit, g.currency, scale));
      });
    });
    var span = g.periods[0].label + ' to ' + g.periods[g.periods.length - 1].label;
    return h('div', {
      className: 'app-fin__plot', ref: on ? on.ref : null, tabIndex: 0, role: 'group',
      'aria-label': names.join('; ') + ', ' + span + '. ' + READ,
      onKeyDown: function (event) {
        if (KEYS[event.key]) event.preventDefault();
        var next = K.keyed(at, event.key, g.periods.length);
        if (next !== at) on.pick(next);
      },
      onBlur: function () { on.pick(null); }
    },
      h('svg', {
        viewBox: '0 0 ' + g.width + ' ' + g.height, height: g.height, 'aria-hidden': 'true',
        onMouseMove: function (event) {
          var rect = event.currentTarget.getBoundingClientRect();
          var ratio = rect.width ? g.width / rect.width : 1;
          on.pick(nearest(g, (event.clientX - rect.left) * ratio));
        },
        onMouseLeave: function () { on.pick(null); }
      },
        g.plots.map(function (p, k) {
          var words = several ? unitWords(p.unit, g.currency, scale) : null;
          return h('g', { key: k }, frame(g, p, words), marks(p, at, !!tip));
        }),
        g.labels.map(function (label) {
          return h('text', {
            key: 'when' + label.i, className: 'app-fin__when', x: label.x, y: g.height - 6,
            textAnchor: label.anchor
          }, label.text);
        }),
        over(g, at)),
      tip && tip.rows ? listed(tip) : null,
      tip && !tip.rows ? h('div', {
        className: 'figure-sm app-fin__tip',
        style: { left: tip.left + 'px', top: tip.y - 6 + 'px' }
      }, tip.text) : null);
  }

  /* The box of several lines `tip` (box): the period, then a row a line, its swatch, its name
     and its figure, each row wearing its line's slot. */
  function listed(tip) {
    var side = tip.left === null ? { right: tip.right + 'px' } : { left: tip.left + 'px' };
    return h('div', {
      className: 'app-fin__tip app-fin__tip--rows',
      style: Object.assign(side, { top: tip.y + 'px' })
    },
      h('div', { className: 'figure-sm app-fin__tipwhen' }, tip.label),
      tip.rows.map(function (row, k) {
        return h('div', { key: k, className: 'app-fin__tiprow is-s' + row.slot },
          swatch(row),
          h('span', { className: 'caption' }, row.name),
          h('span', { className: 'figure-sm' }, row.text));
      }));
  }

  /* A plot's unit in its `words` at its top left, where there are words; its grid, a line a tick
     across the plot, the zero line apart; and its ticks' texts at its right. */
  function frame(g, p, words) {
    var right = g.left + g.plotWidth;
    return [
      words ? h('text', {
        key: 'measure', className: 'app-fin__measure', x: g.left, y: p.top - 6
      }, words) : null
    ].concat(p.ticks.map(function (tick, k) {
      return h(React.Fragment, { key: 'tick' + k },
        h('line', {
          className: tick.zero ? 'app-fin__zero' : 'app-fin__grid', x1: g.left, x2: right,
          y1: tick.y, y2: tick.y
        }),
        tick.text === null ? null
          : h('text', { className: 'app-fin__tick', x: right + 8, y: tick.y + 4 }, tick.text));
    }));
  }

  /* A plot's marks, each of its series' slot: its bars, faded but the period `at` where `boxed`,
     a period's box shown; or its line, its dots and its end marker. */
  function marks(p, at, boxed) {
    return p.series.map(function (s, k) {
      var slot = ' is-s' + s.slot;
      if (p.form === 'bars') {
        return s.bars.map(function (b) {
          return h('path', {
            key: 'bar' + k + '-' + b.i, d: b.d,
            className: 'app-fin__col' + slot + (b.neg ? ' is-neg' : '') +
              (boxed && b.i !== at ? ' is-dim' : '')
          });
        });
      }
      return [
        s.path ? h('path', { key: 'line' + k, className: 'app-fin__line' + slot, d: s.path })
          : null,
        s.dots.map(function (dot) {
          return h('circle', {
            key: 'dot' + k + '-' + dot.i, className: 'app-fin__dot' + slot, cx: dot.x, cy: dot.y,
            r: 2.5
          });
        }),
        s.end ? h('circle', {
          key: 'end' + k, className: 'app-fin__end' + slot, cx: s.end.x, cy: s.end.y, r: 5
        }) : null
      ];
    });
  }

  /* What the period `at` draws over the plots where one is a line's: a crosshair through it from
     the first plot's top to the last plot's foot, and a marker on each line's point there. */
  function over(g, at) {
    var lines = g.plots.filter(function (p) { return p.form === 'line'; });
    if (at === null || !lines.length) return null;
    var x = g.xs[at];
    var last = g.plots[g.plots.length - 1];
    return h(React.Fragment, null,
      h('line', {
        className: 'app-fin__cross', x1: x, x2: x, y1: g.plots[0].top, y2: last.top + last.height
      }),
      lines.map(function (p, k) {
        return p.series.map(function (s, q) {
          return s.tops[at] === null ? null : h('circle', {
            key: 'mark' + k + '-' + q, className: 'app-fin__mark is-s' + s.slot, cx: x,
            cy: s.tops[at], r: 5
          });
        });
      }));
  }

  /* The chart, props {answer, picks, period, scale, onDrop}: the block, keeping the period
     picked, none when it opens, and the width of the plots' wrapper, measured after each draw and
     at each resize of the window. A label's x calls onDrop with its pick; after the draw that
     follows, the focus goes to the first label's x left, or to the plots where none is. */
  function view(props) {
    var at = React.useState(null);
    var width = React.useState(WIDTH);
    var wrapper = React.useRef(null);
    var list = React.useRef(null);
    var dropped = React.useRef(false);
    function measure() {
      var found = wrapper.current ? wrapper.current.clientWidth : 0;
      if (found > 0) width[1](found);
    }
    React.useEffect(measure);
    React.useEffect(function () {
      if (!dropped.current) return;
      dropped.current = false;
      var next = (list.current && list.current.querySelector('.app-fin__x')) || wrapper.current;
      if (next) next.focus({ preventScroll: true });
    });
    React.useEffect(function () {
      window.addEventListener('resize', measure);
      return function () { window.removeEventListener('resize', measure); };
    }, []);
    return block(props.answer, props.picks, props.period, props.scale, at[0], width[0], {
      ref: wrapper, legend: list, pick: at[1],
      drop: function (pick) {
        dropped.current = true;
        props.onDrop(pick);
      }
    });
  }

  /* What the tab and the tests use. */
  P.companyFinancialsChart = {
    series: series, periods: periods, unitWords: unitWords, geometry: geometry,
    nearest: nearest, box: box, block: block, view: view
  };
})();
