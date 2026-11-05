/* The page's header, its status line and the group view, loaded after app.js. The header is the
   design system's AppHeader: the five views (Screen, Groups, Watchlists, Methodology, Settings),
   the engine stamp and the refresh controls; the URL hash names the open view. Under it, the
   status line: the running refresh's one run bar (the design system's RunProgress), or how the
   last one ended in one line, its calibration's breakdown behind Details ▾ (growth-routes spec
   6.1). While a refresh runs, the page asks /api/refresh/current every 2 seconds, one Cancel
   stands where the Refresh buttons were, the stamp is gone and the tables keep their old figures
   at ink-faint; when it ends, the rows (and the groups, when that view is open) load again. The
   group view is one plain table from /api/groups (spec 6.3), with no chart. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var POLL_MS = 2000;
  var BY = { sector: 'Sector', phase: 'Phase', cap: 'Cap band' };
  var RECOMPUTING = 'is-recomputing';
  var UNCLASSIFIED = 'unclassified'; /* the calibration's name for a company without a phase */
  /* The refusals the refresh writes for a company it failed, by the text they start with. */
  var FAILED_REASONS = ['data fetch failed', 'data fetch incomplete', 'valuation failed'];
  /* The server's stage names as the run bar's lowercase verb phrases (spec 4.3). */
  var STAGE_WORDS = {
    universe: 'reading the universe', deciles: 'ranking', fetch: 'fetching',
    backfill: 'reading stored statements', value: 'valuing',
    quotes: 'fetching prices', reprice: 'repricing', done: 'finishing'
  };

  /* The views in the header's order, each with its panel, a section of the page. */
  var VIEWS = ['screen', 'groups', 'watchlists', 'methodology', 'settings'];
  var panels = {};
  VIEWS.forEach(function (id) { panels[id] = document.getElementById(id); });
  var header = ReactDOM.createRoot(document.getElementById('header'));
  var bar = ReactDOM.createRoot(document.getElementById('controls'));
  var groupsRoot = ReactDOM.createRoot(panels.groups);
  var state = {
    tab: 'screen',
    by: 'sector',
    groups: null, groupsLoading: false, groupsError: null,
    running: null, /* the progress, while a refresh runs */
    last: null, /* the last refresh's record */
    notice: null, /* { text, caution }: what the last request came to */
    cancelAsked: false, /* Cancel was accepted: it stays disabled until the run ends */
    detailsOpen: false /* the last refresh's Details ▾ menu is open */
  };
  var timer = null;
  var latestPoll = 0;
  var latestGroups = 0;
  var started = false; /* a refresh was started here and its end is not seen yet */

  /* ------------------------------------------------------------------ polling */

  function poll() {
    var request = ++latestPoll;
    clearTimeout(timer);
    P.getJson('/api/refresh/current')
      .then(function (body) {
        if (request !== latestPoll) return;
        var ended = (state.running !== null || started) && body.refresh === null;
        if (state.notice && state.notice.fromPoll) state.notice = null; /* it answers again */
        state.running = body.refresh;
        if (body.refresh !== null) state.detailsOpen = false; /* the run bar replaces the line */
        if (body.refresh === null) state.last = body.last;
        if (ended) { /* the notice (already running, cancel asked) no longer holds */
          started = false;
          state.notice = null;
          state.cancelAsked = false;
          P.reload();
          if (state.tab === 'groups') loadGroups();
        }
        if (body.refresh !== null) timer = setTimeout(poll, POLL_MS);
        render();
      })
      .catch(function (err) {
        if (request !== latestPoll) return;
        /* While a run is alive, ask again: the buttons and the faded tables recover once the
           server answers. With none alive there is nothing to follow. */
        var alive = state.running !== null || started;
        if (alive) timer = setTimeout(poll, POLL_MS);
        notify('The refresh status did not load: ' + err.message + (alive
          ? '. The page asks again every 2 seconds.' : '. Reload the page to try again.'), true,
          true);
      });
  }

  /* A notice under the status line; one from a failed poll clears when a poll answers. */
  function notify(text, caution, fromPoll) {
    state.notice = text ? { text: text, caution: caution, fromPoll: !!fromPoll } : null;
    render();
  }

  /* A POST, then the status, which polls while a run lives. 409 and 503 have their own words; any
     other refusal (a 403, a 400) and a request that never arrived read in caution. */
  function post(url, body, onOk) {
    notify(null);
    P.api.post(url, body)
      .then(function (r) {
        if (r.status === 409) notify('A refresh is already running.', false);
        else if (r.status === 503) {
          notify('No refresh worker.', false);
        } else if (!r.ok) {
          var detail = r.body && r.body.detail ? String(r.body.detail) : 'no reason given';
          notify('The server refused the request: ' + detail + '.', true);
        } else if (onOk) onOk();
        poll();
      })
      .catch(function (err) {
        notify('The request did not reach the server: ' + err.message +
          '. Reload the page to try again.', true);
      });
  }

  function start(kind) {
    post('/api/refresh', { kind: kind }, function () { started = true; });
  }

  function cancel() {
    post('/api/refresh/cancel', {}, function () {
      state.cancelAsked = true;
      notify('Cancel asked: the refresh stops after the companies in flight.', false);
    });
  }

  /* --------------------------------------------------------------- the groups */

  function loadGroups() {
    var request = ++latestGroups;
    state.groupsLoading = true;
    render();
    P.getJson('/api/groups?by=' + encodeURIComponent(state.by))
      .then(function (body) {
        if (request !== latestGroups) return;
        state.groups = body;
        state.groupsLoading = false;
        state.groupsError = null;
        render();
      })
      .catch(function (err) {
        if (request !== latestGroups) return;
        state.groupsLoading = false;
        state.groupsError = 'The groups did not load: ' + err.message +
          '. Choose the grouping again to retry.';
        render();
      });
  }

  /* Opens a view: its panel shows and the others hide, the hash names it (the Screen has none)
     and its loader runs, the groups' here and each later view's through P.onShow. A view the page
     does not know is the Screen. A section of the Methodology view stays in P.section for that
     view's script to scroll to; one named while the view is open runs its loader again
     (spec 2026-11-04 6). */
  function show(tab, section) {
    if (VIEWS.indexOf(tab) === -1) tab = 'screen';
    var opened = state.tab !== tab;
    P.section = tab === 'methodology' && section ? section : null;
    history.replaceState(null, '', tab === 'screen' ? location.pathname
      : '#' + tab + (P.section ? '/' + P.section : ''));
    if (!opened && !P.section) return;
    state.tab = tab;
    VIEWS.forEach(function (id) { panels[id].hidden = id !== tab; });
    if (tab === 'groups') loadGroups();
    if (P.onShow[tab]) P.onShow[tab]();
    render();
  }

  /* The view a hash names, on load and when a link changes it: #watchlists, #methodology,
     #settings, or #methodology/<section-id>, the Methodology view at that section. */
  function fromHash() {
    var parts = location.hash.slice(1).split('/');
    show(parts[0], parts[1]);
  }

  function groupBy(event) {
    state.by = event.target.value;
    loadGroups();
  }

  /* ----------------------------------------------------------------- the text */

  function count(n) { return Number(n).toLocaleString('en-US'); }

  /* An engine phase name as the design system writes it: Mature growth. */
  function phaseName(name) { return F.PHASES[P.PHASE_NUMBER[name]] || name; }

  /* The run bar's props from the poll's refresh body. The server's counts are per stage and add up
     to the stage's symbols, so they make the total. In the universe and deciles stages the server
     reports every symbol done, yet none is fetched or valued: nothing is done, and the word says
     what is happening. An unknown stage name is shown as it is. */
  function runProps(r) {
    var total = r.done + r.failed + r.remaining;
    var stage = STAGE_WORDS[r.stage] || r.stage;
    if (r.stage === 'universe' || r.stage === 'deciles') {
      return { total: total, done: 0, failed: r.failed, stage: stage };
    }
    return { total: total, done: r.done, failed: r.failed, stage: stage };
  }

  /* The last refresh, from its kind (spec 6.1): full done 1 Nov 2026, 01:20 · 1,052 of 1,759
     valued, then · 3 failed when the run failed companies. A price refresh counts those
     repriced, and those skipped for want of a snapshot. A record without a calibration, a run
     that failed, was cancelled or was scoped, says its message instead. The finish reads in the
     reader's local time. */
  function lastLine(last) {
    if (!last) return ['No refresh has run yet.'];
    var c = last.calibration;
    var finished = last.finishedAt ? P.localIso(last.finishedAt) : null;
    var when = finished ? h('time', {
      key: 'when', dateTime: finished, title: finished
    }, F.formatDate(finished)) : null;
    var line = [last.kind + ' ' + last.status + (when ? ' ' : ''), when];
    if (!c) return line.concat(last.message ? [' · ' + last.message] : []);
    line = line.concat(c.repriced != null
      ? [' · ', count(c.repriced), ' of ', count(c.total), ' repriced']
      : [' · ', count(c.valued), ' of ', count(c.total), ' valued']);
    var failed = failedOf(c);
    if (failed > 0) line = line.concat([' · ', count(failed), ' failed']);
    if (c.skipped > 0) line = line.concat([' · ', count(c.skipped), ' skipped']);
    return line;
  }

  /* The companies a run failed. A price refresh's calibration counts them; a full refresh's or a
     revalue's does not, so they are its refusals of the three reasons the refresh itself writes
     (refresh/run.py): a fetch that failed, one a rate limit stopped, a valuation that raised. */
  function failedOf(c) {
    if (c.failed != null) return c.failed;
    return Object.keys(c.refused || {}).reduce(function (n, reason) {
      return FAILED_REASONS.some(function (head) { return reason.indexOf(head) === 0; })
        ? n + c.refused[reason] : n;
    }, 0);
  }

  /* Details ▾ beside the line of a full refresh or a revalue: in the bundle's sectioned menu (the
     Filters menu's markup), the companies a classifier check flagged; the phases in phase order,
     unclassified last, those with none left out; the refusals grouped by the text before their
     first colon, the most frequent first. A press outside it or Escape closes it (spec 6.3). */
  function detailsMenu(c) {
    var phases = Object.keys(c.phases || {})
      .filter(function (p) { return c.phases[p] > 0; })
      .sort(function (a, b) { return phaseOrder(a) - phaseOrder(b); });
    var reasons = {};
    Object.keys(c.refused || {}).forEach(function (reason) {
      var head = reason.split(':')[0];
      reasons[head] = (reasons[head] || 0) + c.refused[reason];
    });
    var refused = Object.keys(reasons)
      .sort(function (a, b) { return reasons[b] - reasons[a] || (a < b ? -1 : a > b ? 1 : 0); });
    return h('div', { className: 'fb-screen__cols app-details' },
      h(F.Button, {
        size: 'sm', onClick: function () { state.detailsOpen = !state.detailsOpen; render(); },
        'aria-expanded': state.detailsOpen ? 'true' : 'false'
      }, 'Details ▾'),
      state.detailsOpen ? h('div', { className: 'fb-menu fb-menu--filters' },
        h('div', { className: 'fb-menu__body' },
          menuSection('FLAGGED', h('div', { className: 'body app-details__row' },
            count(c.flagged) + ' flagged by a classifier check')),
          h('hr'),
          menuSection('PHASES', phases.length ? phases.map(function (p) {
            return detailsRow(p, p === UNCLASSIFIED ? 'Unclassified' : phaseName(p), c.phases[p]);
          }) : none()),
          h('hr'),
          menuSection('REFUSED', refused.length ? refused.map(function (reason) {
            return detailsRow(reason, reason, reasons[reason]);
          }) : none()))) : null);
  }

  function none() { return h('div', { className: 'body app-details__row app-muted' }, 'none'); }

  function menuSection(head, rows) {
    return h('div', { className: 'fb-menu__sec' },
      h('span', { className: 'fb-menu__h label' }, head), rows);
  }

  /* A word and its count, the count in mono. */
  function detailsRow(key, word, n) {
    return h('div', { key: key, className: 'app-details__row' },
      h('span', { className: 'body' }, word), h('span', { className: 'figure-sm' }, count(n)));
  }

  /* A phase's place in phase order; unclassified, and any name the page does not know, last. */
  function phaseOrder(name) { return P.PHASE_NUMBER[name] || 7; }

  /* ------------------------------------------------------------------ render */

  function render() {
    var alive = state.running !== null;
    /* Every panel's tables fade while a run is alive, but the Methodology view's: its examples
       are figures as of a named date, not the running refresh's. */
    VIEWS.forEach(function (id) {
      if (id !== 'methodology') panels[id].classList.toggle(RECOMPUTING, alive);
    });
    /* The stamp is the latest refresh's finish, whatever its status (the status line says how it
       ended). While a run is alive, or before any refresh finished, there is none: an absent
       stamp, never a placeholder. */
    var ran = alive || !state.last ? null : state.last.finishedAt;
    header.render(h(F.AppHeader, {
      views: [{ id: 'screen', label: 'Screen' }, { id: 'groups', label: 'Groups' },
        { id: 'watchlists', label: 'Watchlists' }, { id: 'methodology', label: 'Methodology' },
        { id: 'settings', label: 'Settings' }],
      view: state.tab,
      onViewChange: show,
      engineRanAt: ran ? P.localIso(ran) : null,
      children: actions(alive)
    }));
    /* The status line: during a run, the run bar, or the stage word alone while the stage reports
       a total of 0 (the component draws nothing for it); else how the last refresh ended. A div,
       since the bar is a block a p cannot hold. Details ▾ stands beside the line, outside the
       status region, when the calibration has a breakdown; the run bar keeps the full width. */
    var run = alive ? runProps(state.running) : null;
    var status = !run ? lastLine(state.last)
      : [run.total > 0 ? h(F.RunProgress, runProps(state.running)) : run.stage];
    var c = !run && state.last ? state.last.calibration : null;
    var details = c && c.phases ? detailsMenu(c) : null;
    var notice = state.notice;
    bar.render(h('div', { className: 'app-bar' },
      h('div', { className: details ? 'app-statusline' : null },
        h.apply(null, ['div', { className: 'caption app-status', role: 'status' }].concat(status)),
        details),
      notice ? h('p', {
        className: 'caption app-status' + (notice.caution ? ' app-status--caution' : '')
      }, notice.text) : null));
    if (state.tab === 'groups') groupsRoot.render(groupsView());
  }

  /* A refresh button's words: the full ones, and the short ones index.html shows in their place
     below 400px, where the full ones no longer fit beside the lockup (B-82). The button names
     itself in full either way. */
  function label(full, short) {
    return [
      h('span', { key: 'l', className: 'app-actions__long' }, full),
      h('span', { key: 's', className: 'app-actions__short' }, short)
    ];
  }

  /* The refresh controls in the header, small: the two refreshes while no run is alive, else one
     Cancel in their place, disabled once a cancel was asked until the run ends. */
  function actions(alive) {
    var buttons = alive ? [
      h(F.Button, {
        key: 'cancel', variant: 'quiet', size: 'sm', disabled: state.cancelAsked, onClick: cancel
      }, 'Cancel')
    ] : [
      h(F.Button, {
        key: 'price', size: 'sm', 'aria-label': 'Refresh prices',
        onClick: function () { start('price'); }
      }, label('Refresh prices', 'Prices')),
      h(F.Button, {
        key: 'full', variant: 'primary', size: 'sm', 'aria-label': 'Refresh all',
        onClick: function () { start('full'); }
      }, label('Refresh all', 'Full'))
    ];
    return h('div', { className: 'app-actions' }, buttons);
  }

  /* The table of the groups last loaded; while others load, it stays, faded. */
  function groupsView() {
    var g = state.groups;
    var picker = h('label', { className: 'label app-by' }, 'Group by ',
      h('select', { className: 'control app-select', value: state.by, onChange: groupBy },
        Object.keys(BY).map(function (by) {
          return h('option', { key: by, value: by }, BY[by]);
        })));
    var body = null;
    if (state.groupsError) body = h('p', { className: 'body app-note' }, state.groupsError);
    else if (g && g.groups.length === 0) {
      body = h('p', { className: 'body app-note' }, 'No companies to group yet. Run a refresh.');
    } else if (g) body = groupsTable(g);
    return h('div', { className: state.groupsLoading ? 'app-groups is-loading' : 'app-groups' },
      h('div', { className: 'app-groups__bar' }, picker),
      body,
      g && g.groups.length ? h('p', { className: 'caption app-muted app-groups__note' },
        'The median and the share count the companies with a value; below value is a price in ' +
        'the Below or Well below band.') : null);
  }

  function groupsTable(g) {
    function figure(v, text) {
      return h('td', { className: 'figure fb-num' + (v == null ? ' app-muted' : '') }, text);
    }
    return h('table', { className: 'fb-table app-groups__table' },
      h('thead', null, h('tr', null,
        h('th', { className: 'label' }, BY[g.by]),
        h('th', { className: 'label fb-num' }, 'Companies'),
        h('th', { className: 'label fb-num' }, 'Valued'),
        h('th', { className: 'label fb-num' }, 'Median price ÷ value'),
        h('th', { className: 'label fb-num' }, 'Below value'))),
      h('tbody', null, g.groups.map(function (row) {
        return h('tr', { key: row.name },
          h('td', { className: 'body' }, g.by === 'phase' ? phaseName(row.name) : row.name),
          figure(row.count, count(row.count)),
          figure(row.valued, count(row.valued)),
          figure(row.medianPriceToValue, F.formatPercent(row.medianPriceToValue)),
          figure(row.shareBelowValue, F.formatPercent(row.shareBelowValue)));
      })));
  }

  /* Details ▾ closes on a press or focus outside it and on Escape, as the screen's menus do. Each
     menu closes itself on a press or focus outside it, so opening one, by pointer or by keyboard,
     closes the others (spec 6.3). Registered once; each reads state.detailsOpen. */
  function closeDetailsOutside(event) {
    if (!state.detailsOpen) return;
    if (event.target instanceof Element && event.target.closest('.app-details')) return;
    state.detailsOpen = false;
    render();
  }
  document.addEventListener('pointerdown', closeDetailsOutside);
  document.addEventListener('focusin', closeDetailsOutside);
  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape' || !state.detailsOpen) return;
    state.detailsOpen = false;
    render();
  });

  /* What the later views use: show opens a view; each view registers its loader in onShow, and
     onShow[tab]() runs each time that view opens; section is the Methodology section a hash
     named; running() is true while a refresh runs; followRefresh() follows a refresh another view
     started (the Settings view's revalue) as the header follows its own: the run bar while it
     runs, the rows loaded again when it ends. */
  P.show = show;
  P.onShow = {};
  P.section = null;
  P.running = function () { return state.running !== null; };
  P.followRefresh = function () { started = true; poll(); };

  window.addEventListener('hashchange', fromHash);
  /* The first view opens once the page's later scripts have run and registered their loaders. */
  document.addEventListener('DOMContentLoaded', fromHash);

  render();
  poll();
})();
