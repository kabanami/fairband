/* The Agents section of the Settings view (spec 2026-11-16 agent launch, 7.3 and 7.4), loaded
   before settings.js, which draws it after its own view and loads it as the view opens. One form
   from GET /api/launch-settings, with a save of its own: under the heading, the sentence of a
   launch.json the server cannot use and what to do about it; a row for each field, its label and
   the server's line of help at the left, its control at the right, a select for a field with
   choices and a text field for the rest, and a refused save's sentence under the field it names;
   Use the Windows Terminal line in the window command's row, where the server suggests one; then
   Save, which sends the changed names alone in one PUT, all or none, and Test, which posts a
   launch with no work item and reads it every 2 seconds while the page follows it, its line under
   the buttons. The section redraws through the Settings view's render, which settings.js hands to
   load and section. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var P = FairbandPage;
  var WINDOW = 'window_command';
  var SAVE = ''; /* the name of a refused save's sentence that names no field: beside Save */
  var READ_MS = 2000; /* how often a followed launch is read */
  var AGAIN = 'Reload the page to try again.';

  var state = {
    form: null, /* the form as GET /api/launch-settings serves it */
    failed: null, /* why the form did not load */
    draft: {}, /* the values typed and not saved, by name; only those unlike the saved one */
    error: null, /* a refused save: { name, sentence }, the name SAVE where it names no field */
    saving: false, /* the PUT in flight */
    testing: false, /* Test's POST in flight */
    launch: null, /* the test's launch, as the server last answered it */
    testError: null /* why the test did not start, or why its launch could not be read again */
  };
  var latest = 0;
  var timer = null; /* the one timer that reads the test's launch again */

  /* ----------------------------------------------------------------- the load */

  /* The form; the drafts stay, and are read against the new values. */
  function load(redraw) {
    var request = ++latest;
    P.getJson('/api/launch-settings').then(function (form) {
      if (request !== latest) return;
      state.form = form;
      state.failed = null;
      redraw();
    }).catch(function (err) {
      if (request !== latest) return;
      state.failed = 'The Agents section did not load: ' + err.message + '. ' + AGAIN;
      redraw();
    });
  }

  /* ------------------------------------------------------- values and words */

  /* The changes a save sends: each name whose draft is unlike the form's value, with its value. */
  function edits(form, draft) {
    var changes = {};
    if (!form) return changes;
    form.fields.forEach(function (field) {
      if (field.name in draft && draft[field.name] !== field.value) {
        changes[field.name] = draft[field.name];
      }
    });
    return changes;
  }

  function named(name) {
    return state.form.fields.filter(function (field) { return field.name === name; })[0] || null;
  }

  /* The value a field's control shows: the draft, else the saved value. */
  function held(field) {
    return field.name in state.draft ? state.draft[field.name] : field.value;
  }

  /* The field's draft, unless it is the saved value; a refused save's sentence about it goes. */
  function setDraft(field, value) {
    if (value === field.value) delete state.draft[field.name];
    else state.draft[field.name] = value;
    if (state.error && state.error.name === field.name) state.error = null;
  }

  /* The line of spec 7.4 for the test's launch, and whether it is a failure's, which takes the
     error style: the overdue line is one, and so is an end with another exit code than 0. */
  function testLine(launch) {
    if (launch.state === 'opening') return { text: 'Opening a window…', failed: false };
    if (launch.state === 'opened') {
      return launch.overdue ? {
        text: 'The window opened, but nothing in it reported after 90 seconds. Check the window.',
        failed: true
      } : { text: 'The window opened, Claude Code is starting…', failed: false };
    }
    if (launch.state === 'failed' && launch.stage === 'window') {
      return { text: 'Could not open the window: ' + launch.detail + '.', failed: true };
    }
    if (launch.state === 'failed') {
      return {
        text: 'The window opened, but Claude Code did not start: ' + launch.detail + '.',
        failed: true
      };
    }
    if (launch.state === 'started') {
      return {
        text: 'Claude Code started. Its window should say that the Fairband research skill is ' +
          'loaded.',
        failed: false
      };
    }
    if (launch.exitCode === 0) return { text: 'Claude Code ended (exit code 0).', failed: false };
    return {
      text: 'Claude Code ended (exit code ' + launch.exitCode + '). Check the window.',
      failed: true
    };
  }

  /* ------------------------------------------------------------ the writes */

  /* Use the Windows Terminal line: the server's line in the window command's draft; nothing is
     saved until Save. */
  function useSuggested(redraw) {
    setDraft(named(WINDOW), state.form.suggested);
    redraw();
  }

  /* Save: the changed names alone, in one PUT, all or none. Taken, the form is the answer and the
     draft is cleared; refused, the server's "<name>: <rule>" stands under the field it names, or,
     where the words before its first colon name no field, "Not saved: <the server's sentence>."
     stands beside Save, as the valuation settings say it (FairbandPage.refusal); a save that fails
     on the network is "Not saved: <the error>." there too. */
  function save(redraw) {
    if (state.saving) return;
    state.saving = true;
    state.error = null;
    redraw();
    P.api.put('/api/launch-settings', { changes: edits(state.form, state.draft) })
      .then(function (r) {
        state.saving = false;
        if (r.ok) {
          latest++; /* a load begun before the save would answer with the old form */
          state.form = r.body;
          state.draft = {};
        } else {
          var detail = P.refusalDetail(r);
          var cut = detail.indexOf(': ');
          var name = cut > 0 ? detail.slice(0, cut) : SAVE;
          state.error = named(name) ? { name: name, sentence: detail }
            : { name: SAVE, sentence: P.refusal('Not saved', r) };
        }
        redraw();
      }).catch(function (err) {
        state.saving = false;
        state.error = { name: SAVE, sentence: 'Not saved: ' + err.message + '.' };
        redraw();
      });
  }

  /* Test: a launch with no work item. A 201 is the launch, which the section then follows; a
     refusal's sentence shows where the test's line shows. A test begun while an earlier one is
     followed stops following the earlier one first. */
  function startTest(redraw) {
    if (state.testing) return;
    stop();
    state.testing = true;
    state.launch = null;
    state.testError = null;
    redraw();
    P.api.post('/api/launches', { test: true }).then(function (r) {
      state.testing = false;
      if (r.ok) {
        state.launch = r.body;
        follow(redraw);
      } else {
        state.testError = P.refusalDetail(r);
      }
      redraw();
    }).catch(function (err) {
      state.testing = false;
      state.testError = err.message;
      redraw();
    });
  }

  /* While the page follows the test's launch (FairbandPage.following), it is read again
     READ_MS after the last answer and drawn each time: one timer at most, and none once the
     launch is no longer followed. An answer for an earlier test is dropped; a read that fails
     ends the following, and the test's line says that the launch could not be read and why, in
     the error style. */
  function follow(redraw) {
    stop();
    if (!P.following(state.launch)) return;
    var id = state.launch.id;
    timer = setTimeout(function () {
      timer = null;
      P.getJson('/api/launches/' + id).then(function (launch) {
        if (!state.launch || state.launch.id !== id) return;
        state.launch = launch;
        follow(redraw);
        redraw();
      }).catch(function (err) {
        if (!state.launch || state.launch.id !== id) return;
        state.testError = 'The test\'s launch could not be read: ' + err.message + '.';
        redraw();
      });
    }, READ_MS);
  }

  function stop() {
    if (timer === null) return;
    clearTimeout(timer);
    timer = null;
  }

  /* ------------------------------------------------------------------ the view */

  /* A field's control, with its label's id and its help tied to it, and the refused save's
     sentence when there is one: a select whose first choice is empty for a field with choices,
     else a text field, wide enough for the window command's one line. A text field with
     suggestions (the model's aliases) names a list of them: the browser offers each and still
     takes any other text. Only a field without them turns the browser's own offers off, since in
     some browsers that setting hides a list too. */
  function control(field, id, error, redraw) {
    var props = {
      id: id, className: 'control app-field app-agents__' + (field.choices ? 'choice' : 'text'),
      'aria-describedby': id + '-help' + (error ? ' ' + id + '-error' : ''),
      'aria-invalid': error ? 'true' : null,
      value: held(field),
      onChange: function (event) {
        setDraft(field, event.target.value);
        redraw();
      }
    };
    if (field.choices) {
      return h('select', props,
        h('option', { value: '' }, 'Default'),
        field.choices.map(function (choice) {
          return h('option', { key: choice, value: choice }, choice);
        }));
    }
    var text = Object.assign({ type: 'text', spellCheck: false }, props);
    if (!field.suggestions) {
      text.autoComplete = 'off';
      return h('input', text);
    }
    return h(React.Fragment, null,
      h('input', Object.assign({ list: id + '-list' }, text)),
      h('datalist', { id: id + '-list' },
        field.suggestions.map(function (suggestion) {
          return h('option', { key: suggestion, value: suggestion });
        })));
  }

  /* A field's row, laid out as a valuation setting's: the label and its line of help at the
     left; at the right the control, Use the Windows Terminal line under the window command's,
     and a refused save's sentence about the field. */
  function row(field, redraw) {
    var id = 'agents-' + field.name;
    var error = state.error && state.error.name === field.name ? state.error.sentence : null;
    return h('div', { key: field.name, className: 'app-set__row', 'data-agent': field.name },
      h('div', { className: 'app-set__text' },
        h('label', { className: 'body app-set__label', htmlFor: id }, field.label),
        h('p', { id: id + '-help', className: 'caption app-set__what' }, field.help)),
      h('div', { className: 'app-set__edit' },
        h('div', { className: 'app-set__fields' }, control(field, id, error, redraw)),
        field.name === WINDOW && state.form.suggested !== null ? h(F.Button, {
          size: 'sm', className: 'app-agents__suggest',
          onClick: function () { useSuggested(redraw); }
        }, 'Use the Windows Terminal line') : null,
        error ? h('p', { id: id + '-error', className: 'caption app-set__error' }, error) : null));
  }

  /* Save and Test, a refused save's sentence that names no field, and the test's line. Save is
     off with no change, except where the server cannot use the file, which a save writes again;
     Test is off while a change is unsaved, since a test runs the saved values, while launching is
     not set up, and while its post is in flight. The test's line: the opening one while the post
     is in flight, else why the test did not start or could not be read, else the launch's. */
  function actions(form, redraw) {
    var changed = Object.keys(edits(form, state.draft)).length > 0;
    var saveError = state.error && state.error.name === SAVE ? state.error.sentence : null;
    var line = state.testing ? testLine({ state: 'opening' })
      : state.testError ? { text: state.testError, failed: true }
      : state.launch ? testLine(state.launch) : null;
    return h('div', { className: 'app-agents__actions' },
      h(F.Button, {
        type: 'submit', variant: 'primary', disabled: state.saving || (!changed && !form.fileError)
      }, 'Save'),
      h(F.Button, {
        disabled: changed || !form.ready || state.testing,
        onClick: function () { startTest(redraw); }
      }, 'Test'),
      saveError ? h('p', { className: 'caption app-set__error app-agents__line' }, saveError)
        : null,
      line ? h('p', {
        className: 'caption app-agents__line' + (line.failed ? ' app-set__error' : '')
      }, line.text) : null);
  }

  /* The section, once the form has loaded or failed to, and nothing before: the heading, why the
     form did not load, the file's fault with what to do about it, and the form. */
  function section(redraw) {
    var form = state.form;
    if (!form && !state.failed) return null;
    return h('section', { className: 'app-set app-agents', 'aria-labelledby': 'set-group-agents' },
      h('h2', { id: 'set-group-agents', className: 'title app-set__head' }, 'Agents'),
      state.failed ? h('p', { className: 'caption app-set__error' }, state.failed) : null,
      form && form.fileError ? h('div', { className: 'app-set__notice' },
        h('p', { className: 'caption app-set__error' }, form.fileError),
        h('p', { className: 'caption' },
          'Correct the file, or save here to write it again with the values shown.'))
        : null,
      form ? h('form', {
        noValidate: true,
        onSubmit: function (event) { event.preventDefault(); save(redraw); }
      },
        form.fields.map(function (field) { return row(field, redraw); }),
        actions(form, redraw)) : null);
  }

  P.agents = { load: load, section: section, edits: edits, testLine: testLine };
})();
