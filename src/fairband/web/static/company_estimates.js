/* The company page's Estimates tab (the company page's design, 9), loaded after company.js: two
   columns, at the left Earnings, the next date in its head over the table of the next date and
   every reported quarter; at the right Analysts, the consensus word in its head over the price
   target and the five ratings' counts, then Consensus estimates, one row a fiscal year. Each
   figure in the currency the read gives it (14.2): the earnings and the price target in US
   dollars, the consensus in the company's reporting currency, its code on the figure. The blocks
   are built from company.js's parts and formatters (FairbandPage.companyPage) and hang on it with
   the tab's function, draw.estimates, which the page draws under the tabs once the tab's answer
   and the company's detail are in. */
(function () {
  'use strict';

  var h = React.createElement;
  var P = FairbandPage;
  var C = P.companyPage;

  /* The Estimates tab (9): the grid's two columns, Earnings alone at the left, Analysts then
     Consensus estimates at the right. The columns end on one line by the page's rule, the last
     block of the shorter one growing to the row's height. */
  function estimates(answer) {
    return h('div', { className: 'app-company__grid' },
      h('div', { className: 'app-company__col' }, earnings(answer)),
      h('div', { className: 'app-company__col' }, analysts(answer), consensus(answer)));
  }

  /* --------------------------------------------------------------------- Earnings */

  /* The Earnings block of the estimates answer: in its head the next date, where there is one,
     with its time and whether it is confirmed (nextLine). A table of the rows as the read gives
     them, the next date first with its two estimates, then every reported quarter, newest first:
     the day, monospaced as a date is (14.1), EPS and its estimate to cents, revenue and its
     estimate compact; a missing figure, the next date's two actuals among them, the dash. No
     surprise column. */
  function earnings(answer) {
    var e = answer.earnings;
    return C.panel('Earnings',
      e.next ? h('p', { className: 'caption app-company__note' }, nextLine(e.next)) : null,
      C.table(['Reported', 'EPS', 'Estimate', 'Revenue', 'Estimate'], e.rows.map(function (row) {
        return [h('span', { className: 'figure' }, C.day(row.day)), C.money(row.eps),
          C.money(row.epsEstimate), C.big(row.revenue), C.big(row.revenueEstimate)];
      })));
  }

  /* The next date's line: next 4 Feb 2027, then after the close for FMP's amc or before the
     open for its bmo, nothing for any other time, then not confirmed only where FMP says false. */
  function nextLine(next) {
    var time = next.time === 'amc' ? 'after the close'
      : next.time === 'bmo' ? 'before the open' : null;
    return 'next ' + C.day(next.day) + (time ? ', ' + time : '') +
      (next.confirmed === false ? ', not confirmed' : '');
  }

  /* ------------------------------------------------------------ Consensus estimates */

  /* The Consensus estimates block of the estimates answer: one row a fiscal year, oldest first,
     as the read gives them: the year, revenue compact, EPS and its low and high to cents, and the
     analysts as a count. */
  function consensus(answer) {
    return C.panel('Consensus estimates', null,
      C.table(['Fiscal year', 'Revenue', 'EPS', 'EPS low', 'EPS high', 'Analysts'],
        answer.consensus.map(function (row) {
          return [row.fiscalYear == null ? '—' : String(row.fiscalYear), C.big(row.revenue),
            C.money(row.eps), C.money(row.epsLow), C.money(row.epsHigh), C.count(row.analysts)];
        })));
  }

  /* --------------------------------------------------------------------- Analysts */

  /* The five ratings, each its field in the read and its name, in the order they are drawn. */
  var RATINGS = [
    ['strongBuy', 'Strong buy'], ['buy', 'Buy'], ['hold', 'Hold'], ['sell', 'Sell'],
    ['strongSell', 'Strong sell']
  ];

  /* The Analysts block of the estimates answer: in its head the analysts' consensus word, none
     without one. Under Price target, four rows to cents in two columns, Consensus and Median,
     then Low and High; under Ratings, five boxes in a row, each its count in figure-lg over its
     name, a missing count the dash. No track and no marks on it. */
  function analysts(answer) {
    var t = answer.target;
    var r = answer.ratings;
    return C.panel('Analysts',
      r.consensus ? h('p', { className: 'caption app-company__note' }, 'consensus ' + r.consensus)
        : null,
      [
        h('h3', { key: 'target', className: 'label app-company__subtitle' }, 'Price target'),
        h('div', { key: 'targets', className: 'app-company__two' },
          C.kv([['Consensus', C.money(t.consensus)], ['Median', C.money(t.median)]]),
          C.kv([['Low', C.money(t.low)], ['High', C.money(t.high)]])),
        h('h3', { key: 'ratings', className: 'label app-company__subtitle' }, 'Ratings'),
        h('div', { key: 'grades', className: 'app-company__grades' },
          RATINGS.map(function (rating) {
            return h('div', { key: rating[0], className: 'app-company__grade' },
              h('p', { className: 'figure-lg' }, C.count(r[rating[0]])),
              h('p', { className: 'caption app-company__gradename' }, rating[1]));
          }))
      ]);
  }

  /* What the page and the tests use: the tab's function and its blocks. */
  C.earnings = earnings;
  C.consensus = consensus;
  C.analysts = analysts;
  C.draw.estimates = estimates;
})();
