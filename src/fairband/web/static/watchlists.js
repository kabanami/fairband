/* The Watchlists view (spec 2026-11-04 9.6), loaded after controls.js. Above the lists, the New
   watchlist field and Create. Each list is a section: its name, its count and the day it was
   made, Request research (spec 2026-11-06 Tier 2, 18.6), Rename and Delete; under them the Add a
   company field, which matches the screen's rows as FIND does and lists up to eight, then the
   list's companies as a ScreenTable of the screen's rows under the screen's columns. A company's
   mark opens the screen's popup, so a company leaves a list when its box there is unchecked; its
   ticker, a link, opens its company page (spec 2026-11-16 company page, 12); the rest of a row
   opens the drawer on the Screen view. Every write goes through FairbandPage.api; after it the
   rows and the lists load again, the screen's marks follow, and the view draws again with
   them. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  /* A symbol as the server takes one; a text no row matches is added as typed when it is one. */
  var SYMBOL = /^[A-Za-z0-9.-]{1,10}$/;
  /* A refused write's first words, by its method, unless the write names its own. */
  var REFUSED = {
    POST: 'Not created', PATCH: 'Not renamed', DELETE: 'Not deleted', PUT: 'Not added'
  };
  /* A refused write's sentence, with the server's reason; null for a write it took. */
  var refusal = P.refusal;

  var panel = document.getElementById('watchlists');
  var root = ReactDOM.createRoot(panel);
  var state = {
    name: '', /* the New watchlist field */
    adding: {}, /* each list's Add a company field, by list id */
    renaming: null, /* { id, name } while a list's name is a field */
    deleting: null, /* { id, name, count } while Delete's dialog is open */
    pending: null, /* { method, id, head? }: the write in flight; no other starts until it ends */
    errors: {}, /* a refused write's sentence, by list id, or under 'new' for Create */
    requested: {}, /* a Request research run's counts, { posted, open }, by list id */
    focus: null /* a selector in the view that takes focus once the view has drawn */
  };

  /* ------------------------------------------------------------------ the writes */

  /* One write at a time, so a second press never makes a second write; Delete's dialog reads
     confirming meanwhile. A write clears the sentences of the writes before it, Request
     research's counts among them, and a refused write's own sentence stands where the write was
     made, led by the write's own head when it names one (read as the write ends, so a run of
     posts names the company it stopped at). Then the write's own last step runs, given the
     sentence (null when the server took it) and the answer's body; the rows and the lists load
     again, so the screen's marks follow; and the view draws. */
  function write(made, call, after) {
    if (state.pending) return;
    var where = made.id == null ? 'new' : made.id;
    state.pending = made;
    state.errors = {};
    state.requested = {};
    render();
    var answer = null;
    call().then(function (r) {
      answer = r.body;
      return refusal(made.head || REFUSED[made.method], r);
    }).catch(function (err) {
      return (made.head || REFUSED[made.method]) + ': ' + err.message + '.';
    }).then(function (error) {
      state.pending = null;
      if (error) state.errors[where] = error;
      after(error, answer);
      P.reload();
      return P.reloadWatchlists();
    }).then(render);
  }

  /* Create: the new list's Add a company field takes focus, ready for its first company. */
  function create() {
    var name = state.name.trim();
    if (!name) return;
    write({ method: 'POST', id: null }, function () {
      return P.api.post('/api/watchlists', { name: name });
    }, function (error, list) {
      if (error) return;
      state.name = '';
      state.focus = inList(list.id, '.app-wl__q');
    });
  }

  /* Enter in the name's field: an unchanged name closes the field without a write. */
  function rename(list) {
    var id = list.id;
    var name = state.renaming.name.trim();
    if (!name) return;
    if (name === list.name) {
      stopRenaming(id);
      return;
    }
    write({ method: 'PATCH', id: id }, function () {
      return P.api.patch('/api/watchlists/' + id, { name: name });
    }, function (error) {
      if (!error) stopRenaming(id);
    });
  }

  function stopRenaming(id) {
    state.renaming = null;
    delete state.errors[id];
    state.focus = inList(id, '.app-wl__rename');
    render();
  }

  /* Confirm in Delete's dialog: the dialog closes as the write ends, taken or refused. */
  function drop(d) {
    write({ method: 'DELETE', id: d.id }, function () {
      return P.api.del('/api/watchlists/' + d.id);
    }, function (error) {
      state.deleting = null;
      state.focus = error ? inList(d.id, '.app-wl__delete') : '#app-wl-new';
    });
  }

  function cancelDelete() {
    if (!state.deleting) return;
    var id = state.deleting.id;
    state.deleting = null;
    state.focus = inList(id, '.app-wl__delete');
    render();
  }

  /* A company onto a list; its Add a company field empties and keeps focus. */
  function add(id, symbol) {
    write({ method: 'PUT', id: id }, function () {
      return P.api.put('/api/watchlists/' + id + '/symbols/' + encodeURIComponent(symbol));
    }, function (error) {
      if (!error) state.adding[id] = '';
      state.focus = inList(id, '.app-wl__q');
    });
  }

  /* Request research (spec 2026-11-06 Tier 2, 18.6): a valuation review posted for each company
     on the list in turn, one post at a time, as the owner. A 201 counts as posted, and a 409, an
     item already open for the company, as already open; any other answer, a 400 or a 5xx, stops
     the run, and its sentence, the server's, stands under the head, led by the company it stopped
     at. The meta line counts as the run goes; the header's Inbox count follows on its next read.
     As it ends, the drawer, if it shows a company on the list, reads it again, so its Request
     research follows, and focus goes back to the button. */
  function requestResearch(list) {
    var tally = { posted: 0, open: 0 };
    var made = { method: 'POST', id: list.id, head: 'Not posted' };
    write(made, function () {
      state.requested[list.id] = tally;
      return list.symbols.reduce(function (run, entry) {
        return run.then(function (last) {
          if (last && !last.ok) return last;
          made.head = 'Not posted for ' + entry.symbol;
          return P.api.post('/api/inbox', { symbol: entry.symbol, mode: 'valuation review' })
            .then(function (r) {
              if (r.status === 409) tally.open++;
              else if (r.ok) tally.posted++;
              else return r;
              render();
              return { ok: true };
            });
        });
      }, Promise.resolve({ ok: true }));
    }, function () {
      list.symbols.forEach(function (entry) { P.reloadDetail(entry.symbol); });
      state.focus = inList(list.id, '.app-wl__request');
    });
  }

  /* --------------------------------------------------------- Add a company */

  /* The screen's rows the text matches as FIND does, the ticker by its start and the name
     anywhere: the ticker the text spells first, then the tickers it starts, then the names it is
     in, each in the screen's order. */
  function found(text) {
    var needle = text.trim().toLowerCase();
    if (!needle) return [];
    var ranked = [[], [], []];
    (P.rows() || []).forEach(function (r) {
      var ticker = r.ticker.toLowerCase();
      if (ticker === needle) ranked[0].push(r);
      else if (ticker.indexOf(needle) === 0) ranked[1].push(r);
      else if ((r.name || '').toLowerCase().indexOf(needle) !== -1) ranked[2].push(r);
    });
    return ranked[0].concat(ranked[1], ranked[2]);
  }

  /* The field under a list's head, its matches under it as buttons: the first eight not on the
     list already. A match's button adds it. Enter adds only a company the reader chose: the row
     whose ticker the text spells, ignoring case, unless it is on the list already; else the one
     match shown; else, when no row matches, the text upper-cased if it is a symbol. Enter never
     adds the first of several. A line under the field says why Enter adds nothing, or what it
     adds when no match shows. */
  function addField(list) {
    var text = state.adding[list.id] || '';
    var on = {};
    list.symbols.forEach(function (s) { on[s.symbol] = true; });
    var all = found(text);
    var shown = all.filter(function (r) { return !on[r.ticker]; }).slice(0, 8);
    var typed = text.trim().toUpperCase();
    var exact = null;
    all.forEach(function (r) {
      if (r.ticker.toUpperCase() === typed) exact = r;
    });
    var asTyped = text.trim() && all.length === 0 && SYMBOL.test(typed) ? typed : null;
    var onEnter = null;
    if (exact) onEnter = on[exact.ticker] ? null : exact.ticker;
    else if (shown.length === 1) onEnter = shown[0].ticker;
    else if (asTyped) onEnter = asTyped;
    var hint = null;
    if (text.trim()) {
      if (exact && !onEnter) hint = exact.ticker + ' is on this list.';
      else if (!all.length) {
        hint = asTyped ? 'No company on the screen matches. Enter adds ' + asTyped + '.'
          : 'No company on the screen matches, and the text is not a symbol.';
      } else if (!shown.length) hint = 'Every company that matches is on this list.';
      else if (!onEnter) hint = 'Choose a company below, or type its full ticker.';
    }
    function set(value) {
      state.adding[list.id] = value;
      render();
    }
    return h('div', { className: 'app-wl__add' },
      h('form', {
        onSubmit: function (event) {
          event.preventDefault();
          if (onEnter) add(list.id, onEnter);
        }
      },
        h('input', {
          type: 'text', className: 'control app-field app-wl__q', placeholder: 'Add a company',
          'aria-label': 'Add a company to ' + list.name, maxLength: 60, value: text,
          onChange: function (event) { set(event.target.value); },
          onKeyDown: function (event) {
            if (event.key === 'Escape' && text) set('');
          }
        })),
      shown.length ? h('ul', { className: 'app-wl__matches' }, shown.map(function (r) {
        return h('li', { key: r.ticker },
          h('button', {
            type: 'button', className: 'app-wl__match control',
            onClick: function () { add(list.id, r.ticker); }
          },
            h('span', { className: 'ticker' }, r.ticker),
            h('span', { className: 'app-wl__matchname' }, r.name)));
      })) : null,
      hint ? h('p', { className: 'caption app-muted app-wl__hint' }, hint) : null);
  }

  /* ------------------------------------------------------------------ the view */

  /* A selector for an element of a list's section. */
  function inList(id, selector) { return '[data-list="' + id + '"] ' + selector; }

  /* A list's rows: the screen's loaded rows joined by symbol, in the list's order, each watched;
     a symbol with no row (it left the universe, or has no snapshot yet) is its ticker alone, an
     em dash in every other cell. */
  function rowsOf(list, bySymbol) {
    return list.symbols.map(function (entry) {
      var symbol = entry.symbol;
      var row = bySymbol[symbol];
      return row ? Object.assign({}, row, { watched: true })
        : { ticker: symbol, name: null, price: null, mechanical: null, reviewed: null,
          phase: null, fairLow: null, fairHigh: null, watched: true };
    });
  }

  function count(n) {
    return Number(n).toLocaleString('en-US') + (n === 1 ? ' company' : ' companies');
  }

  /* What a Request research run came to, or has come to so far, for the meta line after the day
     the list was made: posted 3 requests · 2 already open; null before a run. */
  function requested(tally) {
    if (!tally) return null;
    return 'posted ' + tally.posted + (tally.posted === 1 ? ' request' : ' requests') +
      (tally.open ? ' · ' + tally.open + ' already open' : '');
  }

  /* The list's head: its name, or the name's field while renaming, Enter saving and Escape
     cancelling; its count and the day it was made, in the reader's time, then what a Request
     research run came to; Request research, disabled for a list with no company and while a write
     is in flight, Rename and Delete. */
  function head(list) {
    var renaming = state.renaming && state.renaming.id === list.id;
    var made = P.localIso(list.createdAt);
    var outcome = requested(state.requested[list.id]);
    var title = renaming ? h('form', {
      className: 'app-wl__rename-form',
      onSubmit: function (event) { event.preventDefault(); rename(list); }
    },
      h('input', {
        type: 'text', className: 'control app-field app-wl__name', autoFocus: true,
        'aria-label': 'New name for ' + list.name, maxLength: 60, value: state.renaming.name,
        onChange: function (event) {
          state.renaming.name = event.target.value;
          render();
        },
        onKeyDown: function (event) {
          if (event.key === 'Escape') stopRenaming(list.id);
        }
      })) : h('h2', { className: 'title app-wl__title' }, list.name);
    return h('div', { className: 'app-wl__head' },
      title,
      h('p', { className: 'caption app-wl__meta' }, count(list.count), ' · created ',
        h('time', { dateTime: made, title: made }, F.formatDate(made.slice(0, 10))),
        outcome ? ' · ' + outcome : null),
      h('div', { className: 'app-wl__actions' },
        h(F.Button, {
          size: 'sm', className: 'app-wl__request',
          disabled: list.count === 0 || state.pending !== null,
          onClick: function () { requestResearch(list); }
        }, 'Request research'),
        h(F.Button, {
          size: 'sm', className: 'app-wl__rename',
          onClick: function () {
            state.renaming = { id: list.id, name: list.name };
            render();
          }
        }, 'Rename'),
        h(F.Button, {
          variant: 'danger', size: 'sm', className: 'app-wl__delete',
          onClick: function () {
            state.deleting = { id: list.id, name: list.name, count: list.count };
            state.focus = '.app-dialog .fb-btn--quiet';
            render();
          }
        }, 'Delete')));
  }

  /* A list's section. Its table waits for the screen's rows; a list with no company says so. */
  function section(list, bySymbol) {
    var error = state.errors[list.id];
    var table = null;
    if (list.count === 0) {
      table = h('p', { className: 'caption app-muted app-wl__none' },
        'No companies on this list yet.');
    } else if (bySymbol) {
      table = h('div', { className: 'app-wl__table' }, h(F.ScreenTable, {
        rows: rowsOf(list, bySymbol),
        columns: P.columns(),
        chooser: false, dense: true,
        onOpen: function (row) { P.openRow(row.ticker); },
        onWatch: P.watch,
        companyHref: P.companyHref,
        watchlists: P.watchlists() || []
      }));
    }
    return h('section', { key: list.id, className: 'app-wl', 'data-list': list.id },
      head(list),
      error ? h('p', { className: 'caption app-wl__error' }, error) : null,
      addField(list),
      table);
  }

  /* Delete's dialog, over the page: the payload is the list's name and its count. Its one
     affirmative button, Confirm, deletes, so it is the danger one; there is no revision to bind
     to and no Reject. Escape, a press beside it and Cancel close it. */
  function dialog(d) {
    return h('div', {
      className: 'app-dialog',
      onPointerDown: function (event) {
        if (event.target === event.currentTarget && !state.pending) cancelDelete();
      },
      onKeyDown: function (event) {
        if (event.key === 'Escape' && !state.pending) cancelDelete();
      }
    },
      h(F.ConfirmDialog, {
        title: 'Delete ' + d.name,
        payload: { name: d.name, companies: d.count },
        state: state.pending ? 'confirming' : 'open',
        confirmVariant: 'danger',
        onConfirm: function () { drop(d); },
        onCancel: cancelDelete
      }));
  }

  function View() {
    /* Focus moves where the last change asked, once the view has drawn. */
    React.useEffect(function () {
      if (!state.focus) return;
      var el = panel.querySelector(state.focus);
      state.focus = null;
      if (el) el.focus();
    });
    var lists = P.watchlists();
    var rows = P.rows();
    var bySymbol = null;
    if (rows) {
      bySymbol = {};
      rows.forEach(function (r) { bySymbol[r.ticker] = r; });
    }
    var error = state.errors.new;
    return h('div', { className: 'app-lists' },
      h('form', {
        className: 'app-lists__new',
        onSubmit: function (event) { event.preventDefault(); create(); }
      },
        h('input', {
          id: 'app-wl-new', type: 'text', className: 'control app-field',
          placeholder: 'New watchlist', 'aria-label': 'New watchlist', maxLength: 60,
          value: state.name,
          onChange: function (event) {
            state.name = event.target.value;
            render();
          }
        }),
        h(F.Button, { type: 'submit', disabled: !state.name.trim() }, 'Create')),
      error ? h('p', { className: 'caption app-wl__error' }, error) : null,
      lists && lists.length === 0 ? h('p', { className: 'body app-note app-lists__empty' },
        'No watchlists yet. Create one here, or press the mark beside a ticker on the screen.')
        : null,
      (lists || []).map(function (list) { return section(list, bySymbol); }),
      state.deleting ? dialog(state.deleting) : null);
  }

  function render() { root.render(h(View)); }

  /* The view draws as it opens, and again after each draw of the screen while it is open, so it
     follows the rows and the lists as they load and as the popup changes them. */
  P.onShow.watchlists = render;
  P.onRender = function () { if (!panel.hidden) render(); };
})();
