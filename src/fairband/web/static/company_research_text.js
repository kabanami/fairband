/* The company page's Research tab: the layout rules of a report's section (the Research tab's
   design, 7.4 and 4), loaded after company_financials_chart.js. They are plain functions over the
   section's blocks, as the design system's reader gives them (Fairband.reportText.read: a
   paragraph's items its lines, a list's its items, a table's its rows under its head, each a
   list of pieces, a text or a cite), which give data and draw nothing: the tab draws the rows
   and the cards they return, and the tests read them in node. No function here reads the text's
   shape itself.

   A named block is a list or a table directly under a paragraph of one line, 90 characters or
   fewer, that ends in a colon; the line, its colon off, is its name. A table, bare or named, is
   wide with more than four columns or a cell above 44 characters.

   lay(heading, parts, stance) gives the section's rows, each one of
     { kind: 'run', blocks }          text at the reading width,
     { kind: 'wide', block }          a wide table across the panel,
     { kind: 'columns', blocks }      named lists side by side,
     { kind: 'pair', group, block }   a paragraph beside the charts of its group,
     { kind: 'groups', groups }       the charts of groups alone,
     { kind: 'sides', sides }         two columns, each { label, block },
   and its cards, the named blocks that stand beside the first run of text. By heading:

   1. Summary: the first line leaves where it is exactly `Stance: <word>.` and the word is the
      report's stance, which the bar states; two or more named lists in a row stand side by side,
      under the text before them, what follows them under them.
   2. Any heading but the nine below, a heading the rules do not know among them: a named list,
      and a named table that is not wide, are cards, where some text stays for them to stand
      beside.
   3. Financial performance and health: a paragraph that opens with a bold lead word stands beside
      the charts of the group the word names (group), each group named once, by the first
      paragraph that names it; a group no paragraph names stands in a row after them. Where fewer
      than four paragraphs name a group, every chart stands first, by group, and the text follows.
   5. The bull case and the bear case: a section of exactly two paragraphs, one that opens "The
      bull case" and one "The bear case", stands in two columns, each under those words as its
      label, the words taken off the paragraph's start and the first letter after them upper case.

   Under the earnings call, Valuation, Price and multiples, Recent news, Risks and kill criteria
   and Key judgments, whose cards draw records, and wherever a rule's shape is absent, the blocks
   stand in their order: text in runs, a wide table in a row of its own, a named block in its
   place. A rule moves a block or sets blocks side by side: it never drops or rewrites one, but
   for the stance line and the two columns' opening words. */
(function () {
  'use strict';

  var P = FairbandPage;
  var read = Fairband.reportText.read;

  var NAME_MOST = 90; /* a name's line, at most, in characters */
  var COLUMNS_MOST = 4; /* a table's columns, at most, before it is wide */
  var CELL_MOST = 44; /* a cell's characters, at most, before its table is wide */
  var GROUPS_LEAST = 4; /* the groups named, at least, for the paragraphs to stand beside them */

  var SUMMARY = 'Summary';
  var FINANCIAL = 'Financial performance and health';
  var DEBATE = 'The bull case and the bear case';
  /* The headings whose named blocks stay in the text: the three above, whose rules are their
     own, and the six whose cards draw records. */
  var KEPT = [SUMMARY, FINANCIAL, DEBATE, 'The last earnings call', 'Valuation',
    'Price and multiples', 'Recent news', 'Risks and kill criteria', 'Key judgments'];

  /* The financial tables' groups in their order, and the lead words that name each: one that
     starts with "growth", "cash" or "return", or holds "solvency", "balance", "capital
     allocation" or "quality". */
  var GROUPS = ['growth', 'cash_flow', 'solvency', 'returns', 'capital_allocation', 'quality'];
  var LEADS = [/^growth/, /^cash/, /solvency|balance/, /^return/, /capital allocation/, /quality/];

  /* The two columns' labels, and the opening words each takes off a paragraph's start: the
     words, in bold or not, then a colon or a full stop, and the space after them. */
  var SIDES = [
    { label: 'The bull case', opening: /^\s*(\*\*)?the bull case\b[:.]?(\*\*)?[:.]?\s*/i },
    { label: 'The bear case', opening: /^\s*(\*\*)?the bear case\b[:.]?(\*\*)?[:.]?\s*/i }
  ];

  /* The pieces' text: a text as it is, `**` left out; a cite as its own text. */
  function plain(pieces) {
    return (pieces || []).map(function (piece) {
      if (typeof piece === 'string') return piece.split('**').join('');
      return piece && piece.cite != null ? String(piece.cite) : '';
    }).join('');
  }

  /* A paragraph's name, where it can name the block after it: its pieces without the colon,
     from a paragraph of one line, 90 characters or fewer, whose text ends in a colon; null
     otherwise, and where the colon ends a cite's text. */
  function nameOf(block) {
    if (block.kind !== 'p' || block.items.length !== 1) return null;
    var line = block.items[0];
    var text = plain(line).trim();
    var end = line[line.length - 1];
    if (text.length > NAME_MOST || text.charAt(text.length - 1) !== ':') return null;
    if (typeof end !== 'string' || !/:[*\s]*$/.test(end)) return null;
    var rest = end.replace(/:([*\s]*)$/, function (colon, after) {
      return after.replace(/\s+/g, '');
    });
    return line.slice(0, -1).concat(rest ? [rest] : []);
  }

  /* The blocks with each named block made: a paragraph that names the list or the table
     directly after it becomes { kind: 'named', name, body } with that block. */
  function named(blocks) {
    var out = [];
    for (var i = 0; i < blocks.length; i++) {
      var name = nameOf(blocks[i]);
      var next = blocks[i + 1];
      if (name && next && ['ul', 'ol', 'table'].indexOf(next.kind) >= 0) {
        out.push({ kind: 'named', name: name, body: next });
        i += 1;
      } else {
        out.push(blocks[i]);
      }
    }
    return out;
  }

  /* The table a block is or names; null for any other block. */
  function tableOf(block) {
    var found = block && block.kind === 'named' ? block.body : block;
    return found && found.kind === 'table' ? found : null;
  }

  /* Whether the block is a table, bare or named, with a cell above 44 characters, its head's
     cells among them. */
  function isLong(block) {
    var table = tableOf(block);
    return Boolean(table) && table.head.concat(table.items).some(function (row) {
      return row.some(function (cell) { return plain(cell).trim().length > CELL_MOST; });
    });
  }

  /* Whether the block is a wide table, bare or named: more than four columns in a row, or a
     cell above 44 characters. */
  function isWide(block) {
    var table = tableOf(block);
    return Boolean(table) && (isLong(table) || table.head.concat(table.items).some(function (row) {
      return row.length > COLUMNS_MOST;
    }));
  }

  /* The group a paragraph's lead word names, read without its full stop and without regard to
     case, the first of GROUPS whose word it is; null for none. */
  function group(lead) {
    if (typeof lead !== 'string') return null;
    var word = lead.trim().replace(/\.$/, '').toLowerCase();
    for (var i = 0; i < GROUPS.length; i++) {
      if (LEADS[i].test(word)) return GROUPS[i];
    }
    return null;
  }

  /* A paragraph's lead word: the bold text at its start, a cite in it by its own text; null for
     a paragraph that opens with none, and for any other block. */
  function leadOf(block) {
    if (block.kind !== 'p') return null;
    var text = block.items[0].map(function (piece) {
      return typeof piece === 'string' ? piece : plain([piece]);
    }).join('');
    var found = /^\s*\*\*(.+?)\*\*/.exec(text);
    return found ? found[1] : null;
  }

  /* The blocks in their order: text in runs, a wide table, bare or named, in a row of its own. */
  function flow(blocks) {
    var rows = [];
    var run = null;
    blocks.forEach(function (block) {
      if (isWide(block)) {
        rows.push({ kind: 'wide', block: block });
        run = null;
        return;
      }
      if (!run) {
        run = { kind: 'run', blocks: [] };
        rows.push(run);
      }
      run.blocks.push(block);
    });
    return rows;
  }

  /* The blocks without the Summary's stance line: the first paragraph's first line where its
     text is exactly `Stance: <stance>.`, the paragraph's other lines staying. */
  function withoutStance(blocks, stance) {
    var first = blocks[0];
    var line = first && first.kind === 'p' ? plain(first.items[0]).trim() : null;
    if (line !== 'Stance: ' + stance + '.') return blocks;
    var rest = first.items.slice(1);
    return (rest.length ? [{ kind: 'p', items: rest }] : []).concat(blocks.slice(1));
  }

  function isNamedList(block) {
    return block.kind === 'named' && (block.body.kind === 'ul' || block.body.kind === 'ol');
  }

  /* Rule 1: each two or more named lists in a row in one columns row, the blocks between in
     their order. */
  function summary(blocks) {
    var rows = [];
    var loose = [];
    var i = 0;
    while (i < blocks.length) {
      var end = i;
      while (end < blocks.length && isNamedList(blocks[end])) end += 1;
      if (end - i >= 2) {
        rows = rows.concat(flow(loose), [{ kind: 'columns', blocks: blocks.slice(i, end) }]);
        loose = [];
        i = end;
      } else {
        loose.push(blocks[i]);
        i += 1;
      }
    }
    return rows.concat(flow(loose));
  }

  /* Rule 3: each paragraph that names a group first beside its charts, the other blocks in their
     order between; then the groups no paragraph names. Fewer than four groups named: every
     chart first, then the blocks. */
  function financial(blocks) {
    var used = [];
    var keys = blocks.map(function (block) {
      var key = group(leadOf(block));
      if (key === null || used.indexOf(key) >= 0) return null;
      used.push(key);
      return key;
    });
    if (used.length < GROUPS_LEAST) {
      return [{ kind: 'groups', groups: GROUPS.slice() }].concat(flow(blocks));
    }
    var rows = [];
    var loose = [];
    blocks.forEach(function (block, i) {
      if (keys[i] === null) {
        loose.push(block);
        return;
      }
      rows = rows.concat(flow(loose), [{ kind: 'pair', group: keys[i], block: block }]);
      loose = [];
    });
    var rest = GROUPS.filter(function (key) { return used.indexOf(key) < 0; });
    return rows.concat(flow(loose), rest.length ? [{ kind: 'groups', groups: rest }] : []);
  }

  /* A paragraph as a column: { label, block } where it opens with one side's words, the words
     off; null otherwise. The bold the words opened or closed alone stays, so the paragraph's
     bold keeps its pairs; the first letter after the words is upper case. */
  function sideOf(block) {
    if (block.kind !== 'p' || typeof block.items[0][0] !== 'string') return null;
    var text = block.items[0][0];
    var side = SIDES.filter(function (s) { return s.opening.test(text); })[0];
    if (!side) return null;
    var words = side.opening.exec(text);
    var rest = (Boolean(words[1]) !== Boolean(words[2]) ? '**' : '') + text.slice(words[0].length);
    var first = (rest ? [rest] : []).concat(block.items[0].slice(1));
    var lines = (first.length ? [first] : []).concat(block.items.slice(1));
    if (lines.length && typeof lines[0][0] === 'string') {
      lines[0] = [lines[0][0].replace(/^([*\s]*)(.)/, function (all, marks, letter) {
        return marks + letter.toUpperCase();
      })].concat(lines[0].slice(1));
    }
    return { label: side.label, block: { kind: 'p', items: lines } };
  }

  /* Rule 5: exactly two paragraphs, one a side each, in two columns in their order. */
  function debate(blocks) {
    var sides = blocks.length === 2 ? blocks.map(sideOf) : [];
    if (sides.length !== 2 || !sides[0] || !sides[1] || sides[0].label === sides[1].label) {
      return flow(blocks);
    }
    return [{ kind: 'sides', sides: sides }];
  }

  function isCard(block) { return block.kind === 'named' && !isWide(block); }

  /* Rule 2: the named lists and the named tables that are not wide as cards, the other blocks
     in their order; all of them in their order where no text would stay beside the cards. */
  function beside(blocks) {
    var cards = blocks.filter(isCard);
    var kept = blocks.filter(function (block) { return !isCard(block); });
    var text = kept.some(function (block) { return !isWide(block); });
    if (!cards.length || !text) return { rows: flow(blocks), cards: [] };
    return { rows: flow(kept), cards: cards };
  }

  /* The section's rows and cards (the head comment), its parts read by the design system's
     reader, its named blocks made, under `heading` and the report's `stance`. */
  function lay(heading, parts, stance) {
    var blocks = named(read(parts));
    if (heading === SUMMARY) return { rows: summary(withoutStance(blocks, stance)), cards: [] };
    if (heading === FINANCIAL) return { rows: financial(blocks), cards: [] };
    if (heading === DEBATE) return { rows: debate(blocks), cards: [] };
    if (KEPT.indexOf(heading) >= 0) return { rows: flow(blocks), cards: [] };
    return beside(blocks);
  }

  P.researchText = {
    plain: plain,
    named: named,
    isWide: isWide,
    isLong: isLong,
    GROUPS: GROUPS,
    group: group,
    lay: lay
  };
})();
