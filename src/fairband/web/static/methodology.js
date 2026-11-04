/* The Methodology view (spec 2026-11-04 7), loaded after settings.js. On the view's first open the
   page fetches its fragment, methodology.html, the app's own static file, and inserts it into the
   panel. On every open it fills the fragment's live figures: each data-policy span from
   GET /api/policy by the value's unit, each data-count from GET /api/groups?by=phase (the universe
   from the screen's rows), each data-decile from GET /api/deciles. A figure that does not load
   keeps its em dash. Then it scrolls to the section the hash named. The contents, the bracketed
   sources and the Settings link open their place through FairbandPage.show; an example's Open
   today's row puts its symbol in FIND. The script draws nothing: the prose, the tables and the
   diagram are the fragment's. FairbandPage.methodologySection names the section of a route, for
   the drawer's link (spec 7.7). */
(function () {
  'use strict';

  var F = Fairband;
  var P = FairbandPage;
  var DASH = '—';
  /* The section that explains each of the engine's routes. */
  var SECTIONS = {
    'mature-growth': 'mature-growth', 'mature-stable': 'mature-stable',
    'revenue-growth': 'growth', 'decline': 'decline', 'start-up': 'start-up'
  };
  /* A value by its unit, as the page's prose reads it: a fraction as a percentage to one decimal,
     points and spans of time with their word, a multiple with ×, dollars in billions or millions,
     a count or a score as a plain number, a list of exchanges or symbols in words. A figure and
     its word are joined by a no-break space, so a line never parts them. */
  var FORMATS = {
    fraction: function (v) { return F.formatPercent(v); },
    points: function (v) { return counted(v * 100, 'point'); },
    years: function (v) { return counted(v, 'year'); },
    days: function (v) { return counted(v, 'day'); },
    hours: function (v) { return counted(v, 'hour'); },
    seconds: function (v) { return counted(v, 'second'); },
    times: function (v) { return number(v) + '×'; },
    usd: dollars,
    count: number,
    exchanges: function (v) { return listed(v, 'or'); },
    symbols: function (v) { return v.length ? listed(v, 'and') : 'none'; },
    cap_bands: function (v) {
      return v.map(function (band) { return band[1] + ' from ' + dollars(band[0]); }).join(', ');
    }
  };

  var panel = document.getElementById('methodology');
  var inserted = null; /* the fragment's load, once asked; asked again after a failure */
  var latest = 0;
  var jumping = false; /* a link inside the view moves to a section: scroll, load nothing */

  /* ----------------------------------------------------------------- the text */

  function number(v) {
    return Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 });
  }

  function counted(v, word) {
    var n = number(v);
    return n + '\u00a0' + word + (n === '1' ? '' : 's');
  }

  function dollars(v) {
    var n = Number(v);
    if (Math.abs(n) >= 1e9) return '$' + number(n / 1e9) + '\u00a0billion';
    if (Math.abs(n) >= 1e6) return '$' + number(n / 1e6) + '\u00a0million';
    return F.formatMoney(n);
  }

  /* NYSE, NASDAQ or AMEX. */
  function listed(items, word) {
    if (items.length < 2) return items.join('');
    return items.slice(0, -1).join(', ') + ' ' + word + ' ' + items[items.length - 1];
  }

  function format(unit, value) {
    var f = FORMATS[unit];
    return f && value != null ? f(value) : DASH;
  }

  /* A cited name's value: the name itself, or a name with a moat class or an index after its last
     dot (runway_years.Wide, fair_band.1). A name the response lacks has none. */
  function lookup(values, key) {
    if (values[key]) return { cited: values[key], value: values[key].value };
    var dot = key.lastIndexOf('.');
    var cited = dot > 0 ? values[key.slice(0, dot)] : null;
    var value = cited && cited.value != null ? cited.value[key.slice(dot + 1)] : undefined;
    return value === undefined ? null : { cited: cited, value: value };
  }

  function each(selector, fill) {
    Array.prototype.forEach.call(panel.querySelectorAll(selector), fill);
  }

  /* --------------------------------------------------------------- the figures */

  /* Every data-policy span by its value's unit; a setting the reader changed reads in accent. The
     version, and how many settings differ from the defaults when any does. */
  function fillPolicy(body) {
    each('[data-policy]', function (el) {
      var found = lookup(body.values, el.getAttribute('data-policy'));
      var changed = !!(found && found.cited.changed);
      el.textContent = found ? format(found.cited.unit, found.value) : DASH;
      el.classList.toggle('is-changed', changed);
      el.title = changed ? 'Your setting: it differs from the default' : '';
    });
    each('[data-policy-version]', function (el) { el.textContent = body.version; });
    each('[data-policy-changed]', function (el) {
      el.hidden = !body.changed;
      el.textContent = body.changed === 1 ? '1 setting differs from the defaults.'
        : number(body.changed) + ' settings differ from the defaults.';
    });
  }

  /* The decile edges, data-decile="1" to "9", and the companies they were read from, "n". */
  function fillDeciles(body) {
    each('[data-decile]', function (el) {
      var n = el.getAttribute('data-decile');
      var edge = n === 'n' ? body.n : body.edges[Number(n) - 1];
      el.textContent = edge == null ? DASH : n === 'n' ? number(edge) : F.formatPercent(edge);
    });
  }

  /* Each phase's companies, by the engine's phase name; the unclassified are the group without a
     phase; the universe is every row of the screen. */
  function fillCounts(groups, total) {
    var counts = {};
    if (groups) {
      groups.groups.forEach(function (g) {
        counts[g.name === 'none' ? 'unclassified' : g.name] = g.count;
      });
    }
    each('[data-count]', function (el) {
      var key = el.getAttribute('data-count');
      if (key === 'universe') {
        if (total != null) el.textContent = number(total);
      } else if (groups) el.textContent = number(counts[key] || 0);
    });
  }

  /* The screen's rows, once the Screen has them; else the view asks for them itself. */
  function universe() {
    var rows = P.rows();
    if (rows) return Promise.resolve(rows.length);
    return P.getJson('/api/screen').then(function (body) { return body.rows.length; });
  }

  /* The four answers in one pass, the last pass's only. A figure that fails keeps its em dash and
     the note at the head says which; the deciles answer 404 until a full refresh ranks the
     universe, which is no failure. Settles once the figures are in. */
  function fill() {
    var request = ++latest;
    var failed = [];
    function keep(what) {
      return function (err) {
        failed.push(what + ' (' + err.message + ')');
        return null;
      };
    }
    return Promise.all([
      P.getJson('/api/policy').catch(keep('the policy values')),
      P.getJson('/api/deciles').catch(function (err) {
        return /404/.test(err.message) ? null : keep('the decile edges')(err);
      }),
      P.getJson('/api/groups?by=phase').catch(keep('the phase counts')),
      universe().catch(keep('the universe'))
    ]).then(function (got) {
      if (request !== latest) return;
      if (got[0]) fillPolicy(got[0]);
      if (got[1]) fillDeciles(got[1]);
      fillCounts(got[2], got[3]);
      each('[data-live-note]', function (el) {
        el.hidden = !failed.length;
        el.textContent = failed.length ? 'Some live figures did not load: ' + failed.join(', ') +
          '. Open the view again to retry.' : '';
      });
    });
  }

  /* ------------------------------------------------------- the fragment and links */

  function fragment() {
    if (!inserted) {
      inserted = fetch('/static/methodology.html').then(function (response) {
        if (!response.ok) throw new Error('the server answered ' + response.status);
        return response.text();
      }).then(function (text) {
        panel.innerHTML = text;
      });
      inserted.catch(function () { inserted = null; });
    }
    return inserted;
  }

  /* The section the hash named, at the top of the panel. */
  function scrollToSection() {
    if (!P.section) return;
    var target = panel.querySelector('#' + CSS.escape(P.section));
    if (target) target.scrollIntoView({ block: 'start' });
  }

  /* A link inside the view: Open today's row finds its symbol on the Screen; a link to a place in
     the page (#methodology/<id>, #settings) opens it through show, so the hash names it and a
     section scrolls into view, a second press included. Other links leave the page as links do. */
  panel.addEventListener('click', function (event) {
    var target = event.target instanceof Element ? event.target : null;
    var row = target && target.closest('[data-find]');
    if (row) {
      event.preventDefault();
      P.find(row.getAttribute('data-find'));
      return;
    }
    var link = target && target.closest('a[href^="#"]');
    var place = link ? link.getAttribute('href').slice(1).split('/') : null;
    if (!place || !place[0]) return;
    event.preventDefault();
    jumping = place[0] === 'methodology';
    P.show(place[0], place[1]);
    jumping = false;
  });

  /* Each open: the fragment, once; the section; the live figures, each time, so a changed setting
     shows. The figures change the length of lines above the section, so once they are in the
     section is brought back to the top, unless the reader has scrolled meanwhile. A move inside
     the open view only scrolls. */
  P.onShow.methodology = function () {
    if (jumping) {
      scrollToSection();
      return;
    }
    fragment().then(function () {
      scrollToSection();
      var at = panel.scrollTop;
      fill().then(function () {
        if (panel.scrollTop === at) scrollToSection();
      });
    }, function (err) {
      var note = document.createElement('p');
      note.className = 'body app-note';
      note.textContent = 'The Methodology page did not load: ' + err.message +
        '. Open the view again to retry.';
      panel.replaceChildren(note);
    });
  };

  P.methodologySection = function (route) {
    return SECTIONS[route] || null;
  };
})();
