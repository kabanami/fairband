/* The page's header, its status line and the group view, loaded after app.js. The header is the
   design system's AppHeader: the views (Screen, Groups), the engine stamp and the refresh
   controls. Under it, the status line: the running refresh's progress, or how the last one ended
   with its calibration. While a refresh runs, the page asks /api/refresh/current every 2 seconds,
   one Cancel stands where the Refresh buttons were, the stamp is gone and the tables keep their
   old figures at ink-faint; when it ends, the rows (and the groups, when that view is open) load
   again. The group view is one plain table from /api/groups (spec 6.3), with no chart. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var POLL_MS = 2000;
  var BY = { sector: 'Sector', phase: 'Phase', cap: 'Cap band' };
  var RECOMPUTING = 'is-recomputing';

  var panels = {
    screen: document.getElementById('screen'),
    groups: document.getElementById('groups')
  };
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
    cancelAsked: false /* Cancel was accepted: it stays disabled until the run ends */
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
          notify('No refresh worker: start the server with the vendor keys.', false);
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

  function show(tab) {
    if (state.tab === tab) return;
    state.tab = tab;
    panels.screen.hidden = tab !== 'screen';
    panels.groups.hidden = tab !== 'groups';
    if (tab === 'groups') loadGroups();
    render();
  }

  function groupBy(event) {
    state.by = event.target.value;
    loadGroups();
  }

  /* ----------------------------------------------------------------- the text */

  function count(n) { return Number(n).toLocaleString('en-US'); }

  /* An engine phase name as the design system writes it: Mature growth. */
  function phaseName(name) { return F.PHASES[P.PHASE_NUMBER[name]] || name; }

  function progressLine(r) {
    return [r.kind ? 'Refreshing ' + r.kind : 'Refreshing', r.stage,
      count(r.done) + ' done, ' + count(r.failed) + ' failed, ' + count(r.remaining) + ' remaining'
    ].join(' · ');
  }

  /* A full refresh's calibration: the companies, those valued and those a classifier check
     flagged, the phases with a company, and the refusals grouped by the text before their first
     colon, the most frequent first. A price refresh's counts. */
  function calibrationLine(c) {
    if (c.repriced != null) {
      return count(c.total) + ' companies · ' + count(c.repriced) + ' repriced, ' +
        count(c.failed) + ' failed, ' + count(c.skipped) + ' skipped';
    }
    var parts = [
      count(c.total) + ' companies', count(c.valued) + ' valued',
      count(c.flagged) + ' flagged by a classifier check'
    ];
    var phases = Object.keys(c.phases || {})
      .filter(function (p) { return c.phases[p] > 0; })
      .map(function (p) { return phaseName(p) + ' ' + count(c.phases[p]); });
    if (phases.length) parts.push('phases: ' + phases.join(', '));
    var reasons = {};
    Object.keys(c.refused || {}).forEach(function (reason) {
      var head = reason.split(':')[0];
      reasons[head] = (reasons[head] || 0) + c.refused[reason];
    });
    var refused = Object.keys(reasons)
      .sort(function (a, b) { return reasons[b] - reasons[a] || (a < b ? -1 : a > b ? 1 : 0); })
      .map(function (reason) { return reason + ' ' + count(reasons[reason]); });
    if (refused.length) parts.push('refused: ' + refused.join(', '));
    return parts.join(' · ');
  }

  /* Last refresh: full done 1 Nov 2026, 01:20 · <its message, or its calibration>. The finish
     reads in the reader's local time. */
  function lastLine(last) {
    if (!last) return ['No refresh has run yet.'];
    var after = last.message || (last.calibration ? calibrationLine(last.calibration) : null);
    var finished = last.finishedAt ? P.localIso(last.finishedAt) : null;
    var when = finished ? h('time', {
      key: 'when', dateTime: finished, title: finished
    }, F.formatDate(finished)) : null;
    return ['Last refresh: ' + last.kind + ' ' + last.status + (when ? ' ' : ''), when,
      after ? ' · ' + after : null];
  }

  /* ------------------------------------------------------------------ render */

  function render() {
    var alive = state.running !== null;
    panels.screen.classList.toggle(RECOMPUTING, alive);
    panels.groups.classList.toggle(RECOMPUTING, alive);
    /* The stamp is the latest refresh's finish, whatever its status (the status line says how it
       ended). While a run is alive, or before any refresh finished, there is none: an absent
       stamp, never a placeholder. */
    var ran = alive || !state.last ? null : state.last.finishedAt;
    header.render(h(F.AppHeader, {
      views: [{ id: 'screen', label: 'Screen' }, { id: 'groups', label: 'Groups' }],
      view: state.tab,
      onViewChange: show,
      engineRanAt: ran ? P.localIso(ran) : null,
      children: actions(alive)
    }));
    var status = alive ? [progressLine(state.running)] : lastLine(state.last);
    var notice = state.notice;
    bar.render(h('div', { className: 'app-bar' },
      h.apply(null, ['p', { className: 'caption app-status', role: 'status' }].concat(status)),
      notice ? h('p', {
        className: 'caption app-status' + (notice.caution ? ' app-status--caution' : '')
      }, notice.text) : null));
    if (state.tab === 'groups') groupsRoot.render(groupsView());
  }

  /* The refresh controls in the header, small: the two refreshes while no run is alive, else one
     Cancel in their place, disabled once a cancel was asked until the run ends. */
  function actions(alive) {
    var buttons = alive ? [
      h(F.Button, {
        key: 'cancel', variant: 'quiet', size: 'sm', disabled: state.cancelAsked, onClick: cancel
      }, 'Cancel')
    ] : [
      h(F.Button, { key: 'price', size: 'sm', onClick: function () { start('price'); } },
        'Refresh prices'),
      h(F.Button, {
        key: 'full', variant: 'primary', size: 'sm', onClick: function () { start('full'); }
      }, 'Refresh all')
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
        'The median and the share count the companies with a value; below buy is a price under ' +
        'the buy level.') : null);
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
        h('th', { className: 'label fb-num' }, 'Below buy'))),
      h('tbody', null, g.groups.map(function (row) {
        return h('tr', { key: row.name },
          h('td', { className: 'body' }, g.by === 'phase' ? phaseName(row.name) : row.name),
          figure(row.count, count(row.count)),
          figure(row.valued, count(row.valued)),
          figure(row.medianPriceToValue, F.formatPercent(row.medianPriceToValue)),
          figure(row.shareBelowBuy, F.formatPercent(row.shareBelowBuy)));
      })));
  }

  render();
  poll();
})();
