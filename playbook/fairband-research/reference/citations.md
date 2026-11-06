# Citations

The server checks every number in a report before it publishes it. A report with one number that
traces to nothing is rejected whole, and the published report stays as it was. This file gives the
check's rules in the order you meet them.

## A cite

A section is a list of parts. A part is plain text, or a cite: a number with the reference of the
stored value it shows.

```json
[
  "The price of ",
  {"cite": "$234.70", "ref": "snapshot:412/price"},
  " is below the value of ",
  {"cite": "$283", "ref": "review:88/value"},
  ". Revenue grew ",
  {"cite": "8.4%", "ref": "table:EXMP/growth/revenue_growth/2025", "period": "2025"},
  " in fiscal 2025."
]
```

- `cite`: the text the reader sees. It is one number with its sign and its unit, or one word.
  Nothing else: `$283 a share` is not a cite. Write the cite `$283`, then the plain part ` a share`.
- `ref`: the stored value the number shows (below).
- `period`, optional: the period the text claims, a fiscal year (`2025` or `FY2025`), a quarter
  (`2026-Q2`) or `ttm`. A cite with no period skips the period check.

The server joins the parts with nothing between them. Put the spaces and the punctuation in the
plain parts.

Copy each ref from the tool that gave the figure. The reads of stored figures give each one as
`{value, unit, ref}`: `financials`, `financial_tables`, `estimates`, `price_history` and `peers`.
Build every other ref from its record's id. `company` gives `snapshot.id`; `reviews` and the
answers of `override_add` and `override_drop` give the review's id; `secondary` gives the secondary
valuation's; `finding_add` and `findings` give a finding's; `derive` gives a derivation's; a
pass-through gives its `responseId`.

## The references

A ref is `<form>:<path>`, read for the report's company. A record of another company names
nothing.

| Ref | The stored value | Unit |
|---|---|---|
| `snapshot:<id>/value`, `/price`, `/levels/<name>`, the name `buy`, `fair_low`, `fair_high` or `trim` | the snapshot's value a share, price and levels | per-share |
| `snapshot:<id>/price_to_value` | price ÷ value | multiple |
| `snapshot:<id>/inputs/<name>` | a tagged input, by its name in `company`'s inputs; a word input (the moat class) reads its word | the input's |
| `snapshot:<id>/intermediates/<path>` | an intermediate by its keys and list indexes, `belief/rate` | none |
| `snapshot:<id>/phase/<field>` | a field of the classifier's evidence: `phase`, `growth_3y`, `margin`, `growth_word`, `margin_direction` and the others | the field's |
| `review:<id>/value`, `/price_to_value`, `/levels/<name>` | the review's value a share, price ÷ value and levels | per-share; multiple |
| `review:<id>/bridge/<n>/delta`, `/old`, `/new` | the bridge's line n, counted from 1: its change, the input's old and new value | per-share; the input's |
| `secondary:<id>/value`, `/firm_value`, `/equity`, `/debt`, `/cash`, `/shares`, `/price_to_value`, `/levels/<name>` | the secondary valuation's figures | per-share, currency, count, multiple |
| `secondary:<id>/parts/<n>/pv/<t>`, `/parts/<n>/fcff/<t>`, `/parts/<n>/value`, `/parts/<n>/terminal`, `/parts/<n>/terminal_pv`, `/parts/<n>/terminal_growth` | part n's present value and free cash flow of year t, its value, its terminal value, the terminal's present value and its terminal growth; n and t counted from 1 | currency; percent for the terminal growth |
| `fact:<symbol>/<line>/<year or ttm>` | a stored statement line as the engine reads it | currency; per-share for EPS; count for the diluted shares |
| `table:<symbol>/<table>/<row>/<year>` | a cell of `financial_tables` | the row's |
| `estimate:<symbol>/<period>/<field>` | a stored consensus figure, the period a fiscal year (`2026`) or a quarter (`2026-Q4`) | currency; per-share for EPS; count for the analysts |
| `close:<symbol>/<date>` | a stored daily close | per-share |
| `peer:<symbol>/<peer>/<field>` | a mature peer's `market_cap`, `margin`, `margin_years`, `sales_to_capital` or `roic` | currency, percent, count, multiple, percent |
| `finding:<id>` | a finding's value, unit and period, as recorded | the finding's |
| `derived:<id>` | a derivation's value | the derivation's |
| `response:<id>/<json pointer>` | a field of a stored vendor response, such as `response:731/0/revenue` | none |
| `policy:<name>` | a policy value, by its name, or with a moat class or an index: `runway_years.Wide`, `fair_band.0` | the value's |

A record holds a percent as a fraction: 0.112. The cite writes it as a percentage: `11.2%`.

## How to write the number

The cite is the stored value at the report's rounding, by the ref's unit:

| Unit | Written to | Suffix | Example |
|---|---|---|---|
| currency (a total) | whole dollars, or a scale word at your own precision | `$` or none | `$391,035,000,000`, `$391.0 billion` |
| a share price: `snapshot:<id>/price`, `/inputs/price`, a `close:` | cents, always | `$` or none | `$234.70` |
| per-share: a value, a level, an EPS | cents, or whole dollars | `$` or none | `$283`, `$6.42` |
| percent | one decimal of the fraction × 100 | `%` | `22.7%` |
| multiple | two decimals | `x` or none | `1.18x` |
| years | one decimal | `years` or none | `12.5 years` |
| score | two decimals | none | `2.95` |
| count | a whole number, or a scale word at your own precision | none, never `$` | `15,204,137,000`, `15.2 billion` |
| none (an intermediate, a vendor field) | any suffix, at the decimals you write | any | `7.1%` |

A change may carry a `+`, as a bridge line does: `+$28`, `+5.0%`. A difference of two percents may
be written in points, `2.0 pp` or `2.0 percentage points`, compared as `2.0%` is.

The number must lie within half a step of the stored value at that rounding. `22.7%` cites
0.22702; `23%` does not. When in doubt, write exactly the decimals in the table: `22.7%` for
0.22702, `23.0%` for 0.23.

Four rules more:

- A scale word. A total may take `thousand`, `million`, `billion` or `trillion` (or `k`, `m`, `mn`,
  `b`, `bn`, `tn`), with `$` or none: `$2.1 billion`, `$391bn`, `$126M`. A count may take one with
  no `$`: `15.2 billion`. The server compares at the decimals you wrote, in that scale, so
  `$2.1 billion` cites 2,123,000,000 and `$2.10 billion` does not. Give two significant figures at
  least: `$2 billion` and `$0.4 billion` fail. A whole-dollar total always passes.
- Outflows by their size. The store signs capital spending, dividends and buybacks as negative
  (`fact:` lines, the table rows and the snapshot's trailing inputs). A cite with no sign gives
  their size: "capital spending was $126,000,000" cites −126,000,000. A cite with a sign
  (`−$126,000,000` or `($126,000,000)`) must match the signed value. The net investing and
  financing flows keep their sign.
- A ratio as a percentage. A `%` cite may cite a `derived:` ratio or a table's ratio cell (a
  multiple of two figures in one unit), compared × 100: "stock compensation was 9.5% of net income"
  cites a ratio of 0.0952.
- A word. A cite of a word ref is the word, in any case: `{"cite": "Wide", "ref":
  "snapshot:412/inputs/moat_class"}`, `{"cite": "Mature Growth", "ref":
  "snapshot:412/phase/phase"}`.

## The period

A cite's period must be the ref's. `FY2025` reads as `2025`. A ref with a period and a cite with
none passes. A ref with no period (a snapshot's figure, a policy value) fails a cite that names one.

## The snapshot

Cite the company's latest snapshot: the one `company` gave you. A price refresh during your research
is fine: a reprice of the cited snapshot, with the same data date, method, policy and settings,
counts as the cited one. A revalue or a full refresh in between is not: the report is rejected
`wrong snapshot`, with the latest snapshot's id in the detail. Read `company` again, take the new
ids, check each figure, and submit again.

A `review:` cite must be the company's current review: the newest review on the latest snapshot,
or the one that snapshot reprices. Each applied override and each drop makes a new review; a
refused override makes none. Cite the review your last applied `override_add` or your last
`override_drop` answered. When a drop leaves no override applied, the
company has no review: cite the snapshot.

## What counts as a quantity

Every quantity in plain text is rejected. Cite it, or write it in words.

A quantity is:

- any number a currency sign leads, whatever follows: `$5`, `US$5`, `$391bn`, `€1.5B`;
- a decimal, alone or joined to a one-letter scale: `4.2`, `1.5B shares`, `2.3M users`;
- a number before a unit word, with or without a space: `12 billion`, `50bps`, `5 percentage
  points`, `3 years`;
- a percentage: `11.2%`, `40 percent`, `5 per cent`;
- a multiple: `12.3x`, `5 x`, `12.3×`, `15X`;
- an integer of two or more digits: `17`, `500`;
- any of these with a sign or in parentheses.

Not a quantity, so plain text may hold it:

- a year from 1990 to 2099: `2025`;
- a date: `2026-11-06`, `3 Dec 2026`;
- a number joined to letters: `FY2025`, `Q3`, `COVID-19`, `5G`, `3M`, `401k`, `Phase 2b`;
- a filing form: `10-K`, `8-K`, `20-F`;
- a section's or an item's number: `section 13.3`, `Item 10`;
- anything in a URL or after a slash;
- an integer of one digit with no unit word: `7`.

Write small counts in words: "three reasons", "two quarters in a row", "the past five years".
These forms count, so reword them:

- `52-week high`: write "the high of the past year";
- `10-year`: write "ten-year";
- `over 3 years`: write "over three years" (`3 years` is a number with a unit word);
- `top 10 customers`: write "top ten customers";
- `S&P 500`, `Boeing 737`: a name with a free number of two or more digits; write "the S&P index",
  "Boeing's narrow-body jet";
- a report's, a snapshot's or a work item's id: never write one in the text; name a report by its
  date.

## A figure from outside Fairband: a finding first

A number Fairband does not store (from a filing, a transcript you read elsewhere, a web page) enters
a report only as a finding. Record it with `finding_add(symbol, as_of, text, source, value, unit,
period)`, then cite `finding:<id>`:

- `value` in the unit: a total in dollars in full (`2100000000`), a percent as a fraction (`0.25`
  for 25%), a per-share figure in dollars, a multiple, a count, a score or years;
- `period` as the fact's: `2025`, `2026-Q2` or `ttm`; the cite's period must match it;
- `source` as `{kind, ref, note}`: where a reader finds the fact.

The check cannot prove a finding true. It proves the finding is recorded with its source.

## A threshold you choose

A risk or a kill criterion often names a line to cross. A threshold you choose is not a fact, so it
is never a finding. A number of your own in the text is `a number with no reference`. Write the
event one of two ways:

- Tie it to a stored figure, and cite that figure. "The ROIC falls below the hurdle rate of 9.0%"
  cites `policy:required_return`, or the returns table's `hurdle_rate` cell. "The operating margin
  falls below its 2025 level of 31.2%" cites that cell of the growth table.
- State it in words: "revenue falls two quarters in a row", "the operating margin turns negative".

A kill criterion you record, with `kill_criterion_add` or in a report's `kill_criteria`, is text
only: it carries no cite. Name the stored figure in words, "the ROIC falls below the hurdle rate",
or state the event, "revenue falls two quarters in a row"; section 10 of the report cites the
figure. A threshold that no stored figure gives is a question for the founder: ask the user, and
state the event in words meanwhile. A stored threshold on a kill criterion is a later piece of
Fairband.

## Your own arithmetic: a derivation

Every figure you would compute goes through `derive(symbol, derivations)`, then a cite
`derived:<id>`. A derivation is `{operation, a, b, years?}` over two refs, a table cell included:

| Operation | Gives | Unit |
|---|---|---|
| `ratio` | a ÷ b | multiple for two figures in one unit, else none |
| `difference` | a − b | the shared unit, else none |
| `sum` | a + b | the shared unit, else none |
| `growth` | a ÷ b − 1 | percent |
| `cagr` | (a ÷ b)^(1 ÷ years) − 1 | percent |

One call takes many derivations. A derivation may take a `derived:` ref as `a` or `b`, so a chain
(a sum, then a ratio over it) takes one call for each link. A ref that names no number refuses the
whole call, "unresolved reference: <ref>", and stores none of it. A division by zero, a `cagr` over
a negative ratio or a result that is not finite has no value, and a cite of it fails.

A price over earnings is `ratio` of `snapshot:<id>/price` and an EPS ref, cited `12.34x`. A
multiple written in plain text, `2.4x`, is rejected: derive it and cite it.

## The six failures

A rejected report answers `{"refused": "rejected: <n> findings", "status": 422, "findings": [...]}`.
Each finding is `{where, what, detail}`. `where` is the section and the part, counted from 1 in
your submission, and the text at fault: `section 1, part 3: $12.345`. For a judgment it is the
judgment and its field: `judgment moat, bull: 11.2%`. A cite gets one finding, the first that
applies in the order wrong snapshot, not emitted, unresolved, wrong period, wrong unit. A plain part
gets one for each quantity.

| `what` | It means | What to do |
|---|---|---|
| `a number with no reference` | a quantity in plain text, or in a judgment's text | Cite it. Write a small count in words. Reword a name with a free number. Record a fact Fairband does not hold as a finding first. Never record a threshold you chose as a finding: tie it to a cited figure or state it in words ("A threshold you choose"). Take every figure out of the judgment's text. |
| `unresolved reference` | the ref names nothing, or the record holds no figure there | Copy the ref from the tool's answer again: check the form, the id, the symbol and the year. A table cell with no value cannot be cited: say in words that the figure is not on file. |
| `wrong unit` | the suffix does not fit the ref's unit, or the number is not the stored value at the report's rounding | The detail gives the value as the cite should read. Write it so. A price takes cents; a percent one decimal; a multiple two. |
| `wrong period` | the cite's period is not the ref's | Correct the period or the ref, or leave the period out. |
| `wrong snapshot` | the ref rests on a snapshot other than the latest, or a `review:` ref is not the current review | Read `company` and `reviews` again. Take the ids the detail names. Check each figure, since a revalue may have moved them, and submit again. |
| `a derived figure the engine has not emitted` | a `derived:` ref with no stored derivation of the company, or a multiple in plain text | Call `derive` and cite the `derived:` id it answers. |

Fix every finding of the answer, then submit the whole report again.

## The judgments' text

The check reads the `bull`, `bear` and `decision` of every judgment. Any quantity there is
`a number with no reference`, since a judgment holds no cite. Keep the judgments in words, and put
their figures, cited, in section 8.
