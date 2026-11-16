/* The drawer mockup: three forms of the new drawer, side by side, with the app's own components
   and one company's data. A throwaway: nothing here is product code. */
(function () {
  'use strict';

  var h = React.createElement;
  var F = Fairband;
  var D = window.MOCK;
  var prof = D.profile, res = D.detail.result, lv = res.levels;
  var PHASE_NUMBER = {
    'Start-up': 1, 'Young Growth': 2, 'High Growth': 3,
    'Mature Growth': 4, 'Mature Stable': 5, 'Decline': 6
  };

  function n(v, d) {
    return v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function money(v) { return '$' + n(v, 2); }

  function kv(rows) {
    return h('div', { className: 'cp-kv' }, rows.map(function (row) {
      return h('div', { className: 'cp-kv__row', key: row[0] },
        h('span', { className: 'body cp-kv__k' }, row[0]),
        h('span', { className: 'figure cp-kv__v' }, row[1]));
    }));
  }

  function head() {
    return h('header', { className: 'dr-head' },
      D.logo ? h('img', { className: 'dr-logo', src: D.logo, alt: '' }) : null,
      h('h2', { className: 'ticker dr-ticker' }, prof.symbol),
      h(F.PhaseBadge, { phase: PHASE_NUMBER[res.phase.phase], size: 'sm' }),
      h('p', { className: 'body dr-name' }, prof.companyName),
      h('p', { className: 'caption dr-sector' }, prof.sector + ' · ' + prof.industry),
      h('p', { className: 'body dr-brief' }, prof.description));
  }

  function band() {
    return h('section', { className: 'dr-band' },
      h(F.BandMeter, {
        low: lv.fair_low, high: lv.fair_high, price: res.price, fairValue: res.value,
        buyLevel: lv.buy, trimLevel: lv.trim, designation: res.designation, showScale: false,
        gap: n(res.price_to_value, 2) + ' × the mechanical value'
      }),
      kv([
        ['Fair value', money(res.value)],
        ['Buy level', money(lv.buy)],
        ['Fair band', money(lv.fair_low) + ' – ' + money(lv.fair_high)],
        ['Trim level', money(lv.trim)]
      ]));
  }

  function buttons() {
    return h('div', { className: 'dr-actions' },
      h(F.Button, { variant: 'primary', size: 'sm' }, 'Company page'),
      h(F.Button, { variant: 'secondary', size: 'sm' }, 'Request research'));
  }

  function drawer(parts) {
    return h('aside', { className: 'dr' },
      h('div', { className: 'dr-bar' }, h(F.Button, { variant: 'quiet', size: 'sm' }, 'Close')),
      h('div', { className: 'dr-body' }, parts));
  }

  var OPTIONS = [
    {
      id: 'a', name: 'A. The company and its value',
      note: 'The logo, the name, the brief, the value band and the two buttons. No Details.',
      parts: function () { return [head(), band(), buttons()]; }
    },
    {
      id: 'b', name: 'B. The company only',
      note: 'The logo, the name, the brief and the two buttons. The value is on the company page.',
      parts: function () { return [head(), buttons()]; }
    },
    {
      id: 'c', name: 'C. As A, with Details kept',
      note: 'As A. Details stays at the foot, closed, with the inputs and the route inside.',
      parts: function () {
        return [head(), band(), buttons(),
          h('p', { className: 'control dr-details' }, 'Details ▾')];
      }
    }
  ];

  function Page() {
    return h('main', { className: 'dr-page' },
      h('h1', { className: 'title dr-title' }, 'The new drawer: which form?'),
      h('p', { className: 'body dr-lead' },
        'Each form drops the text about what the price needs. Click the one you want, or say ' +
        'in the terminal what to change. A click on the ticker in the table opens the company ' +
        'page; a click on the rest of the row opens this drawer.'),
      h('div', { className: 'dr-options' }, OPTIONS.map(function (option) {
        return h('div', {
          key: option.id, className: 'card dr-option', 'data-choice': option.id,
          onClick: function (event) {
            if (window.toggleSelect) window.toggleSelect(event.currentTarget);
          }
        },
          h('h2', { className: 'heading dr-option__name' }, option.name),
          h('p', { className: 'caption dr-option__note' }, option.note),
          drawer(option.parts().map(function (part, i) {
            return h(React.Fragment, { key: i }, part);
          })));
      })));
  }

  ReactDOM.createRoot(document.getElementById('root')).render(h(Page));
})();
