/* The company page's price chart (the company page's design, 8.4), loaded after
   company_overview.js, whose Overview draws it first in its right column on the answer's
   `prices`, [day, close, volume] oldest first, keyed on the company so each company's chart opens
   at 1Y with no day picked. The Price block: its seven ranges in its head, 1Y chosen when it
   opens; above the plot the newest close in figure-lg and the change over the range with its
   sign, its percent and the range in words (14.3), in the text's own colour. Two plots on one
   time axis, one measure each (charts.md), the rows evenly spaced by trading day: the close as a
   2px line in chart-1 with its end marker ringed in surface-raised and the newest close in a tag
   on the axis, the y tick the tag covers left out; under it the volume as bars in chart-context,
   its greatest labelled. Grid lines solid in chart-grid; ticks bare and monospaced in ink-faint,
   the first x tick shown and each January naming the year, a range over two years ticking by
   year. The pointer over the plot, or the arrow keys with the plot focused, picks a day: a
   crosshair across both plots, a ringed dot on its close and a box with its day, close and
   volume on the side with room. No table, and nothing animates. A range with no row draws its
   sentence in the plot's place. A row with no close is left out of the line and one with no
   volume draws no bar; a flat or single close's scale is widened by a step, so nothing divides
   by zero. The pieces are pure functions of the rows and the width, on
   FairbandPage.companyChart for the Overview and for the tests, which read them in node; Chart
   keeps the range, the day picked and the width it measures. */
(function () {
  'use strict';

  var h = React.createElement;
  var P = FairbandPage;
  var C = P.companyPage;

  /* The ranges: each its button's label and its words in the lead. */
  var RANGES = [
    ['1M', 'past month'], ['3M', 'past 3 months'], ['6M', 'past 6 months'],
    ['YTD', 'year to date'], ['1Y', 'past year'], ['3Y', 'past 3 years'], ['5Y', 'past 5 years']
  ];
  var MONTHS_BACK = { '1M': 1, '3M': 3, '6M': 6, '1Y': 12, '3Y': 36, '5Y': 60 };
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  /* The plot's frame, as the mockup draws it: the width drawn at before one is measured; the left
     margin; the close's plot under its name, the gap, the volume's plot and the x ticks' room. The
     right margin holds the tag and the y ticks: the tag's width and 8px. */
  var WIDTH = 720;
  var LEFT = 4;
  var TOP = 18;
  var PRICE_HEIGHT = 250;
  var GAP = 30;
  var VOLUME_HEIGHT = 56;
  var BOTTOM = 22;
  var HEIGHT = TOP + PRICE_HEIGHT + GAP + VOLUME_HEIGHT + BOTTOM;
  var TAG_WIDTH = 50; /* the tag's least width; a longer close widens it */
  var CHAR = 6.6; /* a monospaced 11px character's width, near enough to fit a label */
  var CLEAR = 14; /* a y tick nearer the tag than this is left out */
  var BAR_MAX = 24; /* chart-bar-max */
  var MOST = 7; /* the x ticks drawn at most */
  var KEYS = { ArrowLeft: true, ArrowRight: true, Home: true, End: true };

  function ok(v) { return typeof v === 'number' && isFinite(v); }

  /* US dollars, as the page writes money: $356.27. */
  function usd(v) { return C.money({ value: v, currency: 'USD' }); }

  /* A figure as an axis writes it, bare: to `dp` decimals with no thousands separator, as the
     page's money, and a minus, U+2212, where it is below zero at that precision. */
  function bare(v, dp) {
    var text = Math.abs(v).toFixed(dp);
    return v < 0 && /[1-9]/.test(text) ? '−' + text : text;
  }

  /* The range's words: past year for 1Y. */
  function words(id) {
    var found = RANGES.filter(function (range) { return range[0] === id; })[0];
    return found ? found[1] : '';
  }

  /* --------------------------------------------------------------------------- the rows */

  /* The day `months` months before the day `iso`, on its day of the month, or on that month's
     last day where it has no such day: 2025-11-13 for 2026-11-13 and twelve, 2026-02-28 for
     2026-03-31 and one. */
  function monthsBefore(iso, months) {
    var total = Number(iso.slice(0, 4)) * 12 + Number(iso.slice(5, 7)) - 1 - months;
    var year = Math.floor(total / 12);
    var month = total % 12 + 1;
    var last = new Date(Date.UTC(year, month, 0)).getUTCDate();
    return year + '-' + two(month) + '-' + two(Math.min(Number(iso.slice(8, 10)), last));
  }

  function two(n) { return n < 10 ? '0' + n : String(n); }

  /* The rows of the range `id`: from the day that many months before the newest row's day, or,
     for YTD, from the last close of the year before the newest row's, the last row dated before
     its 1 January, whatever day of the week the year ended on, else from the year's first row; a
     range the series does not fill keeps every row it has. */
  function inRange(prices, id) {
    var rows = prices || [];
    if (!rows.length) return [];
    var newest = rows[rows.length - 1][0];
    var january = newest.slice(0, 4) + '-01-01';
    var before = rows.filter(function (row) { return row[0] < january; });
    var from = id !== 'YTD' ? monthsBefore(newest, MONTHS_BACK[id])
      : before.length ? before[before.length - 1][0] : january;
    return rows.filter(function (row) { return row[0] >= from; });
  }

  /* The rows with a close. */
  function priced(rows) {
    return (rows || []).filter(function (row) { return ok(row[1]); });
  }

  /* The change over the rows (14.3): the newest close less the first, and that over the first;
     null for fewer than two closes and for a first close of 0. */
  function change(rows) {
    var closes = priced(rows);
    if (closes.length < 2 || closes[0][1] === 0) return null;
    var amount = closes[closes.length - 1][1] - closes[0][1];
    return { amount: amount, ratio: amount / closes[0][1] };
  }

  /* The lead's change in words: +$83.32 (+30.5%) past year, each figure with its sign; null
     without a change. */
  function lead(rows, id) {
    var moved = change(rows);
    if (!moved) return null;
    return C.signed(usd(Math.abs(moved.amount)), moved.amount) + ' (' +
      C.signed(C.percent(Math.abs(moved.ratio)), moved.ratio) + ') ' + words(id);
  }

  /* ------------------------------------------------------------------------- the geometry */

  /* A clean step for `span` in about `count` steps: 1, 2, 5 or 10 times a power of ten, the raw
     step where it is already one, else rounded up to the next. The raw step over its power of ten
     is read to twelve figures, so a float's last digits (0.0005 reads 5.000000000000001
     ten-thousandths) do not round a clean step up a size. A span that is not above zero is taken
     as 1, so a flat series has a step. */
  function niceStep(span, count) {
    var raw = (span > 0 ? span : 1) / count;
    var power = Math.pow(10, Math.floor(Math.log10(raw)));
    var unit = Number((raw / power).toPrecision(12));
    return (unit > 5 ? 10 : unit > 2 ? 5 : unit > 1 ? 2 : 1) * power;
  }

  /* The decimals a tick at `step` needs to differ from its neighbours: none from 1 up. */
  function decimals(step) { return step >= 1 ? 0 : Math.ceil(-Math.log10(step) - 1e-9); }

  /* The x ticks: at each row that opens a month, or a year when `long`, as { i, text }. At most
     seven: thinned to every second, third, fourth or sixth month, counted from January so that
     January stays, or to every so many years. The first shown and each January name the year;
     by year, the year alone. */
  function xTicks(rows, long) {
    var found = [];
    for (var i = 1; i < rows.length; i++) {
      var a = rows[i - 1][0];
      var b = rows[i][0];
      if (long ? a.slice(0, 4) !== b.slice(0, 4) : a.slice(0, 7) !== b.slice(0, 7)) {
        found.push({ i: i, year: Number(b.slice(0, 4)), month: Number(b.slice(5, 7)) });
      }
    }
    var every = Math.ceil(found.length / MOST);
    while (!long && every < 12 && 12 % every) every++;
    return found.filter(function (tick) {
      return (long ? tick.year : tick.month - 1) % every === 0;
    }).map(function (tick, at) {
      var text = long ? String(tick.year)
        : MONTHS[tick.month - 1] + (at === 0 || tick.month === 1 ? ' ' + tick.year : '');
      return { i: tick.i, text: text };
    });
  }

  /* The two plots of `rows` at `width` (the width drawn at before one is measured where it is
     none), in the svg's units; null where no row has a close. Each row's x, evenly spaced by
     trading day from the plot's left edge to its right, and the y of its close, null without
     one; the line through the closes; the newest close, its marker's place and its tag; the
     close's scale in clean steps, a grid line at each and a tick at each the tag leaves clear;
     the volume's bars, one a row with a volume above zero, under the greatest, none wider than
     chart-bar-max nor past the plot's edges; the x ticks, each anchored so that it stays inside
     the svg. */
  function geometry(rows, width) {
    var closes = priced(rows);
    if (!closes.length) return null;
    var n = rows.length;
    var W = ok(width) && width > 0 ? width : WIDTH;
    var last = closes[closes.length - 1][1];
    var tagText = bare(last, 2);
    var tagWidth = Math.max(TAG_WIDTH, Math.round(tagText.length * CHAR + 10));
    var plotWidth = Math.max(1, W - LEFT - tagWidth - 8);
    var values = closes.map(function (row) { return row[1]; });
    var lo = Math.min.apply(null, values);
    var hi = Math.max.apply(null, values);
    var step = niceStep(hi - lo, 4);
    var y0 = Math.floor(lo / step) * step;
    var y1 = Math.ceil(hi / step) * step;
    if (y1 <= y0) { y0 -= step; y1 += step; }
    var volumeTop = TOP + PRICE_HEIGHT + GAP;
    var base = volumeTop + VOLUME_HEIGHT;
    function y(v) { return TOP + (1 - (v - y0) / (y1 - y0)) * PRICE_HEIGHT; }
    var xs = rows.map(function (row, i) {
      return LEFT + (n > 1 ? i / (n - 1) : 0.5) * plotWidth;
    });
    var ys = rows.map(function (row) { return ok(row[1]) ? y(row[1]) : null; });
    var path = '';
    var newest = 0;
    rows.forEach(function (row, i) {
      if (ys[i] === null) return;
      path += (path ? 'L' : 'M') + xs[i].toFixed(1) + ' ' + ys[i].toFixed(1);
      newest = i;
    });
    var lastX = xs[newest];
    var lastY = ys[newest];
    var grid = [];
    var yTicks = [];
    var dp = decimals(step);
    for (var k = 0; k <= Math.round((y1 - y0) / step); k++) {
      var v = y0 + k * step;
      grid.push(y(v));
      if (Math.abs(y(v) - lastY) > CLEAR) yTicks.push({ y: y(v), text: bare(v, dp) });
    }
    var volumes = rows.map(function (row) { return ok(row[2]) && row[2] > 0 ? row[2] : null; });
    var shown = volumes.filter(function (volume) { return volume !== null; });
    var volumeMax = shown.length ? Math.max.apply(null, shown) : null;
    var bar = Math.min(BAR_MAX, Math.max(1, plotWidth / n - (n > 260 ? 0 : 2)));
    var bars = [];
    volumes.forEach(function (volume, i) {
      if (volume === null) return;
      var from = Math.max(LEFT, xs[i] - bar / 2);
      var to = Math.min(LEFT + plotWidth, xs[i] + bar / 2);
      var tall = volume / volumeMax * VOLUME_HEIGHT;
      bars.push({ i: i, x: from, y: base - tall, width: to - from, height: tall });
    });
    var long = n > 1 && rows[0][0] < monthsBefore(rows[n - 1][0], 24);
    var ticks = xTicks(rows, long).map(function (tick) {
      var x = xs[tick.i];
      var half = tick.text.length * CHAR / 2;
      var anchor = x - half < 0 ? 'start' : x + half > W ? 'end' : 'middle';
      return { i: tick.i, x: x, text: tick.text, anchor: anchor };
    });
    return {
      width: W, height: HEIGHT, left: LEFT, top: TOP, plotWidth: plotWidth,
      priceHeight: PRICE_HEIGHT, volumeTop: volumeTop, volumeHeight: VOLUME_HEIGHT,
      xs: xs, ys: ys, path: path, last: last, lastX: lastX, lastY: lastY,
      tag: { x: LEFT + plotWidth + 6, width: tagWidth, text: tagText },
      grid: grid, yTicks: yTicks, bars: bars, volumeMax: volumeMax, xTicks: ticks
    };
  }

  /* The day nearest `x`, in the svg's units, of the plot `g`. */
  function nearest(g, x) {
    var n = g.xs.length;
    var i = n > 1 ? Math.round((x - g.left) / g.plotWidth * (n - 1)) : 0;
    return Math.max(0, Math.min(n - 1, i));
  }

  /* The day the crosshair moves to at `key` among `n` days, from `at`, null where none is
     picked: the arrows a day to the left or the right, from the newest where none is; Home and
     End the ends; Escape none; any other key leaves it. */
  function keyed(at, key, n) {
    if (!n) return null;
    if (key === 'ArrowLeft') return at === null ? n - 1 : Math.max(0, at - 1);
    if (key === 'ArrowRight') return at === null ? n - 1 : Math.min(n - 1, at + 1);
    if (key === 'Home') return 0;
    if (key === 'End') return n - 1;
    if (key === 'Escape') return null;
    return at;
  }

  /* -------------------------------------------------------------------------- the block */

  /* The Price block of `prices` at the range `range`, the day `at` of the range picked (null:
     none, and so is a day the range does not hold), drawn at `width`. `on` holds the ref the
     plot's wrapper takes, `range(id)`, called at a range's button, and `pick(i)`, called with the
     day the pointer or a key picks, null to clear it; none of them is called while it draws. */
  function block(prices, range, at, width, on) {
    var rows = inRange(prices, range);
    var g = geometry(rows, width);
    var picked = g && at !== null && at >= 0 && at < rows.length ? at : null;
    var moved = lead(rows, range);
    return C.panel('Price', ranges(range, on), g ? [
      h('div', { key: 'lead', className: 'app-price__lead' },
        h('p', { className: 'figure-lg' }, usd(g.last)),
        moved ? h('p', { className: 'figure app-price__move' }, moved) : null),
      plot(rows, g, picked, range, on)
    ] : h('p', { className: 'body app-note' }, 'No prices on file.'));
  }

  /* The ranges' buttons in a group, the chosen one pressed. */
  function ranges(range, on) {
    return h('div', { className: 'app-price__ranges', role: 'group' },
      RANGES.map(function (item) {
        return h('button', {
          key: item[0], type: 'button', className: 'figure-sm app-price__range',
          'aria-pressed': item[0] === range ? 'true' : 'false',
          onClick: function () { on.range(item[0]); }
        }, item[0]);
      }));
  }

  /* The plot's wrapper, which takes focus and the keys, and holds the svg of the two plots and,
     with a day picked, its box. The pointer over the svg picks the day nearest it, the svg's
     width scaled to the units it draws in; leaving the svg or the wrapper's focus clears it. */
  function plot(rows, g, at, range, on) {
    var right = g.left + g.plotWidth;
    var base = g.volumeTop + g.volumeHeight;
    return h('div', {
      key: 'plot', className: 'app-price__plot', ref: on ? on.ref : null, tabIndex: 0,
      role: 'group', 'aria-label': 'Price, ' + words(range),
      onKeyDown: function (event) {
        if (KEYS[event.key]) event.preventDefault();
        var next = keyed(at, event.key, rows.length);
        if (next !== at) on.pick(next);
      },
      onBlur: function () { on.pick(null); }
    },
      h('svg', {
        viewBox: '0 0 ' + g.width + ' ' + g.height, height: g.height, 'aria-hidden': 'true',
        onMouseMove: function (event) {
          var box = event.currentTarget.getBoundingClientRect();
          var scale = box.width ? g.width / box.width : 1;
          on.pick(nearest(g, (event.clientX - box.left) * scale));
        },
        onMouseLeave: function () { on.pick(null); }
      },
        h('text', { className: 'app-price__name', x: g.left, y: 10 }, 'Close, USD'),
        g.grid.map(function (y, k) {
          return h('line', {
            key: 'grid' + k, className: 'app-price__grid', x1: g.left, x2: right, y1: y, y2: y,
            stroke: 'var(--chart-grid)', strokeWidth: 1
          });
        }),
        g.yTicks.map(function (tick, k) {
          return h('text', {
            key: 'tick' + k, className: 'app-price__tick', x: right + 8, y: tick.y + 4
          }, tick.text);
        }),
        h('path', {
          className: 'app-price__line', d: g.path, fill: 'none', stroke: 'var(--chart-1)',
          strokeWidth: 2, strokeLinejoin: 'round', strokeLinecap: 'round'
        }),
        h('circle', {
          className: 'app-price__end', cx: g.lastX, cy: g.lastY, r: 4.5, fill: 'var(--chart-1)',
          stroke: 'var(--surface-raised)', strokeWidth: 2
        }),
        h('rect', {
          className: 'app-price__tagbox', x: g.tag.x, y: g.lastY - 9, width: g.tag.width,
          height: 18, rx: 3, fill: 'var(--accent)'
        }),
        h('text', {
          className: 'app-price__tag', x: g.tag.x + g.tag.width / 2, y: g.lastY + 4,
          textAnchor: 'middle'
        }, g.tag.text),
        h('text', { className: 'app-price__name', x: g.left, y: g.volumeTop - 8 }, 'Volume'),
        h('line', {
          className: 'app-price__grid', x1: g.left, x2: right, y1: base, y2: base,
          stroke: 'var(--chart-grid)', strokeWidth: 1
        }),
        g.volumeMax === null ? null : h('text', {
          className: 'app-price__tick app-price__volume', x: right + 8, y: g.volumeTop + 8
        }, C.big(g.volumeMax)),
        g.bars.map(function (bar) {
          return h('rect', {
            key: 'bar' + bar.i, className: 'app-price__bar', x: bar.x, y: bar.y,
            width: bar.width, height: bar.height, fill: 'var(--chart-context)',
            opacity: bar.i === at ? 1 : 0.55
          });
        }),
        g.xTicks.map(function (tick) {
          return h('text', {
            key: 'day' + tick.i, className: 'app-price__day', x: tick.x, y: g.height - 6,
            textAnchor: tick.anchor
          }, tick.text);
        }),
        at === null ? null : h('line', {
          className: 'app-price__crosshair', x1: g.xs[at], x2: g.xs[at], y1: g.top, y2: base,
          stroke: 'var(--border)', strokeWidth: 1
        }),
        at === null || g.ys[at] === null ? null : h('circle', {
          className: 'app-price__dot', cx: g.xs[at], cy: g.ys[at], r: 4.5,
          fill: 'var(--chart-1)', stroke: 'var(--surface-raised)', strokeWidth: 2
        })),
      at === null ? null : tip(rows[at], g.xs[at], g.width));
  }

  /* The box of the day `row` at `x`: its day, its close and its volume, beside the crosshair on
     the side of the plot with room. */
  function tip(row, x, width) {
    return h('div', {
      className: 'app-price__tip',
      style: x > width / 2 ? { right: (width - x + 12) + 'px' } : { left: (x + 12) + 'px' }
    },
      h('p', { className: 'figure-sm' }, C.day(row[0])),
      h('p', { className: 'figure-sm' },
        h('span', { className: 'app-price__tipname' }, 'Close'), usd(row[1])),
      h('p', { className: 'figure-sm' },
        h('span', { className: 'app-price__tipname' }, 'Volume'), C.big(row[2])));
  }

  /* The chart: the block, keeping its range, 1Y when it opens, the day picked, and the width of
     the plot's wrapper, measured after each draw and at each resize of the window. */
  function Chart(props) {
    var range = React.useState('1Y');
    var at = React.useState(null);
    var width = React.useState(WIDTH);
    var box = React.useRef(null);
    function measure() {
      var found = box.current ? box.current.clientWidth : 0;
      if (found > 0) width[1](found);
    }
    React.useEffect(measure);
    React.useEffect(function () {
      window.addEventListener('resize', measure);
      return function () { window.removeEventListener('resize', measure); };
    }, []);
    return block(props.prices || [], range[0], at[0], width[0], {
      ref: box,
      range: function (id) { at[1](null); range[1](id); },
      pick: at[1]
    });
  }

  /* What the Overview and the tests use. */
  P.companyChart = {
    RANGES: RANGES, inRange: inRange, change: change, lead: lead, niceStep: niceStep,
    xTicks: xTicks, geometry: geometry, nearest: nearest, keyed: keyed, block: block, Chart: Chart
  };
})();
