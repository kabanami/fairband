/* The Settings view (spec 2026-11-04 8.5), loaded after watchlists.js. One form from
   GET /api/settings: the five groups of 8.2 in order, each setting a row. A row holds the label
   and the sentence of what the value does, the default with its source line's first clause and
   when a change takes effect; at its right the field or fields with the unit, the word changed
   while the user holds a value for it, Reset while it differs from its default, the range, and a
   refused save's sentence. Above the form, one notice from valuedUnder and current; under it, the
   Reason field and Save, which shows the changes, old to new, in the design system's
   ConfirmDialog and sends them in one PUT. While a stored setting is one the policy refuses, the
   server answers 409: the view shows its sentence and Reset all settings, and nothing else. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  /* What a figure carries, by unit. A unit led by a space is a word: it follows a field, or a
     list of figures, once. The others follow each figure; a dollar amount leads its figure, which
     a field holds in billions. */
  var UNITS = { fraction: '%', points: ' points', years: ' years', times: '×', days: ' days', seconds: ' s', hours: ' h', count: '', usd: '$' };
  /* The groups of spec 8.2, A to E, by the API's names. */
  var HEADS = {
    valuation: 'Valuation', flags: 'Flags', validity: 'Validity', universe: 'Universe',
    refresh: 'Refresh'
  };
  var EFFECTS = {
    revalue: 'takes effect at the next revalue', full: 'takes effect at the next full refresh',
    run: 'takes effect at the next refresh', 'at once': 'takes effect at once'
  };
  var MOATS = ['None', 'Narrow', 'Wide'];
  var EXCHANGES = ['NYSE', 'NASDAQ', 'AMEX'];
  var BANDS = ['Mega', 'Large', 'Mid'];
  /* The two-value settings' fields, in the order the policy holds the pair. */
  var PAIRS = { fair_band: ['low', 'high'], roic_sensitivity: ['high', 'low'] };
  var NUMBER = /^[-+]?(\d+\.?\d*|\.\d+)$/;
  var SAVE = ''; /* the key of a sentence about the save as a whole, not one setting */
  var RUN_MS = 1000; /* how often the open view asks whether a refresh runs */
  var AGAIN = 'Reload the page to try again.';

  var panel = document.getElementById('settings');
  var root = ReactDOM.createRoot(panel);
  var state = {
    body: null, /* the form as GET /api/settings serves it */
    refused: null, /* the 409's sentence, while a stored setting is one the policy refuses */
    failed: null, /* why the form did not load */
    draft: {}, /* the values typed and not saved, by setting; only those unlike the saved one */
    text: {}, /* a field's text as typed, by field key, so the field never rewrites it */
    bad: {}, /* a setting with a field that does not read as a number */
    error: {}, /* a refused save's sentence, by setting, or under SAVE */
    confirm: null, /* [{ name, from, to }] while the dialog is open */
    saving: false, /* the PUT or the reset in flight */
    reason: '',
    starting: false, /* Revalue now's POST in flight */
    started: null, /* what Revalue now came to, when the revalue did not start */
    focus: null /* a selector in the view that takes focus once the view has drawn */
  };
  var latest = 0;

  /* ----------------------------------------------------------------- the load */

  /* The form, or the 409's sentence; the drafts stay, and are read against the new values. */
  function load() {
    var request = ++latest;
    fetch('/api/settings').then(function (response) {
      return response.json().then(function (body) {
        return { ok: response.ok, status: response.status, body: body };
      });
    }).then(function (r) {
      if (request !== latest) return;
      state.started = null;
      if (r.ok) {
        state.body = r.body;
        state.refused = null;
        state.failed = null;
      } else if (r.status === 409) {
        state.refused = detailOf(r);
      } else {
        state.failed = 'The settings did not load: ' + detailOf(r) + '. ' + AGAIN;
      }
      render();
    }).catch(function (err) {
      if (request !== latest) return;
      state.failed = 'The settings did not load: ' + err.message + '. ' + AGAIN;
      render();
    });
  }

  function detailOf(r) {
    return r.body && typeof r.body.detail === 'string' ? r.body.detail
      : 'the server answered ' + r.status;
  }

  /* ------------------------------------------------------- values and words */

  function all() {
    return state.body.groups.reduce(function (list, g) { return list.concat(g.settings); }, []);
  }

  function find(name) {
    return state.body ? all().filter(function (s) { return s.name === name; })[0] : null;
  }

  /* Two values alike, a table by moat in any key order. */
  function same(a, b) {
    if (a === b) return true;
    if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return false;
    var keys = Object.keys(a);
    return keys.length === Object.keys(b).length &&
      keys.every(function (k) { return same(a[k], b[k]); });
  }

  /* The value a setting's fields show: the draft, else the saved value. */
  function held(s) { return s.name in state.draft ? state.draft[s.name] : s.value; }

  /* The changes a save would send: each draft unlike its saved value. */
  function edits() {
    return state.body ? all().filter(function (s) {
      return s.name in state.draft && !same(state.draft[s.name], s.value);
    }).map(function (s) {
      return { name: s.name, from: s.value, to: state.draft[s.name] };
    }) : [];
  }

  /* A table by moat: an object that is not a list (a symbol list is one field). */
  function byMoat(s) {
    return !!s.value && typeof s.value === 'object' && !Array.isArray(s.value);
  }

  /* A numeric setting's fields: one, two for a pair, three by moat or for the cap bands, each
     with its name and the unit its figure is in; a list's one field has no name. */
  function partsOf(s) {
    if (s.unit === 'cap_bands') return { names: BANDS, unit: 'usd' };
    if (PAIRS[s.name]) return { names: PAIRS[s.name], unit: s.unit };
    if (byMoat(s)) return { names: MOATS, unit: s.unit };
    return { names: [null], unit: s.unit };
  }

  function partOf(s, v, i) {
    if (s.unit === 'cap_bands') return v[i][0];
    if (PAIRS[s.name]) return v[i];
    if (byMoat(s)) return v[MOATS[i]];
    return v;
  }

  function fromParts(s, figures) {
    if (s.unit === 'cap_bands') return BANDS.map(function (b, i) { return [figures[i], b]; });
    if (PAIRS[s.name]) return figures;
    if (byMoat(s)) {
      var table = {};
      MOATS.forEach(function (m, i) { table[m] = figures[i]; });
      return table;
    }
    return figures[0];
  }

  /* A number with its decimal point moved by places, in the decimal it is written as: 0.0825
     moved 2 is 8.25, never 8.250000000000002, and nothing is rounded. */
  function shift(n, places) {
    var parts = String(n).split('e');
    return Number(parts[0] + 'e' + (Number(parts[1] || 0) + places));
  }

  /* A figure as its field holds it, at its own precision: a fraction as its percentage (9 for
     0.09, 8.25 for 0.0825), points as the number of points (4 for 0.04), a dollar amount in
     billions. */
  function fieldText(unit, n) {
    if (unit === 'fraction' || unit === 'points') return String(shift(n, 2));
    if (unit === 'usd') return String(shift(n, -9));
    return String(n);
  }

  /* A field's text as the figure it stands for; null when it is not a number. The decimal point
     moves in the text, so 66.7% is 0.667 exactly, and the field shows it back as 66.7. */
  function fromField(unit, text) {
    var t = text.trim();
    if (!NUMBER.test(t)) return null;
    if (unit === 'fraction' || unit === 'points') return Number(t + 'e-2');
    if (unit === 'usd') return Number(t + 'e9');
    return Number(t);
  }

  /* A figure as a caption and the confirm show it: as its field does, the thousands grouped. */
  function figure(unit, n) {
    return grouped(unit === 'fraction' || unit === 'points' ? shift(n, 2) : n);
  }

  function grouped(n) {
    var parts = String(n).split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return parts.join('.');
  }

  function amount(n) {
    return n < 1e9 ? '$' + grouped(shift(n, -6)) + ' m' : '$' + grouped(shift(n, -9)) + ' bn';
  }

  /* A value as the captions and the confirm show it: 9%, 4 points, 5, 10, 20 years, 0.85×,
     1.15×, $2 bn, V, MA, GPN; an empty list is none. */
  function shown(s, v) {
    if (s.unit === 'symbols' || s.unit === 'exchanges') return v.length ? v.join(', ') : 'none';
    var parts = partsOf(s);
    var figures = parts.names.map(function (_, i) { return partOf(s, v, i); });
    if (parts.unit === 'usd') return figures.map(amount).join(', ');
    var unit = UNITS[parts.unit] || '';
    var word = unit.charAt(0) === ' ';
    if (word && figures.length === 1 && figures[0] === 1 && unit.length > 2) {
      unit = unit.slice(0, -1); /* 1 year, 1 day, 1 point */
    }
    return figures.map(function (n) {
      return figure(parts.unit, n) + (word ? '' : unit);
    }).join(', ') + (word ? unit : '');
  }

  /* The source line's first clause, up to its first colon or semicolon. */
  function origin(source) {
    var clause = String(source || '').split(/[:;]/)[0].trim();
    if (!clause) return '';
    return clause === 'no source' ? ', no source' : ', from ' + clause;
  }

  /* ------------------------------------------------------------ the fields */

  function key(name, i) { return name + '/' + i; }

  function forget(name) {
    Object.keys(state.text).forEach(function (k) {
      if (k.indexOf(name + '/') === 0) delete state.text[k];
    });
    delete state.bad[name];
  }

  /* The setting's draft, unless it is the saved value; a refused save's sentence about it goes. */
  function setDraft(s, v) {
    if (same(v, s.value)) delete state.draft[s.name];
    else state.draft[s.name] = v;
    delete state.error[s.name];
  }

  /* A numeric field typed in: the setting's value from all its fields. A field whose text is the
     saved value's or the default's, as the field shows it, stands for that value, so a figure
     the field rounds (66.7 for two thirds) is never sent as changed. */
  function typeIn(s, i, text) {
    state.text[key(s.name, i)] = text;
    var parts = partsOf(s);
    var ok = true;
    var figures = parts.names.map(function (_, j) {
      var typed = state.text[key(s.name, j)];
      if (typed === undefined) return partOf(s, held(s), j);
      var known = [s.value, s.default].filter(function (v) {
        return typed.trim() === fieldText(parts.unit, partOf(s, v, j));
      })[0];
      if (known !== undefined) return partOf(s, known, j);
      var n = fromField(parts.unit, typed);
      if (n === null) ok = false;
      return n;
    });
    if (ok) {
      delete state.bad[s.name];
      setDraft(s, fromParts(s, figures));
    } else {
      state.bad[s.name] = true;
    }
    render();
  }

  /* The symbols, comma-separated, upper-cased; the server checks each. */
  function typeList(s, text) {
    state.text[key(s.name, 0)] = text;
    setDraft(s, text.split(/[\s,]+/).filter(Boolean).map(function (t) {
      return t.toUpperCase();
    }));
    render();
  }

  function toggle(s, exchange, on) {
    var now = held(s);
    setDraft(s, EXCHANGES.filter(function (x) {
      return x === exchange ? on : now.indexOf(x) !== -1;
    }));
    render();
  }

  /* Reset: the default in the draft, for Save to send; focus stays in the row. */
  function reset(s) {
    forget(s.name);
    setDraft(s, JSON.parse(JSON.stringify(s.default)));
    state.focus = inRow(s.name, 'input');
    render();
  }

  function inRow(name, selector) { return '[data-setting="' + name + '"] ' + selector; }

  /* ------------------------------------------------------------ the writes */

  function openConfirm() {
    if (!edits().length || Object.keys(state.bad).length || state.saving) return;
    state.confirm = edits();
    state.focus = '.app-dialog .fb-btn--quiet';
    render();
  }

  function cancelConfirm() {
    if (!state.confirm || state.saving) return;
    state.confirm = null;
    state.focus = '.app-set__save .fb-btn--primary';
    render();
  }

  /* Confirm: the changes and the reason in one PUT, all or none. Taken, the form is the answer
     and the screen loads again, its words read under the new settings; refused, the sentence
     "<name>: <rule>" stands beside that setting's field, the drafts kept. */
  function save() {
    var changes = {};
    state.confirm.forEach(function (c) { changes[c.name] = c.to; });
    var reason = state.reason.trim() || null;
    state.saving = true;
    state.error = {};
    render();
    P.api.put('/api/settings', { changes: changes, reason: reason }).then(function (r) {
      state.saving = false;
      state.confirm = null;
      if (r.ok) {
        latest++; /* a load begun before the save would answer with the old form */
        state.body = r.body;
        state.draft = {};
        state.text = {};
        state.bad = {};
        state.reason = '';
        state.focus = '.app-set__notice .fb-btn, .app-set__reason';
        P.reload();
      } else if (r.status === 409) {
        load();
      } else {
        var detail = detailOf(r);
        var name = detail.slice(0, detail.indexOf(':'));
        if (r.status === 400 && find(name)) {
          state.error[name] = detail;
          state.focus = inRow(name, 'input');
        } else {
          state.error[SAVE] = 'Not saved: ' + detail + '.';
          state.focus = '.app-set__save .fb-btn--primary';
        }
      }
      render();
    }).catch(function (err) {
      state.saving = false;
      state.confirm = null;
      state.error[SAVE] = 'Not saved: ' + err.message + '.';
      render();
    });
  }

  /* Reset all settings, under a 409: a reset with no names deletes every stored setting. */
  function resetAll() {
    state.saving = true;
    state.error = {};
    render();
    P.api.post('/api/settings/reset', {}).then(function (r) {
      state.saving = false;
      if (r.ok) {
        latest++;
        state.body = r.body;
        state.refused = null;
        state.draft = {};
        state.text = {};
        state.bad = {};
        P.reload();
      } else {
        state.error[SAVE] = 'Not reset: ' + detailOf(r) + '.';
      }
      render();
    }).catch(function (err) {
      state.saving = false;
      state.error[SAVE] = 'Not reset: ' + err.message + '.';
      render();
    });
  }

  /* Revalue now: a revalue the header then follows as it follows its own refreshes. */
  function revalue() {
    state.starting = true;
    state.started = null;
    render();
    P.api.post('/api/refresh', { kind: 'revalue' }).then(function (r) {
      state.starting = false;
      if (r.status === 409) state.started = 'A refresh is already running.';
      else if (r.status === 503) state.started = 'No refresh worker.';
      else if (!r.ok) state.started = 'Not started: ' + detailOf(r) + '.';
      if (r.ok || r.status === 409) P.followRefresh();
      render();
    }).catch(function (err) {
      state.starting = false;
      state.started = 'Not started: ' + err.message + '.';
      render();
    });
  }

  /* ------------------------------------------------------------------ the view */

  /* One of three notices: none while the screen's figures were valued under the current policy
     version and settings hash, or before any was valued; else the revalue's, with Revalue now,
     off while a refresh runs; else the universe's, when a universe setting changed since the
     latest full refresh began. Revalue now is the primary button until the form holds n changes,
     when Save is the one. */
  function notice(body, n) {
    var c = body.current;
    var v = body.valuedUnder;
    if (v.settingsHash != null && (v.settingsHash !== c.settingsHash ||
        v.policyVersion !== c.policyVersion)) {
      return h('div', { className: 'app-set__notice' },
        h('p', { className: 'caption' }, 'Your settings changed since the last valuation.'),
        h(F.Button, {
          variant: n ? 'secondary' : 'primary', size: 'sm',
          disabled: state.starting || P.running(), onClick: revalue
        }, 'Revalue now'),
        P.running() ? h('p', { className: 'caption app-muted' }, 'A refresh is running.') : null,
        state.started ? h('p', { className: 'caption app-set__started' }, state.started) : null);
    }
    if (v.universeChanged) {
      return h('div', { className: 'app-set__notice' }, h('p', { className: 'caption' },
        'A universe setting changed since the last full refresh: run Refresh all.'));
    }
    return null;
  }

  /* A numeric setting's fields: each part's name, when it has one, its field, and the unit; a
     word unit once after the last field, a dollar sign before each field. */
  function numberFields(s, invalid) {
    var parts = partsOf(s);
    var v = held(s);
    var unit = UNITS[parts.unit] || '';
    var word = unit.charAt(0) === ' ';
    var usd = parts.unit === 'usd';
    var last = parts.names.length - 1;
    return parts.names.map(function (name, i) {
      var typed = state.text[key(s.name, i)];
      return h('span', { key: i, className: 'app-set__part' },
        name ? h('span', { className: 'label app-set__partname', 'aria-hidden': 'true' }, name)
          : null,
        usd ? h('span', { className: 'control app-set__unit' }, unit) : null,
        h('input', {
          type: 'text', inputMode: 'decimal', autoComplete: 'off', spellCheck: false,
          id: i === 0 ? 'set-' + s.name : null,
          className: 'control app-field app-set__num',
          'aria-label': name ? s.label + ', ' + name : null,
          'aria-invalid': invalid ? 'true' : null,
          value: typed !== undefined ? typed : fieldText(parts.unit, partOf(s, v, i)),
          onChange: function (event) { typeIn(s, i, event.target.value); }
        }),
        usd && i === last ? h('span', { className: 'control app-set__unit app-set__end' }, ' bn')
          : null,
        !usd && !word && i !== last && unit ?
          h('span', { className: 'control app-set__unit' }, unit) : null,
        !usd && i === last ? end(unit) : null);
    });
  }

  /* The unit after a row's last field, in a slot as wide in every row, so the fields' right
     edges line up down the form; empty where the row has no unit. */
  function end(unit) {
    return h('span', { key: 'end', className: 'control app-set__unit app-set__end' }, unit);
  }

  function fields(s, invalid) {
    if (s.unit === 'exchanges') {
      var on = held(s);
      return [h('span', {
        key: 'x', className: 'app-set__part', role: 'group', 'aria-label': s.label
      }, EXCHANGES.map(function (x) {
        return h('label', { key: x, className: 'control app-set__check' },
          h('input', {
            type: 'checkbox', checked: on.indexOf(x) !== -1,
            onChange: function (event) { toggle(s, x, event.target.checked); }
          }), x);
      })), end('')];
    }
    if (s.unit === 'symbols') {
      var typed = state.text[key(s.name, 0)];
      return [h('input', {
        key: 'x', type: 'text', id: 'set-' + s.name, autoComplete: 'off', spellCheck: false,
        className: 'control app-field app-set__list', 'aria-invalid': invalid ? 'true' : null,
        value: typed !== undefined ? typed : held(s).join(', '),
        onChange: function (event) { typeList(s, event.target.value); }
      }), end('')];
    }
    return numberFields(s, invalid);
  }

  /* A setting's row. The label names the one field it has; a row of several fields names each
     of them by the label and the part. Reset stands while the shown value differs from the
     default: a draft unlike it, or else a value the user holds. */
  function row(s) {
    var error = state.error[s.name];
    var bad = !!state.bad[s.name];
    var multi = s.unit === 'exchanges' || partsOf(s).names.length > 1;
    var off = bad || (s.name in state.draft ? !same(state.draft[s.name], s.default) : s.changed);
    var at = s.changedAt ? P.localIso(s.changedAt) : null;
    return h('div', { key: s.name, className: 'app-set__row', 'data-setting': s.name },
      h('div', { className: 'app-set__text' },
        multi ? h('span', { className: 'body app-set__label' }, s.label)
          : h('label', { className: 'body app-set__label', htmlFor: 'set-' + s.name }, s.label),
        h('p', { className: 'caption app-set__what' }, s.description),
        h('p', { className: 'caption app-set__meta' },
          'default ' + shown(s, s.default) + origin(s.source) + ' · ' +
          (EFFECTS[s.effect] || s.effect))),
      h('div', { className: 'app-set__edit' },
        h('div', { className: 'app-set__fields' },
          s.changed ? h('span', {
            className: 'caption app-set__changed',
            title: at ? 'changed ' + F.formatDate(at.slice(0, 10)) : null
          }, 'changed') : null,
          off ? h(F.Button, {
            size: 'sm', className: 'app-set__reset', onClick: function () { reset(s); }
          }, 'Reset') : null,
          fields(s, bad || !!error)),
        h('p', { className: 'caption app-set__range' }, s.range),
        bad ? h('p', { className: 'caption app-set__error' }, 'Enter a number in each field.')
          : null,
        error ? h('p', { className: 'caption app-set__error' }, error) : null));
  }

  function group(g) {
    return h('section', {
      key: g.name, className: 'app-set__group', 'aria-labelledby': 'set-group-' + g.name
    },
      h('h2', { id: 'set-group-' + g.name, className: 'title app-set__head' },
        HEADS[g.name] || g.name),
      g.settings.map(row));
  }

  /* Save's dialog, over the page: each change by its policy name, old to new, as the server will
     apply it, and the reason when there is one. Its note says what is true of a setting, that
     Reset undoes it. Escape, a press beside it and Cancel close it. */
  function dialog() {
    var n = state.confirm.length;
    var payload = state.confirm.map(function (c) {
      var s = find(c.name);
      return [c.name, shown(s, c.from) + ' → ' + shown(s, c.to)];
    });
    var reason = state.reason.trim();
    if (reason) payload.push(['reason', reason]);
    return h('div', {
      className: 'app-dialog',
      onPointerDown: function (event) {
        if (event.target === event.currentTarget) cancelConfirm();
      },
      onKeyDown: function (event) {
        if (event.key === 'Escape') cancelConfirm();
      }
    },
      h(F.ConfirmDialog, {
        title: 'Change ' + n + ' setting' + (n === 1 ? '' : 's'),
        note: 'Reset returns any setting to its default.',
        payload: payload,
        state: state.saving ? 'confirming' : 'open',
        onConfirm: save,
        onCancel: cancelConfirm
      }));
  }

  /* Under a 409, the sentence and the one way out. */
  function refusedView() {
    var error = state.error[SAVE];
    return h('div', { className: 'app-set' },
      h('p', { className: 'body app-set__refused' }, state.refused),
      h(F.Button, { onClick: resetAll, disabled: state.saving }, 'Reset all settings'),
      error ? h('p', { className: 'caption app-set__error' }, error) : null);
  }

  function saveLine(n, bad) {
    if (bad) return 'A field above does not read as a number.';
    return n ? n + ' unsaved change' + (n === 1 ? '' : 's') : 'No unsaved change.';
  }

  function View() {
    /* Focus moves where the last change asked, once the view has drawn. */
    React.useEffect(function () {
      if (!state.focus) return;
      var el = panel.querySelector(state.focus);
      state.focus = null;
      if (el) el.focus();
    });
    if (state.refused) return refusedView();
    if (!state.body) {
      return state.failed ? h('p', { className: 'body app-note app-set' }, state.failed) : null;
    }
    var n = edits().length;
    var bad = Object.keys(state.bad).length > 0;
    var error = state.error[SAVE];
    return h('form', {
      className: 'app-set', noValidate: true,
      onSubmit: function (event) { event.preventDefault(); openConfirm(); }
    },
      notice(state.body, n),
      state.failed ? h('p', { className: 'caption app-set__error' }, state.failed) : null,
      state.body.groups.map(group),
      h('div', { className: 'app-set__save' },
        h('input', {
          type: 'text', className: 'control app-field app-set__reason',
          placeholder: 'Reason (optional)', 'aria-label': 'Reason', maxLength: 200,
          value: state.reason,
          onChange: function (event) {
            state.reason = event.target.value;
            render();
          }
        }),
        h(F.Button, {
          type: 'submit', variant: 'primary', disabled: !n || bad || state.saving
        }, 'Save'),
        h('span', { className: 'caption app-muted' }, saveLine(n, bad)),
        error ? h('p', { className: 'caption app-set__error app-set__saveerror' }, error) : null),
      state.confirm ? dialog() : null);
  }

  function render() { root.render(h(View)); }

  /* While the view is open it asks whether a refresh runs: Revalue now turns off as a run starts,
     and when the run ends the form loads again, for the notice to say what the figures were
     valued under now. It stops asking once the view is closed. */
  var timer = null;
  var seen = false;
  function follow() {
    if (timer !== null) return;
    seen = P.running();
    timer = setInterval(function () {
      if (panel.hidden) {
        clearInterval(timer);
        timer = null;
        return;
      }
      var running = P.running();
      if (running === seen) return;
      seen = running;
      if (running) render();
      else load();
    }, RUN_MS);
  }

  /* The view loads as it opens, so the notice reads what ran while it was closed. */
  P.onShow.settings = function () {
    load();
    follow();
  };
})();
