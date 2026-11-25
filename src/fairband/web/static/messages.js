/* The owner's messages, as the page keeps them (spec 2026-11-25 owner's inbox, 7.1, 7.3 and 7.6),
   loaded after finder.js and before controls.js, which hands it every read of the inbox and draws
   its count on the header's Inbox entry, and the Inbox view, which draws its Messages tab. A
   work item gives one message where it is done, whoever posted it, or an agent declined it (7.1);
   the item's id names its message for good, so the page keeps ids and no time. The browser keeps
   two lists of them in its local storage (7.3): fairband.inbox.seen, the messages the owner saw
   in the Messages tab, and fairband.inbox.notified, those a notification was handled for, each a
   JSON list of work item ids. A message is unread while its id is not in seen; the header counts
   the unread ones. A list that is missing, or that is no list of ids, is written at the read that
   finds it with every message's id, so the first read after the build, in a new browser or after
   the site's data was cleared, marks nothing and notifies nothing; each later write keeps only
   the ids of its read. Where the browser refuses its storage, the lists live in memory for the
   page's life, by the same rules. Another tab's write of a list reaches this one through the
   browser's storage event, and the count is read again.

   The owner sees the messages while the Messages tab shows (watch) and the document is not
   hidden: a read that lands then, the tab shown over a read that landed, and the browser's tab
   come back to the front add every message's id to seen, and the rows unread at that moment keep
   their mark until the tab no longer shows (marked). A read with an id not in notified writes
   the list first, then, where the browser grants the permission, reads the messages in full and
   shows the browser's system notification of each new one (7.6), or one in their place for more
   than three; a full read that fails shows each by its title alone. Each carries a tag of its
   own, so two tabs that show it at one moment show one; a click brings the tab to the front,
   opens the report on the Research tab, or the Messages tab, and closes it. Only Turn on
   notifications asks the browser for the permission (ask), and a grant shows one notification at
   once, so the owner sees where they appear. The storage, the Notification and document.hidden
   are touched inside a try, never as the script loads. */
(function () {
  'use strict';

  var F = Fairband;
  var P = FairbandPage;
  /* Where the browser keeps the two lists (7.3). */
  var SEEN = 'fairband.inbox.seen';
  var NOTIFIED = 'fairband.inbox.notified';
  /* The full read of the messages (7.2), and the Messages tab, a notification's link where no
     report is. */
  var FULL = '/api/inbox/messages';
  var INBOX = '#inbox';
  /* More new messages than this at one read give one notification in their place (7.6). */
  var MANY = 3;
  var TAG = 'fairband-message-';

  var last = null; /* the ids of the last read's messages, newest first; null before one lands */
  var watched = false; /* the Messages tab shows (watch) */
  var marks = {}; /* the ids whose rows keep their unread mark while the tab shows, by id */
  var listeners = []; /* the functions called when the count or the permission may have moved */
  var memory = {}; /* each list as last read or written, by key: the lists where storage fails */
  var refused = false; /* the browser refused its storage once: the lists live in memory */

  /* ------------------------------------------------------------- the messages */

  /* The items of an inbox read that give a message (7.1): a done item, and a declined one whose
     decline an agent wrote; the newest finish first, then the larger id, as the full read orders
     them. */
  function of(items) {
    return (items || []).filter(function (item) {
      return item.state === 'done' || (item.state === 'declined' && item.declinedBy === 'agent');
    }).sort(function (a, b) {
      return time(b.finishedAt) - time(a.finishedAt) || b.id - a.id;
    });
  }

  /* An instant as a number to order by; one Date cannot read comes last. */
  function time(iso) {
    var at = Date.parse(iso);
    return isNaN(at) ? -Infinity : at;
  }

  function idOf(item) { return item.id; }

  /* -------------------------------------------------------------- the lists */

  /* The list `key` as the browser keeps it: its ids, or null where it is missing or is not a
     JSON list of numbers. Where the browser refuses its storage, the list kept in memory. */
  function stored(key) {
    if (!refused) {
      try {
        memory[key] = listOf(window.localStorage.getItem(key));
      } catch (e) {
        refused = true; /* the lists live in memory for the page's life */
      }
    }
    return memory[key] || null;
  }

  /* A stored text's list of ids, or null where it is none. */
  function listOf(text) {
    var list;
    try {
      list = JSON.parse(text);
    } catch (e) {
      return null;
    }
    if (!Array.isArray(list)) return null;
    for (var i = 0; i < list.length; i += 1) {
      if (typeof list[i] !== 'number') return null;
    }
    return list;
  }

  /* Keeps `ids` as the list `key`, in ascending order, which carries no meaning, in memory and in
     the browser's storage where it takes them. Gives the list kept. */
  function keep(key, ids) {
    var list = ids.slice().sort(function (a, b) { return a - b; });
    memory[key] = list;
    if (!refused) {
      try {
        window.localStorage.setItem(key, JSON.stringify(list));
      } catch (e) {
        refused = true; /* a write the browser refuses: memory from now on, so no id is lost */
      }
    }
    return list;
  }

  /* The ids of `ids` not in `list`. */
  function without(ids, list) {
    return ids.filter(function (id) { return list.indexOf(id) === -1; });
  }

  /* --------------------------------------------------------------- the reads */

  /* A read of the inbox landed, the header's or the Inbox view's (7.3 and 7.6): a missing list
     is written with every message's id; the ids not in notified are new, and where there is one
     the list is written first, then the notifications are made; while the owner sees the
     messages, the ids not in seen join the marks and seen is written. Gives the unread count. */
  function landed(items) {
    var messages = of(items);
    last = messages.map(idOf);
    var seen = stored(SEEN);
    var notified = stored(NOTIFIED);
    if (seen === null) keep(SEEN, last);
    if (notified === null) notified = keep(NOTIFIED, last);
    var fresh = without(last, notified);
    if (fresh.length) {
      keep(NOTIFIED, last);
      announce(messages.filter(function (item) { return fresh.indexOf(item.id) !== -1; }));
    }
    if (watched && shown()) see();
    return unread();
  }

  /* The unread messages: the last read's ids not in seen as the browser keeps it now, which
     another tab may have written; none before a read lands, or with no list. */
  function unread() {
    var seen = stored(SEEN);
    return last === null || seen === null ? 0 : without(last, seen).length;
  }

  /* The owner sees the last read's messages (7.3): the ids not in seen join the marks, and seen
     is written with every id. */
  function see() {
    var seen = stored(SEEN) || [];
    without(last, seen).forEach(function (id) { marks[id] = true; });
    keep(SEEN, last);
  }

  /* Whether the document shows; a browser that cannot say counts as showing. */
  function shown() {
    try {
      return !document.hidden;
    } catch (e) {
      return true;
    }
  }

  /* The Messages tab shows (true) or no longer shows (false). Shown over a read that landed, the
     owner sees its messages where the document shows, and the count may have moved; no longer
     shown, the marks go. */
  function watch(on) {
    watched = on === true;
    if (!watched) {
      marks = {};
      return;
    }
    if (last === null) return;
    if (shown()) see();
    changed();
  }

  /* Whether the row of the message `id` keeps its unread mark while the tab shows. */
  function marked(id) {
    return marks[id] === true;
  }

  /* The browser's tab come back to the front with the Messages tab shown: the owner sees the
     messages of the read that already landed, before the read it asks for lands (7.3). */
  document.addEventListener('visibilitychange', function () {
    if (watched && shown()) watch(true);
  });

  /* Another tab wrote a list, or cleared the storage (a null key): the count is read again. */
  window.addEventListener('storage', function (event) {
    if (event.key === SEEN || event.key === NOTIFIED || event.key === null) changed();
  });

  /* `fn` is called each time the count or the permission may have moved: another tab's write, the
     Messages tab shown over a read, the browser's tab back to the front with it, an ask's end. */
  function listen(fn) {
    listeners.push(fn);
  }

  function changed() {
    listeners.forEach(function (fn) { fn(); });
  }

  /* ------------------------------------------------------- the notification */

  /* The browser's permission to notify (7.6): 'none' where it has no Notification or the page is
     not a secure context, which the API needs; else 'default', 'denied' or 'granted'. */
  function permission() {
    try {
      if (window.isSecureContext === false || typeof window.Notification !== 'function') {
        return 'none';
      }
      return window.Notification.permission;
    } catch (e) {
      return 'none';
    }
  }

  /* Turn on notifications' press, the one request for the permission the page makes (7.6): on a
     grant, one notification at once; then the listeners. Gives a promise of the permission. */
  function ask() {
    return new Promise(function (resolve) {
      resolve(window.Notification.requestPermission());
    }).then(function (answer) {
      if (answer === 'granted') {
        show({
          title: 'Fairband', body: 'Notifications are on.', tag: 'fairband-test', href: INBOX
        });
      }
    }, function () { /* no Notification, or the browser would not ask: nothing changes */ })
      .then(function () {
        changed();
        return permission();
      });
  }

  /* The notifications of the new messages `items`, the newest first (7.6): none without the
     permission; one in their place for more than three, which opens the Messages tab; else the
     messages read in full, one for each, or by its title alone where the full read fails or
     lacks it. They are made the oldest first, so the newest stands on top. */
  function announce(items) {
    if (permission() !== 'granted') return;
    if (items.length > MANY) {
      show({
        title: 'Fairband', body: items.length + ' new messages', tag: 'fairband-messages',
        href: INBOX
      });
      return;
    }
    var oldest = items.slice().reverse();
    P.getJson(FULL).then(function (body) {
      var full = {};
      (body.messages || []).forEach(function (message) { full[message.itemId] = message; });
      oldest.forEach(function (item) {
        show(full[item.id] ? notice(full[item.id]) : titled(item));
      });
    }, function () {
      oldest.forEach(function (item) { show(titled(item)); });
    });
  }

  /* A notification by the cheap read's item alone: its title, no body, the Messages tab. */
  function titled(item) {
    return {
      title: titleOf(item.symbol, item.mode, item.state), body: '', tag: TAG + item.id,
      href: INBOX
    };
  }

  function titleOf(symbol, mode, kind) {
    return symbol + ': ' + mode + ' ' + kind;
  }

  /* A message's notification (7.6): its title, "QCOM: full report done"; its body, for a done
     one the call's stance and figures in the page's money and date forms, for a declined one the
     reason as written; its tag; its link, the report on the Research tab, else the Messages tab,
     a done one's too where its report is not on file (the full read gives it no revision). */
  function notice(message) {
    var done = message.kind === 'done';
    var filed = done && message.reportId != null && message.reportRevision != null;
    return {
      title: titleOf(message.symbol, message.mode, message.kind),
      body: done ? doneBody(message) : message.reason || '',
      tag: TAG + message.itemId,
      href: filed ? P.researchHref(message.symbol, message.reportId) : INBOX
    };
  }

  /* "Hold. Value $210.87 against a price of $173.19 on 7 Nov 2026. Valid until 3 Feb 2027.", the
     value's kind after its money where the call holds a secondary valuation's note, (reviewed,
     secondary valuation), or a mechanical basis, (mechanical), as on the value card; with no
     value, the stance and the refusal's sentence; with neither, no body. A value shows the
     price's date and the end of the validity window with it. */
  function doneBody(m) {
    var stance = m.stance ? m.stance.charAt(0).toUpperCase() + m.stance.slice(1) + '. ' : '';
    if (m.value != null) {
      var kind = m.note ? ' (' + m.basis + ', ' + m.note + ')'
        : m.basis === 'mechanical' ? ' (mechanical)' : '';
      var priced = m.price == null ? ''
        : ' against a price of ' + F.formatMoney(m.price) +
          (m.priceDate ? ' on ' + F.formatDate(m.priceDate) : '');
      return stance + 'Value ' + F.formatMoney(m.value) + kind + priced + '.' +
        (m.validUntil ? ' Valid until ' + F.formatDate(m.validUntil) + '.' : '');
    }
    return m.refusal ? stance + 'No value: ' + m.refusal + '.' : '';
  }

  /* Shows one notification, inside a try: a browser that refuses it (one that wants a service
     worker) stops nothing. A click brings the page's tab to the front, opens its link and closes
     it. */
  function show(note) {
    try {
      var made = new window.Notification(note.title, { body: note.body, tag: note.tag });
      made.onclick = function () {
        window.focus();
        window.location.hash = note.href;
        made.close();
      };
    } catch (e) { /* no notification: the message still counts */ }
  }

  /* What the page uses: of(items), the items that give a message; landed(items), a read of the
     inbox landed, giving the unread count (controls.js); unread(), the count now; watch(on), the
     Messages tab shows or no longer does, and marked(id), whether a row keeps its mark (the Inbox
     view); notice(message), a message's notification; permission() and ask(), the browser's
     permission and Turn on notifications' request; listen(fn), called when the count or the
     permission may have moved. */
  P.messages = {
    of: of, landed: landed, unread: unread, watch: watch, marked: marked, notice: notice,
    permission: permission, ask: ask, listen: listen
  };
})();
