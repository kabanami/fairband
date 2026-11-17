/* The company page's Research tab (the Research tab's design, 7), loaded after
   company_research_text.js: #company/<symbol>/research, the company's latest report, and
   #company/<symbol>/research/<id>, the report with that id, from the tab's read
   (GET /api/companies/{symbol}/page/research), which carries the report shown whole and the
   company's reports on file. It draws and writes nothing else: no override, no kill criterion's
   state, no note and no Request research, which the head has.

   Under the tabs' row, the bar (7.2): Report and Records, the tab's two views; in the Report
   view the report's line, its stance in the Stance column's chip, faded once its validity ended,
   its mode, its revision, its date and time, who wrote it, valid until and, for a valuation
   review, the full report it reuses; at its right Footnote marks and Download .md; under it a
   valuation review's note that it reuses none and the Markdown's refusal. In the Records view
   the line's sentence alone. Then, in the Report view, the section list at the left (7.3): the
   report's headings, the three parts kept closed, References with their count, and the reports
   on file, the one shown marked, each other a link to its address; the name of the section in
   view marked as the app marks a selection, where the browser can tell which is in view, else
   the first. A press on a name scrolls to its panel and opens it where it is closed. At the
   right, a panel a section (7.4): its heading, then the rows its layout gives
   (FairbandPage.researchText.lay), each block drawn by the design system's reader
   (Fairband.reportText.draw), and the cards beside its first run of text, the named blocks its
   layout makes cards and the records' cards the tab hands it by heading. Then the references,
   Appendix A and Appendix B (7.8), each closed, each opened drawing what the report page draws
   (FairbandPage.reportParts). A company with no report draws "No report yet." alone.

   A cited number (7.7) is the design system's cite: the CSS gives it the text's colour and its
   [n] shows while Footnote marks is on, the choice kept in the browser's localStorage under
   fairband.research.marks, read and written inside a try, off where it keeps nothing. Its source,
   the reference's number and its words (source), shows in one box of the tab's own on hover and
   on keyboard focus, each cite made focusable; the cite's own title, its ref, is taken off as the
   box shows, so the browser shows no second one.

   Research, the tab's component, keeps the view, the marks, the section in view and the
   Markdown's refusal in its state, drawn keyed on the company of its answer, so another report of
   the company keeps them and another company opens a new tab. The pieces are pure builders on
   FairbandPage.research, for the tests, which read them in node, and draw.research hangs on the
   company page's draw (company.js). */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var C = P.companyPage;

  var MARKS_KEY = 'fairband.research.marks';
  var RECORDS = 'The company\'s records on file, from any report.';
  var EXPIRED = 'The value of this report is past the date it was valid until';
  var CLOSED = ['research-refs', 'research-a', 'research-b']; /* the closed parts' panels */
  var CITE_TITLE = /^traces to /; /* the start of the bundle's title of a cite, before its ref */

  /* A section's panel's id, from its index in the report: research-s1 for the first. */
  function panelId(index) { return 'research-s' + (index + 1); }

  /* ---------------------------------------------------------------------------- the marks kept */

  /* Whether the browser keeps Footnote marks on: true where it holds 1, else false, and false
     where it keeps nothing or its store throws. */
  function storedMarks() {
    try {
      return window.localStorage.getItem(MARKS_KEY) === '1';
    } catch (e) {
      return false;
    }
  }

  /* Keeps Footnote marks `on` in the browser, 1 or 0; where it keeps nothing, the choice lasts
     while the tab is open. Never throws. */
  function keepMarks(on) {
    try {
      window.localStorage.setItem(MARKS_KEY, on ? '1' : '0');
    } catch (e) { /* no store */ }
  }

  /* -------------------------------------------------------------------------------- the bar */

  /* The bar (7.2) on `answer` in the view `view`, 'report' or 'records', Footnote marks `marks`
     on or off. `act` holds what it draws with and what its controls call: `today`, the detail's
     day, against which the report's validity has ended; `failed`, the Markdown's refusal or null;
     view(next), marks() and download(). Under it, in the Report view, a valuation review's note
     that it reuses no full report, and the Markdown's refusal. */
  function bar(answer, view, marks, act) {
    var report = answer.report;
    var shown = view === 'report';
    return h('div', { className: 'app-research__top' },
      h('div', { className: 'app-research__bar' },
        h('div', {
          className: 'app-research__views', role: 'tablist', 'aria-label': 'What the tab shows'
        }, viewButton('report', 'Report', view, act), viewButton('records', 'Records', view, act)),
        !shown ? h('p', { className: 'caption app-research__line' }, RECORDS)
          : report ? line(answer, act.today) : null,
        shown && report ? h('div', { className: 'app-research__actions' },
          h(F.Button, {
            size: 'sm', className: 'app-research__marks', 'aria-pressed': marks ? 'true' : 'false',
            onClick: act.marks
          }, 'Footnote marks'),
          h(F.Button, { size: 'sm', className: 'app-research__download', onClick: act.download },
            'Download .md')) : null),
      shown && report && report.mode === 'valuation review' && report.reusesFullReportOf == null
        ? h('p', { className: 'caption app-research__note' }, 'No full report to reuse.') : null,
      shown && act.failed ? h('p', { className: 'caption app-research__error' }, act.failed)
        : null);
  }

  /* One of the bar's two views, selected where it is `view`. */
  function viewButton(id, words, view, act) {
    return h('button', {
      key: id, type: 'button', role: 'tab', className: 'control app-research__view',
      'aria-selected': id === view ? 'true' : 'false',
      onClick: function () { act.view(id); }
    }, words);
  }

  /* The report's line: its stance in the Stance column's chip, faded with the report page's
     title where the window of the snapshot it rests on ended before `today`; its mode; its
     revision; its date and time; who wrote it; valid until; and the full report a valuation
     review reuses, by that report's date. */
  function line(answer, today) {
    var report = answer.report;
    var until = report.appendixA.snapshot.validUntil;
    var expired = until < today;
    var reused = reusedOn(answer);
    return h('div', { className: 'app-research__line' },
      h('span', {
        className: 'fb-stance fb-stance--' + report.stance +
          (expired ? ' fb-stance--expired' : '') + ' label',
        title: expired ? EXPIRED : null
      }, report.stance),
      h('span', { className: 'label app-research__mode' }, report.mode),
      h('span', { className: 'figure-sm' }, 'revision ' + report.revision),
      h('span', { className: 'caption' }, P.when(report.createdAt)),
      h(F.PrincipalChip, { principal: report.principal, actor: report.actor }),
      h('span', { className: 'caption' }, 'valid until ' + C.day(until)),
      reused ? h('span', { className: 'caption' }, 'reuses the full report of ' + C.day(reused))
        : null);
  }

  /* When the full report a valuation review reuses was written, in the reader's local time, from
     the company's reports on file; null where it reuses none, or none on file is it. */
  function reusedOn(answer) {
    var id = answer.report.reusesFullReportOf;
    var found = answer.reports.filter(function (r) { return r.id === id; })[0];
    return id != null && found ? P.localIso(found.createdAt) : null;
  }

  /* ------------------------------------------------------------------------------- the list */

  /* The section list (7.3) of `answer`'s report, the name of the panel `shown` marked: the
     report's headings, the three parts kept closed, then the reports on file. */
  function list(answer, shown) {
    var report = answer.report;
    var names = report.sections.map(function (s, i) {
      return link(panelId(i), s.heading, null, shown);
    });
    var kept = [
      link(CLOSED[0], 'References', report.references.length, shown),
      link(CLOSED[1], 'Appendix A', null, shown),
      link(CLOSED[2], 'Appendix B', null, shown)
    ];
    return h('nav', { className: 'app-research__list', 'aria-label': 'The report\'s sections' },
      group('The report', h('ul', { className: 'app-research__links' }, names)),
      group('Kept closed', h('ul', { className: 'app-research__links' }, kept)),
      group('Reports on file · ' + C.count(answer.reports.length),
        h('ul', { className: 'app-research__files' }, answer.reports.map(function (r) {
          return h('li', { key: r.id }, file(r, report.id, answer.symbol));
        }))));
  }

  function group(title, body) {
    return h('div', { key: title, className: 'app-research__group' },
      h('p', { className: 'label app-research__grouphead' }, title), body);
  }

  /* A name in the list: a press scrolls to its panel `id` and opens it where it is closed (go);
     `n`, a count after the name where given; marked where it is the panel `shown`. */
  function link(id, name, n, shown) {
    return h('li', { key: id },
      h('button', {
        type: 'button', className: 'control app-research__link' + (id === shown ? ' is-on' : ''),
        'aria-current': id === shown ? 'true' : null,
        onClick: function () { go(id); }
      },
        h('span', null, name),
        n == null ? null : h('span', { className: 'figure-sm app-research__n' }, C.count(n))));
  }

  /* The panel `id` brought into view, opened where it is a closed part. */
  function go(id) {
    var target = document.getElementById(id);
    if (!target) return;
    if (target.tagName === 'DETAILS') target.open = true;
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /* A report on file: its date and its revision over its mode and its stance; the one shown,
     `shownId`, marked and no link, each other a link to its address on the tab. */
  function file(r, shownId, symbol) {
    var mode = String(r.mode);
    var words = [
      h('span', { key: 'when', className: 'control' },
        C.day(P.localIso(r.createdAt)) + ', revision ' + r.revision),
      h('span', { key: 'what', className: 'caption app-research__what' },
        mode.charAt(0).toUpperCase() + mode.slice(1) + ', ' + r.stance)
    ];
    if (r.id === shownId) {
      return h('span', { className: 'app-research__file is-on', 'aria-current': 'page' }, words);
    }
    return h('a', { className: 'app-research__file', href: C.researchHref(symbol, r.id) }, words);
  }

  /* ---------------------------------------------------------------------------- the sections */

  /* The panel of `s`, the report's section at `index` (7.4): its heading, then the rows its
     layout gives under the report's stance, and its cards, the named blocks the layout makes
     cards and those `cards` holds for its heading, in a column beside its first run of text, or
     after its rows where it has none; no column where it has no card. */
  function section(s, index, report, cards) {
    var laid = P.researchText.lay(s.heading, s.parts, report.stance);
    var footnotes = P.footnotes(report.references);
    var held = Object.prototype.hasOwnProperty.call(cards, s.heading) ? cards[s.heading] : [];
    var aside = laid.cards.map(function (b, i) {
      return labelled(b, footnotes, i, 'app-research__card');
    }).concat(held);
    var rows = laid.rows.map(function (r, i) { return row(r, footnotes, i); });
    if (aside.length) {
      var side = h('div', { key: 'cards', className: 'app-research__cards' }, aside);
      var first = laid.rows.map(function (r) { return r.kind; }).indexOf('run');
      if (first < 0) rows.push(side);
      else {
        rows[first] = h('div', { key: 'split', className: 'app-research__split' }, rows[first],
          side);
      }
    }
    return h('section', {
      key: panelId(index), id: panelId(index), className: 'app-research__sec'
    },
      h('h2', { className: 'heading app-research__title' }, s.heading),
      h('div', { className: 'app-research__body' }, rows));
  }

  /* A row of the layout under `key` (company_research_text.js, lay). */
  function row(r, footnotes, key) {
    if (r.kind === 'run') return run(r.blocks, footnotes, key);
    if (r.kind === 'wide') return wide(r.block, footnotes, key);
    if (r.kind === 'columns') return columns(r.blocks, footnotes, key);
    if (r.kind === 'pair') return pair(r, footnotes, key);
    if (r.kind === 'groups') return groups(r, key);
    if (r.kind === 'sides') return sides(r.sides, footnotes, key);
    return null;
  }

  /* Text at the reading width: the blocks in their order. */
  function run(blocks, footnotes, key) {
    return h('div', { key: key, className: 'app-research__run' }, blocks.map(function (b, i) {
      return block(b, footnotes, i);
    }));
  }

  /* A wide table across the panel, its whole width where a cell is long. */
  function wide(b, footnotes, key) {
    var full = P.researchText.isLong(b);
    return h('div', {
      key: key, className: 'app-research__wide' + (full ? ' app-research__wide--full' : '')
    }, block(b, footnotes, 0));
  }

  /* Named lists side by side. */
  function columns(blocks, footnotes, key) {
    return h('div', { key: key, className: 'app-research__columns' }, blocks.map(function (b, i) {
      return block(b, footnotes, i);
    }));
  }

  /* A paragraph beside the charts of its group: the paragraph at the reading width, as a run
     draws it. */
  function pair(r, footnotes, key) {
    return run([r.block], footnotes, key);
  }

  /* The charts of groups alone: nothing yet. */
  function groups() {
    return null;
  }

  /* Two columns, each its block under its label. */
  function sides(list, footnotes, key) {
    return h('div', { key: key, className: 'app-research__sides' }, list.map(function (s, i) {
      return h('div', { key: i, className: 'app-research__side' },
        h('p', { className: 'label app-research__name' }, s.label),
        block(s.block, footnotes, 'text'));
    }));
  }

  /* A block under `key`: a named block under its name, any other as the design system's reader
     draws it. */
  function block(b, footnotes, key) {
    if (b.kind === 'named') return labelled(b, footnotes, key, 'app-research__named');
    return F.reportText.draw(b, footnotes, key);
  }

  /* A named block, `b`, of the class `className`: its name, a line of pieces the reader draws,
     over its body. */
  function labelled(b, footnotes, key, className) {
    return h('div', { key: key, className: className },
      h('div', { className: 'label app-research__name' },
        F.reportText.draw({ kind: 'p', items: [b.name] }, footnotes, 'name')),
      F.reportText.draw(b.body, footnotes, 'body'));
  }

  /* --------------------------------------------------------------------------- the closed parts */

  /* The references, Appendix A and Appendix B (7.8), each a panel closed until the reader opens
     it, its head its name and one line, each opened drawing what the report page draws. */
  function closed(report) {
    return [
      fold(CLOSED[0], 'References',
        report.references.length + ' sources, one for each cited number',
        P.reportParts.references(report)),
      fold(CLOSED[1], 'Appendix A', 'the audit of the records the report rests on',
        P.reportParts.appendixA(report)),
      fold(CLOSED[2], 'Appendix B', 'the glossary, ' + report.appendixB.length + ' terms',
        P.reportParts.appendixB(report))
    ];
  }

  function fold(id, name, note, body) {
    return h('details', { key: id, id: id, className: 'app-research__sec app-research__closed' },
      h('summary', { className: 'app-research__summary' },
        h('span', { className: 'heading' }, name),
        h('span', { className: 'caption app-research__gloss' }, note)),
      h('div', { className: 'app-research__fold' }, body));
  }

  /* -------------------------------------------------------------------------- a cited number */

  /* The words of the box of a cite of `ref` (7.7): its reference's number and its source,
     "[3] FMP income statement, revenue, fiscal 2026"; null for a ref `references` lack. */
  function source(ref, references) {
    var key = String(ref).trim();
    var found = (references || []).filter(function (e) {
      return String(e.ref).trim() === key;
    })[0];
    return found ? '[' + found.n + '] ' + found.source : null;
  }

  /* The box of a cite's source, for the tab drawn in `root`, whose references `refs.current`
     holds: one element of its own at the page's end, shown over a cite under the pointer or with
     the focus, under it where there is no room above, hidden as the pointer or the focus leaves
     it and as anything scrolls. A cite's own title is taken off as it shows, kept as its
     data-ref. Gives what takes the box and its listeners away. */
  function follow(root, refs) {
    if (!root) return undefined;
    var box = document.createElement('div');
    box.className = 'app-research__tip';
    box.setAttribute('role', 'tooltip');
    box.hidden = true;
    document.body.appendChild(box);
    function citeOf(event) {
      return event.target instanceof Element ? event.target.closest('.fb-cite') : null;
    }
    function hide() { box.hidden = true; }
    function show(event) {
      var cite = citeOf(event);
      if (!cite) { hide(); return; }
      if (cite.hasAttribute('title')) {
        cite.setAttribute('data-ref', cite.getAttribute('title').replace(CITE_TITLE, ''));
        cite.removeAttribute('title');
      }
      var words = source(cite.getAttribute('data-ref'), refs.current);
      if (!words) { hide(); return; }
      box.textContent = words;
      box.hidden = false;
      var at = cite.getBoundingClientRect();
      var size = box.getBoundingClientRect();
      var above = at.top - size.height - 6;
      box.style.left = Math.max(8, Math.min(at.left, window.innerWidth - size.width - 8)) + 'px';
      box.style.top = (above < 8 ? at.bottom + 6 : above) + 'px';
    }
    root.addEventListener('mouseover', show);
    root.addEventListener('mouseleave', hide);
    root.addEventListener('focusin', show);
    root.addEventListener('focusout', hide);
    document.addEventListener('scroll', hide, true);
    return function () {
      root.removeEventListener('mouseover', show);
      root.removeEventListener('mouseleave', hide);
      root.removeEventListener('focusin', show);
      root.removeEventListener('focusout', hide);
      document.removeEventListener('scroll', hide, true);
      box.remove();
    };
  }

  /* Each cite drawn in `root` takes the keyboard's focus, so its box shows on focus too. */
  function focusable(root) {
    if (!root) return;
    Array.prototype.forEach.call(root.querySelectorAll('.fb-cite:not([tabindex])'), function (c) {
      c.tabIndex = 0;
    });
  }

  /* Which panel of the tab drawn in `root` is in view, handed to `mark` as it changes, where the
     browser has an IntersectionObserver: the first of those in the band near the top of the
     window. Gives what stops watching. */
  function watch(root, mark) {
    if (!root || !window.IntersectionObserver) return undefined;
    var panels = Array.prototype.slice.call(root.querySelectorAll('.app-research__sec'));
    var seen = {};
    var spy = new window.IntersectionObserver(function (entries) {
      entries.forEach(function (e) { seen[e.target.id] = e.isIntersecting; });
      var on = panels.filter(function (p) { return seen[p.id]; })[0];
      if (on) mark(on.id);
    }, { rootMargin: '-8% 0px -70% 0px' });
    panels.forEach(function (p) { spy.observe(p); });
    return function () { spy.disconnect(); };
  }

  /* ---------------------------------------------------------------------------------- the tab */

  /* The tab on `props.answer` and the company's `props.detail`: the bar, then in the Report view
     the list and the panels, or "No report yet."; the Records view draws its line alone. It keeps
     the view, Report at first; Footnote marks, as the browser keeps them; the panel in view, the
     first at first; and the Markdown's refusal, with the report it is of, so another report
     draws none. */
  function Research(props) {
    var answer = props.answer;
    var report = answer.report;
    var view = React.useState('report');
    var marks = React.useState(storedMarks());
    var shown = React.useState(panelId(0));
    var failed = React.useState(null);
    var root = React.useRef(null);
    var refs = React.useRef(null);
    refs.current = report ? report.references : [];
    React.useEffect(function () { return follow(root.current, refs); }, []);
    React.useEffect(function () { focusable(root.current); });
    React.useEffect(function () {
      return watch(root.current, shown[1]);
    }, [report ? report.id : null, view[0]]);
    var act = {
      today: props.detail ? props.detail.today : null,
      failed: failed[0] && report && failed[0].id === report.id ? failed[0].text : null,
      view: function (next) { view[1](next); },
      marks: function () {
        keepMarks(!marks[0]);
        marks[1](!marks[0]);
      },
      download: function () {
        var id = report.id;
        failed[1](null);
        P.reportParts.download(report, function (text) { failed[1]({ id: id, text: text }); });
      }
    };
    return h('div', {
      ref: root, className: 'app-research' + (marks[0] ? ' app-research--marks' : '')
    },
      bar(answer, view[0], marks[0], act),
      view[0] !== 'report' ? null
        : report ? h('div', { className: 'app-research__layout' },
          list(answer, shown[0]),
          h('div', { className: 'app-research__main' },
            report.sections.map(function (s, i) { return section(s, i, report, {}); }),
            closed(report)))
          : h('p', { className: 'body app-research__none' }, 'No report yet.'));
  }

  /* The tab's function, draw.research(answer, detail): the tab keyed on the company of its
     answer, so another company's answer opens a new one. */
  function research(answer, detail) {
    return h(Research, { key: answer.symbol, answer: answer, detail: detail });
  }

  /* What the page and the tests use. */
  P.research = {
    bar: bar, list: list, section: section, closed: closed, source: source,
    storedMarks: storedMarks, keepMarks: keepMarks, Research: Research
  };
  C.draw.research = research;
})();
