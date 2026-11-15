# The register

How a Fairband report reads, from design.md 9.2 and the brand book. It applies to the report's
sections, the judgments, every reason on an override and every note.

## The rules of design.md 9.2

- Two parts. The reader part, the sections you write, holds plain text and rounded numbers.
  Appendix A, which the server writes, holds the codes, the sources and the figures at full
  precision. Keep codes out of the reader part: no tag (`growth.belief`), no ref, no id, no
  snake_case input name. Name the input by what it is, in its phrase from "The words a report
  writes" below.
- Put the answer first in each section.
- Keep sentences short, with one idea in each.
- Write the method's terms as "The words a report writes" below gives them: the phrase in the
  text, the term once in brackets in section 8 only.
- Round numbers: prices to cents, values to whole dollars, percentages to one decimal. The check
  holds every cite to these roundings (`reference/citations.md`).
- Keep the summary to one page and the reader part to about five pages.
- Keep the layout the same for every company. Only the valuation section changes with the phase.
- Talk about the valuation in the valuation section only. Every other section argues the business
  and its outlook, in words a reader without the method follows.

## The voice

- Never write in the first person. Fairband has no voice of its own: never "I", "we", "our" or
  "us". Write "the view is wrong if", not "our view is wrong if".
- Write in the third person for what Fairband does: "Fairband recomputes the value after each
  change to an input." Write in the second person only for what the reader does.
- Name the mechanism, not the feeling: "expired 3 Dec 2026", not "needs attention".
- Use plain words. No idiom, no slang, no hype: write "the margin rose", not "the margin took off".
- No emoji. No exclamation marks.
- No title case in a heading. The section headings are fixed; write them exactly as given.
- An override's reason is your own words. Fairband shows it verbatim on the bridge, so write it for
  the reader: what you found, and why it moves the input.

## Numbers, units and dates

- The unit goes in the text: `$121.30`, `4.4%`, `1.18x`. A percentage carries one decimal at most.
- Write small counts in words: "three years", "two quarters".
- Dates read as `3 Dec 2026`. Never a relative date such as "last week".
- Write a ticker exactly as the exchange writes it: `BRK.B`, not `BRK-B`.

## The words

These are the product's terms. They are not interchangeable with their near-synonyms. They are
for your records, your tool calls and Appendix A. An override's reason may use them too, since
Fairband shows it verbatim in Appendix A. The reader part of a report, the judgments' decisions
included, writes the phrases of "The words a report writes" below instead.

| Use | Not | Means |
|---|---|---|
| override | adjustment, tweak | a change to one tagged input, with its reason and evidence; lasting, or period-tied |
| review | analysis | the overrides on one snapshot and the reviewed result they produce |
| snapshot | baseline | a company's frozen inputs with the rules version, data date and price date |
| locked input | | an input no override may change |
| finding | | a dated, sourced fact an agent records |
| judgment | opinion | the record of one input decision, the phase, the moat, the growth belief, the ROIC or the target margin: the decision in words and the override it produced, if any |
| note | comment | a dated note on a company, with the same provenance as an override |
| news item | | a dated item, marked with any kill criterion it triggers |
| report | memo | the agents' written report, in one of two modes |
| work item | task, ticket | a request for an analysis, claimed and completed by an agent |

"Analysis" is kept for the agents' work as a whole. Never use it for one review.

## Naming an agent

Name the model, never the category. An agent is its model identifier, exactly as it arrived, in
lower case: `claude-opus-5-5`, `gpt-5`. Set it in code type where the text allows. Never write
"AI", "assistant", "bot" or a nickname, and never change its case: a reader searches their own
logs for that string.

## The words a report writes

The report is read by people who have never seen Fairband and will not read its method. Write
what a figure is, not what Fairband calls it. Fairband's own terms, the left column below, never
carry a sentence: "The belief is 5.3%" tells such a reader nothing. Write the right column, and
give the term once, in brackets after the phrase, in section 8 only, where the reader needs it to
find the figure in Appendix A or on the Methodology page. Outside section 8 the term does not
appear. The report's fixed headings and the two mode names, full report and valuation review,
stand as given. The names of Fairband's parts never appear in a report: not "the engine", "the
classifier", "the route", "the snapshot", "the check", "a flag", "the bridge", "a tag" or "an id".
Write "Fairband" for the product and say what the thing did: "Fairband puts the company in its
Mature Growth stage", "the data on file as of 4 Nov 2026".

| Term | Write instead |
|---|---|
| value at belief | the value a share: what one share is worth on the figures this report uses, and the one price target |
| mechanical value | the value a share on Fairband's own inputs, before any change to them |
| reviewed value | the value a share after the changes to the inputs that stand |
| buy level | the price at which the discount to the value is wide enough to buy |
| margin of safety | the discount to the value a buyer asks for, wider the less the business is protected from its rivals |
| fair band | the range of prices close to the value, from a little below it to a little above it |
| trim level | the price at which the stock is well above its value |
| designation | where the price stands against the value, in one of five words from Well below to Well above; a fact about the price, never advice to act |
| phase | the company's stage in its life cycle: Start-up, Young Growth, High Growth, Mature Growth, Mature Stable or Decline |
| Dickinson stage | a second reading of the company's life cycle, one of Introduction, Growth, Mature, Shake-out or Decline, from whether the last fiscal year's cash from operations, from investing and from financing came in or went out; shown beside the stage Fairband gives, it never changes it |
| moat | what keeps rivals from taking the company's profits, rated None, Narrow or Wide |
| belief | the growth rate the value assumes after the analysts' forecast years: where the analysts' last year grows faster, growth eases down toward this rate in equal steps, over five years at the defaults, then holds at it until it settles to the long-run rate; where growth settles to the long-run rate sooner, the easing stops there |
| implied growth | the growth the price needs: the yearly growth after the analysts' forecast years at which the value a share equals the price |
| held rate | the growth a fast-growing company's revenue is assumed to keep after the analysts' forecast years, before it slows |
| runway | the years the company's growth is assumed to stay above the long-run rate it settles to; more years for a business better protected from its rivals |
| runway return | the return the company earns on the money it reinvests in the coming years, measured from its recent years |
| return by year | the return the company earns on new capital, which the value assumes holds for N years, then moves in steps to the long-run level |
| target margin | the operating margin a growing company is assumed to reach by its tenth year: the typical margin of mature companies like it |
| margin the price needs | the operating margin a growing company must reach by its tenth year for the value a share to equal the price |
| sales-to-capital | the revenue each dollar put into the business brings in; it sets how much the company must reinvest to grow |
| value outside the business | assets outside the business, worth about $X a share after tax, such as a stake in another company; or a liability outside the business, such as a settlement still owed |
| decline rate | the yearly rate at which a shrinking company's revenue is assumed to fall after the analysts' forecast years, read from its past five years of revenue and easing in a straight line to nothing by the tenth year |
| liquidation floor | the company's current assets less all its liabilities and less the share of its subsidiaries that outside owners hold, a share; when it is above zero, the value of the business as a going concern is not taken below it |
| distress-weighted value | the value a share of the business as a going concern and the value a share in a forced sale, weighted by the chance the company fails within ten years; that chance is read from how many times its operating profit covers its interest, and is nil when its cash covers its debt |
| price-implied requirement | the revenue the company must reach in its tenth year, at the typical operating margin of mature companies like it, for the business to be worth its price today |
| hurdle rate | the yearly return investors require of any company's shares: one rate for every company, restated in the currency of a company that does not report in US dollars; future cash is discounted to today at this rate |
| consensus | the analysts' average estimate |
| override | a change to one of the inputs, with its reason and its evidence |
| review | the valuation under the changes to the inputs that stand: the value after them, and the steps to it from the value before them |
| bridge | the steps from the value before the changes to the inputs to the value after them, one for each change |
| snapshot | the data on file as of a date, the date written out |
| validity window | the time the value stays valid on the data on file: until the company's next earnings report when one is due after the data's date, else for a fixed time after that date; past a share of that time the value is aging, and past its end it has expired. At the defaults the fixed time is about three months and the share two-thirds |
| secondary valuation | a fallback value a share, from a discounted cash flow or a sum of parts on assumptions set for it; made only where Fairband gives no value, with or without the changes to the inputs |
| sensitivity grid | the value a share across a few figures for two inputs; it shows how much of the value rests on assumption, and is never a value itself |
| kill criterion | a measurable event that would prove the report's view wrong |

Two rows, snapshot and bridge, name Fairband's parts: their phrase stands alone, in section 8 too,
never followed by the term in brackets.

The word "stage" names the phase alone: "Fairband puts the company in its Mature Growth stage".
Write the Dickinson stage as the second reading of the life cycle, so a reader does not take it
for a second stage.

Some words belong to the field, not to Fairband: a reader of company research meets them
elsewhere. Write them by name, and give the meaning the first time each appears, in a short clause
or in brackets.

| Term | Meaning |
|---|---|
| free cash flow | the cash the business makes after its investment |
| ROIC | the return on invested capital: the profit after tax over the capital the business uses |
| guidance | a figure the company itself gave for a future period; it enters the value only when it is clear, and the analysts' average estimate stands otherwise |
| cyclical | a business whose profits rise and fall with its industry's cycle: memory chips, energy, steel, shipping and the like |
| mid-cycle | the margin and the earnings a business makes across a whole cycle of its industry, neither at the top nor at the bottom; a business whose profits rise and fall with that cycle is valued on them |
| thesis | the report's own view of the business: which of management's claims it accepts, rejects or holds open, and what must be true for the stance to be right |
| the story | what management says the business will do, claim by claim |
| possible | a claim that could come true: nothing rules it out |
| plausible | a claim the evidence makes believable |
| probable | a claim the evidence makes more likely than not; only such a claim moves a figure in the value |

The three words possible, plausible and probable are Damodaran's. Use them for a verdict on a
claim of the call and for nothing else.
