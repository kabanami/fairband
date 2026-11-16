/* The Overview mockup: the company page's head, its tabs and the Overview tab, drawn with the
   app's own components and one company's data. A throwaway: nothing here is product code. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var D = window.MOCK;
  var prof = D.profile, q = D.quote, r = D.ratios, k = D.metrics, g = D.growth, sc = D.scores;
  var ch = D.change, pt = D.targets, gr = D.grades, fl = D.float, det = D.detail, res = det.result;
  var PHASE_NUMBER = {
    'Start-up': 1, 'Young Growth': 2, 'High Growth': 3,
    'Mature Growth': 4, 'Mature Stable': 5, 'Decline': 6
  };
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  /* ------------------------------------------------------------------ the figures' words */

  function ok(v) { return typeof v === 'number' && isFinite(v); }
  function n(v, d) {
    return ok(v) ? v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
      : '—';
  }
  function money(v) { return ok(v) ? '$' + n(v, 2) : '—'; }
  function big(v, lead) {
    if (!ok(v)) return '—';
    var a = Math.abs(v), s = lead || '';
    if (a >= 1e12) return s + n(v / 1e12, 2) + 'T';
    if (a >= 1e9) return s + n(v / 1e9, a >= 1e11 ? 1 : 2) + 'B';
    if (a >= 1e6) return s + n(v / 1e6, 1) + 'M';
    return s + n(v, 0);
  }
  function pct(v, d) { return ok(v) ? n(v * 100, d == null ? 1 : d) + '%' : '—'; }
  function points(v, d) { return ok(v) ? n(v, d == null ? 1 : d) + '%' : '—'; }
  function signed(v, text) { return (v > 0 ? '+' : v < 0 ? '−' : '') + text; }
  function mult(v) { return ok(v) && v !== 0 ? n(v, 1) + 'x' : '—'; }
  function yearly(total, years) { return ok(total) ? Math.pow(1 + total, 1 / years) - 1 : null; }
  function day(iso) {
    var text = String(iso).slice(0, 10);
    if (F.formatDate) return F.formatDate(text);
    var p = text.split('-');
    return Number(p[2]) + ' ' + MONTHS[Number(p[1]) - 1] + ' ' + p[0];
  }

  /* ------------------------------------------------------------------ the page's parts */

  function panel(title, right, children, key) {
    return h('section', { className: 'cp-panel', key: key || title },
      h('header', { className: 'cp-panel__head' },
        h('h2', { className: 'heading cp-panel__title' }, title), right || null),
      children);
  }

  function kv(rows) {
    return h('div', { className: 'cp-kv' }, rows.map(function (row) {
      return h('div', { className: 'cp-kv__row', key: row[0] },
        h('span', { className: 'body cp-kv__k' }, row[0]),
        h('span', { className: (row[2] ? 'body' : 'figure') + ' cp-kv__v' }, row[1]));
    }));
  }

  function group(title, rows) {
    return h('div', { className: 'cp-group', key: title },
      h('h3', { className: 'label cp-group__title' }, title), kv(rows));
  }

  function table(head, rows) {
    return h('table', { className: 'cp-tbl' },
      h('thead', null, h('tr', null, head.map(function (cell, i) {
        return h('th', { className: 'label', key: i }, cell);
      }))),
      h('tbody', null, rows.map(function (row, i) {
        return h('tr', { key: i }, row.map(function (cell, j) {
          return h('td', { className: j === 0 ? 'body cp-tbl__k' : 'figure', key: j }, cell);
        }));
      })));
  }

  /* ------------------------------------------------------------------ the head and the tabs */

  function head() {
    var phase = PHASE_NUMBER[res.phase.phase];
    return h('header', { className: 'cp-head' },
      h('div', { className: 'cp-id' },
        D.logo ? h('img', { className: 'cp-logo', src: D.logo, alt: '' }) : null,
        h('div', { className: 'cp-names' },
          h('div', { className: 'cp-line' },
            h('h1', { className: 'title cp-name' }, prof.companyName),
            h('span', { className: 'ticker' }, prof.symbol),
            phase ? h(F.PhaseBadge, { phase: phase, size: 'sm' }) : null),
          h('p', { className: 'caption cp-sub' },
            [prof.exchange, prof.sector, prof.industry].join(' · ')))),
      h('div', { className: 'cp-side' },
        h('div', { className: 'cp-quote' },
          h('p', { className: 'figure-lg' }, money(q.price)),
          h('p', { className: 'figure cp-quote__chg' },
            signed(q.change, money(Math.abs(q.change))) + ' (' +
            signed(q.changePercentage, points(Math.abs(q.changePercentage), 2)) + ')'),
          h('p', { className: 'caption cp-quote__at' }, 'close ' + day(res.price_date))),
        h('div', { className: 'cp-actions' },
          h(F.Button, { variant: 'secondary', size: 'sm' }, 'Watchlists ▾'),
          h(F.Button, { variant: 'secondary', size: 'sm' }, 'Request research'))));
  }

  var TABS = ['Overview', 'Financials', 'Estimates', 'Investor relations', 'Research'];

  function tabs(tab, setTab) {
    return h('nav', { className: 'cp-tabs', role: 'tablist', 'aria-label': 'Company' },
      TABS.map(function (name) {
        return h('button', {
          key: name, type: 'button', role: 'tab', className: 'control cp-tab',
          'aria-selected': name === tab ? 'true' : 'false',
          onClick: function () { setTab(name); }
        }, name);
      }),
      h('p', { className: 'caption cp-asof' }, 'data ' + day(D.dataDate)));
  }

  /* ------------------------------------------------------------------ the left column */

  function Company() {
    var state = React.useState(false);
    var open = state[0];
    var site = String(prof.website || '').replace(/^https?:\/\//, '').replace(/^www\./, '');
    return panel('Company', null, [
      h('p', { key: 'brief', className: 'body cp-brief' + (open ? '' : ' is-clamped') },
        prof.description),
      h('button', {
        key: 'more', type: 'button', className: 'caption cp-more',
        onClick: function () { state[1](!open); }
      }, open ? 'Show less' : 'Show more'),
      h('div', { key: 'facts', className: 'cp-two' },
        kv([
          ['CEO', prof.ceo, true],
          ['Website', h('a', { href: prof.website, target: '_blank', rel: 'noreferrer' }, site),
            true],
          ['Employees', n(Number(prof.fullTimeEmployees), 0)],
          ['Listed', day(prof.ipoDate)]
        ]),
        kv([
          ['Sector', prof.sector, true],
          ['Industry', prof.industry, true],
          ['Country', prof.country, true],
          ['Exchange', prof.exchange, true]
        ]))
    ]);
  }

  function value() {
    var report = det.report;
    var lv = res.levels;
    return panel('Fairband value', h(F.BasisChip, { basis: 'mechanical' }), [
      h('div', { key: 'meter', className: 'cp-value__meter' },
        h(F.BandMeter, {
          low: lv.fair_low, high: lv.fair_high, price: res.price, fairValue: res.value,
          buyLevel: lv.buy, trimLevel: lv.trim, designation: res.designation, showScale: false,
          gap: n(res.price_to_value, 2) + ' × the mechanical value', hero: false
        })),
      h('div', { key: 'levels', className: 'cp-two' },
        kv([['Fair value', money(res.value)], ['Buy level', money(lv.buy)]]),
        kv([
          ['Fair band', money(lv.fair_low) + ' – ' + money(lv.fair_high)],
          ['Trim level', money(lv.trim)]
        ])),
      report ? h('div', { key: 'research', className: 'cp-research' },
        h('span', { className: 'fb-stance fb-stance--' + report.stance + ' label' },
          report.stance),
        h('p', { className: 'caption' }, report.mode + ', ' + day(report.createdAt)),
        h(F.PrincipalChip, { principal: report.principal, actor: report.actor }),
        h(F.Button, { variant: 'quiet', size: 'sm' }, 'Open in Research →')) : null
    ]);
  }

  function statistics() {
    var first = [
      group('Size', [
        ['Market cap', big(q.marketCap, '$')],
        ['Enterprise value', big(k.enterpriseValueTTM, '$')],
        ['Shares', big(fl.outstandingShares)],
        ['Free float', points(fl.freeFloat)],
        ['Revenue', big(sc.revenue, '$')],
        ['Employees', n(Number(prof.fullTimeEmployees), 0)],
        ['Beta', n(prof.beta, 2)]
      ]),
      group('Margins', [
        ['Gross', pct(r.grossProfitMarginTTM)],
        ['EBITDA', pct(r.ebitdaMarginTTM)],
        ['Operating', pct(r.operatingProfitMarginTTM)],
        ['Pretax', pct(r.pretaxProfitMarginTTM)],
        ['Net', pct(r.netProfitMarginTTM)]
      ]),
      group('Returns', [
        ['ROE', pct(k.returnOnEquityTTM)],
        ['ROA', pct(k.returnOnAssetsTTM)],
        ['ROIC', pct(k.returnOnInvestedCapitalTTM)],
        ['ROCE', pct(k.returnOnCapitalEmployedTTM)]
      ])
    ];
    var second = [
      group('Valuation', [
        ['P/E', mult(r.priceToEarningsRatioTTM)],
        ['PEG', n(r.priceToEarningsGrowthRatioTTM, 2)],
        ['P/B', mult(r.priceToBookRatioTTM)],
        ['P/S', mult(r.priceToSalesRatioTTM)],
        ['P/FCF', mult(r.priceToFreeCashFlowRatioTTM)],
        ['EV/Sales', mult(k.evToSalesTTM)],
        ['EV/EBITDA', mult(k.evToEBITDATTM)],
        ['EV/FCF', mult(k.evToFreeCashFlowTTM)],
        ['Earnings yield', pct(k.earningsYieldTTM)],
        ['FCF yield', pct(k.freeCashFlowYieldTTM)]
      ]),
      group('Financial health', [
        ['Debt to equity', n(r.debtToEquityRatioTTM, 2)],
        ['Net debt to EBITDA', n(k.netDebtToEBITDATTM, 2)],
        ['Current ratio', n(r.currentRatioTTM, 2)],
        ['Quick ratio', n(r.quickRatioTTM, 2)],
        ['Interest cover', mult(r.interestCoverageRatioTTM)],
        ['Altman Z', n(sc.altmanZScore, 1)],
        ['Piotroski', sc.piotroskiScore + ' of 9']
      ])
    ];
    var third = [
      group('Growth, last fiscal year', [
        ['Revenue', pct(g.revenueGrowth)],
        ['EBITDA', pct(g.ebitdaGrowth)],
        ['EPS', pct(g.epsdilutedGrowth)],
        ['Free cash flow', pct(g.freeCashFlowGrowth)]
      ]),
      h('div', { className: 'cp-group', key: 'per-share' },
        h('h3', { className: 'label cp-group__title' }, 'Growth a year, per share'),
        table(['', '3Y', '5Y', '10Y'], [
          ['Revenue', pct(yearly(g.threeYRevenueGrowthPerShare, 3)),
            pct(yearly(g.fiveYRevenueGrowthPerShare, 5)),
            pct(yearly(g.tenYRevenueGrowthPerShare, 10))],
          ['Net income', pct(yearly(g.threeYNetIncomeGrowthPerShare, 3)),
            pct(yearly(g.fiveYNetIncomeGrowthPerShare, 5)),
            pct(yearly(g.tenYNetIncomeGrowthPerShare, 10))],
          ['Cash flow', pct(yearly(g.threeYOperatingCFGrowthPerShare, 3)),
            pct(yearly(g.fiveYOperatingCFGrowthPerShare, 5)),
            pct(yearly(g.tenYOperatingCFGrowthPerShare, 10))],
          ['Dividend', pct(yearly(g.threeYDividendperShareGrowthPerShare, 3)),
            pct(yearly(g.fiveYDividendperShareGrowthPerShare, 5)),
            pct(yearly(g.tenYDividendperShareGrowthPerShare, 10))]
        ])),
      group('Dividends', [
        ['Yield', pct(r.dividendYieldTTM, 2)],
        ['Payout', pct(r.dividendPayoutRatioTTM)],
        ['Dividend a share', money(r.dividendPerShareTTM)],
        ['Paid', D.dividends.length ? D.dividends[0].frequency : '—', true],
        ['Last payment', D.dividends.length ? day(D.dividends[0].paymentDate) : '—']
      ])
    ];
    return panel('Key statistics',
      h('p', { className: 'caption cp-note' }, 'trailing twelve months, unless the row says'),
      h('div', { className: 'cp-three' },
        h('div', { className: 'cp-stack' }, first),
        h('div', { className: 'cp-stack' }, second),
        h('div', { className: 'cp-stack' }, third)));
  }

  function News() {
    var shown = D.news;
    return h('section', { className: 'cp-panel cp-panel--fill' },
      h('header', { className: 'cp-panel__head' },
        h('h2', { className: 'heading cp-panel__title' }, 'News'),
        h('p', { className: 'caption cp-note' }, shown.length + ' stories')),
      h('ul', { className: 'cp-news cp-news--scroll', tabIndex: 0 }, shown.map(function (story, i) {
        return h('li', { key: i },
          h('span', { className: 'figure-sm cp-news__day' }, day(story.date)),
          h('div', null,
            h('a', {
              className: 'body cp-news__title', href: story.url, target: '_blank',
              rel: 'noreferrer'
            }, story.title),
            h('p', { className: 'caption cp-news__by' }, story.publisher)));
      })));
  }

  /* ------------------------------------------------------------------ the price chart */

  var RANGES = [
    ['1M', 'past month'], ['3M', 'past 3 months'], ['6M', 'past 6 months'],
    ['YTD', 'year to date'], ['1Y', 'past year'], ['3Y', 'past 3 years'], ['5Y', 'past 5 years']
  ];

  /* The rows of a range: from the day that many months before the newest close. */
  function inRange(id) {
    var rows = D.prices;
    var last = rows[rows.length - 1][0];
    var y = Number(last.slice(0, 4)), m = Number(last.slice(5, 7)), d = last.slice(8, 10);
    var from;
    if (id === 'YTD') from = (y - 1) + '-12-31';
    else {
      var months = { '1M': 1, '3M': 3, '6M': 6, '1Y': 12, '3Y': 36, '5Y': 60 }[id];
      var total = y * 12 + (m - 1) - months;
      var mm = String((total % 12) + 1);
      from = Math.floor(total / 12) + '-' + (mm.length < 2 ? '0' + mm : mm) + '-' + d;
    }
    return rows.filter(function (row) { return row[0] >= from; });
  }

  function niceStep(span, count) {
    var raw = span / count;
    var power = Math.pow(10, Math.floor(Math.log10(raw)));
    var unit = raw / power;
    return (unit >= 5 ? 10 : unit >= 2 ? 5 : unit >= 1 ? 2 : 1) * power;
  }

  /* The x ticks: the first trading day of a month, or of a year on a long range, thinned to at
     most seven. */
  function xTicks(rows, long) {
    var found = [];
    for (var i = 1; i < rows.length; i++) {
      var a = rows[i - 1][0], b = rows[i][0];
      var changed = long ? a.slice(0, 4) !== b.slice(0, 4) : a.slice(0, 7) !== b.slice(0, 7);
      if (changed) {
        var month = Number(b.slice(5, 7));
        found.push({ i: i, month: month, year: b.slice(0, 4) });
      }
    }
    var step = Math.ceil(found.length / 7);
    return found.filter(function (_, at) { return at % step === 0; }).map(function (tick, at) {
      var text = long ? tick.year
        : MONTHS[tick.month - 1] + (at === 0 || tick.month === 1 ? ' ' + tick.year : '');
      return { i: tick.i, text: text };
    });
  }

  function PriceChart() {
    var range = React.useState('1Y');
    var hover = React.useState(null);
    var size = React.useState(720);
    var box = React.useRef(null);
    React.useEffect(function () {
      function measure() { if (box.current) size[1](box.current.clientWidth); }
      measure();
      window.addEventListener('resize', measure);
      return function () { window.removeEventListener('resize', measure); };
    }, []);

    var rows = inRange(range[0]);
    var words = RANGES.filter(function (x) { return x[0] === range[0]; })[0][1];
    var first = rows[0][1], last = rows[rows.length - 1][1];
    var W = size[0], left = 4, right = 58, top = 18, priceH = 250, gap = 30, volH = 56;
    var bottom = 22, H = top + priceH + gap + volH + bottom, plotW = W - left - right;
    var closes = rows.map(function (x) { return x[1]; });
    var lo = Math.min.apply(null, closes), hi = Math.max.apply(null, closes);
    var step = niceStep(hi - lo || 1, 4);
    var y0 = Math.floor(lo / step) * step, y1 = Math.ceil(hi / step) * step;
    var maxVol = Math.max.apply(null, rows.map(function (x) { return x[2]; }));
    function x(i) { return left + (rows.length > 1 ? i / (rows.length - 1) : 0.5) * plotW; }
    function y(v) { return top + (1 - (v - y0) / (y1 - y0)) * priceH; }
    var volTop = top + priceH + gap;
    function vy(v) { return volTop + (1 - v / maxVol) * volH; }
    var path = rows.map(function (row, i) {
      return (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(row[1]).toFixed(1);
    }).join('');
    var yTicks = [];
    for (var v = y0; v <= y1 + step / 2; v += step) yTicks.push(v);
    var bar = Math.max(1, plotW / rows.length - (rows.length > 260 ? 0 : 2));
    var at = hover[0];
    var lastX = x(rows.length - 1), lastY = y(last);

    function move(event) {
      var bounds = event.currentTarget.getBoundingClientRect();
      var ratio = (event.clientX - bounds.left - left) / plotW;
      var i = Math.round(ratio * (rows.length - 1));
      hover[1](Math.max(0, Math.min(rows.length - 1, i)));
    }

    return panel('Price',
      h('div', { className: 'cp-ranges', role: 'group', 'aria-label': 'Range' },
        RANGES.map(function (item) {
          return h('button', {
            key: item[0], type: 'button', className: 'figure-sm cp-range',
            'aria-pressed': item[0] === range[0] ? 'true' : 'false',
            onClick: function () { hover[1](null); range[1](item[0]); }
          }, item[0]);
        })),
      [
        h('div', { key: 'lead', className: 'cp-chart__lead' },
          h('p', { className: 'figure-lg' }, money(last)),
          h('p', { className: 'figure cp-chart__chg' },
            signed(last - first, money(Math.abs(last - first))) + ' (' +
            signed(last - first, pct(Math.abs(last / first - 1))) + ') ' + words)),
        h('div', { key: 'chart', className: 'cp-chart', ref: box },
          h('svg', {
            viewBox: '0 0 ' + W + ' ' + H, height: H, role: 'img',
            'aria-label': 'Daily close and volume, ' + words,
            onMouseMove: move, onMouseLeave: function () { hover[1](null); }
          },
            h('text', { className: 'cp-chart__name', x: left, y: 10 }, 'Close, USD'),
            yTicks.map(function (tick) {
              var clear = Math.abs(y(tick) - lastY) > 14;
              return h('g', { key: 'y' + tick },
                h('line', {
                  x1: left, x2: left + plotW, y1: y(tick), y2: y(tick),
                  stroke: 'var(--chart-grid)', strokeWidth: 1
                }),
                clear ? h('text', { x: left + plotW + 8, y: y(tick) + 4 },
                  n(tick, step < 1 ? 2 : 0)) : null);
            }),
            h('path', {
              d: path, fill: 'none', stroke: 'var(--chart-1)', strokeWidth: 2,
              strokeLinejoin: 'round', strokeLinecap: 'round'
            }),
            h('circle', {
              cx: lastX, cy: lastY, r: 4, fill: 'var(--chart-1)',
              stroke: 'var(--surface-raised)', strokeWidth: 2
            }),
            h('rect', {
              x: left + plotW + 6, y: lastY - 9, width: 50, height: 18, rx: 3,
              fill: 'var(--accent)'
            }),
            h('text', {
              className: 'cp-chart__tag', x: left + plotW + 31, y: lastY + 4, textAnchor: 'middle'
            }, n(last, 2)),
            h('text', { className: 'cp-chart__name', x: left, y: volTop - 8 }, 'Volume'),
            h('line', {
              x1: left, x2: left + plotW, y1: volTop + volH, y2: volTop + volH,
              stroke: 'var(--chart-grid)', strokeWidth: 1
            }),
            h('text', { x: left + plotW + 8, y: volTop + 8 }, big(maxVol)),
            rows.map(function (row, i) {
              return h('rect', {
                key: 'v' + i, x: x(i) - bar / 2, y: vy(row[2]), width: bar,
                height: volTop + volH - vy(row[2]), fill: 'var(--chart-context)',
                opacity: at === i ? 1 : 0.55
              });
            }),
            xTicks(rows, rows.length > 520).map(function (tick) {
              return h('text', { key: 'x' + tick.i, x: x(tick.i), y: H - 6, textAnchor: 'middle' },
                tick.text);
            }),
            at == null ? null : h('g', null,
              h('line', {
                x1: x(at), x2: x(at), y1: top, y2: volTop + volH, stroke: 'var(--border)',
                strokeWidth: 1
              }),
              h('circle', {
                cx: x(at), cy: y(rows[at][1]), r: 4, fill: 'var(--chart-1)',
                stroke: 'var(--surface-raised)', strokeWidth: 2
              }))),
          at == null ? null : h('div', {
            className: 'cp-tip',
            style: x(at) > W / 2 ? { right: (W - x(at) + 12) + 'px' } : { left: (x(at) + 12) + 'px' }
          },
            h('p', { className: 'figure-sm' }, day(rows[at][0])),
            h('p', { className: 'figure-sm' },
              h('span', { className: 'cp-tip__k' }, 'Close'), money(rows[at][1])),
            h('p', { className: 'figure-sm' },
              h('span', { className: 'cp-tip__k' }, 'Volume'), big(rows[at][2]))))
      ]);
  }

  /* ------------------------------------------------------------------ the right column */

  function priceFacts() {
    function moved(key) { return signed(ch[key], points(Math.abs(ch[key]))); }
    return panel('Price facts', null,
      h('div', { className: 'cp-three' },
        group('Trading', [
          ['Open', money(q.open)],
          ['Previous close', money(q.previousClose)],
          ['Day range', money(q.dayLow) + ' – ' + money(q.dayHigh)],
          ['52 weeks', money(q.yearLow) + ' – ' + money(q.yearHigh)],
          ['50-day average', money(q.priceAvg50)],
          ['200-day average', money(q.priceAvg200)],
          ['Volume', big(q.volume)],
          ['Average volume', big(prof.averageVolume)],
          ['Next earnings', nextEarnings()]
        ]),
        group('Price change', [
          ['1 day', moved('1D')],
          ['5 days', moved('5D')],
          ['1 month', moved('1M')],
          ['3 months', moved('3M')],
          ['6 months', moved('6M')],
          ['Year to date', moved('ytd')]
        ]),
        group('Price change, years', [
          ['1 year', moved('1Y')],
          ['3 years', moved('3Y')],
          ['5 years', moved('5Y')],
          ['10 years', moved('10Y')]
        ])));
  }

  function nextEarnings() {
    var next = D.earnings.filter(function (e) { return e.epsActual == null; }).pop();
    return next ? day(next.date) : '—';
  }

  function earnings() {
    var next = D.earnings.filter(function (e) { return e.epsActual == null; }).pop();
    var past = D.earnings.filter(function (e) { return e.epsActual != null; });
    var when = { amc: 'after the close', bmo: 'before the open' };
    return panel('Earnings',
      next ? h('p', { className: 'caption cp-note' },
        'next ' + day(next.date) + (when[next.time] ? ', ' + when[next.time] : '') +
        (next.confirmed ? '' : ', not confirmed')) : null,
      table(['Reported', 'EPS', 'Estimate', 'Revenue', 'Estimate'],
        (next ? [[day(next.date), '—', money(next.epsEstimated), '—',
          big(next.revenueEstimated, '$')]] : []).concat(past.map(function (e) {
          return [day(e.date), money(e.epsActual), money(e.epsEstimated),
            big(e.revenueActual, '$'), big(e.revenueEstimated, '$')];
        }))));
  }

  function targets() {
    return panel('Analysts',
      h('p', { className: 'caption cp-note' }, 'consensus ' + gr.consensus), [
        h('h3', { key: 't', className: 'label cp-sub-title' }, 'Price target'),
        h('div', { key: 'two', className: 'cp-two' },
          kv([['Consensus', money(pt.targetConsensus)], ['Median', money(pt.targetMedian)]]),
          kv([['Low', money(pt.targetLow)], ['High', money(pt.targetHigh)]])),
        h('h3', { key: 'r', className: 'label cp-sub-title' }, 'Ratings'),
        h('div', { key: 'grades', className: 'cp-grades' },
          [['Strong buy', gr.strongBuy], ['Buy', gr.buy], ['Hold', gr.hold], ['Sell', gr.sell],
            ['Strong sell', gr.strongSell]].map(function (cell) {
            return h('div', { className: 'cp-grade', key: cell[0] },
              h('p', { className: 'figure-lg' }, cell[1]),
              h('p', { className: 'caption cp-grade__k' }, cell[0]));
          }))
      ]);
  }

  function estimates() {
    var years = D.estimates.slice().reverse().filter(function (e) {
      return e.date > res.data_date;
    });
    return panel('Consensus estimates', null,
      table(['Fiscal year', 'Revenue', 'EPS', 'EPS low', 'EPS high', 'Analysts'],
        years.map(function (e) {
          return [e.date.slice(0, 4), big(e.revenueAvg, '$'), money(e.epsAvg), money(e.epsLow),
            money(e.epsHigh), String(e.numAnalystsEps)];
        })));
  }

  /* ------------------------------------------------------------------ the page */

  function Page() {
    var state = React.useState(D.startTab || 'Overview');
    var tab = state[0];
    return h(React.Fragment, null,
      h('p', { className: 'caption cp-banner' },
        'Mockup of the company page’s Overview. Real data for one company; the buttons that ' +
        'need the server do nothing.'),
      h(F.AppHeader, {
        views: [{ id: 'screen', label: 'Screen' }, { id: 'groups', label: 'Groups' },
          { id: 'watchlists', label: 'Watchlists' }, { id: 'methodology', label: 'Methodology' },
          { id: 'settings', label: 'Settings' }, { id: 'inbox', label: 'Inbox' }],
        view: '', engineRanAt: D.engineRanAt
      }),
      h('main', { className: 'cp' },
        head(),
        tabs(tab, state[1]),
        tab === 'Overview' ? h('div', { className: 'cp-grid' },
          h('div', { className: 'cp-col' }, h(Company), value(), statistics()),
          h('div', { className: 'cp-col cp-col--match' }, h(PriceChart), priceFacts(), h(News)))
          : tab === 'Estimates' ? h('div', { className: 'cp-grid' },
            h('div', { className: 'cp-col' }, earnings()),
            h('div', { className: 'cp-col' }, targets(), estimates()))
            : h('p', { className: 'body cp-later' },
              tab + ': a later plan. The head and the tabs stay as they are on every tab.')));
  }

  ReactDOM.createRoot(document.getElementById('root')).render(h(Page));
})();
