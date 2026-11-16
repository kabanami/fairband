/* The company page's Overview tab (the company page's design, 8), loaded after company.js: two
   columns, at the left Company (8.1), the brief clamped to three lines with Show more and Show
   less over the company's eight facts; Fairband value (8.2), the one block of Fairband's own
   figures, with the basis chip in its head, the meter as the drawer draws it, the four levels
   under it and, where the company has a published report, the report's line; and Key statistics
   (8.3), eight groups in three columns; at the right Price (8.4), the chart company_chart.js
   draws. The blocks are built from company.js's parts and formatters (FairbandPage.companyPage)
   and hang on it with the tab's function, draw.overview, which the page draws under the tabs
   once the tab's answer and the company's detail are in. A vendor's address is a link only
   where it is a web address (safeHref, 10.6). */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var C = P.companyPage;

  /* The Overview (8): the grid's two columns. At the left Company on the answer's company, keyed
     on the company so each company's brief opens closed, Fairband value on the company's detail
     and Key statistics on the answer. At the right first Price, company_chart.js's chart
     (FairbandPage.companyChart, loaded after this script and read as the tab draws) on the
     answer's prices, keyed on the company so each company's chart opens at 1Y with no day picked;
     Price facts and News join it as they are built. */
  function overview(answer, detail) {
    return h('div', { className: 'app-company__grid' },
      h('div', { className: 'app-company__col' },
        h(Company, { key: 'company ' + answer.symbol, company: answer.company }),
        value(detail),
        statistics(answer)),
      h('div', { className: 'app-company__col' },
        h(P.companyChart.Chart, { key: 'price ' + answer.symbol, prices: answer.prices })));
  }

  /* -------------------------------------------------------------------- links */

  /* The address the page makes a link of (10.6): `address` as given where its scheme, as a
     browser reads it, is http or https; null for any other scheme (javascript:, data:), for an
     address with none and for no address. */
  function safeHref(address) {
    if (typeof address !== 'string' || !address) return null;
    try {
      var scheme = new URL(address).protocol;
      return scheme === 'http:' || scheme === 'https:' ? address : null;
    } catch (e) {
      return null;
    }
  }

  /* ------------------------------------------------------------------ Company */

  /* The Company block (8.1), keeping whether its brief is open. */
  function Company(props) {
    var open = React.useState(false);
    return companyBlock(props.company, open[0], function () { open[1](!open[0]); });
  }

  /* The block of the answer's company `c`: the brief, clamped to three lines unless `open`, and
     Show more or Show less, which calls `toggle`; neither without a brief. Under it the eight
     facts in two lists of four: the CEO, the website, the employees and the day it listed; the
     sector, the industry, the country and the exchange. */
  function companyBlock(c, open, toggle) {
    return C.panel('Company', null, [
      c.brief ? h('p', {
        key: 'brief', className: 'body app-company__brief' + (open ? '' : ' is-clamped')
      }, c.brief) : null,
      c.brief ? h('button', {
        key: 'more', type: 'button', className: 'caption app-company__more',
        'aria-expanded': open ? 'true' : 'false', onClick: toggle
      }, open ? 'Show less' : 'Show more') : null,
      h('div', { key: 'facts', className: 'app-company__two' },
        C.kv([
          ['CEO', c.ceo || '—', true],
          ['Website', website(c.website), true],
          ['Employees', C.count(c.employees)],
          ['Listed', C.day(c.listed)]
        ]),
        C.kv([
          ['Sector', c.sector || '—', true],
          ['Industry', c.industry || '—', true],
          ['Country', c.country || '—', true],
          ['Exchange', c.exchange || '—', true]
        ]))
    ]);
  }

  /* The website: a link that opens in a new tab where it is a web address, its text without its
     scheme and a leading www.; else the address as text, or the dash without one. */
  function website(address) {
    var href = safeHref(address);
    if (!href) return address || '—';
    return h('a', {
      className: 'app-link', href: href, target: '_blank', rel: 'noopener noreferrer'
    }, href.replace(/^https?:\/\//i, '').replace(/^www\./i, ''));
  }

  /* ----------------------------------------------------------- Fairband value */

  /* The Fairband value block (8.2) of the company's detail `d`: the basis chip in its head, the
     basis of the band the meter draws (FairbandPage.bandBasis); the meter as the report page
     draws it (FairbandPage.meter), its price in figure, and the four levels of the value it draws
     in two columns (FairbandPage.levelRows); a row with no band, its refusal's sentence in the
     meter's place where it is refused, and no levels. Then the report's line, where the company
     has a published report. */
  function value(d) {
    var rows = P.levelRows(d);
    var refusal = d.result.refusal;
    return C.panel('Fairband value', h(F.BasisChip, { basis: P.bandBasis(d) }), [
      rows ? h('div', { key: 'meter', className: 'app-company__meter' }, P.meter(d, false))
        : refusal ? h('p', { key: 'refusal', className: 'body app-refusal' }, refusal) : null,
      rows ? h('div', { key: 'levels', className: 'app-company__two' },
        C.kv(rows.slice(0, 2)), C.kv(rows.slice(2))) : null,
      d.report ? reportLine(d.result.symbol, d.report) : null
    ]);
  }

  /* The published report's line, under a rule: its stance in the drawer's chip classes, faded once
     the window of the snapshot it rests on has expired, with the drawer's title then; its mode and
     its day in the reader's time zone (full report, 11 Nov 2026); who wrote it; and the link to
     the report page, the symbol encoded as the report page's links encode it. */
  function reportLine(symbol, report) {
    return h('div', { key: 'report', className: 'app-company__research' },
      h('span', {
        className: 'fb-stance fb-stance--' + report.stance +
          (report.expired ? ' fb-stance--expired' : '') + ' label',
        title: report.expired ? 'The snapshot window of this report has expired' : null
      }, report.stance),
      h('p', { className: 'caption' }, report.mode + ', ' + C.day(P.localIso(report.createdAt))),
      h(F.PrincipalChip, { principal: report.principal, actor: report.actor }),
      h('a', {
        className: 'app-link', href: '#report/' + encodeURIComponent(symbol)
      }, 'Open the report'));
  }

  /* ----------------------------------------------------------- Key statistics */

  /* The Key statistics block (8.3) of the overview answer, in the formats of 14.1: compact
     amounts, a money one with its currency's mark; percents to one decimal, the dividend yield
     to two; multiples with their x and the dash at 0; ratios and scores as plain numbers. Three
     columns: Size, Margins and Returns; Valuation and Financial health; the two growth groups,
     the newest fiscal year's named by its year, and Dividends. */
  function statistics(answer) {
    var s = answer.statistics;
    var size = s.size;
    var m = s.margins;
    var r = s.returns;
    var v = s.valuation;
    var health = s.health;
    var g = s.growth;
    var dividends = s.dividends;
    var year = g.fiscalYear == null ? 'Growth, last fiscal year' : 'Growth, fiscal ' + g.fiscalYear;
    var first = [
      C.group('Size', [
        ['Market cap', C.big(size.marketCap)],
        ['Enterprise value', C.big(size.enterpriseValue)],
        ['Shares', C.big(size.shares)],
        ['Free float', C.points(size.freeFloat)],
        ['Revenue', C.big(size.revenue)],
        ['Employees', C.count(size.employees)],
        ['Beta', C.decimal(size.beta, 2)]
      ]),
      C.group('Margins', [
        ['Gross', C.percent(m.gross)],
        ['EBITDA', C.percent(m.ebitda)],
        ['Operating', C.percent(m.operating)],
        ['Pretax', C.percent(m.pretax)],
        ['Net', C.percent(m.net)]
      ]),
      C.group('Returns', [
        ['ROE', C.percent(r.roe)],
        ['ROA', C.percent(r.roa)],
        ['ROIC', C.percent(r.roic)],
        ['ROCE', C.percent(r.roce)]
      ])
    ];
    var second = [
      C.group('Valuation', [
        ['P/E', C.multiple(v.pe)],
        ['PEG', C.decimal(v.peg, 2)],
        ['P/B', C.multiple(v.pb)],
        ['P/S', C.multiple(v.ps)],
        ['P/FCF', C.multiple(v.pfcf)],
        ['EV/Sales', C.multiple(v.evSales)],
        ['EV/EBITDA', C.multiple(v.evEbitda)],
        ['EV/FCF', C.multiple(v.evFcf)],
        ['Earnings yield', C.percent(v.earningsYield)],
        ['FCF yield', C.percent(v.fcfYield)]
      ]),
      C.group('Financial health', [
        ['Debt to equity', C.decimal(health.debtToEquity, 2)],
        ['Net debt to EBITDA', C.decimal(health.netDebtToEbitda, 2)],
        ['Current ratio', C.decimal(health.currentRatio, 2)],
        ['Quick ratio', C.decimal(health.quickRatio, 2)],
        ['Interest cover', C.multiple(health.interestCover)],
        ['Altman Z', C.decimal(health.altmanZ, 1)],
        ['Piotroski', health.piotroski == null ? '—' : C.count(health.piotroski) + ' of 9']
      ])
    ];
    var third = [
      C.group(year, [
        ['Revenue', C.percent(g.revenue)],
        ['EBITDA', C.percent(g.ebitda)],
        ['EPS', C.percent(g.eps)],
        ['Free cash flow', C.percent(g.freeCashFlow)]
      ]),
      perShare(s.perShare),
      C.group('Dividends', [
        ['Yield', C.percent(dividends.yield, 2)],
        ['Payout', C.percent(dividends.payout)],
        ['Dividend a share', C.money(dividends.perShare)],
        ['Paid', dividends.frequency || '—', true],
        ['Last payment', C.day(dividends.lastPayment)]
      ])
    ];
    return C.panel('Key statistics',
      h('p', { className: 'caption app-company__note' },
        'trailing twelve months, unless the row says'),
      h('div', { className: 'app-company__three' },
        h('div', { className: 'app-company__stack' }, first),
        h('div', { className: 'app-company__stack' }, second),
        h('div', { className: 'app-company__stack' }, third)));
  }

  /* The yearly growth a share over three, five and ten years, a small table under its title:
     revenue, net income, cash flow and the dividend, each rate as the read gives it (14.3). */
  var PER_SHARE = [
    ['revenue', 'Revenue'], ['netIncome', 'Net income'], ['cashFlow', 'Cash flow'],
    ['dividend', 'Dividend']
  ];

  function perShare(rates) {
    return h('div', { key: 'per-share', className: 'app-company__group' },
      h('h3', { className: 'label app-company__grouptitle' }, 'Growth a year, per share'),
      C.table(['', '3Y', '5Y', '10Y'], PER_SHARE.map(function (row) {
        var rate = rates[row[0]];
        return [row[1], C.percent(rate.y3), C.percent(rate.y5), C.percent(rate.y10)];
      })));
  }

  /* What the page and the tests use: the tab's function, and its blocks and the link rule, which
     the right column's blocks use too. */
  C.safeHref = safeHref;
  C.Company = Company;
  C.companyBlock = companyBlock;
  C.value = value;
  C.statistics = statistics;
  C.draw.overview = overview;
})();
