/* The company page's Investor relations tab (the Investor relations tab's design, 7), loaded after
   company_estimates.js: #company/<symbol>/investor-relations, the company's earnings calls and its
   filings, from the tab's read of the store (GET /api/companies/{symbol}/page/investor-relations),
   which calls no vendor. One block the page's width (7.2): at its top a row, the switch of the
   tab's two views, Earnings calls and Filings, at its left, drawn as the Financials tab's switch
   of statements, and at its right end the line of the next earnings report, left out where the
   read holds no coming date; under the row the view the address's word names (7.1), the Filings
   view for filings, else the Earnings calls view, on the call the word names (2026Q4) or on the
   newest. The word is the page's own: it never travels to the server, and a change of it reads
   nothing (company.js, load); a press of the switch replaces the hash (FairbandPage.show), as a
   tab's button does. A view with nothing on file draws its sentence, No earnings call on file.
   or No filing on file.; the list of calls, the reader and the table of filings are the views'
   own (7.3 to 7.5).

   The data date at the tabs' row's right end is the view's (7.6), the oldest day among the
   stored answers it draws: company.js asks this script for it (dataDate) on every draw, so a
   view's later reads, which draw the page again as they land (companyPage.redraw), move it with
   no change to company.js. The tab's function hangs on companyPage.draw, its date's on
   companyPage.dataDate, and the pure pieces on FairbandPage.investor, for the tests, which read
   them in node. */
(function () {
  'use strict';

  var h = React.createElement;
  var P = FairbandPage;
  var C = P.companyPage;
  var TAB = 'investor-relations';
  /* The two views, each its id and its name. */
  var VIEWS = [['calls', 'Earnings calls'], ['filings', 'Filings']];

  /* The view the address's word names: filings for the word filings, else calls, the Earnings
     calls view, on the tab alone or on a call. */
  function view(word) { return word === 'filings' ? 'filings' : 'calls'; }

  /* The tab on `answer` at the address's word `word` (7.2): its block, the row of the switch and
     the line, then the view's own. */
  function tab(answer, word) {
    var shown = view(word);
    return h('section', {
      className: 'app-company__panel app-ir', 'aria-label': 'Investor relations'
    },
      bar(answer, shown),
      shown === 'filings' ? filings(answer) : calls(answer));
  }

  /* The block's top row: the switch, the view `shown` selected, each button replacing the hash
     with the tab's address of its view, the Filings view's /filings and the Earnings calls view's
     the tab alone, its newest call; a press of the view shown does nothing, so a call stays. Then
     the line of the next earnings report, the read's day in the page's words, where it has one. */
  function bar(answer, shown) {
    return h('div', { className: 'app-ir__bar' },
      h('div', { className: 'app-fin__seg', role: 'tablist' }, VIEWS.map(function (item) {
        return h('button', {
          key: item[0], type: 'button', role: 'tab', className: 'control app-ir__view',
          'aria-selected': item[0] === shown ? 'true' : 'false',
          onClick: function () {
            if (item[0] === shown) return;
            P.show('company', answer.symbol, TAB, item[0] === 'filings' ? 'filings' : null);
          }
        }, item[1]);
      })),
      answer.nextEarnings ? h('p', { className: 'body app-ir__next' }, 'Next earnings report ',
        h('span', { className: 'app-ir__day' }, C.day(answer.nextEarnings))) : null);
  }

  /* The Earnings calls view (7.3, 7.4): a company with no call on file draws its sentence and no
     reader. */
  function calls(answer) {
    return answer.calls.length ? null : none('No earnings call on file.');
  }

  /* The Filings view (7.5): a company with no filing list on file, or whose first window holds no
     filing, draws its sentence. */
  function filings(answer) {
    var list = answer.filings;
    return list && list.rows.length ? null : none('No filing on file.');
  }

  function none(words) { return h('p', { className: 'body app-ir__none' }, words); }

  /* The data date of the view the address's word names (7.6), the oldest day among the stored
     answers it draws: on the Earnings calls view the read's, which counts the head's quote, the
     list of calls and the earnings rows; on the Filings view the day of the filing list it
     draws, none without one. */
  function dataDate(answer, word) {
    if (view(word) === 'filings') return answer.filings ? answer.filings.observedDay : null;
    return answer.dataDate;
  }

  /* What the page and the tests use: the tab's function, draw['investor-relations'](answer,
     detail, word), and its data date's; the views and the pure pieces. */
  P.investor = { VIEWS: VIEWS, view: view, tab: tab, dataDate: dataDate };
  C.draw[TAB] = function (answer, detail, word) { return tab(answer, word); };
  C.dataDate[TAB] = dataDate;
})();
