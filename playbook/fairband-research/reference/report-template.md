# The report

A report is the agents' written research on one company, in one of two modes. The server publishes
it whole or rejects it whole. This file gives its shape: the submission, the twelve sections, the
summary page and a full example.

The report reads as a story about the business. Section 5, the last earnings call, gives
management's story. Section 6 argues it, and section 7, the thesis, decides it. Section 8 is the
only section that talks about the valuation and its detail. Every other section argues the business
and its outlook.

## The submission

`report_submit(symbol, mode, stance, sections, judgments, kill_criteria?, news_items?, work_item_id?)`

- `mode`: the work item's mode, `full report` or `valuation review`.
- `stance`: `buy`, `hold`, `trim` or `avoid`.
- `sections`: each `{heading, parts}`, in the order below, under the exact headings below. A full
  report has twelve sections. A valuation review has ten: it leaves out "The business" and
  "Industry and competition".
- `judgments`: the record of your input decisions, one of each kind, `{judgment, decision,
  override_id?}`. Every report gives `phase`, `moat` and `belief`. A Mature Growth or Mature
  Stable company adds `roic`; a High Growth, Young Growth or Start-up company adds
  `target_margin`. A judgment takes no other key: a `bull` or a `bear` is refused.
- `kill_criteria`, optional: the new kill criteria this report sets, each `{text}`.
- `news_items`, optional: the dated items section 10 discusses that are not yet recorded, each
  `{date, headline, source, text, kill_criterion_id?}`.
- `work_item_id`, optional: the work item the report completes.

The server checks the structure first: the section count, the stance, the judgments, the headings,
and a secondary valuation on a refused snapshot. A valued snapshot needs none, nor does a refused
one your review values: the secondary valuation is the fallback where neither the route nor your
review values the company, and the server refuses one where either does. A snapshot refused for
a reason you cannot fix (no diluted share count, the reporting currency's or the share basis's)
needs none either, since the secondary valuation refuses it.
Each failure is one sentence, such as "section 5 is headed 'The last earnings call', not
'Life-cycle phase'" or "the report needs a secondary valuation on snapshot 388". Then it checks
every number (`reference/citations.md`).

The server writes the references list (each cite's footnote, numbered, with its source in words),
Appendix A (the audit: every input with its tag and source, the overrides, the guidance on file,
the bridge, the secondary valuation's drivers and projection on a refused row or the reason there
is none, the checks that ran, the versions) and Appendix B (the glossary). Write none of them.

## The sections

Put the answer first in each section. Keep each sentence to one idea.

| # | Heading | Mode | What it holds |
|---|---|---|---|
| 1 | Summary | both | One page: the stance; the thesis in two or three sentences; the value against the price and the levels (on a refused row with no reviewed value, the secondary valuation's value in its place); the phase in one sentence, with the word "cyclical" when the business is; three reasons for; three risks; what would change the view; the end of the validity window. Shape below. |
| 2 | The business | full report | The products (the 10-K's Item 1); the revenue by product and by region over three years (`segments`); what drives revenue: price, volume, users, contracts, recurring or one-time; the customers, any customer at a tenth of revenue or more; the unit economics: the gross margin and the incremental margin (the share of each extra dollar of revenue that became operating profit). |
| 3 | Industry and competition | full report | The value chain: the suppliers, the customers, where the profit goes; the industry's size and growth; the competitors (`peers` and the 10-K); the company's position, its share and its rank; the moat by Damodaran's five sources: brand name, switching costs, network effect, cost advantages, efficient scale. End with a plain answer to "are the economics favorable?", from the gross margin, the incremental margin against the average margin, and the ROIC against the hurdle rate. |
| 4 | Financial performance and health | both | Six parts, one for each table of `financial_tables`, each two or three plain sentences that cite its cells. Detail below. |
| 5 | The last earnings call | both | One page, in seven parts: the verdict; the quarter against expectations; the story management is telling, claim by claim; the guidance; the positives and the negatives; the questions and answers; what the thesis takes from it. Detail below. |
| 6 | The bull case and the bear case | both | The debate about the business and its outlook, in arguments: demand and how long it lasts, where the company is in its cycle, competition and the moat, pricing power, capital allocation, management, the balance sheet, the claims of the call. Each side's strongest case, in words a reader without the method follows. Figures may be cited. No valuation arithmetic, input, tag or parameter. |
| 7 | The thesis | both | The report's own story, set against management's. It opens with a position on each claim of section 5: accepted, rejected or held open. Then the case that settles the debate and leads to the stance: what must be true for the stance to be right, and what you expect to happen. Detail below. |
| 8 | Valuation | both | The only section that talks about the valuation. The phase, the growth word and the margin direction behind it, any check flag, the Dickinson stage (the life-cycle stage, Introduction, Growth, Mature, Shake-out or Decline, that the signs of the three cash flows give), and why if an override changed the phase; the growth the price needs; the belief and why; the mechanical value and the reviewed value, with one sentence in words for each override that moved it; the guidance override in one sentence, where one moved an anchor or a step; on a refused row with no reviewed value only, the secondary valuation in the route's place, and FMP's figure in one sentence when read (where the route or your review values the company, no second value and no DCF beside the route's value); for a cyclical, where it is in its cycle and the mid-cycle basis used; the sensitivity grid. For Start-up, the price-implied requirement. For Decline, the floor and the distress-weighted value. Detail below. |
| 9 | Price and multiples | both | The price facts, and the multiples against their own history. Detail below. |
| 10 | Recent news | both | The dated items that matter to the value. |
| 11 | Risks and kill criteria | both | The risks, and the measurable events that would prove the thesis wrong. A threshold you choose is not a fact and never a finding: tie each event to a stored figure and cite it ("below the yearly return of 9.0% that investors require", citing `policy:required_return`), or state it in words ("revenue falls two quarters in a row"). A threshold no stored figure gives is a question for the founder (`reference/citations.md`, "A threshold you choose"). |
| 12 | Key judgments | both | The record: each judgment's decision in one sentence, naming in words the override it produced. Last, because it is the audit trail and not the reading. |

A valuation review reuses the company's newest full report for the business and the industry. The
server names that report on the published record. Say in the summary which one it is, by its
date, or that there is none: "This valuation review reuses the full report of 3 Oct 2026." Never
name a report by its id: an id of two digits or more is a quantity with no reference.

No ref, tag, id or bridge table appears in the text: the reader sees each cite as its number with
a footnote mark. The overrides, the bridge and the secondary valuation's projection are in
Appendix A. The main text may say in words what an override changed and why, in section 8 and
nowhere else.

### Section 4 from the tables

Write section 4 from the cells of `financial_tables`. Cite each cell by its `ref`. Derive none of
them: the server computed them.

- `growth`: revenue, its growth, the gross, operating and net margins, the EPS.
- `cash_flow`: operating cash flow, capital spending, free cash flow, free cash flow over net
  income, stock compensation over revenue.
- `solvency`: cash, debt, net debt over EBITDA, the interest coverage, the current ratio, and the
  cash runway for a company whose operating cash flow is negative.
- `returns`: ROIC and ROE by year, the ten-year aggregate ROIC (in the newest year's cell only),
  the hurdle rate.
- `capital_allocation`: dividends, buybacks, the change in the share count, acquisitions.
- `quality`: Altman's Z″ and Piotroski's F.

A cell with no value holds no figure: say so in words, and give its `note` when it has one, which
says why (a line not on file, an interest expense stored as zero). A cell can also hold a figure
and a note: a year's ROIC on invested capital at or below zero has no meaning, so give the note's
words beside the figure, or leave the figure out and say why.
Acquisitions and Beneish's M are not on file yet. Lead with the part that holds the measures that
matter most for the phase (Damodaran):

| Phase | What matters most |
|---|---|
| Start-up | the potential market, the access to capital |
| Young Growth | revenue growth, gross margins |
| High Growth | revenue growth, operating margins |
| Mature Growth | earnings growth |
| Mature Stable | earnings stability |
| Decline | book value |

A table in the text is Markdown in the plain parts, each figure a cite.

### Section 5: the last earnings call

One page, in this order. Step 5 of `SKILL.md` says how to build each part.

1. **The verdict.** The call's date and quarter. Whether it confirmed, changed or broke the
   thesis. The price's move on the next trading day, a `derive` `growth` of two closes.
2. **The quarter against expectations.** A table of revenue, EPS, the operating margin and free
   cash flow: the quarter, the same quarter a year before, the consensus for the quarter and the
   surprise. Every cell is a stored quarter's figure from `quarters`, a stored estimate or a
   derivation. Then what drove the quarter: price, volume, mix, currency, one-time items.
3. **The story management is telling.** The frame in their words, quoted. Then three to five
   claims, in a table of four columns:

   | Claim | Evidence | Driver | Test |
   |---|---|---|---|
   | what management says will happen, with its figure and its timeline | what the numbers already show | the input it would move, written as the register's phrase for it (`reference/register.md`, "The words a report writes"): the growth of years two and three, the belief, the held rate, the target margin, the reinvestment, the moat, the risk | what would show it true or false, and by when |

   Then a verdict on each claim, in one of three words. **Possible**: it could happen.
   **Plausible**: the evidence makes it believable. **Probable**: the evidence makes it more likely
   than not. Only a probable claim moves a figure in the value. Then the drift since the previous
   call, and what management did not say.
4. **The guidance.** A table of the records: the metric, the period, the low, the high, the
   midpoint, the basis, raised, held or cut against the prior record, and against the consensus.
   Then one sentence on what the valuation takes from it: the override, or "the analysts' average
   estimate stands".
5. **The positives and the negatives**, each tied to a figure or a quote.
6. **The questions and answers.** The two or three analysts' pushbacks that matter to the thesis,
   and whether the answers were direct.
7. **What the thesis takes from it.** The kill criteria touched, the one thing to watch next
   quarter, and the gap: how far the price moved against how far the reviewed value moved.

When the vendor has no transcript, say so first, and build the parts from the press release. The
quarter's figures still come from `quarters`.

### Section 7: the thesis

Open with each claim of section 5 and its position:

- **accepted**: a driver the valuation moves;
- **rejected**: where the report's value parts from the consensus or the guidance, and why;
- **held open**: a kill criterion, or a thing to watch.

Then the case for the stance, written for every stance. A buy says why the market is wrong on the
downside. A hold says why the price is fair and what the view waits for. A trim says why the price
ran ahead of the business. An avoid says why the business is not worth owning at the prices shown.
The kill criteria of section 11 test it.

### Section 8: valuation

- **What the price needs**, where the price is well above the value (the answer of `company`
  carries `priceNeeds`): the section leads with it, in one or two sentences of your own. The
  figure the price needs sits under its route's own path: on Mature Growth, High Growth and Young
  Growth `snapshot:<id>/intermediates/implied_growth`; on Mature Stable
  `/growth_route/implied_growth`, the growth on the path with the analysts' forecast; on Decline
  `/implied_decline_rate`; under your overrides the review's, `review:<id>/intermediates/...`.
  Write it beside the figure the value rests on. On High Growth and Young Growth give the margin
  the price needs too, `/implied_margin`, beside the margin the value rests on. Where no rate
  reaches the price, say so in words and cite no figure. Where `priceNeeds` says the growth is
  charged at the hurdle rate, growth adds no value at that return: say so, and on Mature Growth
  give the growth the price needs at a 15% return, `/implied_by_roic/0.15`, named as that case
  (see "The phase" below). On Mature Stable no such figure is stored: say it in words. Then say
  in one sentence whether the evidence supports that need. A value far below
  the price says only that the method cannot reach the price; this part says what the price asks
  of the business.
- **The phase.** The phase, the growth word and the margin direction behind it, any check flag,
  the Dickinson stage, and why if an override changed it. Then the growth the price needs,
  `snapshot:<id>/intermediates/implied_growth`, or under your overrides the review's,
  `review:<id>/intermediates/implied_growth`, which differs from the snapshot's; and the belief
  and why. On a row whose runway return is the hurdle rate (the flag `return-floored`, or your
  `return.runway` at that rate), growth adds no value, so `implied_growth` is null or does not
  measure the business's growth: do not cite it. Say in words that no growth rate reaches the
  price at that return, and give the growth the price needs at a 15% return,
  `snapshot:<id>/intermediates/implied_by_roic/0.15` (under your overrides the review's), named
  as that case.
- **The value.** The value before any change to the inputs (the mechanical value) and after the
  changes that stand (the reviewed value). One sentence in words for each override that moved it,
  citing its bridge line: `review:<id>/bridge/<n>/old`, `/new` and `/delta`.
- **The higher case.** For the growth, the margin and the return on new capital, as the
  company's route reads them: the strongest evidence for a higher figure, and why it stood or
  did not, one sentence each, the figures cited. Where it stood, the override's bridge line above
  carries it; where it did not, the sentence names what the evidence lacked.
- **The charge**, on Mature Growth and Mature Stable, where the report explains what the growth
  costs: the return the company earns on new capital, year by year,
  `snapshot:<id>/intermediates/charge/return_by_year/<n>` (counted from 0, year one first), held
  for `/charge/hold_years` years, and the growth it pays for, `/charge/growth_by_year/<n>`. A year
  whose growth outruns its return pays out less than nothing: say the owners fund that year's
  growth. Under heavy capital spending, cite the newest year's marginal return,
  `/runway_return/one_year`, beside the return you chose. Where the return starts at the figure
  without goodwill (the note `return-without-goodwill`), cite the return on the capital without
  goodwill and intangibles, `/runway_return/without_goodwill/measure`, say that the return with
  them is below the yearly return investors require, and say why the growth ahead is the
  business's own, not bought. Where the business has no capital of its own without them, that
  figure is null: say so in words and cite the start alone, `/runway_return/value`. Under
  your overrides cite the review's,
  `review:<id>/intermediates/charge/...`.
- **The value outside the business**: where an override set one, what it is (a stake, an asset
  held for sale, a settlement still owed), its size a share after tax, cited as its bridge line,
  `review:<id>/bridge/<n>/new`, and how nothing counts twice. On Mature Stable its gains came out
  of the trailing earnings through the non-recurring gap's line (`earnings.nri_gap`); on High
  Growth, Young Growth and Decline the value reads operating income, which its gains never enter;
  on Mature Growth the analysts' consensus excludes them. On High Growth, Young Growth and
  Decline, an asset already in cash and short-term investments, or, on a Decline row whose value
  the floor sets (`ncav-floor`), in the current assets the floor reads, is counted by the route
  already: it is not outside the business and is not added. On Mature Growth where the consensus
  may carry the asset's gains, no override adds it: name the asset and its size a share, cited as a
  finding, and say why it is not added. Where the figure comes from secondary coverage, not a
  filing, say so.
- **The share count**, where an override set one or `share-count-gap` stays: the shares the
  company has committed to issue that neither the count nor the analysts' EPS holds yet (warrants,
  a forward sale, a mandatory convertible), set through `shares.committed`, with the filing that
  commits them, which lower the value a share by x ÷ (n + x) for x of them on a count of n, and
  where the cash the issue brings was added; or a share class or units that convert to shares
  that the count leaves out, set through `shares.diluted`; each cited as its bridge line,
  `review:<id>/bridge/<n>/new`. Both are period-tied. A raised diluted count raises the NTM net
  income with it, so say on what share basis the analysts' EPS stands. Where `share-count-gap`
  stays because the market cap leaves a class out, say why the count stands; the screen's row
  shows the review's flags, so the warning stays there too.
- **The stock pay**, on Mature Growth: whether the company's adjusted EPS leaves out stock pay,
  as its own definition in the release says, the passage cited as a finding, and the basis
  override where the row read otherwise. Under an applied `earnings.ntm` still state the basis,
  and set neither stock-pay input, which could not move the value. Where `stock-pay-missing`
  showed, the trailing stock pay from the filings' cash flow statements, cited as its bridge line,
  `review:<id>/bridge/<n>/new`; where the filings show nil too, say so, with the filing cited:
  the company pays no stock, and a lasting `earnings.sbc` of 0 records it.
- **The thin NTM consensus**, where `thin-ntm` shows: the exposure, the thin periods and their
  share of the NTM EPS, each period's EPS cited, `estimate:<symbol>/<period>/eps`. Under a
  guidance override of the anchor the note does not show, and the guidance below covers it.
- **The guidance.** Where a guidance override moved an anchor or a step, one sentence names it
  and cites the record's figure, `guidance:<id>/midpoint`.
- **The secondary valuation**, on a refused row with no reviewed value only: where neither the
  route nor your review values the company, it stands in for the route's value and leads the
  section. Where an override gave the current review a value, the reviewed value leads and there is
  no secondary valuation: Appendix A says "no secondary valuation: the review values the company".
  The drivers in words, with their figures cited (`secondary:<id>/drivers/<name>`,
  `/drivers/<name>/<t>`); the value, `secondary:<id>/value`; the grid's range, two cells
  `secondary:<id>/grid/<i>/<j>`. Where the server refused the secondary valuation for a refusal
  you cannot fix (no diluted share count, the reporting currency's or the share basis's), say so in
  one sentence: the report publishes without one.
  Where the route or your review values the company, write no second value and read no DCF beside
  the route's value.
- **FMP's figure**, only where neither the route nor the review values the company, in one sentence
  when read, beside the secondary valuation: `response:<responseId>/<json pointer>` of the `dcf`
  answer.
- **A cyclical**: where it is in its cycle, and the mid-cycle basis the values rest on: the
  ten-year median net margin, `snapshot:<id>/intermediates/margin_history/net/median`, named
  with its count of years where fewer than ten, against the margin inside the analysts' earnings,
  whether the cut to mid-cycle earnings is the full gap or half of it and why, and the value with
  the other one and with no cut, cells of the sensitivity grid. Where orders already cover the
  coming years, one sentence says the cut lowers those years too, so the value leans low.
- **The sensitivity grid**: the two inputs it sets, and the range of the value across them, two
  cells `sensitivity:<id>/<i>/<j>`, each beside the axis values it sits at,
  `sensitivity:<id>/rows/<i>` and `/cols/<j>`.

### Section 9: price and multiples

The engine or a derivation gives every item. None of them is a target.

- **The price facts.** The current price (`snapshot:<id>/price`). The engine's price facts in the
  snapshot's intermediates: the high and the low of the past year
  (`snapshot:<id>/intermediates/price_facts/high_52w`, `/low_52w`), the change over one, three and
  five years (`/change_1y`, `/change_3y`, `/change_5y`) and the drop from the last peak
  (`/drawdown_from_peak`).
- **Where the price sits in its year's range**, by two `derive` calls. The first: the
  `difference` of the price and the low, and the `difference` of the high and the low. The second:
  the `ratio` of the two `derived:` ids the first answered, cited as a percentage: "the price sits
  53.4% of the way from the low to the high".
- **The earnings multiples against their history**, where earnings are positive. The trailing P/E
  on two bases side by side, the clean P/E (on the method's earnings, without one-time items) and
  the reported P/E, and the forward P/E: `snapshot:<id>/intermediates/multiples/pe_clean`,
  `/pe_reported` and `/pe_forward`. Set each against its own history from `multiples_history`: the
  trailing series' ten-year average, median, high and low (`multiple:<symbol>/pe/avg_10y`,
  `/median_10y`, `/high_10y`, `/low_10y`), and the forward series' the same way
  (`multiple:<symbol>/pe_forward/avg_10y`). The forward series is Fairband's own log: say since
  when it runs (its `since`), and that it is short while it is.
- **The phase's multiples**, each from `derive`:

| Phase | Multiples to show |
|---|---|
| Start-up | EV over the market size, over the users, over the subscribers (each a finding) |
| Young Growth | EV over forward sales |
| High Growth | EV over sales |
| Mature Growth | the forward P/E, beside the growth rate it rests on, the belief (`snapshot:<id>/inputs/belief`); PEG is not available yet |
| Mature Stable | P/E, EV over EBITDA |
| Decline | P/B, EV over the liquidation value |

PEG is not available yet. `derive` takes refs only, so a P/E over a growth rate divides by the
fraction and gives a figure about a hundred times the usual one, which the check would pass. Show
the forward P/E and cite the growth rate beside it instead: the snapshot's belief,
`snapshot:<id>/inputs/belief`, or, when an applied `growth.belief` override replaced it, the
override's line of the current review's bridge, `review:<id>/bridge/<n>/new`.

EV (the enterprise value: the market cap plus debt less cash) takes one `derive` call for each
link, since a link names the `derived:` id the call before it answered:

1. `sum` of `snapshot:<id>/inputs/market_cap` and the solvency table's `debt` cell;
2. `difference` of that `derived:` id and the solvency table's `cash` cell;
3. `ratio` of that `derived:` id and the figure EV is set against: the revenue's `fact:` ref, a
   forward revenue's `estimate:` ref, or EBITDA.

A snapshot refused before its route holds no `inputs/market_cap`. There, start from a `product` of
`snapshot:<id>/price` and `snapshot:<id>/inputs/shares_diluted`, the market cap in US dollars, and
use its `derived:` id in link 1. On a company in another currency the tables are in that currency
and the price is not: first take a `product` of that id and `snapshot:<id>/inputs/fx_rate`, the
market cap in the currency, a derivation with no unit, and use that one in link 1. A snapshot with
no `inputs/shares_diluted` gives no enterprise value: say so in words.

EBITDA is a `sum` of the `operating_income` and `depreciation` `fact:` lines. P/B is a `ratio` of
the market cap and the `equity` `fact:` line.

### The charts

The report page draws the charts itself, from the store: in section 4 each table's figures; in
section 8 the sensitivity grid, or on a refused row the secondary valuation's grid; in section 9
the P/E history with its average lines. The Markdown export carries each chart's table under the
same title. Write no chart and no chart table: write the sentences, and cite the figures they name.

## The summary page

The shape, as the reader sees it once the cites are written in. Every figure is a cite in the
submission. The server's header line gives the company, the date, the snapshot and its price date.

```
Stance: hold.

The thesis: customers stay for years and now sign longer contracts, so revenue keeps compounding.
The price already counts on that. The view waits for two quarters of churn under the new prices.

The price of $234.70 is below the value this report puts on the company, $283 a share, but above
the price at which the discount to the value is wide enough to buy, $212. Prices close to the
value run from $240 to $325.

The company is in its Mature Growth stage. Revenue grew 11.0% a year over three years, which is
high for its size. The operating margin is positive and rising. The business is not cyclical: its
profits do not rise and fall with its industry's cycle.

Reasons for:
1. ...
2. ...
3. ...

Main risks:
1. ...
2. ...
3. ...

What would change the view:
- Two quarters in a row of falling revenue.

Valid until 27 Jan 2027, the date of the next earnings report.
```

Where the price is well above the value, the paragraph on the price says what the price needs,
in one plain sentence after the value: "The price needs earnings to grow 11.9% a year for twenty
years; the value rests on 5.3%." Both figures are cites. Where no rate reaches the price, the
sentence says so and cites none.

A part may hold line breaks. The reader renders this subset and no more: a blank line between
paragraphs; a list, its items `- ` bullets (not `* `) or `1. ` numbers, one a line, with no blank
line needed before it; a table, a header row, a `|---|` separator row under it and the rows, each
a line between `|` marks; and `**bold**`. No heading marks, no links, no nested lists, no images:
anything else shows as plain text.

## A cited part

```json
{"cite": "$283", "ref": "review:89/value"}
```

With the period it claims, a fiscal year, a quarter or `ttm`:

```json
{"cite": "31.2%", "ref": "table:EXMP/growth/operating_margin/2026", "period": "2026"}
```

## A full submission

An invented company, Example Corp (`EXMP`), a Mature Growth company on snapshot 412. Its fiscal
year ends in September. The call of 28 Oct 2026 reported the fourth quarter of fiscal 2026 and
guided fiscal 2027: guidance records 17 (EPS) and 18 (revenue). The agent's override of the NTM
earnings, citing record 17 (override 301), and of the belief (override 302) made review 89.
The route values the company, so the report makes no secondary valuation and reads no DCF, and
Appendix A says "no secondary valuation: the route values the company". Sensitivity reading 57
sets the belief against the runway return. The quarter's revenue and EPS, and the same quarter a
year before, are the stored quarters' figures from `quarters`, each cited by its `fact:` ref;
finding 124, the share of bookings, is a figure the statements do not hold. The derivations: 531
and 532 the surprises, `growth` of the quarter's stored figure (its `fact:` ref) over the
consensus; 534 the next-day move, `growth` of the close of 29 Oct 2026 over the close of 28 Oct
2026; 535 and 536 the two differences of the year's range, and 537 their ratio. Every plain part
holds no quantity; every figure is a cite.

```json
{
  "symbol": "EXMP",
  "mode": "full report",
  "stance": "hold",
  "work_item_id": 41,
  "sections": [
    {
      "heading": "Summary",
      "parts": [
        "Stance: hold.\n\nThe thesis: customers stay for years and now sign longer contracts, so revenue keeps compounding. The price already counts on that. The view waits for two quarters of churn under the new prices.\n\nThe price of ",
        {"cite": "$234.70", "ref": "snapshot:412/price"},
        " is below the value this report puts on the company, ",
        {"cite": "$283", "ref": "review:89/value"},
        " a share, but above the price at which the discount to the value is wide enough to buy, ",
        {"cite": "$212", "ref": "review:89/levels/buy"},
        ". Prices close to the value run from ",
        {"cite": "$240", "ref": "review:89/levels/fair_low"},
        " to ",
        {"cite": "$325", "ref": "review:89/levels/fair_high"},
        ".\n\nThe company is in its Mature Growth stage. Revenue grew ",
        {"cite": "11.0%", "ref": "snapshot:412/phase/growth_3y"},
        " a year over three years, which is high for its size. The operating margin is positive and rising. The business is not cyclical: its profits do not rise and fall with its industry's cycle.\n\nReasons for:\n\n1. Most revenue recurs each month.\n2. Customers rarely leave once their books run on the product.\n3. The company funds its growth from its own cash.\n\nMain risks:\n\n1. Customers may leave under the new prices.\n2. A payroll rival bundles accounting into its own product.\n3. Small firms cut spending in a recession.\n\nWhat would change the view:\n\n- Two quarters in a row of falling revenue.\n\nValid until 27 Jan 2027, the date of the next earnings report."
      ]
    },
    {
      "heading": "The business",
      "parts": [
        "Example Corp sells accounting software to small firms. Customers pay a fee each month, so most revenue recurs: subscriptions made ",
        {"cite": "92.0%", "ref": "finding:118", "period": "2026"},
        " of revenue in fiscal 2026."
      ]
    },
    {
      "heading": "Industry and competition",
      "parts": [
        "The economics are favorable. Switching costs (the work a customer must redo to move to a rival) protect the base. The gross margin was ",
        {"cite": "78.4%", "ref": "table:EXMP/growth/gross_margin/2026", "period": "2026"},
        " in fiscal 2026, and the ROIC (the return on invested capital) of ",
        {"cite": "24.1%", "ref": "table:EXMP/returns/roic/2026", "period": "2026"},
        " is well above the yearly return of ",
        {"cite": "9.0%", "ref": "policy:required_return"},
        " that investors require to own the shares."
      ]
    },
    {
      "heading": "Financial performance and health",
      "parts": [
        "Profit kept pace with sales. The operating margin was ",
        {"cite": "31.2%", "ref": "table:EXMP/growth/operating_margin/2026", "period": "2026"},
        " in fiscal 2026."
      ]
    },
    {
      "heading": "The last earnings call",
      "parts": [
        "**The verdict.** The call of 28 Oct 2026, on the fourth quarter of fiscal 2026, confirmed the thesis. The price rose ",
        {"cite": "+6.1%", "ref": "derived:534"},
        " on the next trading day.\n\n**The quarter against expectations.** The quarter beat the analysts' average estimate on both lines.\n\n| | The quarter | A year before | The analysts' average | The surprise |\n|---|---|---|---|---|\n| Revenue | ",
        {"cite": "$412.3 million", "ref": "fact:EXMP/revenue/2026-Q4", "period": "2026-Q4"},
        " | ",
        {"cite": "$370.8 million", "ref": "fact:EXMP/revenue/2025-Q4", "period": "2025-Q4"},
        " | ",
        {"cite": "$405.1 million", "ref": "estimate:EXMP/2026-Q4/revenue", "period": "2026-Q4"},
        " | ",
        {"cite": "1.8%", "ref": "derived:531"},
        " |\n| EPS | ",
        {"cite": "$1.74", "ref": "fact:EXMP/eps_diluted/2026-Q4", "period": "2026-Q4"},
        " | ",
        {"cite": "$1.52", "ref": "fact:EXMP/eps_diluted/2025-Q4", "period": "2025-Q4"},
        " | ",
        {"cite": "$1.68", "ref": "estimate:EXMP/2026-Q4/eps", "period": "2026-Q4"},
        " | ",
        {"cite": "3.6%", "ref": "derived:532"},
        " |\n\nPrice drove the quarter more than volume: the new price list took effect for new customers in the quarter. There were no one-time items.\n\n**The story management is telling.** Management's frame: \"the system of record for the small firm\". Three claims carry it.\n\n| Claim | Evidence | Driver | Test |\n|---|---|---|---|\n| Customers now sign multi-year contracts. | Multi-year contracts were ",
        {"cite": "41.0%", "ref": "finding:124", "period": "2026-Q4"},
        " of new bookings in the quarter. | The growth of years two and three. | The share holds through fiscal 2027. |\n| The new price list sticks. | Churn did not rise in the first quarter of the new prices. | The protection from rivals. | Churn stays flat through the second quarter of fiscal 2027. |\n| Payroll becomes a second engine of growth. | Payroll is still small, and its growth was not given. | The growth assumed after the analysts' forecast years. | Payroll is reported on its own by the end of fiscal 2027. |\n\nThe verdicts. The multi-year contracts are probable: the bookings already show them. The price list is plausible: one quarter is too short to judge churn. Payroll is possible, and moves no figure.\n\nThe drift since the call of July: management no longer gives the count of new customers, and the word \"macro\" appeared for the first time. They did not say how many customers left after the price rise.\n\n**The guidance.** The company gave ranges for fiscal 2027 (its guidance), both on its reported figures. The EPS outlook is new; the revenue outlook was raised from the call of July.\n\n| Metric | Period | Low | High | Midpoint | Basis | Against the prior record | Against the analysts' average |\n|---|---|---|---|---|---|---|---|\n| EPS | fiscal 2027 | ",
        {"cite": "$7.00", "ref": "guidance:17/low"},
        " | ",
        {"cite": "$7.20", "ref": "guidance:17/high"},
        " | ",
        {"cite": "$7.10", "ref": "guidance:17/midpoint", "period": "2027"},
        " | GAAP | first given | above |\n| Revenue | fiscal 2027 | ",
        {"cite": "$1.80 billion", "ref": "guidance:18/low"},
        " | ",
        {"cite": "$1.84 billion", "ref": "guidance:18/high"},
        " | ",
        {"cite": "$1.82 billion", "ref": "guidance:18/midpoint"},
        " | GAAP | raised | above |\n\nThe analysts' average estimate for fiscal 2027 EPS is ",
        {"cite": "$6.95", "ref": "estimate:EXMP/2027/eps", "period": "2027"},
        ". The valuation takes the EPS guidance: fiscal 2027 is the base year, the fiscal year that holds most of the next four quarters after the last one reported (two half-years for a company that reports twice a year), so its midpoint replaces the analysts' average estimate as the earnings the value starts from. The revenue guidance moves nothing in this valuation. A one-sided promise on the adjusted operating margin stays out of the value.\n\n**The positives and the negatives.** For: multi-year bookings, and an outlook above the analysts' average estimate. Against: the count of new customers is no longer reported, and payroll's growth was not given.\n\n**The questions and answers.** Two analysts pressed on churn after the price rise; the answers named no figure. One asked about payroll; the answer was direct: payroll will be reported on its own next year.\n\n**What the thesis takes from it.** Revenue grew, so falling revenue, the event that would prove the view wrong, has not begun. The one thing to watch next quarter is churn under the new prices. The price moved more than the value: it rose ",
        {"cite": "+6.1%", "ref": "derived:534"},
        ", while the guidance added ",
        {"cite": "+$5", "ref": "review:89/bridge/1/delta"},
        " a share to the value."
      ]
    },
    {
      "heading": "The bull case and the bear case",
      "parts": [
        "The bull case: customers rarely leave, and they now sign for longer and pay more each year. The product sits at the centre of a small firm's books, so the price rise met little resistance. The company funds its growth from its own cash.\n\nThe bear case: rivals sell close substitutes at lower prices. A payroll rival that bundles accounting could win the next generation of small firms. Small firms cut software spending first in a recession, and the price rise has had one quarter to show its cost."
      ]
    },
    {
      "heading": "The thesis",
      "parts": [
        "The thesis takes the call's three claims in turn. Accepted: customers sign for longer, so revenue holds up better in the coming years. Held open: the price list; churn over the next two quarters decides it, and a fall in revenue would prove the view wrong. Rejected: payroll as a second engine of growth; the value gives payroll no growth of its own until it is reported.\n\nThe stance is hold. The price is fair: it already counts on the longer contracts. For the stance to be right, the price list has to hold with churn flat, and nothing more. The view waits for two quarters of churn under the new prices."
      ]
    },
    {
      "heading": "Valuation",
      "parts": [
        "Fairband puts the company in its ",
        {"cite": "Mature Growth", "ref": "snapshot:412/phase/phase"},
        " stage: its revenue still grows fast for its size, and its operating margin is positive and rising. Nothing in the figures puts that stage in doubt. The business is not cyclical, so the value rests on the earnings as they stand.\n\nThe price needs growth of ",
        {"cite": "8.2%", "ref": "snapshot:412/intermediates/implied_growth"},
        " a year after the analysts' forecast years. The value a share on Fairband's own inputs, before any change to them (the mechanical value), is ",
        {"cite": "$247", "ref": "snapshot:412/value"},
        ". Two changes to the inputs moved it to ",
        {"cite": "$283", "ref": "review:89/value"},
        " a share, the value after the changes that stand (the reviewed value). The company's guidance for fiscal 2027 replaced the analysts' average estimate as the earnings of the next twelve months: its midpoint of ",
        {"cite": "$7.10", "ref": "guidance:17/midpoint"},
        " a share added ",
        {"cite": "+$5", "ref": "review:89/bridge/1/delta"},
        ". The growth rate the value assumes after the analysts' years (the belief) rose from ",
        {"cite": "7.1%", "ref": "review:89/bridge/2/old"},
        " to ",
        {"cite": "9.0%", "ref": "review:89/bridge/2/new"},
        ", which added ",
        {"cite": "+$31", "ref": "review:89/bridge/2/delta"},
        ". The reason: the new contracts run longer than the old ones.\n\nA grid of the value under other assumptions (the sensitivity grid) sets that growth rate against the return the company earns on the money it reinvests in the coming years (the runway return). Across the figures tried, the value a share runs from ",
        {"cite": "$238", "ref": "sensitivity:57/1/1"},
        " to ",
        {"cite": "$331", "ref": "sensitivity:57/3/3"},
        ". The price sits near the low end of that range."
      ]
    },
    {
      "heading": "Price and multiples",
      "parts": [
        "The price is ",
        {"cite": "$234.70", "ref": "snapshot:412/price"},
        ". Over the past year it ran from a low of ",
        {"cite": "$196.40", "ref": "snapshot:412/intermediates/price_facts/low_52w"},
        " to a high of ",
        {"cite": "$268.10", "ref": "snapshot:412/intermediates/price_facts/high_52w"},
        ", and it sits ",
        {"cite": "53.4%", "ref": "derived:537"},
        " of the way from the low to the high. It rose ",
        {"cite": "12.4%", "ref": "snapshot:412/intermediates/price_facts/change_1y"},
        " over one year. The drop from its last peak is ",
        {"cite": "−12.5%", "ref": "snapshot:412/intermediates/price_facts/drawdown_from_peak"},
        ".\n\nThe P/E is the price over the earnings a share. The trailing P/E is ",
        {"cite": "36.56x", "ref": "snapshot:412/intermediates/multiples/pe_reported"},
        " on reported earnings, and ",
        {"cite": "36.11x", "ref": "snapshot:412/intermediates/multiples/pe_clean"},
        " on earnings without one-time items. Over the past ten years the trailing P/E averaged ",
        {"cite": "27.80x", "ref": "multiple:EXMP/pe/avg_10y"},
        ", with a median of ",
        {"cite": "26.90x", "ref": "multiple:EXMP/pe/median_10y"},
        ", a high of ",
        {"cite": "41.20x", "ref": "multiple:EXMP/pe/high_10y"},
        " and a low of ",
        {"cite": "18.60x", "ref": "multiple:EXMP/pe/low_10y"},
        ". So the stock trades well above its usual multiple, and below its peak one. The forward P/E, on the analysts' earnings for the next twelve months, is ",
        {"cite": "33.77x", "ref": "snapshot:412/intermediates/multiples/pe_forward"},
        ". Fairband began logging the forward P/E on 1 Nov 2026, so it has no history yet to set it against. It rests on growth of ",
        {"cite": "9.0%", "ref": "review:89/bridge/2/new"},
        " a year after the analysts' forecast years. None of these multiples is a target."
      ]
    },
    {
      "heading": "Recent news",
      "parts": [
        "On 28 Oct 2026 the company raised its prices for new customers. On 4 Nov 2026 a payroll rival announced an accounting product for small firms."
      ]
    },
    {
      "heading": "Risks and kill criteria",
      "parts": [
        "The main risk is churn under the new prices. The thesis is wrong if revenue falls year on year in two quarters in a row, or if the ROIC falls below the yearly return of ",
        {"cite": "9.0%", "ref": "policy:required_return"},
        " that investors require. A payroll rival that bundles accounting is the second risk. A recession that cuts small firms' spending is the third."
      ]
    },
    {
      "heading": "Key judgments",
      "parts": [
        "The company's stage stands as Fairband gave it. The rating of what keeps rivals from taking the company's profits stands at ",
        {"cite": "Narrow", "ref": "snapshot:412/inputs/moat_class"},
        ", the middle of none, narrow and wide: customers face real costs to switch, but rivals sell close substitutes. The growth rate assumed after the analysts' years rose to the rate the longer contracts support, through a change to the inputs. The return on reinvested money, as Fairband measured it, stands. A second change to the inputs set the earnings of the next twelve months at the company's guidance."
      ]
    }
  ],
  "judgments": [
    {"judgment": "phase", "decision": "Mature Growth stands."},
    {
      "judgment": "moat",
      "decision": "Narrow stands: switching costs are real, but rivals sell close substitutes."
    },
    {
      "judgment": "belief",
      "decision": "The growth rate assumed after the analysts' years rose to the rate the longer contracts support.",
      "override_id": 302
    },
    {"judgment": "roic", "decision": "The return on reinvested money, as Fairband measured it, stands."}
  ],
  "kill_criteria": [
    {"text": "Revenue falls year on year in two quarters in a row."},
    {"text": "The ROIC falls below the yearly return investors require."}
  ],
  "news_items": [
    {
      "date": "2026-10-28",
      "headline": "Example Corp raises prices for new customers",
      "source": "https://example.com/news/exmp-price-list",
      "text": "The new price list applies to customers who sign from November."
    },
    {
      "date": "2026-11-04",
      "headline": "A payroll rival adds accounting for small firms",
      "source": "https://example.com/news/payroll-rival-accounting",
      "text": "The rival bundles accounting into its payroll product at no extra charge."
    }
  ]
}
```
