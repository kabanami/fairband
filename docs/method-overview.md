# How Fairband values a company

The exact rules are in [`docs/method.md`](method.md). The section numbers in brackets point into
it.

## What the engine does

The engine gives each company in the universe a value a share, or a stated reason for none. It is
rule-based and holds no AI model. It reads vendor data stored at each refresh. The same inputs,
versions and settings give the same result, bit for bit. This page describes method
`fairband-mechanical/1.8` and policy `fairband-policy-v18`. (method 0, 2, 10)

## From data to a value

1. **Universe.** A listing enters when it trades on NYSE, NASDAQ or AMEX, is not a fund, and has
   a market value of at least $2 billion. Banks, insurers, real estate investment trusts and six other
   financial industries stay out. (method 1)
2. **Phase and route.** The classifier reads three-year revenue growth, ranked against the
   universe, and the operating margin (operating income divided by revenue). It gives one of six
   phases, each with a route (its valuation method). (method 0, 3)
3. **Value.** Each route but Start-up gives a value a share. It discounts future cash at the
   required return r, also called the hurdle rate. Most routes end with a terminal value, which
   grows at terminal growth forever. (method 4.8, 5a.7, 6b, 14.2)
4. **Levels.** The buy level is the value less a margin of safety. The fair band is 0.90 to 1.10
   times the value, and the trim level 1.35 times. (method 4.10)
5. **Designation.** The price divided by the value falls in one of five bands, from Well below to
   Well above. The word describes the price, never an action. (method 4.10)

## The phases and their routes

The six phases are Damodaran's. The first rule that fits decides: Start-up, then Decline, then the
margin rules. The growth word names the pair of deciles (tenths of the ranked companies) that a
company's revenue growth falls in. (method 0, 3.3, 3.5)

| Phase | When | What the route does |
|---|---|---|
| Start-up | Revenue is zero now, or was three years ago | No value, by design. It states the year-10 revenue the price needs. (method 3.5, 6b) |
| Young Growth | Negative operating margin, not rising | The High Growth route, with no charge for the chance of failure. (method 3.5, 5a.12) |
| High Growth | Negative operating margin, rising | Consensus revenue for three years; that growth holds, then fades to terminal growth by year 10. The margin moves to the median of the mature peers. (method 3.5, 5a) |
| Mature Growth | Margin of zero or more; growth word Moderate or higher | Consensus net income for three years, a fade to the belief (the long-run growth rate), the belief to the runway's end (5 to 20 years), then a terminal value. (method 3.5, 5) |
| Mature Stable | Margin of zero or more; growth word Low or lower | Trailing earnings grow at terminal growth. (method 3.5, 6) |
| Decline | Lowest growth word, a falling revenue trend, and revenue down in three of the last four years | A ten-year run-off that frees capital as revenue falls, with a liquidation floor and a distress-sale value. (method 3.5, 6a) |

A company with an operating profit in three of its last five fiscal years, or in five of all the
years on file, is established. It is never a Start-up, Young Growth or High Growth. A company whose
figures support no phase stays unclassified. (method 3.5, 3.8)

On the mature routes, each year reinvests a share of its earnings. This reinvestment charge is
next year's revenue growth divided by the return on new capital. That return starts at the
company's own recent return, at least r. It holds for some years, then fades to the terminal return
by the runway's end. (method 4.6 to 4.8)

## The main inputs

- **Data.** FMP (Financial Modeling Prep) supplies statements, the analysts' consensus (their average forecast), prices,
  peers and exchange rates. Packaged tables give OECD tax rates, IMF inflation projections and
  Fairband's own moat classes. (method 2, 4.1, 4.3, 4.9)
- **Moat class.** Fairband keeps its own table of moat classes, Wide, Narrow or None, one for each
  company. A rule on ten years of returns drafted it, corrected by hand where the rule is wrong.
  The owner or an agent may change a class, and the newest is in force. A company with no class
  is refused. On the mature routes, the runway is 5, 10 or 20 years, from None to Wide. The margin
  of safety is 40%, 30% or 20%, in the same order. A Wide moat lifts the terminal return, up to r
  plus 4 points. (method 4.1, 4.7, 4.9, 4.9a)
- **Policy.** By default r is 9% and terminal growth 3%. The belief is the Base Rate Book's median
  ten-year net income growth for companies of similar sales, plus 2 points. Many policy values are
  user settings; this page gives the defaults. (method 4.1, 5.4)
- **Mature peers.** The vendor's peers that the classifier puts in a mature phase. With too few,
  the largest mature companies of the same industry stand in. (method 5a.4)

## Refusals and flags

A refusal is a result with no value and a reason; the row stays on the screen. The engine refuses
where a rule cannot apply, for example (method 0, 9):

- "no target margin: <n> mature peers". (method 5a.4)
- "<code>: expected inflation <π>% above the 10% bound". (method 7.5)
- "value not positive under the reinvestment charge". (method 5.1, 5a.9, 6.1)

A flag warns and never changes a value, a level or a designation. Twelve flags are quality
warnings; the screen marks a mechanical value with three or more and no reviewed value. The rest
are notes. (method 8)

## What a research agent can change

An agent, an AI model the user connects, changes the method's inputs through overrides. Each sets
one of twenty-four inputs, with a reason and evidence. The moat class is not one: an agent records
its verdict on the class, with its reasons, in each review, and the company is valued again. The
hurdle rate, terminal growth and reported figures are locked. The engine computes the reviewed
value beside the mechanical one. Where neither exists, it can compute a secondary valuation from
the agent's inputs. (method 4.9, 14, 14.1 to 14.5, 15)

## Limits

- Start-ups get no value, and Young Growth values leave out the chance of failure.
  (method 5a.12, 6b)
- The method does not attempt hyperinflation accounting. (method 7.5)
- The engine makes no mid-cycle correction for a cyclical business, except Mature Stable's scaling
  to its median margin. (method 6.2, 14.4)
- The values rest on the vendor's figures. An agent cannot override reported revenue or earnings
  per share. (method 14.2)

For the exact rules, read [`docs/method.md`](method.md). In the running app, the Methodology page
explains the method with worked examples. (method 0)
