/* The Inbox view (spec 2026-11-06 Tier 2, 18.5), loaded after watchlists.js: the work items as
   the server lists them, newest first, in one table. A row: the company's symbol, a plain link
   to the company page (FairbandPage.companyHref; spec 2026-11-22, 11), as the ticker is on the
   Screen and on a watchlist, with no click of its own, so the browser's own ways of opening a
   link work, and the row has no click either; the mode; the state word, a declined item's reason
   under it as written; the date and time it was posted, in the reader's time; who posted it, a
   compact PrincipalChip: the owner, an agent by its model identifier, or the system for the item
   it posts when a watched company's window ends; the agent that claimed it, likewise; the
   requester's note as written; for a done item, a link to the report it was completed with on
   the company page's Research tab (FairbandPage.researchHref, the Research tab's design, 7.1),
   named by its revision ("revision 2", its accessible name "Open revision 2 of the report for
   QCOM"), or Open when the server sends none; and for a pending or claimed item, Decline, which
   opens the reason line under the row: the reason field and Decline again, the owner's decline,
   and Cancel. A refused decline's sentence, the server's, stands on a line under its row. The
   view reads the inbox as it opens and after every write, each read running the expiry rule on
   the server, and hands each read to the header, so its count matches the table; while it
   shows, the header's own reads redraw the table too.

   A pending item's launch (B-210; spec 2026-11-16 agent launch, 10): where launching is set up,
   its row has Open Claude Code before Decline, which posts the item's launch as the drawer's
   button does, so an item no click on Request research made, a watched company's whose window
   ended, starts from here. Under the state word the row says where the item's launch is, in the
   drawer's words, a failure's in the error style with Open again; a refused launch's sentence
   stands on a line under the row. The view keeps a request for each pending item
   (FairbandPage.asking) and follows its launch while that is in flight, as the drawer does. */
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
    ready: false, /* whether launching is set up, as the view's last read said */
    asks: {}, /* each pending item's request and its launch's following, by item id */
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
        state.ready = body.launchReady === true;
        state.loading = false;
        state.error = null;
        P.countInbox(body.items);
        follow(body.items);
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

  /* ------------------------------------------------------------------ the launches */

  /* A pending item's request, made as the item is first drawn or followed and kept while it is
     pending: the drawer's kind (FairbandPage.asking), of which the view uses the launch's part. */
  function asked(item) {
    return state.asks[item.id] || (state.asks[item.id] = P.asking(item.symbol));
  }

  /* An item that is no longer pending: its request's following stops and the request goes. */
  function forget(id) {
    if (!state.asks[id]) return;
    P.stopLaunch(state.asks[id]);
    delete state.asks[id];
  }

  /* A read has landed: each pending item's request follows its launch while that is in flight
     (FairbandPage.followItem), as the drawer's follows its open item's, and an item that is
     claimed or closed stops its own. */
  function follow(items) {
    items.forEach(function (item) {
      if (item.state === 'pending') P.followItem(asked(item), item, redraw, reread(item));
      else forget(item.id);
    });
  }

  /* The draw a following asks for with each answer: the view's, while it shows. Once the view is
     hidden every following stops; the read as the view opens again starts those still in
     flight. */
  function redraw() {
    if (!panel.hidden) return render();
    Object.keys(state.asks).forEach(function (id) { P.stopLaunch(state.asks[id]); });
  }

  /* What runs once a launch's post ends and once its following ends: the drawer, if it shows the
     company, reads it again, so its line follows, and the view, while it shows, reads the inbox
     again, so the row draws the claim or the launch as the server has it. */
  function reread(item) {
    return function () {
      P.reloadDetail(item.symbol);
      if (!panel.hidden) load();
    };
  }

  /* Open Claude Code and Open again: the item's launch, posted as the drawer's button posts it
     (FairbandPage.openLaunch), which the view then follows. */
  function open(item) {
    P.openLaunch(asked(item), item.id, redraw, reread(item));
  }

  /* A pending item's launch in its row, from the item, its request and whether launching is set
     up, in the drawer's words (FairbandPage.launchWords of lineItem): `words`, under the state
     word, where the item has a launch or one's post is in flight, a failure's in the error style;
     `button`, Open Claude Code, or Open again after a failure, where launching is set up. An item
     that is not pending has neither: a claimed one's row says so and by whom. */
  function launchParts(item, ask, ready) {
    if (item.state !== 'pending') return { words: null, button: null };
    var shown = P.lineItem(ask, item);
    var line = P.launchWords(shown, ready);
    var again = line.action === 'again';
    return {
      words: shown.launch ? h('span', {
        className: 'caption app-inbox__why' + (line.failed ? ' app-inbox__failed' : '')
      }, line.text) : null,
      button: ready && line.action ? h(F.Button, {
        size: 'sm', className: 'app-inbox__open',
        'aria-label': 'Open Claude Code ' + (again ? 'again ' : '') + 'for the work item for ' +
          item.symbol,
        onClick: function () { open(item); }
      }, again ? 'Open again' : 'Open Claude Code') : null
    };
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
     line with its refused decline's sentence when there is one, then a refused launch's. An open
     item's last cell is Decline, which opens the reason line and gives way to it; a pending
     item's has its launch's button before it and its state cell the launch's words
     (launchParts). */
  function row(item) {
    var open = OPEN.indexOf(item.state) !== -1;
    var declining = open && state.declining === item.id;
    var ask = item.state === 'pending' ? asked(item) : null;
    var parts = launchParts(item, ask, state.ready);
    return h(React.Fragment, { key: item.id },
      h('tr', { 'data-item': item.id },
        h('td', null, h('a', {
          className: 'ticker app-link app-inbox__symbol',
          href: P.companyHref({ ticker: item.symbol })
        }, item.symbol)),
        h('td', { className: 'body' }, item.mode),
        h('td', { className: 'body app-inbox__wrap' }, item.state,
          item.state === 'declined' && item.reason
            ? h('span', { className: 'caption app-inbox__why' }, item.reason) : null,
          parts.words),
        h('td', { className: 'figure fb-num' }, posted(item.postedAt)),
        h('td', null,
          h(F.PrincipalChip, { principal: item.postedBy, actor: item.postedActor, compact: true })),
        h('td', null, item.claimedBy
          ? h(F.PrincipalChip, { principal: 'agent', actor: item.claimedBy, compact: true })
          : none()),
        h('td', { className: 'body app-inbox__wrap' }, item.note || none()),
        h('td', null, item.state === 'done' && item.reportId != null ? h('a', {
          className: 'app-link', href: P.researchHref(item.symbol, item.reportId),
          'aria-label': item.reportRevision != null
            ? 'Open revision ' + item.reportRevision + ' of the report for ' + item.symbol
            : 'Open the report for ' + item.symbol
        }, item.reportRevision != null ? 'revision ' + item.reportRevision : 'Open') : none()),
        h('td', null, parts.button, open && !declining ? h(F.Button, {
          size: 'sm', className: 'app-inbox__decline',
          'aria-label': 'Decline the work item for ' + item.symbol,
          onClick: function () {
            state.declining = item.id;
            render();
          }
        }, 'Decline') : null)),
      declining ? reasonLine(item) : null,
      state.errors[item.id] ? refused(state.errors[item.id]) : null,
      ask && ask.error ? refused(ask.error) : null);
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

  /* The line under a row whose decline or launch the server refused: the sentence, as it
     arrived; a launch's read that failed says so here too. */
  function refused(sentence) {
    return h('tr', { className: 'app-inbox__refused' },
      h('td', { colSpan: HEADS.length + 1, className: 'caption app-inbox__error' }, sentence));
  }

  /* The table: the heads, the posted day's at the right as its dates are, then a last column
     with no head for Open Claude Code and Decline. It scrolls sideways on its own in a narrow
     window. */
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
    follow(items);
    render();
  }

  P.onShow.inbox = load;
  P.onInbox = fromHeader;
  /* For the tests, which read them in node: a pending item's launch parts and an item's row. */
  P.inbox = { launchParts: launchParts, row: row };
})();
