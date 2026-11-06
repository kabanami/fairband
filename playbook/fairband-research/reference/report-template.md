# The report

A report is the agents' written research on one company, in one of two modes. The server publishes
it whole or rejects it whole. This file gives its shape: the submission, the sections, the summary
page and a full example.

## The submission

`report_submit(symbol, mode, stance, sections, judgments, kill_criteria?, news_items?, work_item_id?)`

- `mode`: the work item's mode, `full report` or `valuation review`.
- `stance`: `buy`, `hold`, `trim` or `avoid`.
- `sections`: each `{heading, parts}`, in the order below, under the exact headings below. A full
  report has ten sections. A valuation review has eight: it leaves out "The business" and
  "Industry and competition".
- `judgments`: one of each kind, `{judgment, bull, bear, decision, override_id?}`. Every report
  gives `phase`, `moat` and `belief`. A Mature Growth or Mature Stable company adds `roic`; a High
  Growth, Young Growth or Start-up company adds `target_margin`.
- `kill_criteria`, optional: the new kill criteria this report sets, each `{text}`.
- `news_items`, optional: the dated items section 9 discusses that are not yet recorded, each
  `{date, headline, source, text, kill_criterion_id?}`.
- `work_item_id`, optional: the work item the report completes.

The server checks the structure first: the section count, the stance, the judgments and the
headings. Each failure is one sentence, such as "section 4 is headed 'Financial performance and
health', not 'Financials'". Then it checks every number (`reference/citations.md`).

The server writes Appendix A (the audit: every input with its tag and source, the overrides, the
bridge, the checks that ran, the versions) and Appendix B (the glossary). Write neither.

## The sections

Put the answer first in each section. Keep each sentence to one idea.

| # | Heading | Mode | What it holds |
|---|---|---|---|
| 1 | Summary | both | One page: the stance; the value against the price and the levels; the phase in one sentence; three reasons for; three risks; what would change the view; the end of the validity window. Shape below. |
| 2 | The business | full report | The products (the 10-K's Item 1); the revenue by product and by region over three years (`segments`); what drives revenue: price, volume, users, contracts, recurring or one-time; the customers, any customer at a tenth of revenue or more; the unit economics: the gross margin and the incremental margin (the share of each extra dollar of revenue that became operating profit). |
| 3 | Industry and competition | full report | The value chain: the suppliers, the customers, where the profit goes; the industry's size and growth; the competitors (`peers` and the 10-K); the company's position, its share and its rank; the moat by Damodaran's five sources: brand name, switching costs, network effect, cost advantages, efficient scale. End with a plain answer to "are the economics favorable?", from the gross margin, the incremental margin against the average margin, and the ROIC against the hurdle rate. |
| 4 | Financial performance and health | both | Six parts, one for each table of `financial_tables`, each two or three plain sentences that cite its cells. Detail below. |
| 5 | Life-cycle phase | both | The phase, the growth word and the margin direction behind it, any check flag, and the Dickinson stage (the phase the signs of the three cash flows give). If an override changed the phase, why. |
| 6 | Valuation | both | The growth the price needs; the belief and why; the value and the levels; the bridge, each override's line with its reason; a small sensitivity table. For Start-up, the price-implied requirement. For Decline, the floor and the distress-weighted value. A secondary valuation, when there is one, with its parts. |
| 7 | Price facts and multiples | both | The price facts and the multiples. Detail below. |
| 8 | Key judgments | both | For each judgment, the bull view, the bear view and the decision, with their figures cited. |
| 9 | Recent news | both | The dated items that matter to the value. |
| 10 | Risks and kill criteria | both | The risks, and the measurable events that would prove the view wrong. A threshold you choose is not a fact and never a finding: tie each event to a stored figure and cite it ("below the hurdle rate of 9.0%", citing `policy:required_return`), or state it in words ("revenue falls two quarters in a row"). A threshold no stored figure gives is a question for the founder (`reference/citations.md`, "A threshold you choose"). |

A valuation review reuses the company's newest full report for the business and the industry. The
server names that report on the published record. Say in the summary which one it is, by its
date, or that there is none: "This valuation review reuses the full report of 3 Oct 2026." Never
name a report by its id: an id of two digits or more is a quantity with no reference.

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

A cell with no value is not on file: say so in words, and give its `note` when it has one.
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

### Section 7: price facts and multiples

The engine or a derivation gives every item. None of them is a target.

- The price facts: the current price; the high and the low of the past year (the closes of
  `price_history`); the change over one, three and five years and the drop from the last peak
  (`derive`, `growth`, of two closes).
- The earnings multiples, where earnings are positive: the trailing P/E on two bases side by side,
  the clean P/E (on the method's earnings, without one-time items) and the reported P/E, and the
  forward P/E. The engine gives them in the intermediates: `multiples/pe_clean`,
  `multiples/pe_reported` and `multiples/pe_forward`.
- The phase's multiples, each from `derive`:

| Phase | Multiples to show |
|---|---|
| Start-up | EV over the market size, over the users, over the subscribers (each a finding) |
| Young Growth | EV over forward sales |
| High Growth | EV over sales |
| Mature Growth | the forward P/E, beside the growth rate it rests on; PEG is not available yet |
| Mature Stable | P/E, EV over EBITDA |
| Decline | P/B, EV over the liquidation value |

PEG is not available yet. `derive` takes refs only, so a P/E over a growth rate divides by the
fraction and gives a figure about a hundred times the usual one, which the check would pass. Show
the forward P/E and cite the growth rate beside it instead.

EV (the enterprise value: the market cap plus debt less cash) takes one `derive` call for each
link, since a link names the `derived:` id the call before it answered:

1. `sum` of `snapshot:<id>/inputs/market_cap` and the solvency table's `debt` cell;
2. `difference` of that `derived:` id and the solvency table's `cash` cell;
3. `ratio` of that `derived:` id and the figure EV is set against: the revenue's `fact:` ref, a
   forward revenue's `estimate:` ref, or EBITDA.

EBITDA is a `sum` of the `operating_income` and `depreciation` `fact:` lines. P/B is a `ratio` of
the market cap and the `equity` `fact:` line.

## The summary page

The shape, as the reader sees it once the cites are written in. Every figure is a cite in the
submission. The server's header line gives the company, the date, the snapshot and its price date.

```
Stance: hold.

The price of $234.70 is below the reviewed value of $283 a share, but above the buy level of $212.
The fair band runs from $240 to $325. Trim above $424.

Phase: Mature Growth. Revenue grew 11.0% a year over three years, which is high for its size.
The operating margin is positive and rising.

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

Valid until 3 Dec 2026, the date of the next earnings report.
```

A part may hold line breaks. A blank line starts a new paragraph; a line that starts with `- ` or
`1. ` after a blank line starts a list.

## A cited part

```json
{"cite": "$283", "ref": "review:88/value"}
```

With the period it claims, a fiscal year, a quarter or `ttm`:

```json
{"cite": "31.2%", "ref": "table:EXMP/growth/operating_margin/2025", "period": "2025"}
```

## A full submission

An invented company, Example Corp (`EXMP`), a Mature Growth company on snapshot 412. The agent's
override of the belief (override 301) made review 88. Every plain part holds no quantity; every
figure is a cite.

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
        "Stance: hold.\n\nThe price of ",
        {"cite": "$234.70", "ref": "snapshot:412/price"},
        " is below the reviewed value of ",
        {"cite": "$283", "ref": "review:88/value"},
        " a share, but above the buy level of ",
        {"cite": "$212", "ref": "review:88/levels/buy"},
        ". The reviewed value is the engine's value under this report's overrides. The buy level is that value less a margin of safety.\n\nPhase: Mature Growth. Revenue grew ",
        {"cite": "11.0%", "ref": "snapshot:412/phase/growth_3y"},
        " a year over three years, which is high for its size. The operating margin is positive and rising.\n\nReasons for:\n\n1. Most revenue recurs each month.\n2. Customers rarely leave once their books run on the product.\n3. The company funds its growth from its own cash.\n\nMain risks:\n\n1. A payroll rival bundles accounting into its own product.\n2. Small firms cut spending in a recession.\n3. The new price list may push some customers away.\n\nWhat would change the view:\n\n- Two quarters in a row of falling revenue.\n\nValid until 3 Dec 2026, the date of the next earnings report."
      ]
    },
    {
      "heading": "The business",
      "parts": [
        "Example Corp sells accounting software to small firms. Customers pay a fee each month, so most revenue recurs."
      ]
    },
    {
      "heading": "Industry and competition",
      "parts": [
        "The economics are favorable. Switching costs (the work a customer must redo to move to a rival) protect the base."
      ]
    },
    {
      "heading": "Financial performance and health",
      "parts": [
        "Profit kept pace with sales. The operating margin was ",
        {"cite": "31.2%", "ref": "table:EXMP/growth/operating_margin/2025", "period": "2025"},
        " in fiscal 2025."
      ]
    },
    {
      "heading": "Life-cycle phase",
      "parts": [
        "The classifier puts the company in ",
        {"cite": "Mature Growth", "ref": "snapshot:412/phase/phase"},
        ": its revenue still grows fast for its size, and its margin is positive."
      ]
    },
    {
      "heading": "Valuation",
      "parts": [
        "One override moved the value. The belief (the growth rate after the analysts' years) rose from ",
        {"cite": "7.1%", "ref": "review:88/bridge/1/old"},
        " to ",
        {"cite": "9.0%", "ref": "review:88/bridge/1/new"},
        ", which added ",
        {"cite": "$21", "ref": "review:88/bridge/1/delta"},
        " a share. The reason: the company's new contracts run longer than its old ones."
      ]
    },
    {
      "heading": "Price facts and multiples",
      "parts": [
        "The clean P/E (the price over the earnings a share without one-time items) is ",
        {"cite": "29.4x", "ref": "snapshot:412/intermediates/multiples/pe_clean"},
        ". None of these multiples is a target."
      ]
    },
    {
      "heading": "Key judgments",
      "parts": [
        "The moat is Narrow. Customers face real costs to switch, but rivals sell close substitutes."
      ]
    },
    {
      "heading": "Recent news",
      "parts": [
        "On 28 Oct 2026 the company raised its prices for new customers."
      ]
    },
    {
      "heading": "Risks and kill criteria",
      "parts": [
        "The view is wrong if revenue falls year on year in two quarters in a row."
      ]
    }
  ],
  "judgments": [
    {
      "judgment": "phase",
      "bull": "Revenue still grows fast for a company of its size.",
      "bear": "Growth has slowed in each of the last two years.",
      "decision": "Mature Growth stands."
    },
    {
      "judgment": "moat",
      "bull": "Switching costs keep customers for years.",
      "bear": "Rivals sell close substitutes at lower prices.",
      "decision": "Narrow stands."
    },
    {
      "judgment": "belief",
      "bull": "New contracts run longer and renew at higher prices.",
      "bear": "Small firms cut software spending first in a recession.",
      "decision": "The belief rises to the rate the longer contracts support.",
      "override_id": 301
    },
    {
      "judgment": "roic",
      "bull": "The business needs little capital to grow.",
      "bear": "Recent acquisitions add capital that earns less.",
      "decision": "The runway return the engine measured stands."
    }
  ],
  "kill_criteria": [
    {"text": "Revenue falls year on year in two quarters in a row."}
  ],
  "news_items": [
    {
      "date": "2026-10-28",
      "headline": "Example Corp raises prices for new customers",
      "source": "https://example.com/news/exmp-price-list",
      "text": "The new price list applies to customers who sign from November."
    }
  ]
}
```
