/* The watchlist page's head (spec 2026-11-22 7.3 and 7.4), loaded after controls.js. The page
   shows one list: the Screen's own table and drawer (app.js) draw its companies in the Screen's
   panel under this one, with a FIND, filters and a sort of their own, and this script draws the
   head above them and names the list they draw (FairbandPage.selectList). The head is one row
   that wraps: a selector of the lists by name, the default list's entry marked, the list's count
   and the day it was made, Set as default (Default on the default list, where a second press
   clears it), Rename and Delete, then the New watchlist field and Create; under it the Add a
   company field, which matches the screen's rows as FIND does and lists up to eight. The page
   opens on the list the address names (#watchlists/<id>, FairbandPage.listId), else the
   default, which the browser keeps, else the first by name; the address follows the list shown,
   replaced, so the browser's Back does not step through the lists. With no list, the head is
   the New watchlist field, Create and a sentence. Every write goes through FairbandPage.api;
   after it the rows and the lists load again, the screen's marks follow, and the head draws
   again with them. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  /* A symbol as the server takes one; a text no row matches is added as typed when it is one. */
  var SYMBOL = /^[A-Za-z0-9.-]{1,10}$/;
  /* A refused write's first words, by its method. */
  var REFUSED = {
    POST: 'Not created', PATCH: 'Not renamed', DELETE: 'Not deleted', PUT: 'Not added'
  };
  /* Where the browser keeps the default list's id (spec 2026-11-22 7.3). */
  var DEFAULT_KEY = 'fairband.watchlist.default';
  /* A refused write's sentence, with the server's reason; null for a write it took. */
  var refusal = P.refusal;

  var panel = document.getElementById('watchlists');
  var root = ReactDOM.createRoot(panel);
  var state = {
    name: '', /* the New watchlist field */
    adding: {}, /* each list's Add a company field, by list id */
    renaming: null, /* { id, name } while the selector is the list's name field */
    deleting: null, /* { id, name, count } while Delete's dialog is open */
    pending: null, /* { method, id }: the write in flight; no other starts until it ends */
    errors: {}, /* a refused write's sentence, by list id, or under 'new' for Create */
    selected: null, /* the id of the list the page shows; null before the lists arrive, or none */
    next: null, /* the id of a list just created, shown once the lists hold it */
    defaultId: readDefault(), /* the default list's id, or null for none */
    focus: null /* a selector in the view that takes focus once the view has drawn */
  };

  /* ---------------------------------------------------------------- the default */

  /* The default list's id as the browser keeps it, read once as the page loads; a stored value
     that is no whole number, and a browser with no storage, read as none. */
  function readDefault() {
    try {
      var stored = window.localStorage.getItem(DEFAULT_KEY);
      return /^\d+$/.test(String(stored)) ? Number(stored) : null;
    } catch (e) {
      return null;
    }
  }

  /* The default list: `id`, kept in the browser, or none, its key removed. Without storage the
     default holds until the page reloads (spec 2026-11-22 7.3). */
  function setDefault(id) {
    state.defaultId = id;
    try {
      if (id == null) window.localStorage.removeItem(DEFAULT_KEY);
      else window.localStorage.setItem(DEFAULT_KEY, String(id));
    } catch (e) { /* no storage: the default lasts until the page reloads */ }
  }

  /* ------------------------------------------------------------- the list shown */

  /* The list the page opens on (spec 2026-11-22 7.3): the one `addressId` names, else the one
     `defaultId` names, else the first, the lists coming by name; an id that names no list counts
     as none. Null with no list. */
  function opens(lists, addressId, defaultId) {
    var ids = lists.map(function (w) { return w.id; });
    if (ids.indexOf(addressId) !== -1) return addressId;
    if (ids.indexOf(defaultId) !== -1) return defaultId;
    return lists.length ? lists[0].id : null;
  }

  /* The list `id` shows, or none: the address names it, replaced as a change of the company
     page's tab is, and the table draws it. */
  function select(id) {
    state.selected = id;
    P.listId = id;
    history.replaceState(null, '', '#watchlists' + (id == null ? '' : '/' + id));
    P.selectList(id);
  }

  /* After each draw of the screen while the page shows (P.onRender), and as it opens: once the
     lists are in, the list shown is the one selected while the lists hold it, a list just created
     once they hold it, else the one the page opens on (opens); the address and the table follow
     it where either differs. An address the page did not write (controls.js keeps it as the
     hash changes, P.listId) forgets the selection first: the table's turn to the list draws, and
     so runs this, before the view's loader forgets it, and a selection kept from the last visit
     would otherwise outrank the address. Before the lists arrive nothing is chosen and no address
     written, so a reload at #watchlists/<id> waits for them. The table draws again as it
     follows, which calls this again; that call finds nothing to change, so the loop ends
     there. */
  function follow() {
    if (panel.hidden) return;
    var lists = P.watchlists();
    if (lists) {
      var ids = lists.map(function (w) { return w.id; });
      if (P.listId !== state.selected) state.selected = null;
      var want = state.selected;
      if (state.next != null && ids.indexOf(state.next) !== -1) {
        want = state.next;
        state.next = null;
      } else if (ids.indexOf(want) === -1) {
        want = opens(lists, P.listId, state.defaultId);
      }
      if (want !== state.selected || want !== P.listId) select(want);
    }
    render();
  }

  /* ------------------------------------------------------------------ the writes */

  /* One write at a time, so a second press never makes a second write; Delete's dialog reads
     confirming meanwhile. A write clears the sentences of the writes before it, and a refused
     write's own sentence stands under the head, led by the write's first words. Then the write's
     own last step runs, given the sentence (null when the server took it) and the answer's body;
     the rows and the lists load again, so the screen's marks follow; and the view draws. */
  function write(made, call, after) {
    if (state.pending) return;
    var where = made.id == null ? 'new' : made.id;
    var head = REFUSED[made.method];
    state.pending = made;
    state.errors = {};
    render();
    var answer = null;
    call().then(function (r) {
      answer = r.body;
      return refusal(head, r);
    }).catch(function (err) {
      return head + ': ' + err.message + '.';
    }).then(function (error) {
      state.pending = null;
      if (error) state.errors[where] = error;
      after(error, answer);
      P.reload();
      return P.reloadWatchlists();
    }).then(render);
  }

  /* Create: the page shows the new list once the lists hold it (follow), and its Add a company
     field takes focus then, ready for its first company. */
  function create() {
    var name = state.name.trim();
    if (!name) return;
    write({ method: 'POST', id: null }, function () {
      return P.api.post('/api/watchlists', { name: name });
    }, function (error, list) {
      if (error) return;
      state.name = '';
      state.next = list.id;
      state.focus = '.app-wl__q';
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

  /* The name's field closes, the selector back in its place, and focus goes back to Rename. */
  function stopRenaming(id) {
    state.renaming = null;
    delete state.errors[id];
    state.focus = '.app-wl__rename';
    render();
  }

  /* Confirm in Delete's dialog: the dialog closes as the write ends, taken or refused. A list
     deleted leaves the page on the default list, or the first by name (follow), and, when it was
     the default, the default goes with it. */
  function drop(d) {
    write({ method: 'DELETE', id: d.id }, function () {
      return P.api.del('/api/watchlists/' + d.id);
    }, function (error) {
      state.deleting = null;
      state.focus = error ? '.app-wl__delete' : '#app-wl-new';
      if (!error && d.id === state.defaultId) setDefault(null);
    });
  }

  function cancelDelete() {
    if (!state.deleting) return;
    state.deleting = null;
    state.focus = '.app-wl__delete';
    render();
  }

  /* A company onto a list; its Add a company field empties and keeps focus. */
  function add(id, symbol) {
    write({ method: 'PUT', id: id }, function () {
      return P.api.put('/api/watchlists/' + id + '/symbols/' + encodeURIComponent(symbol));
    }, function (error) {
      if (!error) state.adding[id] = '';
      state.focus = '.app-wl__q';
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

  /* The field under the head, its matches under it as buttons: the first eight not on the list
     already. A match's button adds it. Enter adds only a company the reader chose: the row whose
     ticker the text spells, ignoring case, unless it is on the list already; else the one match
     shown; else, when no row matches, the text upper-cased if it is a symbol. Enter never adds
     the first of several. A line under the field says why Enter adds nothing, or what it adds
     when no match shows. */
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

  function count(n) {
    return Number(n).toLocaleString('en-US') + (n === 1 ? ' company' : ' companies');
  }

  /* The head of `list`, one of `lists`, `defaultId` the default's: the selector, the lists in
     their order, the default's entry ending (default), or while renaming the name's field in its
     place, Enter saving and Escape cancelling; the list's count and the day it was made, in the
     reader's time; Set as default, which reads Default, pressed, on the default list, where a
     press clears the default; Rename and Delete. A choice in the selector shows that list. */
  function head(list, lists, defaultId) {
    var renaming = state.renaming && state.renaming.id === list.id;
    var made = P.localIso(list.createdAt);
    var isDefault = list.id === defaultId;
    var name = renaming ? h('form', {
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
      })) : h('select', {
        className: 'control app-select app-wl__pick', 'aria-label': 'Watchlist',
        value: String(list.id),
        onChange: function (event) {
          select(Number(event.target.value));
          render();
        }
      }, lists.map(function (w) {
        return h('option', { key: w.id, value: String(w.id) },
          w.name + (w.id === defaultId ? ' (default)' : ''));
      }));
    return h('div', { className: 'app-wl__head' },
      name,
      h('p', { className: 'caption app-wl__meta' }, count(list.count), ' · created ',
        h('time', { dateTime: made, title: made }, F.formatDate(made.slice(0, 10)))),
      h('div', { className: 'app-wl__actions' },
        h(F.Button, {
          size: 'sm', className: 'app-wl__default', 'aria-pressed': isDefault ? 'true' : 'false',
          onClick: function () {
            setDefault(isDefault ? null : list.id);
            render();
          }
        }, isDefault ? 'Default' : 'Set as default'),
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

  /* The head's row, the selected list's head then New watchlist and Create; a refused write's
     sentence under it; then the list's Add a company, or, with no list, the sentence that says
     how to make one. Nothing of the list draws before the lists arrive. */
  function View() {
    /* Focus moves where the last change asked, once the view has drawn it; after Create, once
       the new list shows. */
    React.useEffect(function () {
      if (!state.focus || state.next != null) return;
      var el = panel.querySelector(state.focus);
      state.focus = null;
      if (el) el.focus();
    });
    var lists = P.watchlists();
    var list = (lists || []).filter(function (w) { return w.id === state.selected; })[0];
    var error = state.errors.new || (list ? state.errors[list.id] : null);
    return h('div', { className: 'app-lists' },
      h('div', { className: 'app-lists__row' },
        list ? head(list, lists, state.defaultId) : null,
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
          h(F.Button, { type: 'submit', size: 'sm', disabled: !state.name.trim() }, 'Create'))),
      error ? h('p', { className: 'caption app-wl__error' }, error) : null,
      lists && lists.length === 0 ? h('p', { className: 'body app-note app-lists__empty' },
        'No watchlists yet. Create one here, or press the mark beside a ticker on the screen.')
        : null,
      list ? addField(list) : null,
      state.deleting ? dialog(state.deleting) : null);
  }

  function render() { root.render(h(View)); }

  /* The page opens on the list its address names, or the default: the selection is forgotten,
     so the header's Watchlists link, #watchlists, opens the default. After each draw of the
     screen while it shows it follows the lists as they load and as the popup changes them. The
     opening list and the head are here for the tests. */
  P.onShow.watchlists = function () {
    state.selected = null;
    follow();
  };
  P.onRender = follow;
  P.lists = { opens: opens, head: head };
})();
