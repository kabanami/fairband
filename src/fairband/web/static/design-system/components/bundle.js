/* @ds-bundle: {"format":4,"namespace":"Fairband","components":[{"name":"ScreenTable"},{"name":"PhaseBadge"},{"name":"BandMeter"},{"name":"ValueCell"},{"name":"ValueBridge"},{"name":"ValidityWindow"},{"name":"PrincipalChip"},{"name":"BasisChip"},{"name":"OverrideRecord"},{"name":"ReportReader"},{"name":"ProposalCard"},{"name":"ConfirmDialog"},{"name":"TaggedInput"},{"name":"Button"},{"name":"BandHistory"},{"name":"HistoryBars"},{"name":"SpreadChart"},{"name":"SensitivityGrid"}]} */
(function (global) {
  'use strict';

  var React = global.React;
  var h = React.createElement;

  function cx() {
    var out = [];
    for (var i = 0; i < arguments.length; i++) if (arguments[i]) out.push(arguments[i]);
    return out.join(' ');
  }

  /* Damodaran's six life-cycle phases, in order. */
  var PHASES = {
    1: 'Start-up', 2: 'Young growth', 3: 'High growth',
    4: 'Mature growth', 5: 'Mature stable', 6: 'Decline'
  };

  /* One chip, one question.
     PRINCIPALS sit on a write and answer who did it.
     BASIS sits on a computed number and answers which inputs went in.
     They never share a chip: the engine is the author of both the mechanical
     and the reviewed number, so a principal cannot tell them apart. */
  var PRINCIPALS = {
    owner: { word: 'Owner', note: 'Written by you' },
    agent: { word: 'Agent', note: 'Written by an agent over MCP' },
    system: { word: 'System', note: 'Written by the system' }
  };
  var BASIS = {
    mechanical: { word: 'mechanical', note: 'Computed from the system’s own inputs only' },
    reviewed: { word: 'reviewed', note: 'Computed with one or more overrides inside' }
  };
  var GLYPH_INPUT = '◆';
  var GLYPH_DERIVED = 'ƒ';

  var FRESHNESS = {
    current: { word: 'Current', mark: '' },
    aging: { word: 'Aging — past two thirds of its validity window', mark: '!' },
    expired: { word: 'Expired — past the end of its validity window', mark: '×' }
  };

  var STANCE = { buy: 'Buy', hold: 'Hold', trim: 'Trim' };

  /* ------------------------------------------------------------- formatting */

  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  /* Reader view: 3 Dec 2026. The ISO string never leaves the markup — it rides
     in the datetime attribute and the title, so sorting, diffing and grepping
     are unaffected. Parsed by hand rather than via Date, which would shift the
     day across a timezone. */
  function readable(iso) {
    if (!iso) return '—';
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
    if (!m) return String(iso);
    var rest = String(iso).slice(10).trim();
    // fairband: a timestamp reads as its date; the full ISO stays in datetime and the title.
    if (rest.charAt(0) === 'T') rest = '';
    return Number(m[3]) + ' ' + MONTHS[Number(m[2]) - 1] + ' ' + m[1] + (rest ? ' ' + rest : '');
  }

  function DateText(props) {
    var iso = props.value;
    if (!iso) return h('span', { className: props.className }, '—');
    return h('time', {
      className: props.className,
      dateTime: String(iso),
      title: String(iso)
    }, readable(iso));
  }

  /* One currency, so the symbol goes in the text rather than in a caption. */
  function money(v) {
    if (v === null || v === undefined || isNaN(Number(v))) return '—';
    var n = Number(v);
    return (n < 0 ? '−$' : '$') + Math.abs(n).toFixed(2);
  }

  function signedMoney(v) {
    var n = Number(v);
    if (isNaN(n)) return '—';
    return (n > 0 ? '+$' : n < 0 ? '−$' : '$') + Math.abs(n).toFixed(2);
  }

  function pct(v, dp) { return v.toFixed(dp === undefined ? 1 : dp) + '%'; }

  function stanceOf(price, buyLevel, trimLevel) {
    if (buyLevel != null && price < buyLevel) return 'buy';
    if (trimLevel != null && price >= trimLevel) return 'trim';
    return 'hold';
  }

  function markFor(freshness) {
    return FRESHNESS[freshness] && freshness !== 'current' ? FRESHNESS[freshness].mark : '';
  }

  /* ---------------------------------------------------------------- Button */

  function Button(props) {
    var p = props || {};
    return h('button', {
      type: p.type || 'button',
      className: cx('fb-btn', 'control', 'fb-btn--' + (p.variant || 'secondary'),
        p.size === 'sm' && 'fb-btn--sm', p.className),
      disabled: !!p.disabled,
      onClick: p.onClick
    }, p.children);
  }

  /* ------------------------------------------------------------ PhaseBadge */

  function PhaseBadge(props) {
    var p = props || {};
    // fairband: a company with no phase has no badge, only an em dash; never "1 Start-up".
    if (p.phase == null) return h('span', { className: 'fb-screen__none' }, '—');
    var n = Number(p.phase);
    var name = p.label || PHASES[n] || ('Phase ' + n);
    return h('span', {
      className: cx('fb-phase', 'fb-phase--' + n, p.size === 'sm' && 'fb-phase--sm'),
      title: 'Life-cycle phase ' + n + ' of 6 — ' + name
    },
      h('span', { className: 'fb-phase__n figure-sm' }, n),
      p.showLabel === false ? null : h('span', { className: 'fb-phase__label label' }, name)
    );
  }

  /* --------------------------------------------------------- PrincipalChip */

  function PrincipalChip(props) {
    var p = props || {};
    var key = PRINCIPALS[p.principal] ? p.principal : 'system';
    var who = PRINCIPALS[key];
    return h('span', {
      className: cx('fb-chip', 'fb-chip--principal', p.weight === 'strong' && 'fb-chip--strong',
        p.compact && 'fb-chip--compact'),
      title: who.note + (p.actor ? ' (' + p.actor + ')' : '') + (p.reason ? ' — ' + p.reason : '')
    },
      h('span', { className: 'fb-chip__glyph', 'aria-hidden': 'true' }, GLYPH_INPUT),
      h('span', { className: 'fb-chip__who figure-sm' }, who.word),
      p.actor ? h('span', { className: 'fb-chip__role figure-sm' }, p.actor) : null,
      !p.compact && p.at ? h('span', { className: 'fb-chip__at caption' },
        h(DateText, { value: p.at })) : null
    );
  }

  /* ------------------------------------------------------------- BasisChip */

  function BasisChip(props) {
    var p = props || {};
    var key = BASIS[p.basis] ? p.basis : 'mechanical';
    return h('span', {
      className: cx('fb-chip', 'fb-chip--basis', 'fb-chip--' + key, p.compact && 'fb-chip--compact'),
      title: BASIS[key].note
    },
      p.showGlyph === false ? null
        : h('span', { className: 'fb-chip__glyph', 'aria-hidden': 'true' }, GLYPH_DERIVED),
      h('span', { className: 'fb-chip__basis label' }, BASIS[key].word)
    );
  }

  /* ------------------------------------------------------------- ValueCell */

  function ValueCell(props) {
    var p = props || {};
    var basis = BASIS[p.basis] ? p.basis : 'mechanical';
    var f = FRESHNESS[p.freshness] ? p.freshness : 'current';
    var dates = [];
    if (p.asOf) dates.push(['as of', p.asOf]);
    if (p.observedAt) dates.push(['observed', p.observedAt]);
    if (p.enteredAt) dates.push(['entered', p.enteredAt]);
    return h('span', {
      className: cx('fb-value', 'fb-value--' + f, 'fb-value--' + basis,
        p.emphasis === 'strong' && 'fb-value--strong',
        p.align === 'left' && 'fb-value--left'),
      title: BASIS[basis].note + (f === 'current' ? '' : ' · ' + FRESHNESS[f].word)
    },
      h('span', { className: 'fb-value__glyph', 'aria-hidden': 'true' }, GLYPH_DERIVED),
      h('span', { className: p.emphasis === 'strong' ? 'figure-lg' : 'figure' },
        p.format === 'plain' ? p.value : money(p.value)),
      p.showBasis === false ? null
        : h('span', { className: cx('fb-value__basis label', 'fb-value__basis--' + basis) },
            BASIS[basis].word),
      f === 'current' ? null : h('span', {
        className: 'fb-mark fb-mark--' + f, title: FRESHNESS[f].word
      }, FRESHNESS[f].mark),
      dates.length && p.showDates ? h('span', { className: 'fb-value__dates caption' },
        dates.map(function (d, i) {
          return h(React.Fragment, { key: d[0] },
            i ? ' · ' : null, d[0] + ' ', h(DateText, { value: d[1] }));
        })) : null
    );
  }

  /* ----------------------------------------------------------- ValueBridge */

  /* The one place the two chip families meet: a walk from the mechanical
     number to the reviewed one, one line per override. */
  function ValueBridge(props) {
    var p = props || {};
    var overrides = p.overrides || [];
    return h('div', { className: 'fb-bridge' },
      h('table', { className: 'fb-bridge__t' },
        h('thead', null, h('tr', null,
          h('th', { className: 'label', 'aria-label': 'Glyph' }),
          h('th', { className: 'label' }, 'Line'),
          h('th', { className: 'label' }, 'Who or which'),
          h('th', { className: 'label fb-num' }, 'Value')
        )),
        h('tbody', null,
          h('tr', null,
            h('td', { className: 'fb-bridge__g fb-bridge__g--f', 'aria-hidden': 'true' }, GLYPH_DERIVED),
            h('td', { className: 'body' }, 'Mechanical value'),
            h('td', null, h(BasisChip, { basis: 'mechanical', showGlyph: false })),
            h('td', { className: 'fb-num figure' }, money(p.mechanical))
          ),
          overrides.map(function (o, i) {
            return h('tr', { key: o.tag + i },
              h('td', { className: 'fb-bridge__g fb-bridge__g--d', 'aria-hidden': 'true' }, GLYPH_INPUT),
              h('td', null,
                h('span', { className: 'fb-bridge__chg body' },
                  'Override — ',
                  h('code', { className: 'fb-tag figure-sm' }, o.tag), ' ',
                  h('span', { className: 'fb-bridge__from figure-sm' }, o.from),
                  ' → ',
                  h('span', { className: 'figure-sm' }, o.to)),
                o.reason ? h('span', { className: 'fb-bridge__reason body' }, o.reason)
                  : h('span', { className: 'fb-bridge__reason caption fb-bridge__noreason' },
                      'No reason given')),
              h('td', null, h(PrincipalChip, { principal: o.principal, actor: o.actor })),
              h('td', {
                className: cx('fb-num figure', Number(o.delta) >= 0
                  ? 'fb-delta--up' : 'fb-delta--down')
              }, signedMoney(o.delta))
            );
          }),
          h('tr', { className: 'fb-bridge__sum' },
            h('td', { className: 'fb-bridge__g fb-bridge__g--f', 'aria-hidden': 'true' }, GLYPH_DERIVED),
            h('td', { className: 'body' }, 'Reviewed value'),
            h('td', null, h(BasisChip, { basis: 'reviewed', showGlyph: false })),
            h('td', { className: 'fb-num figure-lg' }, money(p.reviewed))
          )
        )
      ),
      p.note ? h('p', { className: 'fb-bridge__note caption' }, p.note) : null
    );
  }

  /* ------------------------------------------------------------- BandMeter */

  function BandMeter(props) {
    var p = props || {};
    var low = Number(p.low), high = Number(p.high), price = Number(p.price);
    var fair = p.fairValue == null ? (low + high) / 2 : Number(p.fairValue);
    var buy = p.buyLevel == null ? null : Number(p.buyLevel);
    var trim = p.trimLevel == null ? null : Number(p.trimLevel);

    var pts = [low, high, price, fair];
    if (buy != null) pts.push(buy);
    if (trim != null) pts.push(trim);
    var lo = Math.min.apply(null, pts), hi = Math.max.apply(null, pts);
    var pad = ((hi - lo) || Math.abs(hi) || 1) * 0.12;
    var min = lo - pad, max = hi + pad;
    var at = function (v) { return ((v - min) / (max - min)) * 100; };

    var stance = stanceOf(price, buy, trim);
    var toFair = fair ? (fair - price) / fair : 0;
    var toLevel = stance === 'buy' && buy ? (buy - price) / buy
      : stance === 'trim' && trim ? (price - trim) / trim : 0;

    var holdFrom = buy == null ? 0 : at(buy);
    var holdTo = trim == null ? 100 : at(trim);

    return h('div', {
      className: 'fb-band',
      style: p.width ? { maxWidth: p.width + 'px' } : null
    },
      h('div', { className: 'fb-band__head' },
        h('span', { className: 'fb-band__price figure-lg' }, money(price)),
        h('span', { className: cx('fb-stance', 'fb-stance--' + stance, 'label') }, STANCE[stance]),
        h('span', { className: 'fb-band__gap caption' },
          pct(Math.abs(toFair) * 100) + (toFair >= 0 ? ' below' : ' above') + ' fair value',
          toLevel ? ' · ' + pct(Math.abs(toLevel) * 100) + ' ' +
            (stance === 'buy' ? 'below the buy level' : 'above the trim level') : null)
      ),

      /* the band's own numbers, on their own tier above the track */
      h('div', { className: 'fb-band__tier figure-sm' },
        h('span', { style: { left: at(low) + '%' } }, money(low)),
        h('span', { style: { left: at(high) + '%' } }, money(high)),
        /* a div, not a span: the tier's span rule centres its labels on their
           own position, which would drag the bracket half its width left */
        h('div', {
          className: 'fb-band__bracket',
          style: { left: at(low) + '%', width: (at(high) - at(low)) + '%' }
        })
      ),

      h('div', { className: 'fb-band__track' },
        h('div', { className: 'fb-band__clip' },
          h('div', {
            className: 'fb-zone fb-zone--hold',
            style: { left: holdFrom + '%', width: (holdTo - holdFrom) + '%' }
          }, h('span', { className: 'label' }, STANCE.hold)),
          h('div', {
            className: 'fb-zone fb-zone--fair',
            style: { left: at(low) + '%', width: (at(high) - at(low)) + '%' }
          }),
          buy == null ? null : h('div', {
            className: 'fb-zone fb-zone--buy', style: { left: 0, width: at(buy) + '%' }
          }, h('span', { className: 'label' }, STANCE.buy)),
          trim == null ? null : h('div', {
            className: 'fb-zone fb-zone--trim', style: { left: at(trim) + '%', right: 0 }
          }, h('span', { className: 'label' }, STANCE.trim)),
          h('div', { className: 'fb-band__fairmark', style: { left: at(fair) + '%' } })
        ),
        h('div', {
          className: 'fb-band__price-mark',
          style: { left: at(price) + '%' },
          title: 'Price ' + money(price) + ' — ' + STANCE[stance]
        })
      ),

      p.showScale === false ? null : h('div', { className: 'fb-band__scale figure-sm' },
        buy == null ? null : h('span', { style: { left: at(buy) + '%' } },
          money(buy), h('em', { className: 'label' }, 'Buy')),
        h('span', { style: { left: at(fair) + '%' } },
          money(fair), h('em', { className: 'label' }, 'Fair value')),
        trim == null ? null : h('span', { style: { left: at(trim) + '%' } },
          money(trim), h('em', { className: 'label' }, 'Trim'))
      ),

      p.caption ? h('div', { className: 'fb-band__caption caption' }, p.caption) : null
    );
  }

  /* -------------------------------------------------------- ValidityWindow */

  function ValidityWindow(props) {
    var p = props || {};
    var from = Date.parse(p.validFrom), until = Date.parse(p.validUntil);
    var now = Date.parse(p.today || p.enteredAt || p.validFrom);
    var span = Math.max(until - from, 1);
    var ratio = (now - from) / span;
    var pos = Math.min(Math.max(ratio, 0), 1) * 100;
    var state = ratio > 1 ? 'expired' : ratio > 0.6667 ? 'aging' : 'current';
    var rows = [
      ['As of', p.asOf, 'the period this fact describes'],
      ['Observed', p.observedAt, 'read from its source'],
      ['Entered', p.enteredAt, 'written into Fairband']
    ];
    return h('div', { className: cx('fb-window', 'fb-window--' + state) },
      p.tag ? h('code', { className: 'fb-tag figure-sm' }, p.tag) : null,
      h('dl', { className: 'fb-window__dates' }, rows.map(function (r) {
        return h(React.Fragment, { key: r[0] },
          h('dt', { className: 'label' }, r[0]),
          h('dd', null,
            h(DateText, { className: 'figure-sm', value: r[1] }),
            h('span', { className: 'fb-window__gloss caption' }, r[2]))
        );
      })),
      h('div', { className: 'fb-window__track' },
        h('div', { className: 'fb-window__fill', style: { width: pos + '%' } }),
        h('div', { className: 'fb-window__now', style: { left: pos + '%' } })
      ),
      h('div', { className: 'fb-window__ends caption' },
        h('span', null, 'valid from ', h(DateText, { value: p.validFrom })),
        h('span', { className: cx('fb-window__until', state !== 'current' && 'is-' + state) },
          state === 'expired' ? [FRESHNESS.expired.mark + ' expired '] : null,
          state === 'aging' ? [FRESHNESS.aging.mark + ' '] : null,
          state === 'expired' ? null : 'until ',
          h(DateText, { value: p.validUntil }))
      )
    );
  }

  /* ----------------------------------------------------------- TaggedInput */

  function TaggedInput(props) {
    var p = props || {};
    var id = 'fb-' + String(p.tag || 'input').replace(/[^A-Za-z0-9_-]/g, '-');
    return h('div', { className: cx('fb-input', p.locked && 'fb-input--locked') },
      h('div', { className: 'fb-input__head' },
        h('label', { className: 'fb-input__label label', htmlFor: id }, p.label),
        h('code', { className: 'fb-tag figure-sm' }, p.tag)
      ),
      h('div', { className: 'fb-input__field' },
        h('input', {
          id: id, className: 'fb-input__control figure',
          defaultValue: p.value, readOnly: !!p.locked,
          inputMode: 'decimal', onChange: p.onChange
        }),
        p.unit ? h('span', { className: 'fb-input__unit caption' }, p.unit) : null
      ),
      h('div', { className: 'fb-input__foot' },
        h(PrincipalChip, { principal: p.principal || 'owner', actor: p.actor, compact: true }),
        p.reason
          ? h('p', { className: 'fb-input__reason body' }, p.reason)
          : h('p', { className: 'fb-input__reason fb-input__reason--missing caption' },
              'A reason is required before this change is saved.')
      )
    );
  }

  /* ======================================================= the three records
     An agent never writes a value. It writes three kinds of record, and each
     has its own lifecycle:
       OverrideRecord — one tagged input, applied at once by the server.
       ReportReader   — prose with cited numbers, published or rejected whole.
       ProposalCard   — a trade, policy change or thesis revision, held for
                        the Owner. The only record with a confirm. */

  var OVERRIDE_STATES = {
    'applied': { word: 'applied', tone: 'applied' },
    'refused-locked': { word: 'refused · locked input', tone: 'refused' },
    'refused-evidence': { word: 'refused · needs extra evidence', tone: 'refused' },
    'refused-unit': { word: 'refused · unit or range', tone: 'refused' },
    'refused-not-input': { word: 'refused · a value, not an input', tone: 'refused' },
    'conflict-stale': { word: 'conflict · stale revision', tone: 'stale' }
  };

  var LIFETIMES = {
    lasting: { word: 'lasting', gloss: 'stays until you ask for an updated valuation' },
    'period-tied': { word: 'period-tied', gloss: 'ends with its period' }
  };

  function RecordState(props) {
    var tone = props.tone || 'applied';
    return h('span', { className: cx('fb-rec__state', 'fb-rec__state--' + tone, 'label') },
      props.children);
  }

  function Evidence(props) {
    var items = props.items || [];
    if (!items.length) return null;
    return h('span', { className: 'fb-ev body' }, items.map(function (e, i) {
      return h(React.Fragment, { key: (e.ref || '') + i },
        i ? ' · ' : null,
        e.kind || 'evidence', ' ',
        h('code', { className: 'fb-ev__ref figure-sm' }, e.ref),
        e.note ? h('span', { className: 'fb-ev__note' }, ' — ' + e.note) : null
      );
    }));
  }

  function Payload(props) {
    var rows = Array.isArray(props.payload)
      ? props.payload
      : Object.keys(props.payload || {}).map(function (k) { return [k, props.payload[k]]; });
    return h('div', { className: cx('fb-payload', props.muted && 'is-muted') },
      h('dl', { className: 'figure-sm' }, rows.map(function (r) {
        return h(React.Fragment, { key: r[0] },
          h('dt', null, r[0]),
          h('dd', null, String(r[1])));
      }))
    );
  }

  /* --------------------------------------------------------- OverrideRecord */

  function OverrideRecord(props) {
    var p = props || {};
    var key = OVERRIDE_STATES[p.state] ? p.state : 'applied';
    var st = OVERRIDE_STATES[key];
    var applied = key === 'applied';
    var life = LIFETIMES[p.lifetime] || LIFETIMES.lasting;

    return h('article', { className: cx('fb-rec', 'fb-rec--' + st.tone) },
      h('header', { className: 'fb-rec__head' },
        h(PrincipalChip, { principal: p.principal || 'agent', actor: p.actor }),
        h('span', { className: 'fb-rec__kind label' }, 'Override'),
        h(RecordState, { tone: st.tone }, st.word),
        p.revisionFrom || p.revisionTo ? h('span', { className: 'fb-rec__rev figure-sm' },
          'review ', p.revisionFrom, p.revisionTo ? ' → ' + p.revisionTo : null) : null
      ),
      h('div', { className: 'fb-rec__body' },
        h('div', { className: 'fb-rec__chg' },
          h('code', { className: 'fb-tag figure-sm' }, p.tag),
          h('span', { className: 'fb-rec__from figure' }, p.from),
          h('span', { className: 'fb-rec__arrow', 'aria-hidden': 'true' }, '→'),
          h('span', { className: 'figure' }, p.to)
        ),
        applied
          ? h('dl', { className: 'fb-rec__f' },
              h('dt', { className: 'label' }, 'Lifetime'),
              h('dd', { className: 'body' }, life.word,
                p.period ? h('span', { className: 'fb-rec__period figure-sm' }, ' · ' + p.period) : null,
                h('span', { className: 'fb-rec__gloss caption' }, ' — ' + life.gloss)),
              h('dt', { className: 'label' }, 'Reason'),
              h('dd', { className: 'body' }, p.reason),
              p.evidence && p.evidence.length ? h('dt', { className: 'label' }, 'Evidence') : null,
              p.evidence && p.evidence.length
                ? h('dd', null, h(Evidence, { items: p.evidence })) : null,
              h('dt', { className: 'label' }, 'Result'),
              h('dd', { className: 'body' },
                h('b', { className: 'fb-rec__effect' }, signedMoney(p.effect)), ' per share',
                p.reviewed != null ? h(React.Fragment, null, ' · reviewed ',
                  h('span', { className: 'figure-sm' }, money(p.reviewed))) : null,
                p.validUntil ? h('span', { className: 'fb-rec__gloss caption' },
                  ' · valid to ', h(DateText, { value: p.validUntil })) : null)
            )
          : h('p', { className: 'fb-rec__msg body' }, p.message)
      )
    );
  }

  /* ------------------------------------------------------------ ReportReader */

  /* `ref` is reserved in React and never reaches a function component, so the
     citation's reference travels as `source`. */
  function Cite(props) {
    return h('span', {
      className: 'fb-cite figure-sm',
      title: 'traces to ' + props.source
    }, props.children);
  }

  function ReportReader(props) {
    var p = props || {};
    var rejected = p.state === 'rejected';
    var cites = p.cites || {};
    var findings = p.findings || [];

    return h('article', { className: cx('fb-rec', 'fb-report', rejected ? 'fb-rec--refused' : 'fb-rec--applied') },
      h('header', { className: 'fb-rec__head' },
        h('span', { className: 'fb-rec__kind label' }, 'Report'),
        h('span', { className: 'fb-rec__mode label' }, p.mode || 'valuation review'),
        h(RecordState, { tone: rejected ? 'refused' : 'applied' },
          rejected ? 'rejected' : 'published'),
        h('span', { className: 'fb-rec__rev figure-sm' },
          rejected ? findings.length + (findings.length === 1 ? ' finding' : ' findings') : p.revision)
      ),
      h('div', { className: 'fb-rec__body' },
        rejected
          ? h(React.Fragment, null,
              h('p', { className: 'fb-report__unchanged caption' },
                'The published report is unchanged. A rejected submission never replaces it.'),
              h('table', { className: 'fb-report__findings' },
                h('thead', null, h('tr', null,
                  h('th', { className: 'label' }, 'Where'),
                  h('th', { className: 'label' }, 'What failed'))),
                h('tbody', null, findings.map(function (f, i) {
                  return h('tr', { key: i },
                    h('td', { className: 'fb-report__where figure-sm' }, f.where),
                    h('td', null,
                      h('span', { className: 'fb-report__what body' }, f.what),
                      f.detail ? h('span', { className: 'fb-report__detail caption' },
                        ' — ' + f.detail) : null));
                }))
              ))
          : h(React.Fragment, null,
              h('p', { className: 'fb-report__cites caption' },
                'cites snapshot ', h('span', { className: 'figure-sm' }, cites.snapshot),
                ' · review ', h('span', { className: 'figure-sm' }, cites.review),
                ' · thesis ', h('span', { className: 'figure-sm' }, cites.thesis),
                cites.reusesFullReportOf ? h(React.Fragment, null, ' · reuses the full report of ',
                  h(DateText, { value: cites.reusesFullReportOf })) : null),
              (p.sections || []).map(function (s, i) {
                return h('section', { key: i, className: 'fb-report__section' },
                  s.heading ? h('h4', { className: 'heading' }, s.heading) : null,
                  h('p', { className: 'fb-report__prose body' }, (s.parts || []).map(function (part, j) {
                    return typeof part === 'string' ? part
                      : h(Cite, { key: j, source: part.ref }, part.cite);
                  }))
                );
              }),
              p.appendixes === false ? null : h('p', { className: 'fb-report__appx caption' },
                'Appendix A the audit · Appendix B the glossary')
            )
      )
    );
  }

  /* ------------------------------------------------------------ ProposalCard */

  var PROPOSAL_TONES = {
    pending: 'pending', stale: 'stale', confirmed: 'applied', rejected: 'refused'
  };

  function ProposalCard(props) {
    var p = props || {};
    var state = PROPOSAL_TONES[p.state] ? p.state : 'pending';
    var tone = PROPOSAL_TONES[state];

    return h('article', { className: cx('fb-rec', 'fb-rec--' + tone) },
      h('header', { className: 'fb-rec__head' },
        state === 'pending' || state === 'stale'
          ? h(PrincipalChip, { principal: p.principal || 'agent', actor: p.actor }) : null,
        h('span', { className: 'fb-rec__kind label' }, 'Proposal · ' + (p.kind || 'trade')),
        h(RecordState, { tone: tone }, state)
      ),
      h('div', { className: 'fb-rec__body' },
        state === 'confirmed' ? h(React.Fragment, null,
          h('p', { className: 'body fb-rec__outcome' },
            'Confirmed by ', (p.by || 'Owner'),
            p.record ? h(React.Fragment, null, ' · resulting record ',
              h('span', { className: 'fb-rec__link figure-sm' }, p.record)) : null),
          h('p', { className: 'fb-rec__gloss caption' },
            h(DateText, { value: p.at }), ' · confirming again returns this same outcome')
        ) : null,

        state === 'rejected' ? h(React.Fragment, null,
          h('p', { className: 'body fb-rec__outcome' }, '“' + (p.rejectionReason || '') + '”'),
          h('p', { className: 'fb-rec__gloss caption' },
            'Rejected by ', (p.by || 'Owner'), ' · ', h(DateText, { value: p.at }))
        ) : null,

        state === 'stale' ? h('p', { className: 'fb-rec__msg body' },
          'The target moved to review ',
          h('span', { className: 'figure-sm' }, p.currentRevision),
          '. This proposal cannot be confirmed; the agent must propose again against the current revision.'
        ) : null,

        state === 'pending' ? h('dl', { className: 'fb-rec__f' },
          h('dt', { className: 'label' }, 'Reason'),
          h('dd', { className: 'body' }, p.reason),
          p.evidence && p.evidence.length ? h('dt', { className: 'label' }, 'Evidence') : null,
          p.evidence && p.evidence.length ? h('dd', null, h(Evidence, { items: p.evidence })) : null
        ) : null,

        p.payload ? h('div', { className: 'fb-rec__pay' },
          state === 'pending' ? h('span', { className: 'fb-rec__paylab label' },
            'Exact payload, as the server will apply it') : null,
          h(Payload, { payload: p.payload, muted: state !== 'pending' })
        ) : null,

        state === 'pending' || state === 'stale' ? h('p', { className: 'fb-rec__gloss caption' },
          'target · review ', h('span', { className: 'figure-sm' }, p.targetRevision),
          p.at ? h(React.Fragment, null, ' · proposed ', h(DateText, { value: p.at })) : null
        ) : null,

        state === 'pending' ? h('div', { className: 'fb-rec__foot' },
          h(Button, { variant: 'primary', size: 'sm', onClick: p.onConfirm }, 'Confirm…'),
          h(Button, { variant: 'danger', size: 'sm', onClick: p.onReject }, 'Reject with a reason')
        ) : null
      )
    );
  }

  /* ----------------------------------------------------------- ConfirmDialog */

  function ConfirmDialog(props) {
    var p = props || {};
    var state = p.state || 'open';
    var stale = state === 'stale';
    return h('div', { className: cx('fb-dlg', 'fb-dlg--' + state), role: 'dialog', 'aria-modal': 'true' },
      h('h4', { className: 'fb-dlg__title title' }, p.title || 'Confirm this change'),
      h('p', { className: 'fb-dlg__warn-note caption' }, 'This cannot be undone.'),
      p.payload ? h(Payload, { payload: p.payload, muted: stale }) : null,
      stale
        ? h('p', { className: 'fb-dlg__stale body' },
            'The target changed while this was open. Reload to see the current revision; this '
            + 'confirmation no longer binds to anything.')
        : h('p', { className: 'fb-rec__gloss caption' },
            'target · review ', h('span', { className: 'figure-sm' }, p.targetRevision)),
      h('div', { className: 'fb-dlg__foot' },
        h(Button, {
          variant: 'primary', size: 'sm',
          disabled: stale || state === 'confirming' || state === 'done',
          onClick: p.onConfirm
        }, state === 'confirming' ? 'Confirming…' : 'Confirm'),
        stale
          ? h(Button, { size: 'sm', onClick: p.onReload }, 'Reload')
          : h(Button, { variant: 'danger', size: 'sm', onClick: p.onReject }, 'Reject'),
        h(Button, { variant: 'quiet', size: 'sm', onClick: p.onCancel }, 'Cancel')
      )
    );
  }

  /* ----------------------------------------------------------- ScreenTable */

  // fairband: the formats of the extra columns (spec 6.3). A fraction reads as a percentage to
  // one decimal, a multiple to one decimal with x, a market cap in billions; a minus is U+2212.
  function signed(s) { return /^-0?\.?0*$/.test(s) ? s.slice(1) : s.replace(/^-/, '−'); }
  function percent(v) {
    return v == null || isNaN(Number(v)) ? '—' : signed((Number(v) * 100).toFixed(1)) + '%';
  }
  function multiple(v) {
    return v == null || isNaN(Number(v)) ? '—' : signed(Number(v).toFixed(1)) + 'x';
  }
  function billions(v) {
    if (v == null || isNaN(Number(v))) return '—';
    return '$' + (Number(v) / 1e9).toLocaleString('en-US',
      { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' bn';
  }
  function figureCell(text) { return h('td', { className: 'fb-num figure' }, text); }
  function wordCell(text) { return h('td', { className: 'body' }, text == null ? '—' : text); }
  function dateCell(iso) {
    return h('td', { className: 'fb-num figure' }, h(DateText, { value: iso }));
  }

  var COLUMNS = [
    { key: 'ticker', head: 'Ticker', locked: true,
      cell: function (r) { return h('td', { className: 'fb-screen__ticker ticker' }, r.ticker); } },
    { key: 'name', head: 'Company',
      cell: function (r) { return h('td', { className: 'fb-screen__name body' }, r.name); } },
    { key: 'phase', head: 'Phase',
      cell: function (r) { return h('td', null, h(PhaseBadge, { phase: r.phase, size: 'sm' })); } },
    { key: 'band', head: 'Fair band', num: true,
      cell: function (r) {
        return h('td', { className: 'fb-num figure-sm fb-screen__band' },
          money(r.fairLow) + ' – ' + money(r.fairHigh));
      } },
    { key: 'fairValue', head: 'Fair value', num: true,
      cell: function (r) { return h('td', { className: 'fb-num figure-sm' }, money(r.fairValue)); } },
    { key: 'buyLevel', head: 'Buy level', num: true,
      cell: function (r) { return h('td', { className: 'fb-num figure-sm' }, money(r.buyLevel)); } },
    { key: 'trimLevel', head: 'Trim level', num: true,
      cell: function (r) { return h('td', { className: 'fb-num figure-sm' }, money(r.trimLevel)); } },
    { key: 'mechanical', head: 'Mechanical', num: true, basis: true,
      cell: function (r) {
        return h('td', { className: 'fb-num figure fb-screen__mech' }, money(r.mechanical));
      } },
    { key: 'reviewed', head: 'Reviewed', num: true, basis: true,
      cell: function (r) {
        return h('td', { className: 'fb-num figure' },
          r.reviewed == null ? h('span', { className: 'fb-screen__none' }, '—') : money(r.reviewed));
      } },
    { key: 'price', head: 'Price', num: true, locked: true,
      cell: function (r) { return h('td', { className: 'fb-num figure' }, money(r.price)); } },
    { key: 'stance', head: 'Stance',
      cell: function (r) {
        // fairband: a row without a price or levels (a refusal) has no stance; never "Hold".
        if (r.price == null || r.buyLevel == null || r.trimLevel == null) {
          return h('td', null, h('span', { className: 'fb-screen__none' }, '—'));
        }
        var s = stanceOf(r.price, r.buyLevel, r.trimLevel);
        return h('td', null,
          h('span', { className: cx('fb-stance', 'fb-stance--' + s, 'label') }, STANCE[s]));
      } },
    { key: 'overrides', head: 'Overrides',
      cell: function (r) {
        return h('td', null, r.overrides
          ? h(PrincipalChip, { principal: 'system', compact: true, actor: String(r.overrides) })
          : h('span', { className: 'caption fb-screen__none' }, 'none'));
      } },
    { key: 'entered', head: 'Entered',
      cell: function (r) {
        var f = FRESHNESS[r.freshness] ? r.freshness : 'current';
        return h('td', { className: 'fb-screen__when caption' },
          h(DateText, { value: r.enteredAt }),
          f === 'current' ? null : h('span', {
            className: 'fb-mark fb-mark--' + f, title: FRESHNESS[f].word
          }, FRESHNESS[f].mark));
      } },
    // fairband: the extra columns of spec 6.3, each a plain figure, word or date from the row.
    { key: 'sector', head: 'Sector', cell: function (r) { return wordCell(r.sector); } },
    { key: 'capBand', head: 'Cap', cell: function (r) { return wordCell(r.capBand); } },
    { key: 'marketCap', head: 'Market cap', num: true,
      cell: function (r) { return figureCell(billions(r.marketCap)); } },
    { key: 'moat', head: 'Moat', cell: function (r) { return wordCell(r.moat); } },
    { key: 'impliedGrowth', head: 'Implied growth', num: true,
      cell: function (r) { return figureCell(percent(r.impliedGrowth)); } },
    { key: 'expectedReturn', head: 'Expected return', num: true,
      cell: function (r) { return figureCell(percent(r.expectedReturn)); } },
    { key: 'epv', head: 'EPV', num: true,
      cell: function (r) { return figureCell(money(r.epv)); } },
    { key: 'peReported', head: 'P/E', num: true,
      cell: function (r) { return figureCell(multiple(r.peReported)); } },
    { key: 'peClean', head: 'Clean P/E', num: true,
      cell: function (r) { return figureCell(multiple(r.peClean)); } },
    { key: 'peForward', head: 'Forward P/E', num: true,
      cell: function (r) { return figureCell(multiple(r.peForward)); } },
    { key: 'high52w', head: '52w high', num: true,
      cell: function (r) { return figureCell(money(r.high52w)); } },
    { key: 'low52w', head: '52w low', num: true,
      cell: function (r) { return figureCell(money(r.low52w)); } },
    { key: 'change1y', head: '1y', num: true,
      cell: function (r) { return figureCell(percent(r.change1y)); } },
    { key: 'change3y', head: '3y', num: true,
      cell: function (r) { return figureCell(percent(r.change3y)); } },
    { key: 'change5y', head: '5y', num: true,
      cell: function (r) { return figureCell(percent(r.change5y)); } },
    { key: 'drawdown', head: 'Drawdown', num: true,
      cell: function (r) { return figureCell(percent(r.drawdown)); } },
    { key: 'flags', head: 'Flags',
      cell: function (r) { return h('td', { className: 'body' }, (r.flags || []).join(' · ')); } },
    { key: 'refusal', head: 'Refusal',
      cell: function (r) { return h('td', { className: 'caption' }, r.refusal || ''); } },
    { key: 'priceDate', head: 'Price date', num: true,
      cell: function (r) { return dateCell(r.priceDate); } },
    { key: 'dataDate', head: 'Data date', num: true,
      cell: function (r) { return dateCell(r.dataDate); } },
    { key: 'validUntil', head: 'Valid until', num: true,
      cell: function (r) { return dateCell(r.validUntil); } }
  ];

  var DEFAULT_COLUMNS = ['ticker', 'name', 'phase', 'band', 'mechanical',
                         'reviewed', 'price', 'stance'];

  function ScreenTable(props) {
    var p = props || {};
    var rows = p.rows || [];
    var open = React.useState(false);
    var visible = p.columns || DEFAULT_COLUMNS;
    var shown = COLUMNS.filter(function (c) {
      return c.locked || visible.indexOf(c.key) !== -1;
    });

    function toggle(key) {
      if (!p.onColumnsChange) return;
      var next = visible.indexOf(key) === -1
        ? visible.concat([key])
        : visible.filter(function (k) { return k !== key; });
      p.onColumnsChange(next);
    }

    return h('div', { className: cx('fb-screen', p.dense && 'fb-screen--dense') },
      p.chooser === false ? null : h('div', { className: 'fb-screen__bar' },
        h('span', { className: 'fb-screen__count caption' }, p.footnote),
        h('div', { className: 'fb-screen__cols' },
          h(Button, {
            size: 'sm', onClick: function () { open[1](!open[0]); },
            'aria-expanded': open[0] ? 'true' : 'false'
          }, 'Columns ▾'),
          open[0] ? h('div', { className: 'fb-menu' },
            COLUMNS.map(function (c) {
              var on = c.locked || visible.indexOf(c.key) !== -1;
              return h('label', { key: c.key, className: cx('fb-menu__row control', c.locked && 'is-locked') },
                h('input', {
                  type: 'checkbox', checked: on, disabled: !!c.locked,
                  onChange: function () { toggle(c.key); }
                }),
                h('span', null, c.head));
            }),
            h('hr'),
            h('button', {
              type: 'button', className: 'fb-menu__reset control',
              onClick: function () { if (p.onColumnsChange) p.onColumnsChange(DEFAULT_COLUMNS.slice()); }
            }, 'Reset to the default eight')
          ) : null
        )
      ),
      h('table', { className: 'fb-table' },
        h('thead', null, h('tr', null, shown.map(function (c) {
          var sorted = p.sort && p.sort.column === c.key;
          return h('th', {
            key: c.key,
            className: cx('label', c.num && 'fb-num', sorted && 'is-sorted'),
            'aria-sort': sorted ? (p.sort.direction === 'desc' ? 'descending' : 'ascending') : null,
            // fairband: the cell names its column; given onSort, a click, Enter or Space asks
            // the consumer to sort by it. The component still sorts nothing itself.
            'data-key': c.key,
            tabIndex: p.onSort ? 0 : null,
            onClick: p.onSort ? function () { p.onSort(c.key); } : null,
            onKeyDown: p.onSort ? function (e) {
              if (e.key !== 'Enter' && e.key !== ' ') return;
              e.preventDefault();
              p.onSort(c.key);
            } : null
          },
            c.basis ? h('span', { className: 'fb-screen__basisg', 'aria-hidden': 'true' },
              GLYPH_DERIVED) : null,
            c.head,
            sorted ? h('span', { className: 'fb-sort', 'aria-hidden': 'true' },
              p.sort.direction === 'desc' ? '▼' : '▲') : null
          );
        }))),
        h('tbody', null, rows.map(function (r) {
          return h('tr', {
            key: r.ticker,
            className: cx(r.selected && 'is-selected'),
            'aria-selected': r.selected ? 'true' : null,
            // fairband: given onOpen, a row takes focus like a button and opens on a click,
            // Enter or Space. Its only interactions stay hover, selection and opening.
            tabIndex: p.onOpen ? 0 : null,
            role: p.onOpen ? 'button' : null,
            onClick: p.onOpen ? function () { p.onOpen(r); } : null,
            onKeyDown: p.onOpen ? function (e) {
              if (e.key !== 'Enter' && e.key !== ' ') return;
              e.preventDefault();
              p.onOpen(r);
            } : null
          }, shown.map(function (c) {
            return h(React.Fragment, { key: c.key }, c.cell(r));
          }));
        }))
      )
    );
  }

  /* ================================================================ charts */

  var CW = 680;

  function useMeasuredWidth(ref, fallback) {
    var st = React.useState(fallback);
    React.useEffect(function () {
      var el = ref.current;
      if (!el || typeof ResizeObserver === 'undefined') return;
      var ro = new ResizeObserver(function (entries) {
        var w = Math.round(entries[0].contentRect.width);
        if (w > 0) st[1](w);
      });
      ro.observe(el);
      return function () { ro.disconnect(); };
    }, []);
    return st[0];
  }

  function niceTicks(min, max, n) {
    n = n || 4;
    if (!isFinite(min) || !isFinite(max)) { min = 0; max = 1; }
    if (min === max) { max = min + (Math.abs(min) || 1); }
    var raw = (max - min) / n;
    var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var norm = raw / mag;
    var step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
    var out = [];
    for (var v = Math.floor(min / step) * step; v <= Math.ceil(max / step) * step + step * 1e-6; v += step) {
      out.push(Math.round(v / step) * step);
    }
    return out;
  }

  /* Axis ticks stay bare — the title names the measure, and a currency symbol
     down five ticks is noise. Direct labels and tooltips carry the symbol. */
  function compact(v) {
    var a = Math.abs(v);
    if (a >= 1e9) return (v / 1e9).toFixed(a >= 1e10 ? 0 : 1) + 'B';
    if (a >= 1e6) return (v / 1e6).toFixed(a >= 1e7 ? 0 : 1) + 'M';
    if (a >= 1e3) return (v / 1e3).toFixed(a >= 1e4 ? 0 : 1) + 'K';
    return Math.round(a) === a ? String(v) : v.toFixed(2);
  }

  function labelEvery(n) { return Math.max(1, Math.ceil(n / 7)); }

  function periodLabel(d, i, n) {
    var every = labelEvery(n);
    if (i === 0 || i === n - 1) return d.period;
    if (i % every !== 0) return '';
    if (n - 1 - i < every) return '';
    return d.period;
  }

  function nearestIndex(event, node, n, left, right) {
    if (!node || n < 2) return 0;
    var box = node.getBoundingClientRect();
    var t = (event.clientX - box.left - left) / (right - left);
    return Math.max(0, Math.min(n - 1, Math.round(t * (n - 1))));
  }

  function Grid(props) {
    var p = props;
    return h('g', { className: 'fb-c__grid' }, p.ticks.map(function (t) {
      var y = p.scale(t);
      return h('g', { key: t },
        h('line', { x1: p.left, x2: p.right, y1: y, y2: y }),
        h('text', { className: 'fb-c__tick', x: p.left - 8, y: y + 3.5 }, p.format(t))
      );
    }));
  }

  function XAxis(props) {
    var p = props;
    return h('g', { className: 'fb-c__xaxis' },
      h('line', { className: 'fb-c__axisline', x1: p.left, x2: p.right, y1: p.y, y2: p.y }),
      p.series.map(function (d, i) {
        var text = periodLabel(d, i, p.series.length);
        if (!text) return null;
        var mark = markFor(d.freshness);
        var end = i === 0 ? 'fb-c__tick--start'
          : (i === p.series.length - 1 ? 'fb-c__tick--end' : null);
        return h('text', { key: d.period, className: cx('fb-c__tick', end), x: p.x(i), y: p.y + 16 },
          text,
          mark ? h('tspan', { className: 'fb-c__stale fb-c__stale--' + d.freshness }, ' ' + mark) : null
        );
      })
    );
  }

  function Tip(props) {
    if (props.at == null) return null;
    return h('div', { className: 'fb-c__tip', style: { left: props.at + 'px' } }, props.children);
  }

  function DataTable(props) {
    if (!props.show) return null;
    return h('table', { className: 'fb-c__table' },
      h('thead', null, h('tr', null, props.head.map(function (c, i) {
        return h('th', { key: c, className: cx('label', i > 0 && 'fb-num') }, c);
      }))),
      h('tbody', null, props.rows.map(function (r) {
        return h('tr', { key: r[0] }, r.map(function (c, i) {
          return h('td', { key: i, className: cx(i === 0 ? 'figure-sm' : 'figure-sm fb-num') }, c);
        }));
      }))
    );
  }

  /* ----------------------------------------------------------- BandHistory */

  function BandHistory(props) {
    var p = props || {};
    var series = p.series || [];
    var n = series.length;
    var PH = p.height || 220;
    var wrap = React.useRef(null);
    var W = useMeasuredWidth(wrap, p.width || CW);
    var L = 56, R = W - 86, T = 12, B = T + PH, H = B + 30;
    var node = React.useRef(null);
    var hover = React.useState(null);
    var at = hover[0], setAt = hover[1];

    var vals = [];
    series.forEach(function (d) { vals.push(d.fairLow, d.fairHigh, d.price); });
    var ticks = niceTicks(Math.min.apply(null, vals), Math.max.apply(null, vals), 4);
    var lo = ticks[0], hi = ticks[ticks.length - 1];
    var X = function (i) { return n < 2 ? (L + R) / 2 : L + (R - L) * i / (n - 1); };
    var Y = function (v) { return B - (B - T) * (v - lo) / (hi - lo); };

    var band = series.map(function (d, i) { return X(i) + ',' + Y(d.fairHigh); })
      .concat(series.slice().reverse().map(function (d, i) {
        return X(n - 1 - i) + ',' + Y(d.fairLow);
      })).join(' ');
    var line = series.map(function (d, i) { return X(i) + ',' + Y(d.price); }).join(' ');
    var last = series[n - 1] || {};
    var cur = at == null ? null : series[at];

    return h('figure', { className: 'fb-c' },
      h('figcaption', { className: 'fb-c__head' },
        h('span', { className: 'fb-c__title heading' }, p.title || 'Price against the fair band'),
        h('span', { className: 'fb-c__sub caption' },
          p.subtitle || 'Band from the phase model, recomputed each quarter'),
        h(BasisChip, { basis: p.basis || 'mechanical', compact: true })
      ),
      h('div', { className: 'fb-c__plot', ref: wrap },
        h('svg', {
          ref: node, className: 'fb-c__svg', width: W, height: H,
          viewBox: '0 0 ' + W + ' ' + H, role: 'img',
          'aria-label': (p.title || 'Price against the fair band') + ' — ' + n + ' periods',
          onMouseMove: function (e) { setAt(nearestIndex(e, node.current, n, L, R)); },
          onMouseLeave: function () { setAt(null); }
        },
          h(Grid, { ticks: ticks, scale: Y, left: L, right: R, format: compact }),
          h('polygon', { className: 'fb-c__band', points: band }),
          h('polyline', { className: 'fb-c__bandedge', points: series.map(function (d, i) { return X(i) + ',' + Y(d.fairHigh); }).join(' ') }),
          h('polyline', { className: 'fb-c__bandedge', points: series.map(function (d, i) { return X(i) + ',' + Y(d.fairLow); }).join(' ') }),
          h('polyline', { className: 'fb-c__line fb-c__line--price', points: line }),
          cur ? h('line', { className: 'fb-c__crosshair', x1: X(at), x2: X(at), y1: T, y2: B }) : null,
          cur ? h('circle', { className: 'fb-c__dot fb-c__dot--price', cx: X(at), cy: Y(cur.price), r: 4.5 }) : null,
          h('circle', { className: 'fb-c__dot fb-c__dot--price', cx: X(n - 1), cy: Y(last.price), r: 4.5 }),
          h('text', { className: 'fb-c__endlabel', x: X(n - 1) + 12, y: Y(last.price) + 4 }, money(last.price)),
          h(XAxis, { series: series, x: X, y: B, left: L, right: R })
        ),
        h(Tip, { at: cur ? X(at) : null },
          h('span', { className: 'label' }, cur ? cur.period : ''),
          cur ? h('span', { className: 'figure-sm' }, 'price ' + money(cur.price)) : null,
          cur ? h('span', { className: 'figure-sm' },
            'band ' + money(cur.fairLow) + ' – ' + money(cur.fairHigh)) : null
        )
      ),
      h(DataTable, {
        show: p.tableView,
        head: ['Period', 'Price', 'Band low', 'Band high'],
        rows: series.map(function (d) {
          return [d.period, money(d.price), money(d.fairLow), money(d.fairHigh)];
        })
      })
    );
  }

  /* ------------------------------------------------------------ HistoryBars */

  function columnPath(x, w, yVal, yZero, r) {
    var up = yVal <= yZero;
    r = Math.min(r, w / 2, Math.abs(yZero - yVal));
    var e = up ? yVal + r : yVal - r;
    return 'M' + x + ',' + yZero + ' V' + e +
      ' Q' + x + ',' + yVal + ' ' + (x + r) + ',' + yVal +
      ' H' + (x + w - r) + ' Q' + (x + w) + ',' + yVal + ' ' + (x + w) + ',' + e +
      ' V' + yZero + ' Z';
  }

  function HistoryBars(props) {
    var p = props || {};
    var series = p.series || [];
    var n = series.length;
    var PH = p.height || 180;
    var wrap = React.useRef(null);
    var W = useMeasuredWidth(wrap, p.width || CW);
    var L = 56, R = W - 16, T = 12, B = T + PH, H = B + 30;
    var hover = React.useState(null);
    var at = hover[0], setAt = hover[1];
    var fmt = p.format || compact;

    var values = series.map(function (d) { return d.value; });
    var signed = values.some(function (v) { return v < 0; });
    var ticks = niceTicks(Math.min(0, Math.min.apply(null, values)),
      Math.max(0, Math.max.apply(null, values)), 4);
    var lo = ticks[0], hi = ticks[ticks.length - 1];
    var Y = function (v) { return B - (B - T) * (v - lo) / (hi - lo); };
    var slot = (R - L) / Math.max(n, 1);
    var bw = Math.min(24, slot - 10);
    var X = function (i) { return L + slot * i + (slot - bw) / 2; };
    var zero = Y(0);
    var cur = at == null ? null : series[at];

    return h('figure', { className: 'fb-c' },
      h('figcaption', { className: 'fb-c__head' },
        h('span', { className: 'fb-c__title heading' }, p.title),
        p.unit ? h('span', { className: 'fb-c__sub caption' }, p.unit) : null,
        h(BasisChip, { basis: p.basis || 'mechanical', compact: true })
      ),
      h('div', { className: 'fb-c__plot', ref: wrap },
        h('svg', {
          className: 'fb-c__svg', width: W, height: H,
          viewBox: '0 0 ' + W + ' ' + H, role: 'img',
          'aria-label': p.title + ' by fiscal year'
        },
          h(Grid, { ticks: ticks, scale: Y, left: L, right: R, format: fmt }),
          signed ? h('line', { className: 'fb-c__zero', x1: L, x2: R, y1: zero, y2: zero }) : null,
          h('g', null, series.map(function (d, i) {
            var cls = !signed ? 'fb-c__bar'
              : (d.value < 0 ? 'fb-c__bar fb-c__bar--neg' : 'fb-c__bar fb-c__bar--pos');
            return h('path', {
              key: d.period, className: cx(cls, at === i && 'is-hovered'),
              d: columnPath(X(i), bw, Y(d.value), zero, 4),
              onMouseEnter: function () { setAt(i); },
              onMouseLeave: function () { setAt(null); }
            });
          })),
          series.length ? h('text', {
            className: 'fb-c__capvalue', x: X(n - 1) + bw / 2,
            y: Y(series[n - 1].value) + (series[n - 1].value < 0 ? 14 : -7)
          }, fmt(series[n - 1].value)) : null,
          h(XAxis, { series: series, x: function (i) { return X(i) + bw / 2; }, y: B, left: L, right: R })
        ),
        h(Tip, { at: cur ? X(at) + bw / 2 : null },
          h('span', { className: 'label' }, cur ? cur.period : ''),
          cur ? h('span', { className: 'figure-sm' }, fmt(cur.value) + (p.unit ? ' ' + p.unit : '')) : null,
          cur && cur.freshness && cur.freshness !== 'current'
            ? h('span', { className: 'caption' }, FRESHNESS[cur.freshness].word) : null
        )
      ),
      h(DataTable, {
        show: p.tableView,
        head: ['Period', p.title || 'Value'],
        rows: series.map(function (d) { return [d.period + markFor(d.freshness), fmt(d.value)]; })
      })
    );
  }

  /* ------------------------------------------------------------ SpreadChart */

  function SpreadChart(props) {
    var p = props || {};
    var series = p.series || [];
    var n = series.length;
    var PH = p.height || 180;
    var wrap = React.useRef(null);
    var W = useMeasuredWidth(wrap, p.width || CW);
    var L = 56, R = W - 78, T = 12, B = T + PH, H = B + 30;
    var node = React.useRef(null);
    var hover = React.useState(null);
    var at = hover[0], setAt = hover[1];

    var vals = [];
    series.forEach(function (d) { vals.push(d.roic, d.wacc); });
    var ticks = niceTicks(Math.min.apply(null, vals), Math.max.apply(null, vals), 4);
    var lo = ticks[0], hi = ticks[ticks.length - 1];
    var X = function (i) { return n < 2 ? (L + R) / 2 : L + (R - L) * i / (n - 1); };
    var Y = function (v) { return B - (B - T) * (v - lo) / (hi - lo); };

    var pts = [];
    series.forEach(function (d, i) {
      pts.push({ t: i, roic: d.roic, wacc: d.wacc });
      var next = series[i + 1];
      if (!next) return;
      var d0 = d.roic - d.wacc, d1 = next.roic - next.wacc;
      if ((d0 > 0 && d1 < 0) || (d0 < 0 && d1 > 0)) {
        var f = d0 / (d0 - d1);
        var meet = d.wacc + (next.wacc - d.wacc) * f;
        pts.push({ t: i + f, roic: meet, wacc: meet });
      }
    });

    var runs = [], run = null, carry = null;
    pts.forEach(function (pt) {
      var gap = pt.roic - pt.wacc;
      if (Math.abs(gap) < 1e-9) {
        if (run) run.pts.push(pt);
        carry = pt; run = null;
        return;
      }
      var sign = gap > 0 ? 'pos' : 'neg';
      if (!run || run.sign !== sign) {
        run = { sign: sign, pts: carry ? [carry] : [] };
        runs.push(run);
      }
      run.pts.push(pt);
      carry = null;
    });

    var area = function (r) {
      return r.pts.map(function (pt) { return X(pt.t) + ',' + Y(pt.roic); })
        .concat(r.pts.slice().reverse().map(function (pt) { return X(pt.t) + ',' + Y(pt.wacc); }))
        .join(' ');
    };

    var last = series[n - 1] || {};
    var cur = at == null ? null : series[at];

    return h('figure', { className: 'fb-c' },
      h('figcaption', { className: 'fb-c__head' },
        h('span', { className: 'fb-c__title heading' },
          p.title || 'Return on capital against cost of capital'),
        h('span', { className: 'fb-c__sub caption' }, p.subtitle || 'The gap is the subject'),
        h(BasisChip, { basis: p.basis || 'mechanical', compact: true })
      ),
      h('ul', { className: 'fb-c__legend' },
        h('li', null, h('span', { className: 'fb-c__key fb-c__key--1' }), h('span', { className: 'label' }, 'ROIC')),
        h('li', null, h('span', { className: 'fb-c__key fb-c__key--context' }), h('span', { className: 'label' }, 'WACC')),
        h('li', null, h('span', { className: 'fb-c__key fb-c__key--pos' }), h('span', { className: 'label' }, 'creating value')),
        h('li', null, h('span', { className: 'fb-c__key fb-c__key--neg' }), h('span', { className: 'label' }, 'destroying value'))
      ),
      h('div', { className: 'fb-c__plot', ref: wrap },
        h('svg', {
          ref: node, className: 'fb-c__svg', width: W, height: H,
          viewBox: '0 0 ' + W + ' ' + H, role: 'img',
          'aria-label': 'Return on invested capital against cost of capital, ' + n + ' periods',
          onMouseMove: function (e) { setAt(nearestIndex(e, node.current, n, L, R)); },
          onMouseLeave: function () { setAt(null); }
        },
          h(Grid, { ticks: ticks, scale: Y, left: L, right: R, format: function (t) { return pct(t, 0); } }),
          h('g', null, runs.map(function (r, i) {
            return h('polygon', { key: i, className: 'fb-c__spread fb-c__spread--' + r.sign, points: area(r) });
          })),
          h('polyline', {
            className: 'fb-c__line fb-c__line--context',
            points: series.map(function (d, i) { return X(i) + ',' + Y(d.wacc); }).join(' ')
          }),
          h('polyline', {
            className: 'fb-c__line fb-c__line--1',
            points: series.map(function (d, i) { return X(i) + ',' + Y(d.roic); }).join(' ')
          }),
          cur ? h('line', { className: 'fb-c__crosshair', x1: X(at), x2: X(at), y1: T, y2: B }) : null,
          h('circle', { className: 'fb-c__dot fb-c__dot--1', cx: X(n - 1), cy: Y(last.roic), r: 4.5 }),
          h('text', { className: 'fb-c__endlabel', x: X(n - 1) + 12, y: Y(last.roic) + 4 }, pct(last.roic)),
          h('text', { className: 'fb-c__endlabel fb-c__endlabel--context', x: X(n - 1) + 12, y: Y(last.wacc) + 4 }, pct(last.wacc)),
          h(XAxis, { series: series, x: X, y: B, left: L, right: R })
        ),
        h(Tip, { at: cur ? X(at) : null },
          h('span', { className: 'label' }, cur ? cur.period : ''),
          cur ? h('span', { className: 'figure-sm' }, 'ROIC ' + pct(cur.roic)) : null,
          cur ? h('span', { className: 'figure-sm' }, 'WACC ' + pct(cur.wacc)) : null,
          cur ? h('span', { className: cx('label', cur.roic >= cur.wacc ? 'fb-stance--buy' : 'fb-stance--trim') },
            (cur.roic >= cur.wacc ? '+' : '') + pct(cur.roic - cur.wacc) + ' spread') : null
        )
      ),
      h(DataTable, {
        show: p.tableView,
        head: ['Period', 'ROIC', 'WACC', 'Spread'],
        rows: series.map(function (d) {
          return [d.period, pct(d.roic), pct(d.wacc), (d.roic >= d.wacc ? '+' : '') + pct(d.roic - d.wacc)];
        })
      })
    );
  }

  /* -------------------------------------------------------- SensitivityGrid */

  var SENS_STOPS = [0.02, 0.10, 0.30];

  function sensStep(value, price) {
    if (!price) return 'mid';
    var d = (value - price) / price;
    var a = Math.abs(d);
    if (a < SENS_STOPS[0]) return 'mid';
    return (d > 0 ? 'pos' : 'neg') + '-' + (a < SENS_STOPS[1] ? 1 : a < SENS_STOPS[2] ? 2 : 3);
  }

  function SensitivityGrid(props) {
    var p = props || {};
    var rows = p.rows || [], cols = p.cols || [], cells = p.cells || [];
    var price = p.price, current = p.current || {};

    return h('figure', { className: 'fb-c fb-sens' },
      h('figcaption', { className: 'fb-c__head' },
        h('span', { className: 'fb-c__title heading' }, p.title || 'Value per share by assumption'),
        h('span', { className: 'fb-c__sub caption' },
          p.subtitle || ('against a price of ' + money(price))),
        h(BasisChip, { basis: p.basis || 'mechanical', compact: true })
      ),
      h('table', { className: 'fb-sens__grid' },
        h('caption', { className: 'caption' },
          (p.rowLabel || 'Terminal growth') + ' × ' + (p.colLabel || 'Discount rate') +
          '. Every cell carries its value; the ring marks the assumption in force.'),
        h('thead', null, h('tr', null,
          h('th', { className: 'label' }, ''),
          cols.map(function (c) { return h('th', { key: c, className: 'label fb-num' }, c); })
        )),
        h('tbody', null, rows.map(function (r, ri) {
          return h('tr', { key: r },
            h('th', { className: 'label fb-num', scope: 'row' }, r),
            cols.map(function (c, ci) {
              var v = (cells[ri] || [])[ci];
              var step = sensStep(v, price);
              var isNow = current.row === ri && current.col === ci;
              return h('td', {
                key: c,
                className: cx('fb-sens__cell', 'fb-sens__cell--' + step, isNow && 'is-current'),
                title: (p.rowLabel || 'g') + ' ' + r + ' · ' + (p.colLabel || 'r') + ' ' + c +
                  ' → ' + money(v) + (isNow ? ' · in force' : '')
              }, h('span', { className: 'figure-sm' }, money(v)));
            })
          );
        }))
      ),
      h('ul', { className: 'fb-c__legend fb-sens__scale' },
        h('li', null, h('span', { className: 'fb-c__key fb-c__key--neg3' }), h('span', { className: 'label' }, 'well below price')),
        h('li', null, h('span', { className: 'fb-c__key fb-c__key--mid' }), h('span', { className: 'label' }, 'at price')),
        h('li', null, h('span', { className: 'fb-c__key fb-c__key--pos3' }), h('span', { className: 'label' }, 'well above price'))
      )
    );
  }

  global.Fairband = {
    ScreenTable: ScreenTable,
    BandHistory: BandHistory,
    HistoryBars: HistoryBars,
    SpreadChart: SpreadChart,
    SensitivityGrid: SensitivityGrid,
    PhaseBadge: PhaseBadge,
    BandMeter: BandMeter,
    ValueCell: ValueCell,
    ValueBridge: ValueBridge,
    ValidityWindow: ValidityWindow,
    PrincipalChip: PrincipalChip,
    BasisChip: BasisChip,
    OverrideRecord: OverrideRecord,
    ReportReader: ReportReader,
    ProposalCard: ProposalCard,
    ConfirmDialog: ConfirmDialog,
    TaggedInput: TaggedInput,
    Button: Button,
    PHASES: PHASES,
    DEFAULT_COLUMNS: DEFAULT_COLUMNS,
    formatDate: readable,
    formatMoney: money,
    // fairband: the extra columns' percentage, for the detail drawer.
    formatPercent: percent
  };
})(typeof window !== 'undefined' ? window : this);
