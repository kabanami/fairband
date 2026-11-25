/* The company page's Investor relations tab (the Investor relations tab's design, 7), loaded after
   company_financials_chart.js: #company/<symbol>/investor-relations, the company's earnings
   calls and its filings, from the tab's read of the store
   (GET /api/companies/{symbol}/page/investor-relations), which calls no vendor, and from the
   lists a view reads as it opens (below). One block the
   page's width (7.2): at its top a row, the switch of the tab's two views, Earnings calls and
   Filings, at its left, drawn as the Financials tab's switch of statements, and at its right
   end the line of the next earnings report, left out where the read holds no coming date;
   under the row the view the address's word names (7.1), the Filings
   view for filings, else the Earnings calls view, on the call the word names (2026Q4) or on the
   newest. The word is the page's own: it never travels to the server, and a change of it never
   reads the tab again (company.js, load); a press of the switch replaces the hash
   (FairbandPage.show), as a tab's button does. A view with nothing on file draws its sentence,
   No earnings call on file. or No filing on file. Where the read's callsServed is false (the
   plan of the server's FMP key serves no earnings call: Premium), a company with no call on
   file draws Earnings calls need FMP's Ultimate plan. in the first one's place; calls the store
   holds from another plan's time draw as on any plan.

   The lists, read as a view opens (B-252; the founder, 2026-11-18 and 2026-11-25): no refresh
   stores a company's list of earnings calls or its filings, so the tab's read answers what the
   store holds, whatever its age, and names each list that is stale (callsStale, filingsStale):
   none on file, or one older than the reuse window. A view draws the list on file at once and,
   where it is stale, asks for a newer one as it first draws on that answer of the tab: the
   Earnings calls view the list of calls (GET .../investor-relations/calls), unless the plan
   serves none, and the Filings view the first window (GET .../investor-relations/filings with no
   to, the server's day), each with the request header, since it may call a vendor. So a reader
   of the calls alone costs no filing list. The newer list takes the stored one's place as it
   lands, and the page draws again (companyPage.redraw). A view with no list on file draws one
   sentence in the list's place while its read is out, Reading the earnings calls. or Reading the
   filings., with no spinner and no bar (the brand book; the founder's ruling on motion of
   2026-11-23), then the list, or The earnings calls could not be read: <reason>. (The filings
   could not be read: <reason>.). Where a list is on file and the newer one cannot be read, the
   list stays under The newer earnings calls could not be read: <reason>. (The newer filings ...).
   The reads are kept with the answer of the tab they were asked for (lists): a view drawn again
   asks nothing, a read that lands for an answer the page no longer holds draws nothing, and the
   tab read anew, the reader back on the company, asks again.

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
   is put right to the tab alone once drawn, reading nothing of the tab; while the list's read is
   out the address stays, and is judged on the list that lands. A change of call takes
   the page to its top, as a change of report does on the Research tab, and empties the find box.

   The Filings view (7.5): five filters, each with its count, the first pressed as the view opens
   for a company, a press drawing the page again and reading nothing; then the table of the
   filings the filter keeps, newest first, in a box of its own that scrolls sideways, each row its
   day, its form, the form's plain words (FORMS, the mockup's) and its links to the SEC's site,
   each drawn only where it starts https:// and opening in a new tab. Under it the line of the
   windows read, and Show older filings, which reads the window of the 365 days before the oldest
   read (olderTo), through the filings read (GET .../investor-relations/filings?to=, with the
   request header: it may call a vendor), and adds its rows under the table's, a row drawn
   already left out (merged); a window that answers no filing takes the button away, one that
   cannot be read leaves the table as it was with its sentence under it. The windows read are
   kept by company and first window for the page's life; one that lands for a company or a first
   window no longer shown is kept and draws nothing.

   The data date at the tabs' row's right end is the view's (7.6), the oldest day among the
   stored answers it draws: the tab's read's, which counts the head's quote and the earnings
   rows, and on Earnings calls the day of the list of calls drawn, the transcript shown not
   counted; on Filings the days of the filing lists read. company.js asks
   this script for it (dataDate) on every draw, so an older window, which draws the page again as
   it lands (companyPage.redraw), moves it with no change to company.js. The tab's function hangs
   on companyPage.draw, its date's on companyPage.dataDate, and the pure pieces on
   FairbandPage.investor, for the tests, which read them in node. */
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

  /* The Filings view's state, for the page's life: the company it drew last and the filter
     pressed for it, an index of FILTERS, the first for another company; the key of the windows
     the page shows (keptKey), none while it shows the Earnings calls view; and by that key the
     older windows read after a first window, oldest last, { windows, out, failed }: those read,
     whether a read of one is out, and the server's sentence why the last could not be read, or
     null. */
  var filed = { symbol: null, filter: 0, shown: null, kept: {} };

  /* The lists read as a view opens (B-252), for one answer of the tab: `of`, that answer, and
     each list's read, null until its view asks for it, { out: true } while it is out, then
     { answer }, the read's answer, or { failed }, the server's sentence why not. Another answer,
     another company's or this company's tab read anew, starts them again. */
  var lists = { of: null, calls: null, filings: null };

  /* The view the address's word names: filings for the word filings, else calls, the Earnings
     calls view, on the tab alone or on a call. */
  function view(word) { return word === 'filings' ? 'filings' : 'calls'; }

  /* The lists' reads of `answer`, those kept where the page still holds it; this reads nothing. */
  function listsOf(answer) {
    if (lists.of !== answer) lists = { of: answer, calls: null, filings: null };
    return lists;
  }

  /* The read of the list `name` (calls, filings) of `answer`, null where none was asked for:
     started here, through the tab's read of `path` with the request header, where the tab's read
     names the list stale (`stale`) and this answer asked for none yet. As it lands, its answer
     or the server's sentence why not is kept with the answer it was asked for, and the page
     draws again where it still holds that answer. */
  function listRead(answer, name, stale, path) {
    var kept = listsOf(answer);
    if (kept[name] || !stale) return kept[name];
    kept[name] = { out: true };
    C.readVendor('/api/companies/' + encodeURIComponent(answer.symbol) + '/page/' + TAB + path)
      .then(function (got) { return { answer: got }; },
        function (err) { return { failed: err.message }; })
      .then(function (got) {
        kept[name] = got;
        if (lists === kept) C.redraw();
      });
    return kept[name];
  }

  /* The list a view draws on `answer`: its read's where one landed, a list or null; else `stored`,
     the tab's read's. */
  function listed(read, stored) { return read && read.answer ? read.answer : stored; }

  /* The oldest of `days`, ISO days, a missing one aside; null with none. */
  function oldest(days) {
    return days.reduce(function (found, day) {
      return day && (!found || day < found) ? day : found;
    }, null);
  }

  /* The tab on `answer` at the address's word `word` (7.2): its block, the row of the switch and
     the line, then the view's own; the Filings view says which windows it shows (filed.shown),
     none on the Earnings calls view. */
  function tab(answer, word) {
    var shown = view(word);
    filed.shown = null;
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
     reader of the call shown, side by side. The list is the newer one read as the view opened
     where it landed, else the tab's read's (listRead: asked where that is stale, unless the plan
     serves no earnings call). A company with no call to draw draws its sentence and no reader:
     while the list's read is out, Reading the earnings calls.; where it failed, why; where the
     read's callsServed is false, the plan of the server's key serving no earnings call, the
     sentence of what they need; else No earnings call on file. A list on file whose newer one
     could not be read stays, under the sentence that says so. A word that names no call on the
     list is put right (putRight), but not while the list's read is out. A change of call
     from the one the reader drew last, of the same company, takes the page to its top and
     empties the find box; another company's starts with five fiscal years and an empty box. */
  function calls(answer, word) {
    var served = answer.callsServed !== false;
    var read = listRead(answer, 'calls', !!answer.callsStale && served, '/calls');
    var out = !!(read && read.out);
    var failed = read && read.failed != null ? read.failed : null;
    var list = read && read.answer ? read.answer.calls : answer.calls;
    if (word != null && !out && !named(list, word)) putRight(answer.symbol, word);
    if (!list.length) {
      return none(out ? 'Reading the earnings calls.'
        : failed != null ? 'The earnings calls could not be read: ' + failed + '.'
          : served ? 'No earnings call on file.' : 'Earnings calls need FMP\'s Ultimate plan.');
    }
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
    var block = h('div', { key: 'calls', className: 'app-ir__calls' },
      callList(answer.symbol, list, call, word),
      reader(call, reading(answer.symbol, call)));
    return failed == null ? block
      : [none('The newer earnings calls could not be read: ' + failed + '.', 'newer'), block];
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

  /* The forms in plain words (7.5), the mockup's table as written there: a line states what the
     form is and judges nothing. */
  var FORMS = {
    '10-K': 'Annual report', '10-Q': 'Quarterly report',
    '8-K': 'Current report: an event the company must disclose',
    'DEF 14A': 'Proxy statement for the shareholders\' meeting',
    'DEFA14A': 'Additional proxy material',
    '3': 'An insider\'s first statement of holdings',
    '4': 'A change in an insider\'s holdings',
    '5': 'An insider\'s yearly statement of holdings',
    '144': 'Notice of a planned sale of restricted shares',
    '424B2': 'Prospectus for securities on offer', 'FWP': 'Free writing prospectus',
    '25-NSE': 'Notice that a security leaves an exchange', 'SD': 'Specialized disclosure report',
    '11-K': 'Annual report of an employee stock plan',
    'S-8': 'Registration of shares for employee plans',
    'S-3ASR': 'Shelf registration of securities', '20-F': 'Annual report of a foreign issuer',
    '6-K': 'Report of a foreign issuer', 'SC 13G': 'A large holder\'s statement of ownership',
    'SC 13G/A': 'A change to a large holder\'s statement',
    'PX14A6G': 'A shareholder\'s notice of exempt solicitation',
    'ARS': 'Annual report to shareholders'
  };
  var AMENDED = '/A'; /* an amendment's mark at a form's end: 8-K/A */
  /* The insider forms, the agents' filing list's OWNERSHIP_FORMS (filings_api), which it leaves
     out by default, as the first filter does; a test holds the two alike. */
  var INSIDER = ['3', '4', '5', '144'];
  var HTTPS = 'https://'; /* the start of a link the table draws (7.5) */
  var HEADS = ['Filed', 'Form', 'What it is', 'On the SEC\'s site'];
  var DAY = 864e5; /* a day's milliseconds */

  /* A form as the filters read it: as given, its outer spaces off and in upper case. */
  function upper(form) { return String(form).trim().toUpperCase(); }

  /* The form an amendment `form` amends (8-K for 8-K/A); null for a form that is no amendment. */
  function amended(form) {
    return form.slice(-AMENDED.length) === AMENDED ? form.slice(0, -AMENDED.length) : null;
  }

  /* Whether `form` is an insider's form, 3, 4, 5 or 144, or an amendment of one (4/A), as the
     agents' filing list judges it. */
  function insider(form) {
    var f = upper(form);
    return INSIDER.indexOf(amended(f) || f) !== -1;
  }

  /* Whether `form` starts with one of `heads`: 10-K/A and 10-KT start 10-K. */
  function starts(form, heads) {
    var f = upper(form);
    return heads.some(function (head) { return f.indexOf(head) === 0; });
  }

  /* The five filters (7.5), each its name and the test of a form it keeps; the first pressed as
     the view opens. A foreign issuer's 20-F and 6-K stand under the first and under All. */
  var FILTERS = [
    { name: 'Without insider forms', test: function (form) { return !insider(form); } },
    { name: '10-K and 10-Q', test: function (form) { return starts(form, ['10-K', '10-Q']); } },
    { name: '8-K', test: function (form) { return starts(form, ['8-K']); } },
    { name: 'Insider forms', test: insider },
    { name: 'All', test: function () { return true; } }
  ];

  /* The key the older windows of `symbol` read after its first window `list` are kept under:
     the company and the first window's last day, so a newer first window (a refresh's) starts
     them again and leaves no gap behind it. */
  function keptKey(symbol, list) { return symbol + '/' + list.to; }

  /* What it is (7.5): `form`'s words from the table; an amendment the table lacks, Amendment: and
     its form's words; nothing for a form the table lacks. */
  function what(form) {
    var f = String(form == null ? '' : form);
    var base = amended(f);
    if (has(FORMS, f)) return FORMS[f];
    return base !== null && has(FORMS, base) ? 'Amendment: ' + FORMS[base] : '';
  }

  function has(table, key) { return Object.prototype.hasOwnProperty.call(table, key); }

  /* The day before the ISO day `iso`. */
  function dayBefore(iso) {
    return new Date(Date.parse(iso + 'T00:00:00Z') - DAY).toISOString().slice(0, 10);
  }

  /* The last day of the next window to read (7.5) after `windows`, the filing lists read, oldest
     last, of which `rows` are the rows shown: the day before the oldest window's first day; where
     that window is cut at the vendor's limit, so its oldest filings are missing, the filing day of
     the oldest row shown, a row with no day aside, or, with none, the day before its first. */
  function olderTo(windows, rows) {
    var oldest = windows[windows.length - 1];
    var day = null;
    if (oldest.truncated) {
      rows.forEach(function (row) { if (row.filed && (!day || row.filed < day)) day = row.filed; });
    }
    return day || dayBefore(oldest.from);
  }

  /* A row's identity among the windows read: its files link, its form and its day. */
  function sameAs(row) { return JSON.stringify([row.files, row.form, row.filed]); }

  /* `rows`, the rows drawn, and under them the rows of `more`, a window read, in their order, but
     a row with the same files link, form and day as one drawn already (7.5): the next window after
     a cut one starts on the cut one's oldest day, which both hold. */
  function merged(rows, more) {
    var drawn = Object.create(null);
    rows.forEach(function (row) { drawn[sameAs(row)] = true; });
    return rows.concat(more.filter(function (row) { return !drawn[sameAs(row)]; }));
  }

  /* The Filings view (7.5) on `answer`. Its first window is the newer one read as the view
     opened where it landed, else the tab's read's (listRead: asked where that is stale). A
     company with no filing list to draw draws its sentence and no button: while the list's read
     is out, Reading the filings.; where it failed, why; else No filing on file. A list on file
     whose newer one could not be read stays, under the sentence that says so.
     Else the first window and the older ones read after it, their rows one under
     the other: the filters, each with its count among them, the table of those the filter
     pressed keeps, in a box of its own that scrolls sideways, and under it the line of the
     windows read, the vendor's cut where the oldest is cut, Show older filings until a window older
     than the first answers no filing, and the sentence of an older window that could not be read.
     A first window with no filing draws its sentence and the button alone. While an older window's
     read is out the view waits, faded (aria-busy). While the newer first window's read is out
     Show older filings is off and a press reads nothing: the older windows are kept by the first
     window's last day, so one read then would go as the newer list lands. */
  function filings(answer) {
    var read = listRead(answer, 'filings', !!answer.filingsStale, '/filings');
    var failed = read && read.failed != null ? read.failed : null;
    var list = listed(read, answer.filings);
    if (filed.symbol !== answer.symbol) {
      filed.symbol = answer.symbol;
      filed.filter = 0;
    }
    if (!list) {
      return none(read && read.out ? 'Reading the filings.'
        : failed != null ? 'The filings could not be read: ' + failed + '.'
          : 'No filing on file.');
    }
    var key = keptKey(answer.symbol, list);
    var kept = filed.kept[key] || (filed.kept[key] = { windows: [], out: false, failed: null });
    filed.shown = key;
    var windows = [list].concat(kept.windows);
    var rows = windows.reduce(function (all, w) { return merged(all, w.rows); }, []);
    var more = windows.length === 1 || windows[windows.length - 1].rows.length > 0;
    var waiting = !!(read && read.out);
    var press = function () { if (!waiting) older(answer.symbol, key, kept, windows, rows); };
    var block = h('div', {
      key: 'filings', className: 'app-ir__filings', 'aria-busy': kept.out ? 'true' : null
    },
      rows.length ? filters(rows) : none('No filing on file.'),
      rows.length ? h('div', { className: 'app-ir__scroll' }, table(rows)) : null,
      foot(rows.length ? line(windows) : null, more ? press : null, kept.out || waiting),
      kept.failed != null ? none('The older filings could not be read: ' + kept.failed + '.')
        : null);
    return failed == null ? block
      : [none('The newer filings could not be read: ' + failed + '.', 'newer'), block];
  }

  /* Under the table (7.5): `words`, the line of the windows read, where rows are drawn, then
     Show older filings, `press` its press, where a window may be read, disabled while one is
     `out`. */
  function foot(words, press, out) {
    return h('div', { className: 'app-ir__foot' }, words,
      press ? h(F.Button, {
        size: 'sm', className: 'app-ir__older', disabled: out, onClick: press
      }, 'Show older filings') : null);
  }

  /* The line of `windows`, the filing lists read, oldest last: from the oldest's first day to
     the first's last, and the vendor's cut where the oldest holds its limit of rows, so its
     oldest filings are missing; a cut window with a whole one read behind it leaves no gap. */
  function line(windows) {
    var oldest = windows[windows.length - 1];
    var cut = !!oldest.truncated;
    return h('p', { className: 'body app-ir__window' },
      'Filed from ' + C.day(oldest.from) + ' to ' + C.day(windows[0].to) + '.',
      cut ? h('span', { className: 'app-ir__cut' },
        ' The vendor\'s list is cut at 1,000 filings a window.') : null);
  }

  /* The row of the five filters over the table, the one pressed marked, each with its count
     among `rows`; a press draws the page again with its rows and reads nothing. */
  function filters(rows) {
    return h('div', { className: 'app-ir__filters' }, FILTERS.map(function (f, i) {
      var n = rows.filter(function (row) { return f.test(row.form); }).length;
      return h('button', {
        key: f.name, type: 'button', className: 'control app-ir__filter',
        'aria-pressed': i === filed.filter ? 'true' : 'false',
        onClick: function () { filed.filter = i; C.redraw(); }
      }, f.name, ' ', h('span', { className: 'figure-sm app-ir__n' }, C.count(n)));
    }));
  }

  /* The table (7.5) of the `rows` the filter pressed keeps, newest first, four columns: the day
     filed, the form as the vendor gives it, the form's plain words, and its links. */
  function table(rows) {
    var test = FILTERS[filed.filter].test;
    return h('table', { className: 'app-ir__table' },
      h('thead', null, h('tr', null, HEADS.map(function (head) {
        return h('th', { key: head, className: 'label' }, head);
      }))),
      h('tbody', null, rows.filter(function (row) { return test(row.form); }).map(
        function (row, i) {
          return h('tr', { key: i },
            h('td', { className: 'figure app-ir__filed' }, C.day(row.filed)),
            h('td', { className: 'body app-ir__form' }, row.form),
            h('td', { className: 'body app-ir__what' }, what(row.form)),
            h('td', { className: 'body app-ir__links' },
              link(row.document, 'Document'), link(row.files, 'All files')));
        })));
  }

  /* A link to the SEC's site that opens in a new tab, its words `words`, where `href` starts
     https://, as the read gives none other; nothing else. */
  function link(href, words) {
    if (typeof href !== 'string' || href.indexOf(HTTPS) !== 0) return null;
    return h('a', {
      className: 'app-link app-ir__link', href: href, target: '_blank', rel: 'noopener'
    }, words);
  }

  /* Show older filings (7.5, 7.6) for `symbol`'s windows `kept` under `key`, `windows` and `rows`
     those drawn: unless a read is out, the next window's read (olderTo), with the request header,
     the view faded meanwhile; as it lands, its window kept under its own key, or the server's
     sentence why not, and the page drawn again where it still shows that key's windows. A late
     answer of another company draws nothing. */
  function older(symbol, key, kept, windows, rows) {
    if (kept.out) return;
    kept.out = true;
    kept.failed = null;
    C.readVendor('/api/companies/' + encodeURIComponent(symbol) + '/page/' + TAB +
      '/filings?to=' + olderTo(windows, rows))
      .then(function (answer) { kept.windows.push(answer); },
        function (err) { kept.failed = err.message; })
      .then(function () {
        kept.out = false;
        if (filed.shown === key) C.redraw();
      });
    C.redraw();
  }

  /* A view's sentence `text`; `key` where it stands in a list beside the view's block. */
  function none(text, key) { return h('p', { key: key, className: 'body app-ir__none' }, text); }

  /* The data date of the view the address's word names (7.6), the oldest day among the stored
     answers it draws: the read's, which counts the head's quote and the earnings rows, drawn on
     both views, and on the Earnings calls view the day of the list of calls drawn, the newer one
     read as the view opened where it landed, else the tab's read's, and not the transcript
     shown, whose words do not age and whose call carries its own date; on the Filings view the
     days of the filing lists read (filingsDate). It starts no read. */
  function dataDate(answer, word) {
    if (view(word) === 'filings') return filingsDate(answer);
    var read = listsOf(answer).calls;
    return oldest([answer.dataDate, read && read.answer ? read.answer.callsDay : answer.callsDay]);
  }

  /* The Filings view's data date on `answer`: the oldest day among its dataDate and the filing
     lists read, its first window's, the newer one read as the view opened where it landed, and
     the older windows' read after it; its dataDate without a filing list. */
  function filingsDate(answer) {
    var list = listed(listsOf(answer).filings, answer.filings);
    var kept = list ? filed.kept[keptKey(answer.symbol, list)] : null;
    var read = list ? [list].concat(kept ? kept.windows : []) : [];
    return oldest([answer.dataDate].concat(read.map(function (w) { return w.observedDay; })));
  }

  /* What the page and the tests use: the tab's function, draw['investor-relations'](answer,
     detail, word), and its data date's; the views and the pure pieces. */
  P.investor = {
    VIEWS: VIEWS, view: view, tab: tab, dataDate: dataDate, years: years, marked: marked,
    title: title, FILTERS: FILTERS, FORMS: FORMS, INSIDER: INSIDER, words: what,
    olderTo: olderTo, merged: merged
  };
  C.draw[TAB] = function (answer, detail, word) { return tab(answer, word); };
  C.dataDate[TAB] = dataDate;
})();
