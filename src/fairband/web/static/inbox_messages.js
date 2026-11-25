/* The Inbox view's Messages tab (spec 2026-11-25 owner's inbox, 7.4 and 7.6), loaded after
   messages.js and watchlists.js and before inbox.js, which draws the view's two tabs and, on this
   one, the panel this script gives (view). The owner's messages, one for each report an agent
   finished and each request an agent declined, the newest first, as the server reads them in full
   (/api/inbox/messages, 7.2): read as the tab opens, and again where a read of the work items
   holds a message the tab does not show (lacks), inbox.js asking for both. The messages shown
   stay, faded, until a read lands, and the latest read wins. Over them, the one line about the
   browser's notification, by its permission (line), with none where it is granted; Turn on
   notifications in it is the one control on the page that asks the browser for the permission
   (FairbandPage.messages.ask). With no message, one sentence says when one arrives; a failed
   read, the server's sentence, as the Work queue words its own.

   A message's row (row): the unread mark, a small square named "unread", where the message was
   unread as the tab showed (FairbandPage.messages.marked), before the symbol, a plain link to the
   company page as in the Work queue; what ended, "Full report done"; for a done one, the stance in
   the Stance column's chip and the call in the words its notification uses
   (FairbandPage.messages.parts): the value, the price with its date and the end of the validity
   window, or the refusal's sentence where the call has no value; for a declined one, the reason
   as written, in a cell that wraps; who ended it, a compact PrincipalChip; when, in the reader's
   time; and for a done one, the link to its report on the Research tab, named as the Work
   queue's names it. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var FULL = '/api/inbox/messages';
  var HEADS = ['Symbol', 'Message', 'Summary', 'By', 'Ended', 'Report'];
  /* The line about the notification, by the browser's permission (7.6), and the tab's sentence
     with no message (7.4). */
  var CANNOT = 'This browser cannot show notifications at this address.';
  var OFF = 'Notifications are off.';
  var BLOCKED = 'The browser blocks notifications for this address. Allow them in the ' +
    'browser\'s site settings.';
  var NONE_YET = 'No messages. One arrives when an agent finishes a report or declines a request.';

  var state = {
    messages: null, /* the messages, newest first; null until the first read lands */
    loading: false, /* a read is in flight */
    error: null /* a failed read's sentence */
  };
  var latest = 0;

  /* The messages read in full (7.2), as the tab opens and where a read of the work items holds
     one the tab does not show; the latest read wins. Gives a promise that settles as the read
     lands or fails, once the state holds it, for the view to draw. */
  function load() {
    var request = ++latest;
    state.loading = true;
    return P.getJson(FULL)
      .then(function (body) {
        if (request !== latest) return;
        state.messages = body.messages;
        state.loading = false;
        state.error = null;
      }, function (err) {
        if (request !== latest) return;
        state.loading = false;
        state.error = 'The messages did not load: ' + err.message +
          '. Reload the page to try again.';
      });
  }

  /* Whether the work items `items` hold a message the tab does not show (7.2): one whose id is
     not among the messages last read, while no read is in flight, which may bring it; a read
     after it that still lacks it asks again. */
  function lacks(items) {
    if (state.loading) return false;
    var shown = (state.messages || []).map(function (message) { return message.itemId; });
    return P.messages.of(items).some(function (item) { return shown.indexOf(item.id) === -1; });
  }

  /* Whether a read of the messages is in flight: the view fades the rows it shows meanwhile. */
  function loading() {
    return state.loading;
  }

  /* The muted dash of a cell with nothing to show: no author, no summary, no report. The Work
     queue draws its empty cells the same way (inbox.js), so the two tabs read alike. */
  function none() { return h('span', { className: 'app-muted' }, '—'); }

  /* A message's row, `marked` where it keeps its unread mark (7.3 and 7.4). */
  function row(message, marked) {
    var by = message.by || {};
    return h('tr', { key: message.itemId, 'data-message': message.itemId },
      h('td', null,
        marked ? h('span', { role: 'img', 'aria-label': 'unread', className: 'app-inbox__new' })
          : null,
        h('a', {
          className: 'ticker app-link app-inbox__symbol',
          href: P.companyHref({ ticker: message.symbol })
        }, message.symbol)),
      h('td', { className: 'body' }, P.messages.ended(message.mode, message.kind, true)),
      summary(message),
      h('td', null, by.principal
        ? h(F.PrincipalChip, { principal: by.principal, actor: by.actor, compact: true })
        : none()),
      h('td', { className: 'figure fb-num' }, P.when(message.at)),
      h('td', null, report(message)));
  }

  /* The Summary cell, which wraps: a done message's stance in the Stance column's chip, then
     "Value $210.87 · price $173.19 on 7 Nov 2026 · valid until 3 Feb 2027", or the refusal's
     sentence where the call has no value, or the dash where it has neither, as where the report
     is no longer on file; a declined one's reason as written. */
  function summary(message) {
    if (message.kind !== 'done') {
      return h('td', { className: 'body app-inbox__wrap' }, message.reason || none());
    }
    var said = P.messages.parts(message);
    var words = said.value
      ? said.value + (said.price ? ' · price ' + said.price : '') +
        (said.validUntil ? ' · valid until ' + said.validUntil : '')
      : said.refusal;
    return h('td', { className: 'body app-inbox__wrap' },
      message.stance ? h('span', {
        className: 'fb-stance fb-stance--' + message.stance + ' label'
      }, message.stance) : null,
      message.stance ? ' ' : null,
      words || none());
  }

  /* A done message's report on the company page's Research tab, as the Work queue links a done
     item's: named by its revision, "Open revision 2 of the report for QCOM", or Open where the
     read gives none; the dash for a declined one. */
  function report(message) {
    if (message.kind !== 'done' || message.reportId == null) return none();
    var revision = message.reportRevision;
    return h('a', {
      className: 'app-link', href: P.researchHref(message.symbol, message.reportId),
      'aria-label': revision != null
        ? 'Open revision ' + revision + ' of the report for ' + message.symbol
        : 'Open the report for ' + message.symbol
    }, revision != null ? 'revision ' + revision : 'Open');
  }

  /* The notification's line by the browser's permission (7.6): it cannot notify here, with no
     Notification or outside a secure context ('none'); it is off ('default'), with Turn on
     notifications, which calls `onAsk`; the browser blocks it ('denied'); and no line where it
     is granted. */
  function line(permission, onAsk) {
    if (permission === 'granted') return null;
    var off = permission === 'default';
    return h('p', { className: 'body app-note app-inbox__notify' },
      off ? OFF : permission === 'denied' ? BLOCKED : CANNOT,
      off ? ' ' : null,
      off ? h(F.Button, { size: 'sm', onClick: onAsk }, 'Turn on notifications') : null);
  }

  /* Turn on notifications' press: the browser's request for the permission, inside the press.
     Its end calls messages.js's listeners, and the Inbox view draws its line again. */
  function ask() {
    P.messages.ask();
  }

  /* The table of the messages, the time each ended at the right, as dates are; it scrolls
     sideways on its own in a narrow window, as the Work queue's does. */
  function table(messages) {
    return h('div', { className: 'app-inbox__scroll' },
      h('table', { className: 'fb-table' },
        h('thead', null, h('tr', null,
          HEADS.map(function (head) {
            return h('th', {
              key: head, className: head === 'Ended' ? 'label fb-num' : 'label'
            }, head);
          }))),
        h('tbody', null, messages.map(function (message) {
          return row(message, P.messages.marked(message.itemId));
        }))));
  }

  /* The tab's panel: the notification's line, then a failed read's sentence, then the sentence
     with no message or the table. */
  function view() {
    var messages = state.messages;
    return h(React.Fragment, null,
      line(P.messages.permission(), ask),
      state.error ? h('p', { className: 'body app-note' }, state.error) : null,
      messages && messages.length === 0 ? h('p', { className: 'body app-note' }, NONE_YET) : null,
      messages && messages.length ? table(messages) : null);
  }

  /* What inbox.js uses: load(), the read; lacks(items), whether a read of the work items holds a
     message the tab does not show; loading(), whether a read is in flight; view(), the tab's
     panel. The tests read row(message, marked) and line(permission, onAsk) in node too. */
  P.inboxMessages = {
    load: load, lacks: lacks, loading: loading, view: view, row: row, line: line
  };
})();
