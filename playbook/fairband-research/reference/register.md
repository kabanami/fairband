# The register

How a Fairband report reads, from design.md 9.2 and the brand book. It applies to the report's
sections, the judgments, every reason on an override and every note.

## The rules of design.md 9.2

- Two parts. The reader part, the sections you write, holds plain text and rounded numbers.
  Appendix A, which the server writes, holds the codes, the sources and the figures at full
  precision. Keep codes out of the reader part: no tag (`growth.belief`), no ref, no id, no
  snake_case input name. Name the input in words: "the belief".
- Put the answer first in each section.
- Keep sentences short, with one idea in each.
- Explain each term the first time it appears, in brackets or in a short clause.
- Round numbers: prices to cents, values to whole dollars, percentages to one decimal. The check
  holds every cite to these roundings (`reference/citations.md`).
- Keep the summary to one page and the reader part to about five pages.
- Keep the layout the same for every company. Only the valuation section changes with the phase.
- Talk about the valuation in the valuation section only. Every other section argues the business
  and its outlook, in words a reader without the method follows.

## The voice

- Never write in the first person. Fairband has no voice of its own: never "I", "we", "our" or
  "us". Write "the view is wrong if", not "our view is wrong if".
- Write in the third person for what the engine does: "The engine recomputes the value after each
  override." Write in the second person only for what the reader does.
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

These are the product's terms. They are not interchangeable with their near-synonyms.

| Use | Not | Means |
|---|---|---|
| override | adjustment, tweak | a change to one tagged input, with its reason and evidence; lasting, or period-tied |
| review | analysis | the overrides on one snapshot and the reviewed result they produce |
| snapshot | baseline | a company's frozen inputs with the rules version, the data date and the price date |
| locked input | | an input no override may change |
| finding | | a dated, sourced fact an agent records |
| judgment | opinion | the record of one input decision, the phase, the moat, the growth belief, the ROIC or the target margin: the decision in words and the override it produced, if any |
| note | comment | a dated note on a company, with the same provenance as an override |
| news item | | a dated item, marked with any kill criterion it touches |
| report | memo | the agents' written report, in one of two modes |
| work item | task, ticket | a request for research on one company, claimed and completed by an agent |

"Analysis" is kept for the agents' work as a whole. Never use it for one review.

## Naming an agent

Name the model, never the category. An agent is its model identifier, exactly as it arrived, in
lower case: `claude-opus-5-5`, `gpt-5`. Set it in code type where the text allows. Never write
"AI", "assistant", "bot" or a nickname, and never change its case: a reader searches their own
logs for that string.

## Plain meanings to reuse

The first time a report uses one of these terms, give its plain meaning.

| Term | Plain meaning |
|---|---|
| value, value at belief | the engine's value a share at the growth belief; the one price target |
| mechanical value | the engine's value with no override |
| reviewed value | the engine's value under the agent's overrides |
| bridge | the steps from the mechanical value to the reviewed value, one for each override |
| buy level | the value less a margin of safety |
| margin of safety | the discount to the value that the moat sets |
| fair band | the range of prices close to the value |
| trim level | the price at which the stock is well above its value |
| designation | where the price stands against the value; a fact about the price, never an action |
| phase | the company's stage in its life cycle: Start-up, Young Growth, High Growth, Mature Growth, Mature Stable or Decline |
| moat | what keeps rivals from taking the company's profits; its class is None, Narrow or Wide |
| belief | the growth rate the value holds after the analysts' years |
| held rate | the growth a young company's revenue holds after the analysts' years |
| runway | the years the company's growth stays above the long-run rate, which the moat sets |
| free cash flow | the cash the business makes after its investment |
| ROIC | the return on invested capital: the profit after tax over the capital the business uses |
| hurdle rate | the return an investor requires, r |
| sales-to-capital | the revenue a dollar of invested capital buys |
| target margin | the operating margin a young company reaches in year ten |
| secondary valuation | the fallback value a share where the route refuses or no route fits: the standard discounted cash flow, from drivers the agent sets (or a cash-flow path for each part), which the engine projects and discounts; none where the route values the company |
| validity window | the time a value stays current, to the next earnings report |
| kill criterion | a measurable event that would prove the view wrong |
| thesis | the report's own view of the business: which of management's claims it accepts, rejects or holds open, and what must be true for the stance to be right |
| cyclical | a business whose profits rise and fall with its industry's cycle: memory chips, energy, steel, shipping and the like |
| mid-cycle | the margin and the earnings a cyclical business makes across a whole cycle, neither at its peak nor at its trough; a cyclical is valued on them |
| guidance | a figure the company itself gave for a future period; it enters the value only when it is clear, and the analysts' consensus stands otherwise |
| consensus | the average of the analysts' estimates on file |
| the story | what management says the business will do, claim by claim |
| possible | a claim that could come true: nothing rules it out |
| plausible | a claim the evidence makes believable |
| probable | a claim the evidence makes more likely than not; only a probable claim moves a figure in the value |
| sensitivity grid | the value a share across a few values of two inputs; it shows how much of the value is assumption, and is never a value |

The three words possible, plausible and probable are Damodaran's. Use them for a verdict on a
claim of the call and for nothing else.
