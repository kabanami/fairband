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
  (`2026-Q2`), `ttm` or an estimate year (`2026E`). A cite with no period skips the period check.

The server joins the parts with nothing between them. Put the spaces and the punctuation in the
plain parts.

The reader never sees a ref. The server numbers the cites as footnotes, one number for each
distinct ref in the order it is first cited, and lists the references once, after the last
section, each with its source in words. Write no footnote, no mark and no reference list yourself:
the cite is all the server needs.

Copy each ref from the tool that gave the figure. The reads of stored figures give each one with
its `ref`: `financials`, `quarters`, `financial_tables`, `estimates`, `price_history`, `peers` and
`multiples_history`. `filing_report` and `filing_search` give each row of a filing report with its
`rowRef`. Build every other ref from its record's id. `company` gives `snapshot.id`;
`reviews` and the answers of `override_add` and `override_drop` give the review's id; `secondary`
and `secondary_valuation` give the secondary valuation's; `sensitivity` gives the reading's;
`guidance` and `guidance_add` give a guidance record's; `finding_add` and `findings` give a
finding's; `kill_criterion_add` and `kill_criteria` give a kill criterion's; `derive` gives a
derivation's; a pass-through gives its `responseId`.

## The references

A ref is `<form>:<path>`, read for the report's company. A record of another company names
nothing.

| Ref | The stored value | Unit |
|---|---|---|
| `snapshot:<id>/value`, `/price`, `/levels/<name>`, the name `buy`, `fair_low`, `fair_high` or `trim` | the snapshot's value a share, price and levels | per-share |
| `snapshot:<id>/price_to_value` | price ÷ value | multiple |
| `snapshot:<id>/inputs/<name>` | a tagged input, by its name in `company`'s inputs; a word input (the moat class) reads its word. On a company in another currency, `fx_rate` is the exchange rate, units of the currency per US dollar, and `adr_ratio` on an ADR the whole number Fairband found between FMP's stored share count and the quote's, where the counts differ. On High Growth, Young Growth, Decline and Start-up, `debt` and `cash` are the newest balance sheet's, a quarter's or a fiscal year's, whose period their notes name, and `minority_interest` is that sheet's minority interest as it presents it: no figure where the sheet does not present the line, and a figure at or below zero as it stands, which the route counts as nil | the input's: currency for a code, per-share for `<code> a share`; none for `fx_rate`, multiple for `adr_ratio` and for `sales_to_capital` (write it `1.21x`) |
| `snapshot:<id>/intermediates/<path>` | an intermediate by its keys and list indexes, `belief/rate`; a list counts from 0. On Mature Growth and Mature Stable, the charge: `charge/return_by_year/<n>`, the return year n + 1 pays at, `charge/growth_by_year/<n>`, the growth year n + 1's reinvestment pays for (the next year's), and `charge/hold_years`, the years the runway return holds; on Mature Growth, `charge/revenue_steps/<n>`, the revenue step of year n + 2 the charge read, yours under `revenue.step_2` or `revenue.step_3`, so cite it from the review, `charge/revenue_steps_found/<n>`, the analysts' revenue step as found, and `charge/revenue_step_source/<n>`, where the step read came from, `consensus`, `agent`, `thin` (a step above `thin_revenue_step_max` on fewer than `analyst_min` revenue analysts, the earnings step paid for) or `none`; `runway_return/one_year`, the newest year's marginal return, shown and never used by the charge; `runway_return/constant_margin`, the five-year marginal return at a constant margin, the newest margin times the revenue added over the capital added, shown and never used by the charge, none with fewer than six ROIC years, a year of the span without a revenue, a newest revenue at or below zero, or a span over which capital did not grow by a fifth or revenue did not grow; `runway_return/without_goodwill/measure`, the return on capital without goodwill and intangibles, which the charge starts at, under its cap, only where the measure with them is below the hurdle rate (the note `return-without-goodwill`). On Mature Growth, `sbc_basis`, the stock-pay basis the anchor read (`includes-sbc`, `excludes-sbc` or `unknown`), and `sbc_ttm`, the trailing stock pay it read, a total in the reporting currency; under `earnings.sbc_basis` or `earnings.sbc` the review holds your figure, so cite it from the review. On Mature Growth, `anchor/source`, what the analysts' NTM EPS read: `periods`, the sum of the NTM window's EPS means, or `annual`, that sum corrected by the annual consensus of the last fiscal year the window reaches, where a period of the window in that year has fewer than `analyst_min` EPS analysts or no count; `anchor/periods_sum`, the sum of the window's EPS means on either source; and on `annual`, `anchor/annual/fiscal_year`, that fiscal year; `anchor/annual/eps` and `anchor/annual/analysts`, its annual EPS mean and its EPS analysts; `anchor/annual/year_sum`, the sum of the EPS means of its periods; `anchor/annual/share`, the window's share of them; and `anchor/annual/correction`, what the correction adds a share, (`eps` − `year_sum`) × `share`. On every route, `margin_history/operating/median` and `margin_history/net/median`, the ten-year median operating and net margins on the statements as reported, and `margin_history/operating/years` and `margin_history/net/years`, the fiscal years behind each, fewer than ten on a shorter history; a margin no year has is absent, and a ref to it names no figure. `outside_value_per_share`, the value outside the business, is written only under a `value.outside` override, so cite it from the review. On High Growth, Young Growth, Decline and Start-up, `minority_interest`, the minority interest the route subtracted, a total in the reporting currency at book, 0 where the newest balance sheet holds none above zero; under `balance.minority` the review holds your figure, so cite it from the review; and `balance_sheet/label` and `balance_sheet/period_end`, the period of the newest balance sheet that debt, cash and the minority interest were read from (`fiscal 2026 Q3`, `2026-09-30`) | none |
| `snapshot:<id>/phase/<field>` | a field of the classifier's evidence: `phase`, `growth_3y`, `margin`, `growth_word`, `margin_direction` and the others | the field's |
| `review:<id>/value`, `/price_to_value`, `/levels/<name>` | the review's value a share, price ÷ value and levels | per-share; multiple |
| `review:<id>/bridge/<n>/delta`, `/old`, `/new` | the bridge's line n, counted from 1: its change, the input's old and new value | per-share; the input's |
| `review:<id>/intermediates/<path>` | an intermediate of the reviewed result, by its path as a snapshot's: `implied_growth`, the growth the price needs under your overrides, which differs from the snapshot's. `override_add` and `override_drop` answer the review with its `result`, whose `intermediates` hold them | none |
| `secondary:<id>/value`, `/firm_value`, `/equity`, `/debt`, `/cash`, `/shares`, `/price_to_value`, `/levels/<name>` | the secondary valuation's figures | per-share, currency, count, multiple |
| `secondary:<id>/years/<t>/<line>`, `/terminal_fcff`, `/terminal`, `/terminal_pv` | on the drivers form, the projection's line of year t, `revenue`, `ebit`, `nopat`, `reinvestment`, `fcff` or `pv`; the terminal free cash flow, the terminal value and its present value; t counted from 1 | currency |
| `secondary:<id>/drivers/<name>`, `/drivers/<name>/<t>` | on the drivers form, a driver as you set it: `years`, `tax_rate`, `sales_to_capital`, `terminal_growth`; year t's `revenue_growth` or `operating_margin`, t counted from 1 | count for the years, multiple for sales-to-capital, percent for the others |
| `secondary:<id>/grid/<i>/<j>` | the grid's value a share at row i (a terminal growth, or the shift on the parts form) and column j (a rate), each counted from 1; the centre cell, `/grid/2/2`, is the value | per-share |
| `secondary:<id>/parts/<n>/pv/<t>`, `/parts/<n>/fcff/<t>`, `/parts/<n>/value`, `/parts/<n>/terminal`, `/parts/<n>/terminal_pv`, `/parts/<n>/terminal_growth` | on the parts form, part n's present value and free cash flow of year t, its value, its terminal value, the terminal's present value and its terminal growth; n and t counted from 1 | currency; percent for the terminal growth |
| `sensitivity:<id>/<i>/<j>` | a sensitivity reading's value a share at row i and column j, each counted from 1; a refused cell holds no value | per-share |
| `sensitivity:<id>/rows/<i>`, `/cols/<j>` | the axis value row i or column j names: the rate, growth or margin the cells of that row or column were read at, in its input's unit; a word axis (the moat class) its word. Cite it beside the cell, so the sentence "at a 10% runway return the value is $120" traces both figures | the input's |
| `guidance:<id>/low`, `/high`, `/midpoint`, `/step` | a guidance record's figures, of its period; the step only on a `gaap` fiscal-year revenue, EPS or net income record with the year before's actual on file | the metric's: currency for revenue, net income, free cash flow and capex, per-share for EPS, percent for the margin and the two growth rates; percent for the step |
| `multiple:<symbol>/<series>/<date>`, `multiple:<symbol>/<series>/<stat>` | a point of the trailing (`pe`) or the forward (`pe_forward`) P/E history by its date, or a statistic over the ten years to the series' newest day: `avg_10y`, `median_10y`, `high_10y`, `low_10y`; a date with no point (a loss, a day off the series) names nothing | multiple |
| `fact:<symbol>/<line>/<year, quarter or ttm>` | a stored statement line as the engine reads it: a fiscal year's, a stored quarter's by its fiscal label (`2027-Q1`), or the trailing figures'. `quarters` gives a quarter's lines with their refs | currency; per-share for EPS; count for the diluted shares |
| `table:<symbol>/<table>/<row>/<period>` | a cell of `financial_tables` by its column's period: a fiscal year (`2025`), that year's figure; `ttm`, the trailing twelve months' figure; a year and `E` (`2026E`), the analysts' estimate for that year; or, on the table `quarters`, a stored period (`2026-Q3`), that period's figure. A cell that is one stored line gives its `fact:` ref instead. Cite an estimate cell of revenue or EPS by the `estimate:` ref the read gives. A cite of an estimate cell, by either ref, may give its period as `2026E` or `2026`. A period the table has no column for names nothing | the row's |
| `estimate:<symbol>/<period>/<field>` | a stored consensus figure, the period a fiscal year (`2026`) or a quarter (`2026-Q4`) | currency; per-share for EPS; count for the analysts |
| `close:<symbol>/<date>` | a stored daily close | per-share |
| `peer:<symbol>/<peer>/<field>` | a mature peer's `market_cap`, `margin`, `margin_years`, `sales_to_capital` or `roic` | currency, percent, count, multiple, percent |
| `finding:<id>` | a finding's value, unit and period, as recorded | the finding's |
| `kill:<id>` | a kill criterion's threshold, the number you chose for it, whatever the criterion's state; it passes in Risks and kill criteria alone ("A threshold you choose"), and a criterion with no threshold names nothing | the threshold's |
| `derived:<id>` | a derivation's value | the derivation's |
| `filing:<id>/<sheet>/<row>/<col>` | a cell of a stored filing report as served, a number or a word as the tool shows it: the sheet by its name as the sheet list gives it, `~` written `~0` and `/` written `~1`, and the row and the cell by their indexes from 0. A row's `rowRef` plus `/<col>`, such as `filing:812/LEASES/2/0`; a row with no `rowRef` holds no cell to cite | none |
| `response:<id>/<json pointer>` | a field of a stored vendor response, such as `response:731/0/revenue` | none |
| `policy:<name>` | a policy value, by its name, or with a moat class or an index: `runway_years.Wide`, `fair_band.0` | the value's |

A record holds a percent as a fraction: 0.112. The cite writes it as a percentage: `11.2%`.

`number:<n>` is no ref a report cites: it is an operand of `derive` alone ("Your own
arithmetic"). A cite of it is `unresolved reference`: cite the derivation that used it.

A filing report's cell. Copy its ref from the answer: the row's `rowRef` plus `/<col>`, the cell's
index counted from 0. Never build a `filing:` ref by hand: a sheet name with a `/` or a `~` is
written otherwise inside a ref (`~1`, `~0`), so a ref built from the name as you read it may
resolve to nothing. A sheet's columns are periods or members, and a `filing:` ref names no
period, so a cite of last year's column passes the check as this year's would: read the column's
words (the sheet's `columns`, or the hit's `column`) before you cite a number, and name that period
in the sentence. The references list names the column by its index and its words. The sheet's
title names the scale (`$ in Millions`). A filing cell holds the number at its sheet's scale, so
scale the cell first: before it meets a figure in full units (a `fact:` or a `table:` figure), or
a cell of a sheet with another scale, take the `derive` `product` of the cell and its sheet's
scale, `number:1000000` for `$ in Millions` (`number:1000` for thousands). A row the title scales
apart takes its own scale: in a sheet "in Millions, except Per Share data" a figure a share is in
full units, and a count of shares may be in thousands, as the title says. A figure the filing
states is still cited from its cell: never record it as a finding in full units to compute with
it. Cite the number as the cell holds it, with no period (a `filing:` ref has none, so a cite that
names one fails), and write the scale word in the plain part after the cite:

```json
[
  "At the quarter's end, leases not yet commenced came to ",
  {"cite": "$12.5", "ref": "filing:<id>/Leases - Additional Informatio/2/0"},
  " million."
]
```

## How to write the number

The cite is the stored value at the report's rounding, by the ref's unit:

| Unit | Written to | Suffix | Example |
|---|---|---|---|
| currency (a total) | whole units, or a scale word at your own precision | `$` for US dollars, or none | `$391,035,000,000`, `$391.0 billion`; in TWD `3,809,054,300,000` after `TWD ` |
| a share price: `snapshot:<id>/price`, `/inputs/price`, a `close:` | cents, always | `$` or none | `$234.70` |
| per-share: a value, a level, an EPS | cents, or whole units | `$` for US dollars, or none | `$283`, `$6.42`; in TWD `12,807.36` after `TWD ` |
| percent | one decimal of the fraction × 100 | `%` | `22.7%` |
| multiple | two decimals | `x` or none | `1.18x` |
| years | one decimal | `years` or none | `12.5 years` |
| score | two decimals | none | `2.95` |
| count | a whole number, or a scale word at your own precision | none, never `$` | `15,204,137,000`, `15.2 billion` |
| none (an intermediate, a vendor field) | any suffix, at the decimals you write | any | `7.1%` |

A change may carry a `+`, as a bridge line does: `+$28`, `+5.0%`. A difference of two percents may
be written in points, `2.0 pp` or `2.0 percentage points`, compared as `2.0%` is.

The currency. `$` for a figure in US dollars only: the price, the value a share, the levels, a
close, a grid's or a reading's cells, a record's figure in US dollars, and every figure of a
company that reports in US dollars but a record it states in another currency. A company in
another currency (`company`'s `currency`) has its statements, consensus, inputs, overrides and
secondary valuation's totals in that currency. A money figure you record, a finding's, a guidance
record's or a kill criterion's threshold, is in the currency the company states it in: pass
`currency` when that is not the reporting currency, and every read answers the record's
`currency`. Cite a figure in any currency but the US dollar with no `$`: put the code before the
number in the plain part, `"TWD "` then `{"cite": "331.25", "ref": ...}`, or its sign for €, £
and ¥, `"€"` then the cite. So a record's figure takes `$` where it is in US dollars, and its code
in the plain text before a bare cite otherwise. The cite is the number alone, read in the ref's
unit; a sign or a code alone in a plain part is no quantity. On a `finding:`, a `guidance:` or a
`kill:` cite the check knows the record's currency: a `$` there passes only where the record is in
US dollars, and is `wrong unit` otherwise, "finding:812 reads TWD 1,000,000,000: write the number
without $ and name TWD before it". On any other ref it does not know the currency, so the rule is
yours to keep.

A record in another currency than the reporting one is kept out of money arithmetic until you
convert it ("Your own arithmetic"): to set an input from it, or to compare it with a statement,
take first the `derive` `product` of a US-dollar figure and `snapshot:<id>/inputs/fx_rate`, the
reporting currency per US dollar. A derivation of it keeps its currency until that product, its
quarter or its average among them, so convert first, or keep to figures in its own currency. A
figure in a third currency, neither the reporting currency nor the US dollar, has no rate: it is
stated and cited in its own currency and enters no arithmetic with the company's figures.

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

A cite's period must be the ref's. `FY2025` reads as `2025`, and `2026E` as `2026`. A ref with a
period and a cite with none passes. A ref with no period (a snapshot's figure, a policy value)
fails a cite that names one.
A finding's and a guidance record's period is the one recorded: a guidance quarter reads `2027Q1`,
with no dash, while a consensus quarter reads `2027-Q1`. A close's and a multiple's period is its
date. When in doubt, leave the period out.

## The snapshot

Cite the company's latest snapshot: the one `company` gave you. A price refresh during your
research is fine: a reprice of the cited snapshot, with the same data date, method, policy and
settings, counts as the cited one. A revalue or a full refresh in between is not: the report is
rejected `wrong snapshot`, with the latest snapshot's id in the detail. Read `company` again, take
the new ids, check each figure, and submit again. A `secondary:` and a `sensitivity:` ref rest on
their record's snapshot too, and a `derived:` ref on every snapshot its operands rest on, the
operands of a derivation it takes as an operand included: after a revalue, make the reading and
those derivations again, and the secondary valuation too where neither the route nor your review
values the company; where either does, the server refuses one. A `finding:`, a `guidance:`, a
`kill:` and a `multiple:` ref rest on none, and so does a fixed number.

A `review:` cite must be the company's current review: the newest review on the latest snapshot,
or the one that snapshot reprices. Each applied override and each drop makes a new review; a
refused override makes none. Cite the review your last applied `override_add` or your last
`override_drop` answered. When a drop leaves no override applied, the
company has no review: cite the snapshot. A `sensitivity:` cite goes stale the same way: a reading
taken before your last applied override or drop is `wrong snapshot`, "the review moved". Take the
reading again after your last override, and cite the new one.

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
- a list's number at a line's start with a space after it on the same line, `1. `, `12. ` or
  `12) `, and a table's separator row, `|---|---|`: marks, not quantities (a number alone on its
  line, `12.`, is a quantity);
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

A number Fairband does not store (from a sentence of a filing, a document the filing report does
not hold, a transcript you read elsewhere, a web page) enters a report only as a finding. A filing
report's number cell is stored: cite its `filing:` ref, with no finding. Record a finding with
`finding_add(symbol, as_of, text, source, value, unit, period, currency?)`, then cite
`finding:<id>`:

- `value` in the unit: a total in full (`2100000000`), a percent as a fraction (`0.25` for 25%), a
  per-share figure, a multiple, a count, a score or years; money in the currency the company
  states it in, with `currency` when that is not the reporting currency ("The currency");
- `period` as the fact's: `2025`, `2026-Q2` or `ttm`; the cite's period must match it;
- `source` as `{kind, ref, note}`: where a reader finds the fact.

The check cannot prove a finding true. It proves the finding is recorded with its source.

A figure you take from a secondary analysis (a broker's note, an article, a data site that quotes
the filing) names that source in its finding, not the filing it quotes, and the report says that
the filing itself was not read.

## A threshold you choose

A risk or a kill criterion often names a line to cross. A threshold you choose is not a fact, so it
is never a finding, and a number of your own in the text is `a number with no reference`. Write
the event one of three ways:

- Tie it to a stored figure, and cite that figure. "The ROIC falls below the yearly return of 9.0%
  that investors require" cites `policy:required_return`, or the returns table's `hurdle_rate`
  cell. "The operating margin falls below its 2025 level of 31.2%" cites that cell of the growth
  table. A reader can follow such a line to its source, so it is the better criterion where one
  serves.
- Put the threshold on the kill criterion. Record the criterion with
  `kill_criterion_add(symbol, text, threshold, unit, currency?)` before you write the report: the
  number, its unit (one of a finding's) and, for a money figure, its currency as "The currency"
  says. Cite it as `kill:<id>` in Risks and kill criteria (section 11 of a full report, the ninth
  of a valuation review), and only there: anywhere else it is `unresolved reference`, and `derive`
  refuses it, so it enters no arithmetic. The references list names it "kill criterion <id>, a
  threshold the author chose". Leave the criterion out of the report's `kill_criteria`: that list
  takes text alone, a threshold put there is dropped without a word, and the criterion would be
  recorded twice. If the report is not published, retire the criterion with
  `kill_criterion_set(id, "retired", reason)`.
- State it in words: "revenue falls two quarters in a row", "the operating margin turns negative".

A kill criterion in the report's `kill_criteria`, or one you record with no threshold, is text
only: it carries no cite. Name the stored figure in words, "the ROIC falls below the yearly return
that investors require", or state the event, "revenue falls two quarters in a row"; section 11 of
the report cites the figure.

## Your own arithmetic: a derivation

Every figure you would compute goes through `derive(symbol, derivations)`, then a cite
`derived:<id>`. A derivation is `{operation, a, b, years?}` over two refs, a table cell included:

| Operation | Gives | Unit |
|---|---|---|
| `ratio` | a ÷ b | multiple for two figures in one unit, else none |
| `difference` | a − b | the shared unit, else none |
| `sum` | a + b | the shared unit, else none |
| `product` | a × b | the other operand's unit when one is a multiple or a percent; currency for a figure a share times a count; else none |
| `growth` | a ÷ b − 1 | percent |
| `cagr` | (a ÷ b)^(1 ÷ years) − 1 | percent |

One operand may be a fixed number, written `number:<n>` where a ref goes, in digits alone: the
whole numbers 0 to 12, then 52, 100, 365, 1000 and each further power of ten up to
1,000,000,000,000. A number has no unit, so the result's follows the stored figure: a `sum`, a
`difference` or a `product` with a number, and a `ratio` of a figure over a number, keep the
figure's unit; a `ratio` of a number over a figure has none. Any other number is refused, "a fixed
number is one of 0 to 12, 52, 100, 365 or a power of ten up to 1,000,000,000,000, not <what was
written>", and so are two numbers in one derivation, "a derivation needs a stored figure". A
derivation with a number anywhere in it, its own operands or those of a `derived:` operand, must
move with a stored figure. One that keeps its value whatever its figures are is a number you chose
passed off as a sourced one, and is refused, "a derivation with a fixed number must depend on a
stored figure: this one has the same value whatever its figures are": a figure times `number:0`, a
number over a figure over itself, a figure plus a number less the same figure. A figure that is
nought moves nothing, so a derivation of it with a number is refused in the same words: cite the
figure itself.

A fixed number is a number of arithmetic, never a figure you chose: the server takes no other, and
a multiple, a rate or a threshold you assume is not arithmetic. A threshold goes on its kill
criterion ("A threshold you choose"). The recipes:

- a complement: the `difference` of `number:1` and a rate, such as 1 less the tax rate;
- an average: the `sum` of the figures (chained `sum` calls for more than two), then the `ratio`
  of that `derived:` id and their count, `number:2` for two;
- a change of sign: the `difference` of `number:0` and the figure;
- a filing cell before it meets a figure in full units: the `product` of the cell and its sheet's
  scale, `number:1000000` for `$ in Millions`, a figure with no unit, as the cell has none; a row
  the title scales apart takes its own scale (a figure a share in a sheet "in Millions, except Per
  Share data" is in full units, and a count of shares may be in thousands);
- a PEG: the `ratio` of the P/E and the growth rate, a figure with no unit that is a hundred times
  the PEG, since the rate is a fraction; then the `ratio` of that `derived:` id and `number:100`.

A figure a filing states is still cited from its cell: a finding in full units is not the way to
compute with it.

One call takes many derivations. A derivation may take a `derived:` ref as `a` or `b`, so a chain
(a sum, then a ratio over it) takes one call for each link. A ref that names no number refuses the
whole call, "unresolved reference: <ref>", and stores none of it; so does a `kill:` ref, since a
threshold you chose enters no arithmetic. A division by zero, a `growth` or a `cagr` from a base
at or below zero, a `cagr` over a negative ratio or a result that is not finite has no value, and
a cite of it fails.

A record in another currency. A finding or a guidance record whose `currency` is not the
reporting currency stays out of money arithmetic until you convert it, and so does every
derivation of it: its quarter (a `ratio` over `number:4`), its average with another record, the
record times `number:1`, each keeps its currency until its `product` with the rate. With a money
figure (a total or a figure a share) that is not in its own currency, the record or a derivation
of it has no value, and no derivation with it has a money unit; with another record in its
currency, or a derivation of one, it gives a growth, a ratio, or a sum or a difference with no
unit. The `product` of a US-dollar record, or of a derivation of one, and
`snapshot:<id>/inputs/fx_rate` is the figure in the reporting currency, with no unit, which then
combines with anything: convert so first, before you set an input from the record or set it
against a statement, or keep to figures in its own currency. On a company in another currency a
US-dollar record has no value with the price, the value a share, the levels, a close or a grid's
cells, whose currency the server does not know. A derivation with no unit is cited at the
decimals you write: name its currency in the text.

A price over earnings is `ratio` of `snapshot:<id>/price` and an EPS ref, cited `12.34x`. A
multiple written in plain text, `2.4x`, is rejected: derive it and cite it.

## The six failures

A rejected report answers `{"refused": "rejected: <n> findings", "status": 422, "findings": [...]}`.
Each finding is `{where, what, detail}`. `where` is the section and the part, counted from 1 in
your submission, and the text at fault: `section 1, part 3: $12.345`. For a judgment it is the
judgment and its field: `judgment moat, decision: 11.2%`. A cite gets one finding, the first that
applies in the order wrong snapshot, not emitted, unresolved, wrong period, wrong unit. A plain part
gets one for each quantity.

| `what` | It means | What to do |
|---|---|---|
| `a number with no reference` | a quantity in plain text, or in a judgment's text | Cite it. Write a small count in words. Reword a name with a free number. Record a fact Fairband does not hold as a finding first. Never record a threshold you chose as a finding: tie the event to a cited figure where one serves, else put it on its kill criterion and cite `kill:<id>` in Risks and kill criteria, or state it in words ("A threshold you choose"). Take every figure out of the judgment's text. |
| `unresolved reference` | the ref names nothing, or the record holds no figure there; or it is a `number:` ref, an operand of `derive` alone; or a `kill:` ref outside Risks and kill criteria | Copy the ref from the tool's answer again: check the form, the id, the symbol and the year. A table cell with no value cannot be cited: say in words that the figure is not on file. A `number:` cite, "number:100 is an operand of derive: cite the derivation": cite the derivation that used it. A `kill:` cite in another section, "kill:12 is the author's own threshold: cite it in Risks and kill criteria": move it there, or tie the sentence to a stored figure. |
| `wrong unit` | the suffix does not fit the ref's unit, or the number is not the stored value at the report's rounding; or a `$` on a record's figure in another currency than the US dollar | The detail gives the value as the cite should read. Write it so. A price takes cents; a percent one decimal; a multiple two. A record's figure in another currency: write the number without `$`, and its code before it in the plain part. |
| `wrong period` | the cite's period is not the ref's (a quarter reads the same with its dash or without, `2027-Q1` as `2027Q1`) | Correct the period or the ref, or leave the period out. |
| `wrong snapshot` | the ref rests on a snapshot other than the latest (a `derived:` ref on any snapshot its operands rest on, nested ones' too), a `review:` ref is not the current review, or a `sensitivity:` ref's reading was taken before the review moved | Read `company` and `reviews` again. Take the ids the detail names. Check each figure, since a revalue may have moved them, and submit again. |
| `a derived figure the engine has not emitted` | a `derived:` ref with no stored derivation of the company, or a multiple in plain text | Call `derive` and cite the `derived:` id it answers. |

Fix every finding of the answer, then submit the whole report again.

## The judgments' text

The check reads the `decision` of every judgment. Any quantity there is `a number with no
reference`, since a judgment holds no cite. Keep the decisions in words, and put their figures,
cited, in section 8.

## Before the numbers: the structure

The server checks the structure before it reads a number, in this order: the section count (twelve
for a full report, ten for a valuation review); the stance word; the judgments the route needs, one
of each; the headings, in order; and a secondary valuation on a refused snapshot (none where the
route or your review values the company, and none on a snapshot refused for a reason you cannot
fix: no diluted share count, the reporting currency's or the share basis's). The first check that
fails is answered with its one sentence (400), such as "the
report needs a secondary valuation on snapshot <id>", and no number is checked. Fix the one thing
the sentence names and submit again.
