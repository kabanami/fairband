/* The company page's Investor relations tab (the Investor relations tab's design, 7), loaded after
   company_estimates.js: #company/<symbol>/investor-relations, the company's earnings calls and its
   filings, from the tab's read of the store (GET /api/companies/{symbol}/page/investor-relations),
   which calls no vendor. One block the page's width (7.2): at its top a row, the switch of the
   tab's two views, Earnings calls and Filings, at its left, drawn as the Financials tab's switch
   of statements, and at its right end the line of the next earnings report, left out where the
   read holds no coming date; under the row the view the address's word names (7.1), the Filings
   view for filings, else the Earnings calls view, on the call the word names (2026Q4) or on the
   newest. The word is the page's own: it never travels to the server, and a change of it never
   reads the tab again (company.js, load); a press of the switch replaces the hash
   (FairbandPage.show), as a tab's button does. A view with nothing on file draws its sentence,
   No earnings call on file. or No filing on file.; the table of filings is its view's own (7.5).

   The Earnings calls view (7.3, 7.4): at its left the list of calls, under one head a fiscal
   year, newest first, the newest five years and Show all <n> calls where there are more, the call
   shown marked; a press on a row replaces the hash with that call's address (FairbandPage.show,
   which writes it by companyPath) and reads nothing of the tab. At its right the reader of the
   call shown: its title and its day, its four figures as the read gives them, no gap to the
   estimate drawn, then its transcript, read through the call's read
   (GET .../investor-relations/call?year=&quarter=, with the request header: it may call a vendor)
   as the view first shows the call, and kept by company, year and quarter for the page's life, so
   each call is read once; one that failed is read again as its row is pressed. While its read is
   out the reader waits, faded (aria-busy); a read that lands for a call or a company no longer
   shown is kept and draws nothing; one for the call shown draws the page again
   (companyPage.redraw). The transcript is the server's turns and paragraphs, drawn as text: over
   it the find box, which marks its words as plain words, whatever the case, from two characters
   on (marked), each a mark element around a text node, and Go to the questions where the server
   found their start. An address naming a call the company has none of shows the newest call, and
   is put right to the tab alone once drawn, reading nothing of the tab. A change of call takes
   the page to its top, as a change of report does on the Research tab, and empties the find box.

   The data date at the tabs' row's right end is the view's (7.6), the oldest day among the
   stored answers it draws: company.js asks this script for it (dataDate) on every draw, so a
   view's later reads, which draw the page again as they land (companyPage.redraw), move it with
   no change to company.js. The tab's function hangs on companyPage.draw, its date's on
   companyPage.dataDate, and the pure pieces on FairbandPage.investor, for the tests, which read
   them in node. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var C = P.companyPage;
  var TAB = 'investor-relations';
  /* The two views, each its id and its name. */
  var VIEWS = [['calls', 'Earnings calls'], ['filings', 'Filings']];
  var YEARS = 5; /* the fiscal years the list shows before Show all (7.3) */
  var SHORTEST = 2; /* the fewest characters the find box marks (7.4) */
  var QUESTIONS = 'ir-questions'; /* the id of the questions' first turn, the button's target */
  /* The reader's four figures (7.4), each its field in a call, its name and its words: EPS to
     cents, revenue compact, as the Estimates tab writes them, in US dollars as the read gives
     them. */
  var FIGURES = [
    ['epsReported', 'EPS reported', 'money'], ['epsEstimate', 'EPS estimate', 'money'],
    ['revenueReported', 'Revenue reported', 'big'], ['revenueEstimate', 'Revenue estimate', 'big']
  ];

  /* The Earnings calls view's state, for the page's life: the company it drew last, the key of
     the call its reader drew last (keyOf), whether every fiscal year is shown, Show all pressed,
     for that company, the find box's words, for that call, and each call's read by company,
     year and quarter: { out: true } while it is out, then { answer }, the read's answer, or
     { failed }, the server's sentence why not. */
  var held = { symbol: null, call: null, all: false, words: '', reads: {} };

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
      shown === 'filings' ? filings(answer) : calls(answer, word));
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

  /* ------------------------------------------------------------------- the Earnings calls view */

  /* A call's word in the address: 2026Q4. */
  function wordOf(call) { return call.fiscalYear + 'Q' + call.quarter; }

  /* The key a call's read is kept under: the company, the fiscal year and the quarter. */
  function keyOf(symbol, call) { return symbol + '/' + call.fiscalYear + '/' + call.quarter; }

  /* The call the address's word names among `calls`, none for no word or a call not on file. */
  function named(calls, word) {
    if (word == null) return null;
    return calls.filter(function (c) { return wordOf(c) === word; })[0] || null;
  }

  /* The call the view shows on `calls` at the word: the call it names, else the newest. */
  function chosen(calls, word) { return named(calls, word) || calls[0]; }

  /* The Earnings calls view on `answer` at the address's word `word` (7.3, 7.4): the list and the
     reader of the call shown, side by side; a company with no call on file draws its sentence
     and no reader. A word that names no call on file is put right (putRight). A change of call
     from the one the reader drew last, of the same company, takes the page to its top and
     empties the find box; another company's starts with five fiscal years and an empty box. */
  function calls(answer, word) {
    var list = answer.calls;
    if (word != null && !named(list, word)) putRight(answer.symbol, word);
    if (!list.length) return none('No earnings call on file.');
    var call = chosen(list, word);
    var key = keyOf(answer.symbol, call);
    if (held.symbol !== answer.symbol) {
      held.symbol = answer.symbol;
      held.all = false;
      held.words = '';
    } else if (held.call !== key) {
      held.words = '';
      top();
    }
    held.call = key;
    return h('div', { className: 'app-ir__calls' },
      callList(answer.symbol, list, call, word),
      reader(call, reading(answer.symbol, call)));
  }

  /* An address naming a call the company has none of (7.1) is put right to the tab alone, which
     shows the newest call, once the draw that found it is done: where the address the page holds
     is still that one, FairbandPage.show replaces the hash, and the page draws the answer it
     holds on the tab alone, reading nothing of the tab (company.js, redrawn). */
  function putRight(symbol, word) {
    Promise.resolve().then(function () {
      var at = P.company;
      if (at && at.symbol === symbol && at.tab === TAB && at.id === word) {
        P.show('company', symbol, TAB, null);
      }
    });
  }

  /* The company page's panel, which scrolls, back at its top. */
  function top() {
    var mount = document.getElementById('company');
    if (mount) mount.scrollTop = 0;
  }

  /* `calls` under one head a fiscal year (7.3), in the order they stand, newest first, each
     { year, calls }: the newest five years, or every year where `shown`. */
  function years(calls, shown) {
    var found = [];
    var at = {};
    calls.forEach(function (call) {
      if (!Object.prototype.hasOwnProperty.call(at, call.fiscalYear)) {
        at[call.fiscalYear] = found.length;
        found.push({ year: call.fiscalYear, calls: [] });
      }
      found[at[call.fiscalYear]].calls.push(call);
    });
    return shown ? found : found.slice(0, YEARS);
  }

  /* The list of calls (7.3) of `symbol`, the call `call` shown and marked as the Research tab
     marks its section, each row a button of its quarter and its day; every fiscal year where
     Show all was pressed or the call shown is older than the five newest, else the five and,
     where there are more, Show all <n> calls. `word` is the address's, which a press compares
     its call's against. */
  function callList(symbol, calls, call, word) {
    var five = years(calls, false);
    var every = held.all || five.every(function (y) { return y.calls.indexOf(call) === -1; });
    var shown = every ? years(calls, true) : five;
    var more = !every && shown.length < years(calls, true).length;
    return h('nav', { className: 'app-ir__list' },
      shown.map(function (y) {
        return h('div', { key: y.year, className: 'app-ir__group' },
          h('h3', { className: 'label app-ir__year' }, 'Fiscal ' + y.year),
          y.calls.map(function (c) {
            var on = c === call;
            return h('button', {
              key: wordOf(c) + '/' + c.date, type: 'button', className: 'control app-ir__call',
              'aria-current': on ? 'true' : null,
              onClick: function () { pick(symbol, c, word); }
            },
              h('span', { className: 'app-ir__q' }, 'Q' + c.quarter),
              h('span', { className: 'figure-sm app-ir__date' }, C.day(c.date)));
          }));
      }),
      more ? h(F.Button, {
        size: 'sm', className: 'app-ir__all',
        onClick: function () { held.all = true; C.redraw(); }
      }, 'Show all ' + C.count(calls.length) + ' calls') : null);
  }

  /* A press on the row of `call` of `symbol`, the address's word `word`: the hash becomes the
     call's address, which draws it with no read of the tab; a read of it that failed is let go
     first, so it is read again, and where the address names it already, the page draws again. */
  function pick(symbol, call, word) {
    var key = keyOf(symbol, call);
    var kept = held.reads[key];
    var failed = !!(kept && kept.failed != null);
    if (failed) delete held.reads[key];
    if (wordOf(call) !== word) P.show('company', symbol, TAB, wordOf(call));
    else if (failed) C.redraw();
  }

  /* The read of `call` of `symbol` as the view keeps it, started where it keeps none: the call's
     read with the request header, its answer or its refusal kept by company, year and quarter;
     as it lands the page draws again where the reader drew that call last, else nothing. */
  function reading(symbol, call) {
    var key = keyOf(symbol, call);
    if (held.reads[key]) return held.reads[key];
    var out = held.reads[key] = { out: true };
    C.readVendor('/api/companies/' + encodeURIComponent(symbol) + '/page/' + TAB +
      '/call?year=' + call.fiscalYear + '&quarter=' + call.quarter)
      .then(function (answer) { return { answer: answer }; },
        function (err) { return { failed: err.message }; })
      .then(function (got) {
        if (held.reads[key] !== out) return;
        held.reads[key] = got;
        if (held.call === key) C.redraw();
      });
    return out;
  }

  /* A call's title (7.4): Q4 fiscal 2026 earnings call. */
  function title(call) {
    return 'Q' + call.quarter + ' fiscal ' + call.fiscalYear + ' earnings call';
  }

  /* The reader of `call` (7.4), its read `kept` (reading): its title and its day, its figures,
     then, as its read has landed, its transcript and the tools over it, the sentence of a call
     with no words, or the sentence of a read that failed; while the read is out, nothing more,
     the reader faded. */
  function reader(call, kept) {
    var out = !!kept.out;
    return h('article', { className: 'app-ir__reader', 'aria-busy': out ? 'true' : null },
      h('h2', { className: 'heading app-ir__title' }, title(call)),
      h('p', { className: 'body app-ir__when' }, C.day(call.date)),
      figures(call),
      out ? null
        : kept.failed != null ? none('The transcript could not be read: ' + kept.failed + '.')
          : !kept.answer.turns.length ? none('No transcript on file for this call.')
            : transcript(kept.answer));
  }

  /* The quarter's four figures in a row (7.4), each its name over its figure, a missing one the
     dash; no row where the four are missing, a call no stored earnings row is the call's. */
  function figures(call) {
    if (FIGURES.every(function (f) { return call[f[0]] == null; })) return null;
    return h('div', { className: 'app-ir__figures' }, FIGURES.map(function (f) {
      return h('div', { key: f[0], className: 'app-ir__figure' },
        h('p', { className: 'label app-ir__name' }, f[1]),
        h('p', { className: 'figure app-ir__amount' }, C[f[2]](call[f[0]])));
    }));
  }

  /* The transcript of the call's read's `answer` (7.4), under the tools: one block a turn, the
     speaker's name over the turn's paragraphs, a turn with no name drawn with none; the operator's
     name fainter; the questions' first turn, where the server found it, under the label
     Questions and answers and a heavier rule, with the id Go to the questions takes the reader
     to. Each paragraph's text drawn as text, the find box's words in it each in a mark element;
     their count beside the box: 3 matches, 1 match, none under two characters. */
  function transcript(answer) {
    var hits = 0;
    var at = answer.questionsAt;
    var start = typeof at === 'number' && answer.turns[at] ? at : null;
    var turns = answer.turns.map(function (turn, i) {
      var first = i === start;
      var who = turn.speaker;
      return h('section', {
        key: i, id: first ? QUESTIONS : null,
        className: 'app-ir__turn' + (first ? ' app-ir__turn--questions' : '')
      },
        first ? h('p', { className: 'label app-ir__part' }, 'Questions and answers') : null,
        who == null ? null : h('h3', {
          className: 'body app-ir__who' +
            (who.toLowerCase() === 'operator' ? ' app-ir__who--operator' : '')
        }, who),
        turn.paragraphs.map(function (paragraph, j) {
          var found = marked(paragraph, held.words);
          hits += found.hits;
          return h('p', { key: j, className: 'body app-ir__words' },
            found.parts.map(function (p, k) {
              return p.hit ? h('mark', { key: k }, p.text) : p.text;
            }));
        }));
    });
    return [
      h('div', { key: 'tools', className: 'app-ir__tools' },
        h('input', {
          type: 'search', className: 'control app-ir__find', placeholder: 'Find in this call',
          'aria-label': 'Find in this call', value: held.words,
          onChange: function (event) { held.words = event.target.value; C.redraw(); }
        }),
        h('span', { className: 'caption app-ir__count', role: 'status' },
          words(held.words) ? (hits === 1 ? '1 match' : C.count(hits) + ' matches') : ''),
        start === null ? null : h(F.Button, {
          size: 'sm', className: 'app-ir__go', onClick: toQuestions
        }, 'Go to the questions')),
      h('div', { key: 'turns', className: 'app-ir__turns' }, turns)
    ];
  }

  /* Go to the questions: their first turn scrolled into view at the top. */
  function toQuestions() {
    var target = document.getElementById(QUESTIONS);
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /* The find box's words to find: the words typed with their outer spaces off, none ('') under
     two characters. */
  function words(typed) {
    var found = String(typed == null ? '' : typed).trim();
    return Array.from(found).length < SHORTEST ? '' : found;
  }

  /* `text` with each of its UTF-16 units in lower case where that keeps it one unit, so a place
     found in it is the same place in `text`: the whole text lowered where that keeps its length,
     as it does for all but a few letters (İ). */
  function fold(text) {
    var lower = text.toLowerCase();
    if (lower.length === text.length) return lower;
    var out = '';
    for (var i = 0; i < text.length; i++) {
      var c = text.charAt(i).toLowerCase();
      out += c.length === 1 ? c : text.charAt(i);
    }
    return out;
  }

  /* `paragraph` cut at each place the find box's `typed` words stand in it (7.4; Review Focus 5):
     plain words, never a pattern, whatever the case, from two characters on (words), none
     overlapping. { parts, hits }: the parts in order, each { text, hit }, a found one a hit, which
     join to the paragraph whole, none empty; and the count of hits. */
  function marked(paragraph, typed) {
    var text = String(paragraph);
    var find = fold(words(typed));
    var parts = [];
    var at = 0;
    if (find) {
      var lower = fold(text);
      for (var i = lower.indexOf(find); i !== -1; i = lower.indexOf(find, at)) {
        if (i > at) parts.push({ text: text.slice(at, i), hit: false });
        parts.push({ text: text.slice(i, i + find.length), hit: true });
        at = i + find.length;
      }
    }
    if (at < text.length) parts.push({ text: text.slice(at), hit: false });
    return { parts: parts, hits: parts.filter(function (p) { return p.hit; }).length };
  }

  /* ------------------------------------------------------------------------ the Filings view */

  /* The Filings view (7.5): a company with no filing list on file, or whose first window holds no
     filing, draws its sentence. */
  function filings(answer) {
    var list = answer.filings;
    return list && list.rows.length ? null : none('No filing on file.');
  }

  function none(text) { return h('p', { className: 'body app-ir__none' }, text); }

  /* The data date of the view the address's word names (7.6), the oldest day among the stored
     answers it draws: on the Earnings calls view the read's, which counts the head's quote, the
     list of calls and the earnings rows, or the day of the transcript shown where it is older,
     once its read has landed with words; on the Filings view the day of the filing list it
     draws, none without one. */
  function dataDate(answer, word) {
    if (view(word) === 'filings') return answer.filings ? answer.filings.observedDay : null;
    if (!answer.calls.length || !answer.dataDate) return answer.dataDate;
    var kept = held.reads[keyOf(answer.symbol, chosen(answer.calls, word))];
    var shown = kept && kept.answer && kept.answer.turns.length ? kept.answer.observedDay : null;
    return shown && shown < answer.dataDate ? shown : answer.dataDate;
  }

  /* What the page and the tests use: the tab's function, draw['investor-relations'](answer,
     detail, word), and its data date's; the views and the pure pieces. */
  P.investor = {
    VIEWS: VIEWS, view: view, tab: tab, dataDate: dataDate, years: years, marked: marked,
    title: title
  };
  C.draw[TAB] = function (answer, detail, word) { return tab(answer, word); };
  C.dataDate[TAB] = dataDate;
})();
