/* The screen page: fetches /api/screen and renders the design system's ScreenTable, and beside it
   the detail drawer of the row the reader opens (spec 6.4), fetched from /api/companies/{symbol}.
   No JSX and no build step: React.createElement against window.Fairband. The server sorts and the
   engine computes; this script asks for an order, remembers the chosen columns, narrows the
   loaded rows to the reader's find and filters and lays out what the engine produced, rounded for
   display only. The header, the status line and the group view are controls.js, loaded after
   this script; it reaches the screen through window.FairbandPage. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var COLUMNS_KEY = 'fairband.columns';

  /* The columns that draw a row key under another name sort by that key. */
  var SORT_KEYS = { band: 'fairLow', stance: 'stance3', entered: 'enteredAt' };
  /* The engine's phase names, as PhaseBadge's numbers. */
  var PHASE_NUMBER = {
    'Start-up': 1, 'Young Growth': 2, 'High Growth': 3,
    'Mature Growth': 4, 'Mature Stable': 5, 'Decline': 6
  };
  var ROUTES = { 'mature-growth': 'Mature growth route', 'mature-stable': 'Mature stable route' };

  var mount = document.getElementById('screen');
  var root = ReactDOM.createRoot(mount);
  var state = {
    rows: null,
    error: null,
    sort: { column: 'ticker', direction: 'asc' },
    columns: loadColumns(),
    /* The FIND text and the Filters menu's choice. Neither is saved: every page load starts
       with the whole screen (screen-controls spec 4.4). */
    query: '',
    filters: F.EMPTY_FILTERS,
    drawer: null /* { symbol, body, loading, error } while open */
  };
  var latest = 0;
  var latestDetail = 0;

  function loadColumns() {
    try {
      var saved = JSON.parse(window.localStorage.getItem(COLUMNS_KEY));
      if (Array.isArray(saved)) return saved;
    } catch (e) { /* no storage, or not a list: the default */ }
    return F.DEFAULT_COLUMNS.slice();
  }

  function setColumns(columns) {
    state.columns = columns;
    try {
      window.localStorage.setItem(COLUMNS_KEY, JSON.stringify(columns));
    } catch (e) { /* no storage: the choice lasts until the page reloads */ }
    render();
  }

  function setQuery(query) {
    state.query = query;
    render();
  }

  function setFilters(filters) {
    state.filters = filters;
    render();
  }

  function getJson(url) {
    return fetch(url).then(function (response) {
      if (!response.ok) throw new Error('the server answered ' + response.status);
      return response.json();
    });
  }

  /* The server refuses a POST without the X-Fairband-Request header (D11): a cross-site form
     cannot send it, nor a cross-origin script without a preflight the server never answers. The
     refresh controls post through here; the promise gives the status and the parsed body. */
  var api = {
    post: function (url, body) {
      return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Fairband-Request': '1' },
        body: JSON.stringify(body || {})
      }).then(function (response) {
        return response.json().then(function (json) {
          return { ok: response.ok, status: response.status, body: json };
        });
      });
    }
  };

  /* The server writes a timestamp in UTC (+00:00), and the design system prints a string's own
     hour and minute, so a UTC stamp would read as the reader's clock and be hours off. This is
     the same instant in the browser's offset (2026-10-31T22:20:00+00:00 is
     2026-11-01T01:20:00+03:00 at +03:00), so datetime stays true and the text reads as local
     time: the header's engine stamp, the last-refresh line, the table's Entered dates and the
     drawer's timestamps. A plain date (no T) is a day, not an instant, and passes through; so
     does a string Date cannot read. */
  function localIso(iso) {
    if (!iso || String(iso).indexOf('T') < 0) return iso;
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    var offset = -d.getTimezoneOffset();
    var abs = Math.abs(offset);
    return d.getFullYear() + '-' + two(d.getMonth() + 1) + '-' + two(d.getDate()) + 'T' +
      two(d.getHours()) + ':' + two(d.getMinutes()) + ':' + two(d.getSeconds()) +
      (offset < 0 ? '-' : '+') + two(Math.floor(abs / 60)) + ':' + two(abs % 60);
  }

  function two(n) { return (n < 10 ? '0' : '') + n; }

  /* What controls.js uses: the screen's reload when a refresh ends, the POST helper, the GET
     helper, the local-time helper and the phase numbers. */
  window.FairbandPage = {
    reload: load, api: api, getJson: getJson, localIso: localIso, PHASE_NUMBER: PHASE_NUMBER
  };

  function load() {
    var request = ++latest;
    var sort = state.sort;
    var key = SORT_KEYS[sort.column] || sort.column;
    getJson('/api/screen?sort=' + encodeURIComponent(key) + '&dir=' + sort.direction)
      .then(function (body) {
        if (request !== latest) return;
        state.rows = body.rows.map(localRow);
        state.error = null;
        render();
      })
      .catch(function (err) {
        if (request !== latest) return;
        state.error = 'The screen did not load: ' + err.message + '. Reload the page to try again.';
        render();
      });
  }

  /* A row with its entered time in the reader's offset, so the Entered cell shows the local date
     (the local-offset ISO in datetime) and agrees with the drawer's ValidityWindow. */
  function localRow(r) {
    return r.enteredAt ? Object.assign({}, r, { enteredAt: localIso(r.enteredAt) }) : r;
  }

  /* A header click, or Enter or Space on a focused header: the sorted column turns its
     direction; another column sorts ascending. */
  function sortBy(column) {
    var turn = state.sort.column === column && state.sort.direction === 'asc';
    state.sort = { column: column, direction: turn ? 'desc' : 'asc' };
    render();
    load();
  }

  /* A row click, or Enter or Space on a focused row. The previous company stays in the drawer,
     faded, until the new one lands. */
  function open(row) {
    var d = state.drawer;
    if (d && d.symbol === row.ticker && !d.error) return;
    var request = ++latestDetail;
    state.drawer = { symbol: row.ticker, body: d && d.body, loading: true, error: null };
    render();
    getJson('/api/companies/' + encodeURIComponent(row.ticker))
      .then(function (body) {
        if (request !== latestDetail) return;
        state.drawer = { symbol: row.ticker, body: body, loading: false, error: null };
        render();
      })
      .catch(function (err) {
        if (request !== latestDetail) return;
        state.drawer = {
          symbol: row.ticker, body: null, loading: false,
          error: 'The detail for ' + row.ticker + ' did not load: ' + err.message +
            '. Open the row again to retry.'
        };
        render();
      });
  }

  function close() {
    latestDetail++;
    state.drawer = null;
    render();
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && state.drawer) close();
  });

  /* ------------------------------------------------------- find and filters */

  /* The stance column's rule (the bundle's stanceOf with its fairband patch): a row without a
     price or levels has no stance, so a stance filter drops it; else buy below the buy level,
     trim at or above the trim level, hold between. */
  function stanceOf(r) {
    if (r.price == null || r.buyLevel == null || r.trimLevel == null) return null;
    if (r.price < r.buyLevel) return 'buy';
    if (r.price >= r.trimLevel) return 'trim';
    return 'hold';
  }

  /* An empty group narrows nothing; a non-empty one keeps only the rows whose value it names. */
  function within(list, value) { return !list.length || list.indexOf(value) !== -1; }

  /* The design system's reference rule (the gallery's apply). ScreenTable narrows nothing, so the
     page keeps the rows it loaded and draws the ones that pass; the server's order stands. The
     ticker matches by prefix and the name anywhere. A field a row lacks matches no filter: a
     placeholder has no stance or phase, and may have no sector or cap. The row's phase is
     already the menu's number (the server maps the engine's phase name through PHASE_NUMBER),
     and its cap band is the menu's id once lower-cased (Mega is mega); small never matches, the
     universe's floor being $2 bn. */
  function narrow(rows, query, filters) {
    var needle = (query || '').trim().toLowerCase();
    return rows.filter(function (r) {
      var found = !needle || r.ticker.toLowerCase().indexOf(needle) === 0 ||
        (r.name || '').toLowerCase().indexOf(needle) !== -1;
      return found &&
        within(filters.stance, stanceOf(r)) &&
        within(filters.phase, r.phase) &&
        within(filters.cap, (r.capBand || '').toLowerCase()) &&
        within(filters.sector, r.sector) &&
        (!filters.reviewedOnly || r.reviewed != null) &&
        (!filters.hideExpired || r.freshness !== 'expired');
    });
  }

  /* The menu's sectors: the screener's names found on the loaded rows, sorted, rather than the
     GICS names the design system lists by default. */
  function sectorsOf(rows) {
    var seen = {};
    rows.forEach(function (r) { if (r.sector != null) seen[r.sector] = true; });
    return Object.keys(seen).sort();
  }

  function note(text) { return h('p', { className: 'body app-note' }, text); }

  function render() {
    var d = state.drawer;
    var main = null;
    if (state.error) {
      main = note(state.error);
    } else if (state.rows && state.rows.length === 0) {
      main = note('No snapshots yet. Run a refresh.');
    } else if (state.rows) {
      /* A narrowing that leaves no row still draws the table: its bar says 0 of the total and
         offers Clear. The drawer stays open when its row is narrowed away. */
      var rows = narrow(state.rows, state.query, state.filters);
      main = h(F.ScreenTable, {
        rows: d ? rows.map(function (r) {
          return r.ticker === d.symbol ? Object.assign({}, r, { selected: true }) : r;
        }) : rows,
        total: state.rows.length,
        query: state.query,
        onQueryChange: setQuery,
        filters: state.filters,
        onFiltersChange: setFilters,
        sectors: sectorsOf(state.rows),
        columns: state.columns,
        onColumnsChange: setColumns,
        sort: state.sort,
        onSort: sortBy,
        onOpen: open,
        chooser: true
      });
    }
    root.render(h('div', { className: d ? 'app-layout app-layout--drawer' : 'app-layout' },
      h('div', { className: 'app-main' }, main),
      d ? drawer(d) : null));
  }

  /* ------------------------------------------------------------------ the drawer */

  function drawer(d) {
    var content;
    if (d.error) content = note(d.error);
    else if (d.body) content = sections(d.body);
    else content = h('h2', { className: 'ticker app-drawer__ticker' }, d.symbol);
    return h('aside', { className: 'app-drawer', 'aria-label': 'Detail for ' + d.symbol },
      h('div', { className: 'app-drawer__bar' },
        h(F.Button, { variant: 'quiet', size: 'sm', onClick: close }, 'Close')),
      h('div', { className: d.loading ? 'app-drawer__body is-loading' : 'app-drawer__body' },
        content));
  }

  function sections(body) {
    var r = body.result;
    var phase = PHASE_NUMBER[r.phase.phase];
    var valued = r.value != null && r.levels != null && r.price != null;
    var estimates = r.inputs.filter(function (i) { return i.kind === 'estimate'; });
    return [
      h('header', { key: 'head', className: 'app-drawer__head' },
        h('h2', { className: 'ticker app-drawer__ticker' }, r.symbol),
        phase ? h(F.PhaseBadge, { phase: phase, size: 'sm' }) : null,
        body.company && body.company.name
          ? h('p', { className: 'body app-drawer__name' }, body.company.name) : null),
      valued ? section('band', null,
        h(F.BandMeter, {
          low: r.levels.fair_low, high: r.levels.fair_high, price: r.price, fairValue: r.value,
          buyLevel: r.levels.buy, trimLevel: r.levels.trim, caption: ROUTES[r.route] || r.route
        }),
        crossCheck(r.intermediates.growth_route),
        r.stance5 ? h('p', { className: 'caption app-muted' }, 'Five-step stance: ' + r.stance5)
          : null) : null,
      /* A refusal takes the band's place: it is the answer when there is no value. */
      r.refusal ? section('refusal', 'Refusal',
        h('p', { className: 'body app-refusal' }, r.refusal)) : null,
      section('window', null, h(F.ValidityWindow, {
        asOf: r.data_date, observedAt: r.data_date,
        enteredAt: localIso(body.snapshot.createdAt),
        validFrom: r.data_date, validUntil: r.valid_until, today: body.today
      })),
      section('phase', 'Phase evidence', pairs(evidence(r.phase, phase))),
      section('inputs', 'Inputs', inputsTable(r.inputs)),
      section('intermediates', 'Intermediate results', intermediates(r.intermediates)),
      section('flags', 'Flags', r.flags.length ? h('ul', { className: 'app-list' },
        r.flags.map(function (f) {
          return h('li', { key: f.code },
            h('span', { className: 'label' }, f.word),
            h('p', { className: 'body' }, f.sentence));
        })) : h('p', { className: 'caption app-muted' }, 'none')),
      estimates.length ? section('estimates', 'Estimates', h('ul', { className: 'app-list' },
        estimates.map(function (i) {
          return h('li', { key: i.name },
            h('span', { className: 'figure-sm' }, i.name),
            h('p', { className: 'body' }, i.estimate_method || 'no method recorded'));
        }))) : null,
      h('p', { key: 'versions', className: 'caption app-muted app-section' },
        'Policy ' + r.policy_version + ' · method ' + r.method_version)
    ];
  }

  /* A Mature Stable row's growth-route value, under the band (calibration spec 5.7); a refused
     cross-check shows only among the intermediates. */
  function crossCheck(g) {
    if (!g || g.value_per_share == null) return null;
    return h('p', { className: 'caption app-muted' }, 'Growth-route cross-check: ' +
      F.formatMoney(g.value_per_share) + ' (implied growth ' + F.formatPercent(g.implied_growth) +
      ')');
  }

  function section(key, title) {
    var head = title ? h('h3', { className: 'heading' }, title) : null;
    return h.apply(null, ['section', { key: key, className: 'app-section' }, head]
      .concat(Array.prototype.slice.call(arguments, 2)));
  }

  /* [label, value, numeric] rows as a two-column list; numbers in mono, words in sans. */
  function pairs(rows) {
    return h('dl', { className: 'app-pairs' }, rows.map(function (row) {
      return h(React.Fragment, { key: row[0] },
        h('dt', { className: 'caption' }, row[0]),
        h('dd', { className: row[2] ? 'figure-sm' : 'body' }, row[1]));
    }));
  }

  function evidence(p, phase) {
    var rows = [['Phase', phase ? F.PHASES[phase] : '—', false]];
    if (p.reason) rows.push(['Reason', p.reason, false]);
    return rows.concat([
      ['Revenue growth, 3 years', F.formatPercent(p.growth_3y), true],
      ['Growth word', (p.growth_word || '—') +
        (p.growth_decile == null ? '' : ' · decile ' + p.growth_decile), false],
      ['Operating margin', F.formatPercent(p.margin), true],
      ['Margin trend', (p.margin_slope == null ? '—'
        : F.formatPercent(p.margin_slope).replace('%', ' points a year')) +
        (p.margin_direction ? ' · ' + p.margin_direction : ''), false],
      ['Free cash flow', p.fcf_sign || '—', false],
      ['Dickinson stage', p.dickinson || '—', false],
      ['Checks', p.checks.length
        ? p.checks.map(function (c) { return c.word; }).join(' · ') : 'none', false]
    ]);
  }

  /* ---------------------------------------------------------------- the inputs */

  /* A date as it is; a timestamp in the reader's local time. */
  function when(iso) {
    if (!iso) return '—';
    var local = localIso(iso);
    return h('time', { dateTime: local, title: local }, F.formatDate(local));
  }

  /* A minus is U+2212; a negative that rounds to zero loses its sign. */
  function minus(s) { return /^-[0.,]*$/.test(s) ? s.slice(1) : s.replace(/^-/, '−'); }

  function decimals(v, dp) {
    return minus(Number(v).toLocaleString('en-US',
      { minimumFractionDigits: dp, maximumFractionDigits: dp }));
  }

  /* A count: whole numbers as they are (a year stays 2027), separated from 10,000 up. */
  function plain(v) {
    var n = Number(v);
    if (Number.isInteger(n) && Math.abs(n) < 10000) return minus(String(n));
    return decimals(n, Number.isInteger(n) ? 0 : 2);
  }

  /* A total in whole dollars, with separators: $5,900,000,000. */
  function dollars(v) { return (v < 0 ? '−$' : '$') + decimals(Math.abs(v), 0); }

  /* By unit: a price to cents, a total to whole dollars, a ratio to one decimal of a percent.
     A price and a total share the unit USD; a price is under a million. */
  function inputValue(i) {
    if (i.value == null) return '—';
    if (i.unit === 'USD a share') return F.formatMoney(i.value);
    if (i.unit === 'USD') return Math.abs(i.value) < 1e6 ? F.formatMoney(i.value) : dollars(i.value);
    if (i.unit === 'ratio') return F.formatPercent(i.value);
    return plain(i.value);
  }

  /* Each input on one row, its nine fields stacked so they fit the rail: the name, tag, kind and
     source, then the three dates in caption, and the value with its unit on the right. */
  function inputsTable(inputs) {
    return h('table', { className: 'fb-table app-inputs' },
      h('thead', null, h('tr', null,
        h('th', { className: 'label' }, 'Input'),
        h('th', { className: 'label fb-num' }, 'Value'))),
      h('tbody', null, inputs.map(function (i) {
        var p = i.provenance;
        return h('tr', { key: i.name },
          h('td', null,
            h('span', { className: 'app-line' },
              h('span', { className: 'figure-sm' }, i.name), ' ',
              h('code', { className: 'fb-tag figure-sm' }, i.tag)),
            h('span', { className: 'caption app-line' },
              (i.estimate_method ? i.kind + ' (' + i.estimate_method + ')' : i.kind) +
              ' · ' + p.source),
            i.note ? h('span', { className: 'caption app-muted app-line' }, i.note) : null,
            h('span', { className: 'caption app-muted app-line' },
              h('span', { className: 'app-nowrap' }, 'as of ', when(p.as_of)), ' · ',
              h('span', { className: 'app-nowrap' }, 'observed ', when(p.observed_at)), ' · ',
              h('span', { className: 'app-nowrap' }, 'entered ', when(p.entered_at)))),
          h('td', { className: 'fb-num' },
            h('span', { className: 'figure-sm app-line' }, inputValue(i)),
            h('span', { className: 'caption app-muted app-line' }, i.unit)));
      })));
  }

  /* ---------------------------------------------------------- the intermediates */

  /* A number's key says what it is. A key ending in one of these names a fraction, which reads
     as a percentage; so do the fractions those endings miss (the implied-growth maps, the price
     changes, the drawdown, the path steps, the growth rates, the growth share). A dollar amount
     or a count whose key happens to end the same way (value_by_roic, stable_growth, roic's years)
     does not. A map keyed by runway years or by ROIC values takes its own key's reading, and so
     does a bare value (runway_return's). */
  var PERCENT = /(_growth|_yield|_return|margin|roic|belief)$/;
  var ALSO_PERCENT = /^(implied_|change_|drawdown|path_steps$|growth_rates$|growth_share$)/;
  var NOT_PERCENT = /^(value_|stable_growth|years?$)/;
  /* Counts and years read whole. P/E multiples to one decimal with x. A figure a share (EPV, the
     value, EPS, the non-recurring gap, the 52-week prices, the value maps by runway and by ROIC,
     whatever the entry's key) reads to cents; a total (NOPAT, invested capital, net income,
     earnings, anything at a million or more) to whole dollars. Any other number to two
     decimals. */
  var COUNT = /^(years?|base_year|runway|fade_years|analysts|shares)$/;
  var MULTIPLE = /^pe_/;
  var PER_SHARE = /^(epv|value_per_share|stable_growth|nri_gap|ntm_eps.*|.*_per_share|.*_52w)$/;
  var PER_SHARE_GROUP = /^(eps$|value_by_)/;
  var TOTAL = /(_total|nopat|average_capital|net_income)$|^e_/;

  function figure(v, key, group) {
    if (isPercent(key, group)) return F.formatPercent(v);
    if (PER_SHARE_GROUP.test(group || '')) return F.formatMoney(v);  /* value_by_roic's runway */
    if (COUNT.test(key)) return plain(v);
    if (MULTIPLE.test(key)) return decimals(v, 1) + 'x';
    if (PER_SHARE.test(key)) return F.formatMoney(v);
    if (TOTAL.test(key) || Math.abs(v) >= 1e6) return dollars(v);
    return decimals(v, 2);
  }

  function isPercent(key, group) {
    if (NOT_PERCENT.test(key)) return false;
    if (PERCENT.test(key) || ALSO_PERCENT.test(key)) return true;
    return !!group && !NOT_PERCENT.test(group) && (PERCENT.test(group) || ALSO_PERCENT.test(group));
  }

  function isTable(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }

  /* One value as text: null an em dash, a number by its key, a list inline (a list of tables one
     table a line, its year first), a deeper table inline. */
  function shown(v, key, group) {
    if (v == null) return '—';
    if (typeof v === 'number') return figure(v, key, group);
    if (Array.isArray(v)) {
      if (!v.some(isTable)) return v.map(function (x) { return shown(x, key, group); }).join(', ');
      return v.map(function (x, n) {
        return h('span', { key: n, className: 'app-line' }, shown(x, key, group));
      });
    }
    if (isTable(v)) {
      return Object.keys(v).sort(function (a, b) { return (b === 'year') - (a === 'year'); })
        .map(function (k) { return k + ' ' + shown(v[k], k, key); }).join(' · ');
    }
    return String(v);
  }

  /* One group per top-level key: a table's entries, with a nested table flattened one level. */
  function intermediates(im) {
    return Object.keys(im).map(function (key) {
      var v = im[key];
      var rows = [];
      if (!isTable(v)) {
        rows.push([key, shown(v, key, null), true]);
      } else {
        Object.keys(v).forEach(function (k) {
          if (!isTable(v[k])) return rows.push([k, shown(v[k], k, key), true]);
          Object.keys(v[k]).forEach(function (kk) {
            rows.push([k + '.' + kk, shown(v[k][kk], kk, k), true]);
          });
        });
      }
      return h('div', { key: key, className: 'app-group' },
        isTable(v) ? h('h4', { className: 'label app-group__head' }, key) : null,
        pairs(rows));
    });
  }

  render();
  load();
})();
