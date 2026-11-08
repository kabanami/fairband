/* The Inbox view (spec 2026-11-06 Tier 2, 18.5), loaded after watchlists.js: the work items as
   the server lists them, newest first, in one table. A row: the company's symbol, a link that
   opens its drawer on the Screen view as a watchlist's row does; the mode; the state word, a
   declined item's reason under it as written; the date and time it was posted, in the reader's
   time; who posted it, a compact PrincipalChip: the owner, an agent by its model identifier, or
   the system for the item it posts when a watched company's window ends; the agent that claimed
   it, likewise; the requester's note as written; for a done item, a link to the report page of
   the report it was completed with, named by its revision ("revision 2", its accessible name
   "Open revision 2 of the report for QCOM"), or Open when the server sends none; and for a
   pending or claimed item, Decline, which opens the reason line under the row: the reason field
   and Decline again, the owner's decline, and Cancel. A refused decline's sentence, the
   server's, stands on a line under its row. The view reads the inbox as it opens and after every
   write, each read running the expiry rule on the server, and hands each read to the header, so
   its count matches the table; while it shows, the header's own reads redraw the table too. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var HEADS = ['Symbol', 'Mode', 'State', 'Posted', 'By', 'Claimed by', 'Note', 'Report'];
  var OPEN = P.OPEN_STATES; /* the states an item is declined from */
  var refusal = P.refusal;

  var panel = document.getElementById('inbox');
  var root = ReactDOM.createRoot(panel);
  var state = {
    items: null, /* the items, newest first; null until the first read lands */
    loading: false,
    error: null, /* a failed read's sentence */
    declining: null, /* the item whose reason line is open; one at a time */
    reasons: {}, /* each item's reason field as typed, by item id, kept while the page lives */
    pending: null, /* the item whose decline is in flight; no other starts until it ends */
    errors: {}, /* a refused decline's sentence, by item id */
    focus: null /* selectors in the view, the first found taking focus once a read has landed */
  };
  var latest = 0;

  /* The inbox, read as the view opens and after every write. The items shown stay, faded, until
     the read lands, and the latest read wins; its items go to the header's count. */
  function load() {
    var request = ++latest;
    state.loading = true;
    render();
    return P.getJson('/api/inbox')
      .then(function (body) {
        if (request !== latest) return;
        state.items = body.items;
        state.loading = false;
        state.error = null;
        P.countInbox(body.items);
        render();
      })
      .catch(function (err) {
        if (request !== latest) return;
        state.loading = false;
        state.error = 'The work items did not load: ' + err.message +
          '. Reload the page to try again.';
        render();
      });
  }

  /* Decline: the owner's decline of an open item, with the reason as typed, its ends trimmed.
     One at a time, so a second press never sends a second decline. A decline clears the
     sentences of those before it. A taken one closes its own reason line, not another row's the
     owner opened meanwhile, and leaves focus on its row's symbol; a refused one's sentence stands
     under its row, the line and its reason kept for another try while the item is open, and focus
     goes back to the field once the read has landed, or to the row's symbol when the item is no
     longer open (declined elsewhere, say). Then the drawer, if it shows the company, reads it
     again, so its Request research follows, and the view reads the inbox again. */
  function decline(item) {
    var reason = (state.reasons[item.id] || '').trim();
    if (!reason || state.pending !== null) return;
    state.pending = item.id;
    state.errors = {};
    render();
    P.api.patch('/api/inbox/' + item.id, { action: 'decline', reason: reason })
      .then(function (r) {
        return refusal('Not declined', r);
      })
      .catch(function (err) {
        return 'Not declined: ' + err.message + '.';
      })
      .then(function (error) {
        state.pending = null;
        if (error) state.errors[item.id] = error;
        else {
          delete state.reasons[item.id];
          if (state.declining === item.id) state.declining = null;
        }
        state.focus = (error ? [inRow(item.id, '.app-inbox__reason')] : [])
          .concat([inRow(item.id, '.app-inbox__symbol')]);
        P.reloadDetail(item.symbol);
        return load();
      });
  }

  /* ------------------------------------------------------------------ the view */

  /* A selector for an element of an item's row. */
  function inRow(id, selector) { return '[data-item="' + id + '"] ' + selector; }

  function none() { return h('span', { className: 'app-muted' }, '—'); }

  /* The date and time an item was posted, in the reader's time ("8 Nov 2026, 17:56"), since two
     items on one day read the same by date alone (18.5, plan 4); P.when's element, the instant
     in datetime and the title. */
  function posted(iso) {
    return P.when(iso);
  }

  /* An item's row; under it, its reason line while that is open and the item still is, then the
     line with its refused decline's sentence when there is one. An open item's last cell is
     Decline, which opens the reason line and gives way to it. */
  function row(item) {
    var open = OPEN.indexOf(item.state) !== -1;
    var declining = open && state.declining === item.id;
    return h(React.Fragment, { key: item.id },
      h('tr', { 'data-item': item.id },
        h('td', null, h('a', {
          className: 'ticker app-link app-inbox__symbol', href: '#',
          onClick: function (event) { event.preventDefault(); P.openRow(item.symbol); }
        }, item.symbol)),
        h('td', { className: 'body' }, item.mode),
        h('td', { className: 'body app-inbox__wrap' }, item.state,
          item.state === 'declined' && item.reason
            ? h('span', { className: 'caption app-inbox__why' }, item.reason) : null),
        h('td', { className: 'figure fb-num' }, posted(item.postedAt)),
        h('td', null,
          h(F.PrincipalChip, { principal: item.postedBy, actor: item.postedActor, compact: true })),
        h('td', null, item.claimedBy
          ? h(F.PrincipalChip, { principal: 'agent', actor: item.claimedBy, compact: true })
          : none()),
        h('td', { className: 'body app-inbox__wrap' }, item.note || none()),
        h('td', null, item.state === 'done' && item.reportId != null ? h('a', {
          className: 'app-link',
          href: '#report/' + encodeURIComponent(item.symbol) + '/' + item.reportId,
          'aria-label': item.reportRevision != null
            ? 'Open revision ' + item.reportRevision + ' of the report for ' + item.symbol
            : 'Open the report for ' + item.symbol
        }, item.reportRevision != null ? 'revision ' + item.reportRevision : 'Open') : none()),
        h('td', null, open && !declining ? h(F.Button, {
          size: 'sm', className: 'app-inbox__decline',
          'aria-label': 'Decline the work item for ' + item.symbol,
          onClick: function () {
            state.declining = item.id;
            render();
          }
        }, 'Decline') : null)),
      declining ? reasonLine(item) : null,
      state.errors[item.id] ? refused(item) : null);
  }

  /* The reason line under an open item's row: the reason field, which takes focus as the line
     opens, Decline, which sends the owner's decline and waits for a reason and for the decline in
     flight, and Cancel. Enter in the field sends it; Escape or Cancel closes the line, the reason
     kept, and focus goes back to the row's Decline. */
  function reasonLine(item) {
    var reason = state.reasons[item.id] || '';
    function close() {
      state.declining = null;
      state.focus = [inRow(item.id, '.app-inbox__decline')];
      render();
    }
    return h('tr', { className: 'app-inbox__line', 'data-item': item.id },
      h('td', { colSpan: HEADS.length + 1 },
        h('form', {
          className: 'app-inbox__form',
          onSubmit: function (event) { event.preventDefault(); decline(item); }
        },
          h('input', {
            type: 'text', className: 'control app-field app-inbox__reason', autoFocus: true,
            placeholder: 'Reason', 'aria-label': 'Reason for declining ' + item.symbol,
            maxLength: 200, value: reason,
            onChange: function (event) {
              state.reasons[item.id] = event.target.value;
              render();
            },
            onKeyDown: function (event) {
              if (event.key === 'Escape') close();
            }
          }),
          h(F.Button, {
            type: 'submit', size: 'sm', disabled: !reason.trim() || state.pending !== null
          }, 'Decline'),
          h(F.Button, { variant: 'quiet', size: 'sm', onClick: close }, 'Cancel'))));
  }

  /* The line under a row whose decline the server refused: the sentence, as it arrived. */
  function refused(item) {
    return h('tr', { className: 'app-inbox__refused' },
      h('td', { colSpan: HEADS.length + 1, className: 'caption app-inbox__error' },
        state.errors[item.id]));
  }

  /* The table: the heads, the posted day's at the right as its dates are, then a last column
     with no head for Decline. It scrolls sideways on its own in a narrow window. */
  function table(items) {
    return h('div', { className: 'app-inbox__scroll' },
      h('table', { className: 'fb-table' },
        h('thead', null, h('tr', null,
          HEADS.map(function (head) {
            return h('th', {
              key: head, className: head === 'Posted' ? 'label fb-num' : 'label'
            }, head);
          }),
          h('th', { key: 'decline' }))),
        h('tbody', null, items.map(row))));
  }

  function View() {
    /* Focus moves where the last change asked, to the first of its places the view has, once the
       read after it has landed and the view has drawn its items. */
    React.useEffect(function () {
      if (!state.focus || state.loading) return;
      var el = null;
      state.focus.some(function (selector) { return (el = panel.querySelector(selector)); });
      state.focus = null;
      if (el) el.focus();
    });
    var items = state.items;
    return h('div', { className: state.loading ? 'app-inbox is-loading' : 'app-inbox' },
      state.error ? h('p', { className: 'body app-note' }, state.error) : null,
      items && items.length === 0 ? h('p', { className: 'body app-note' }, 'No work items.')
        : null,
      items && items.length ? table(items) : null);
  }

  function render() { root.render(h(View)); }

  /* The header's own read of the inbox, every thirty seconds: while the view shows, the table
     takes its items, so the table and the count agree, unless a read of the view's own is in
     flight, which lands after it. */
  function fromHeader(items) {
    if (panel.hidden || state.loading) return;
    state.items = items;
    state.error = null;
    render();
  }

  P.onShow.inbox = load;
  P.onInbox = fromHeader;
})();
