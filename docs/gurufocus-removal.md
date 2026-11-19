# Removing the GuruFocus dependency

Fairband needs two paid data sources today, FMP and GuruFocus. The founder wants to know what each
GuruFocus item is for and whether Fairband can run without it (2026-11-19). This document holds the
list of what Fairband reads from GuruFocus and, an item at a time, the decision on each. An item is
written here when the founder rules on it.

**Status, 2026-11-19:** the list is complete and every item has a decision: EPS without NRI
(section 2), with the way the screen shows that a mechanical value may not be sound (2.7); the ADR
ratio (section 3); the daily trailing P/E series (section 4); Altman's Z″ (section 5); the Moat
Score (section 6), replaced by Fairband's own table of classes. Nothing is built. The work is filed
in the backlog as B-254 to B-261.

The counts below come from the live data, refresh 68: 1,558 companies, 1,363 of them valued. They
were read on 2026-11-19 without a write.

## 1. What Fairband reads from GuruFocus

Fairband makes three GuruFocus calls and reads five fields from them. `summary` and `keyratios`
are fetched for every company at a refresh and reused for seven days. `pettm` is fetched for one
company when a reader or an agent opens its P/E history.

| Item | GuruFocus call | Where Fairband uses it | On refresh 68 | Rating | Decision |
|---|---|---|---|---|---|
| Moat Score | `summary`, each refresh | It sets the moat class (`moat_class` in `engine/anchor.py`). The class sets the runway years (5, 10 or 20), the terminal return and the margin of safety (45%, 35% or 25%). The pages show the class as the moat stamp. | 1,353 valued rows have a score. Classes: 145 Wide, 1,132 Narrow, 86 None. | Critical | Decided: section 6 |
| EPS (TTM) and EPS without NRI | `keyratios`, each refresh | Their difference is the non-recurring gap (`nri_gap` in `engine/route_steps.py`). Mature Stable takes the gap off the trailing earnings, so it moves the value there. The other routes use it for the clean EPS, EPV and the flags `large-nri` and `consensus-basis-unknown` only. | The gap is not zero on 410 of 448 valued Mature Stable rows, median 6.8% of EPS. `large-nri` is on 655 valued rows. | Critical on Mature Stable; nice to have on the other routes | Decided: section 2 |
| ADR ratio (ordinary shares per ADS) | `summary`, each refresh | The listed-share basis rule (`method.md` 4.2; `_adr_ratio` in `refresh/inputs.py`). It corrects a share count that FMP holds wrong by the ratio. It is also the `adr_ratio` input on the row. | 83 rows have a ratio that is not 0 or 1. The rule scaled 10 rows and refused 1. Two values rest on it (section 3). | Critical for the two values; no effect on the others | Decided: section 3 |
| Daily trailing P/E series | `pettm`, on demand | The P/E chart under "Price and multiples" on the Research tab, the `multiple:` refs in an agent's report, and the MCP tools `pe_history` and `multiples_history`. No value reads it. | Stored for 31 companies. | Nice to have | Decided: section 4 |
| Altman Z″ (`z2score`) | `summary`, each refresh | Nothing reads it. The Decline route computes Z″ from FMP's statements (`engine/distress.py`). | None | Not needed | Decided: section 5 |

**Without a GuruFocus key today.** The refresh runs: its four required calls are FMP's. Every
company reads the moat class None, the gap is nil, no ADR ratio is on file and the P/E series is
off.

**Call volume.** A full refresh makes two GuruFocus calls a company, about 3,100 a week for the
universe of refresh 68.

**Not dependencies.** The backlog rows B-71, B-72 and B-219 name GuruFocus as a possible source,
and none is built. The research playbook reaches GuruFocus only through the two MCP tools in the
table.

## 2. EPS without NRI

### 2.1 What Fairband does with it

The non-recurring gap is GuruFocus's EPS (TTM) less its EPS without NRI, a share. A net one-time
charge makes it negative.

- **Mature Stable.** E = trailing net income − the gap × diluted shares (`method.md` 6.1). The gap
  moves the value.
- **Every other route.** The gap gives the clean EPS, EPV and the clean P/E, and it fires the flags
  `large-nri` and `consensus-basis-unknown`. It moves no value.
- **An agent's review.** The override `earnings.nri_gap` takes the gap's place (`method.md` 14).

Fairband does not need GuruFocus's EPS (TTM) on its own. It is within 2% of FMP's trailing diluted
EPS on 91% of 1,085 valued rows. The real dependency is EPS without NRI.

### 2.2 What the figure is

GuruFocus's glossary (https://www.gurufocus.com/glossary/eps_nri, as updated 2026-03-19) gives the
formula: net income from continuing operations, plus or minus the after-tax unusual items and the
after-tax goodwill impairments, less preferred dividends, over the weighted average shares. The
trailing figure is the sum of four quarters. The page says that what counts as non-recurring is a
judgment and that the adjustments vary by data provider.

FMP has four of the five inputs. It has no line for the unusual items. That one input is the
dependency.

### 2.3 What was tested

**FMP holds no such field.** Nine stored FMP answers (the statements, the ratios, the key metrics,
the growth figures, the scores and the estimates) hold no adjusted, normalized or unusual figure.
FMP's as-reported income statement, read once for one company, shows the lines on the face of the
statement only, such as "other operating charges". The impairments and the gains are in the notes.

**No gap built from FMP's data follows GuruFocus's.** Each candidate was compared with GuruFocus's
gap on the valued Mature Stable rows in USD with a trailing EPS above $0.10 (374 rows).

| Candidate gap | Median distance from GuruFocus's gap, as a share of EPS | Rows within 2% of EPS |
|---|---|---|
| No gap | 4.9% | 34% |
| Discontinued operations only | 5.2% | 34% |
| Non-operating income above the company's own eight-quarter median, after tax | 6.5% | 25% |
| Non-operating income, after tax | 7.7% | 19% |
| GAAP EPS less the street's EPS, with stock pay put back where the street leaves it out | 8.6% | 19% |
| GAAP EPS less the street's EPS | 11.8% | 19% |
| Other operating expenses, after tax | 13.2% | 19% |

Every candidate is farther from GuruFocus's gap than no gap.

**No normal-earnings rule from FMP's data follows it either.** Four rules that need no gap were
compared with the earnings under GuruFocus's gap, on 385 Mature Stable rows.

| Earnings from | Median absolute difference | Rows 20% or more apart |
|---|---|---|
| Trailing net income, no gap | 5.1% | 22% |
| Twice the middle two of the last four quarters | 10.3% | 29% |
| Trailing revenue × the median net margin of eight quarters | 15.7% | 44% |
| Trailing revenue × the median net margin of five fiscal years | 21.4% | 51% |
| Trailing revenue × the median net margin of three fiscal years | 23.0% | 54% |

**Other sources.**

- Yahoo's statement data holds a line for the unusual items and its tax effect. The `yfinance`
  library reads it with no key. Yahoo has no official API, and the library says the data is for
  personal use. It was read for one company only, KO: over the trailing four quarters GuruFocus
  reads net one-time charges and Yahoo reads net one-time gains. Two vendors disagree on the sign,
  so the unusual items are a vendor's judgment, not a fact of the filing.
- The SEC's filing data is free and official. A rule would sum a fixed list of tags. It covers
  SEC filers only and was not tested.

### 2.4 What no gap costs

Every company of refresh 68 was valued twice in memory, with GuruFocus's two EPS figures and
without them. With them, the value equals the stored one on all 1,363 valued rows.

- **Mature Growth, High Growth, Young Growth and Decline (915 valued rows):** no value moves.
- **Mature Stable (448 valued rows):** 301 values go down, 90 go up, 38 stay and 19 rows are
  refused.
- **Size, on the 429 rows still valued:** the median change is −3.1% and the median absolute
  change 4.9%.

| Moved by | Rows | Down | Up |
|---|---|---|---|
| 5% or more | 213 | 181 | 32 |
| 10% or more | 151 | 128 | 23 |
| 20% or more | 82 | 68 | 14 |
| 50% or more | 24 | 19 | 5 |

- **The ends:** GPC −95.9% and APD −79.4%; TAC +805.3% and ZIM +224.8%.
- **The 19 refusals:** "no positive trailing earnings". Their trailing loss comes from a one-time
  charge; GILD and KHC are two.
- **Flags:** `large-nri` leaves 691 rows and `consensus-basis-unknown` 559, valued and refused rows
  together.

### 2.5 The decision

The founder, 2026-11-19:

1. **The mechanical valuations are basic.** They are preliminary and not vetted, and Fairband says
   so. This holds for every route, not for Mature Stable alone.
2. **The mechanical routes use what FMP gives.** They read no EPS from GuruFocus and take no
   non-recurring gap, for a user with a GuruFocus key as for one without. One method gives every
   user the same mechanical value.
3. **An agent calculates the gap in a review.** When an agent is asked to value a company, it
   reads the filings and sets the gap through `earnings.nri_gap`. The playbook tells it how.

Left out: the candidates of 2.3, which do not follow the figure; Yahoo's line, which rests on no
official API; the SEC's tags, a larger build that was not tested.

### 2.6 The work that follows

None of it is started.

1. **The playbook.** Today the playbook sends an agent to the gap only under the flag
   `consensus-basis-unknown`, which fires with `large-nri`, and both read GuruFocus's gap. It gives
   no recipe. The change:
   - The one-time items become a standing step of every Mature Stable review, with no flag needed.
   - The recipe: sum the one-time items of the trailing four quarters; count restructuring,
     impairments, gains and losses on sales, litigation and debt retirement; take them after tax
     and a diluted share; write a net charge as a negative figure.
   - The rule for an asset outside the business speaks of "the gap found". With no gap found, the
     agent's figure is the whole gap.
2. **The engine.** The routes take a nil gap. The override `earnings.nri_gap` stays. The
   `keyratios` call, its two observations and the inputs `gf_eps_ttm` and `gf_eps_without_nri` go,
   with the split and the currency rules written for them. The flags `large-nri` and
   `consensus-basis-unknown` lose their source and go; item 4's warning takes the first one's place. This is a new method version, so `method.md` and the Methodology page change in
   the same commit, and the refresh after it should read as 2.4.
3. **The words.** The Methodology page says that a mechanical value is preliminary, that it
   includes one-time items, and that a review takes them out.
4. **A warning from FMP's data** (the founder, 2026-11-19, on Claude's proposal). A Mature Stable
   row gets one warning when GAAP EPS and the street's EPS differ by 20% of EPS or more. It takes
   the place of `large-nri` among the warnings the mark counts (2.7), and it counts as one: alone
   it does not mark a row. `large-nri` and `consensus-basis-unknown` go, since both read
   GuruFocus's gap. It is on Mature Stable alone, the one route where the missing gap moves the
   value. Without it, a company with a one-time charge reads as expensive and nobody asks for its
   review.

   The threshold was tested against the rows whose value really moves when the gap is taken out:
   392 Mature Stable rows, of which 85 move by 20% or more or are refused.

   | GAAP and street EPS differ by | Rows warned | Finds of the 85 large moves | Warned rows that move 10% or more |
   |---|---|---|---|
   | 5% or more | 269 (69%) | 93% | 51% |
   | 10% or more | 231 (59%) | 92% | 56% |
   | 20% or more | 177 (45%) | 89% | 67% |
   | 30% or more | 144 (37%) | 86% | 70% |

   At 5% the warning sits on two rows in three and says little. Left out: the street's EPS with
   stock pay put back, a little sharper (152 rows warned, 87% found) for one more step.
5. **The warnings mark and the preliminary note.** Section 2.7.

### 2.7 How the screen says it: the warnings mark and the preliminary note

The founder, 2026-11-19. The reader of the screen must see that a mechanical value may not be
sound. The Flags column does not do this: a reader does not understand its words, and it is off by
default, as the Warnings column is. The way is a simple visual cue, never a block of text.

**What is on the screen today.** Twelve flags are quality warnings: they say the value may be
wrong (`method.md` 8). On refresh 68 most valued rows carry one or more:

| Warnings on the row | Valued rows |
|---|---|
| None | 216 (16%) |
| One | 471 (35%) |
| Two | 390 (29%) |
| Three or more | 286 (21%) |

**The mark.** One mark, on or off: a small filled dot beside the mechanical value of a row with
three warnings or more. A row with fewer has nothing.

```
Mechanical
  $197.23
● $12.40
```

- **The cut-off is three.** A mark on any warning would sit on 84% of the valued rows and say
  nothing, and two or more would mark half of them. At three the mark is on 286 rows, 21%, and
  means more reasons for doubt than usual. It is one number, to look at again on the screen. The
  counts include `large-nri` from GuruFocus's gap, so they change with item 4 of 2.6.
- **A mark or nothing.** There is no second symbol for a row without warnings: it would read as
  approval. No row gets a word of trust, since every mechanical value needs a review whatever it
  shows. "High confidence" and words like it are out (the founder).
- **A reviewed value has no mark.** A review vetted it.
- **The brand book's limits.** The colours `caution` and `critical` mean aging and expired, and
  the glyphs `!` and `×` are taken, so the mark uses neither. The dot reads without colour.

**The detail comes on request only.** A reader does not see the warnings themselves unless they
ask (the founder). In plain view there is the mark and nothing else. A hover names the row's
warnings in short words ("3 warnings: one-time items; heavy capital spending; negative free cash
flow"), on a row without the mark too when it has one or two. No list of warnings stands beside
the value on a page, and no click opens the warnings' full sentences: those stay for an agent,
which reads them through `company`.

**The preliminary note.** A hover on the mechanical value, on its mark and on the head of the
Mechanical column says that the value is preliminary and names the next step. The founder's
words, 2026-11-19, with the button's label as the page has it:

- On the screen's table: "Preliminary estimate only. To ask an agent for a reviewed valuation,
  open the company and click Request research."
- In the drawer and on the company page, where the company is open already: "Preliminary estimate
  only. To ask an agent for a reviewed valuation, click Request research."

"Reviewed" is the screen's own word: the result stands in the Reviewed column, beside Mechanical.
It was preferred to "revised", which says the value will change, where a review can confirm it.

The note stays on hover: no line of it stands in plain view on a page. Why the value is
preliminary, fixed rules that no one checked, is said on the Methodology page (2.6, item 3).

**The Flags and the Warnings columns go** from the columns a reader can add (the founder). Both
are off by default today, and a reader does not understand them; the mark and its hover take their
place. The notes that are not warnings, the lease notes among them, are then on no page, and an
agent reads them.

**No filter for the mark** (the founder): none is needed.

**Considered and left.** A three-step meter of confidence: its top step is a word of trust. A
meter of three bars that counts the warnings: the one mark is simpler (the founder). The figure
drawn in a lighter ink: a reader cannot tell three greys apart. A column of words: one more column
on a dense screen. A click on the mark that opens the warnings' full sentences, and the note as a
line in plain view on the company page: both are text, and the way is a visual cue.

**The Clean filter goes** (the founder): it keeps the rows with no warning, and no column shows what
it filters any more.

## 3. The ADR ratio

### 3.1 What Fairband does with it

The ratio is the number of ordinary shares one ADS stands for. FMP states an ADR's share count and
EPS per ADS, the unit the quote prices, but on some periods it holds a count that is wrong by the
ratio. The listed-share basis rule (`method.md` 4.2) corrects this. It compares a statement's
count with the quote's count, market cap ÷ price. When the two differ, it tries the ratio and its
inverse as factors: a count that fits by one of them is read × the factor and its EPS ÷ it. A
newest count that fits no factor refuses the row, "share basis unclear". The ratio is also the
input `adr_ratio` on the row.

So the ratio itself decides nothing. The two counts show that a row is wrong, and the ratio only
supplies the factor to try.

### 3.2 What no ratio costs

Every company of refresh 68 was valued in memory with GuruFocus's ratio and with none. On refresh
68 the rule scaled 10 rows and refused 1, but only two values rest on it, and both become badly
wrong:

| Row | Value today | Value with no ratio |
|---|---|---|
| CX | $7.49 | $51.82 |
| SIMO | $95.71 | $413.16 |

GDS changes its refusal reason, from "share basis unclear" to "no positive forward anchor". No
other row moves. This corrects the first reading of section 1, "critical for about 11 rows".

### 3.3 What was tested

**FMP holds no ratio.** Its profile holds the ADR flag (`isAdr`) and nothing more.

**The ratio from the two counts.** The rule: on a row FMP flags as an ADR, when the statement's
count and the quote's count differ beyond the tolerance, the ratio is the whole number, or one
over a whole number, that brings them together. The rule of 4.2 then runs with that ratio in
GuruFocus's place.

Worked, on CX: FMP's statements hold 145.8 million shares and the quote's count is 1,450.8
million. 1,450.8 ÷ 145.8 = 9.95, and the nearest whole number is 10. The count reads × 10 and the
EPS ÷ 10, and the value is $7.49, as today.

- **On the flagged ADRs** (137 rows) four have counts that differ, and on each the rule finds
  GuruFocus's ratio: CX 10, SIMO 4, XPEV 2, and TAL 3, where GuruFocus states the inverse, 0.3333.
- **On all 1,558 rows** no value differs from today's. GDS's counts differ by a factor that no
  whole number explains, so its refusal keeps today's reason only if the rule refuses such a row.
- **Without the ADR flag as a guard** the rule fires on 23 other rows and changes 7 values. Those
  are companies with several share classes, a separate problem (B-162), and companies whose count
  doubled in a merger. The guard is part of the rule.

### 3.4 The decision

The founder, 2026-11-19: Fairband works the ratio out from FMP's data, by the rule of 3.3. It is a
change to the mechanical rule, in the code that reads the share counts
(`refresh/inputs_splits.py`). An agent's method does not change.

Left out: refusing every flagged ADR whose counts differ, which costs CX and SIMO their values; a
table of ratios kept by hand in the repository, 83 rows today, which needs upkeep; an agent's
`shares.diluted` in a review alone, which reaches reviewed rows only.

### 3.5 The work that follows

None of it is started.

1. **The rule.** The ratio comes from the two counts on a flagged ADR, a whole number or one over
   it, within `split_implied_count_tolerance`. A flagged ADR whose counts differ by a factor that
   no such ratio explains is refused, "share basis unclear", as today.
2. **The input.** `adr_ratio` becomes an estimate from the two counts, on the rows the rule
   scales. An ADR whose counts agree shows no ratio, where today it shows GuruFocus's.
3. **The documents.** `method.md` 4.2, 5.12 and 7 and the Methodology page change in the same
   commit, under a new method version. The playbook changes its words in two places: where it
   names `adrRatio` and where it explains the note `basis-scaled`.
4. **The call.** `summary` stays until the Moat Score is decided: it carries both.

The limits, to read again when it is built:

- The test covers the four rows whose counts differ today.
- A ratio that is not a whole number or one over it, 1.5 say, is not found. The row is refused,
  which is safe.
- The rule rests on FMP's ADR flag. JBS and MAAS carry no flag and GuruFocus holds a ratio for
  each. Both are refused for other reasons today, so no value moves.

## 4. The daily trailing P/E series

### 4.1 What Fairband does with it

`pettm` is GuruFocus's trailing P/E, a point a day. Fairband fetches it for one company when a
reader or an agent opens the P/E history, and keeps ten years of points with four statistics, the
average, the median, the high and the low (`method.md` 16.7). It feeds the P/E chart under "Price
and multiples" on the Research tab, the `multiple:` refs in an agent's report, and the MCP tools
`pe_history` and `multiples_history`. No value reads it. Without a GuruFocus key the series is off.

### 4.2 What was tested

**The rule.** A day's P/E is its close ÷ the diluted EPS of the last four quarters, both from
FMP. The EPS changes at each quarter's end, as it does in GuruFocus's series: an EPS that changes
at the filing date follows GuruFocus's series less well, 65% of days within 2% against 92%.

**Against GuruFocus's stored series,** on companies that report in USD:

| Test | Days compared | Median difference | Days within 2% | Days within 5% |
|---|---|---|---|---|
| The last year, 25 companies, from the stored closes and quarters | 7,136 | 0.09% | 92% | 95% |
| Ten years, 10 companies, from deeper FMP answers | 24,374 | 0.12% | 89% | 96% |

- **The ten-year statistics agree.** On AAPL, NVDA, GOOG, MSFT and MU each of the four, the
  average, the median, the high and the low, is within 5% of GuruFocus's, and most are within 1%.
- **Splits cause no error.** NVDA, GOOG, AMZN, AVGO and AAPL split inside the ten years.
- **Loss days agree.** Of the 753 days on which either series shows a loss, 734 are a loss in
  both.

### 4.3 The decision

The founder, 2026-11-19: Fairband builds the series from FMP's data, by the rule of 4.2. It is a
change to Fairband's code, in the part that fetches and serves the P/E history. No valuation
changes, and an agent's method does not change.

Left out: FMP's own P/E for each period, four points a year, which loses the daily high and low
and was not tested; removing the trailing P/E history.

### 4.4 The work that follows

None of it is started.

1. **The data.** Ten years of daily closes and about 44 quarters of diluted EPS, two deeper FMP
   calls a company, made when the history is opened. The store holds five years of closes and
   eight quarters today.
2. **The series.** The points and the statistics as `method.md` 16.7 states them; a day whose
   trailing EPS is not above zero is a loss and has no point.
3. **Foreign filers.** Their EPS is in another currency, so the series needs ten years of
   exchange rates, and Fairband holds three (`refresh.fx_history_years`). Not tested: of the 31
   stored series, four are such companies (ASML, NVO, RELX, TSM).
4. **Half-yearly reporters.** The trailing EPS is the sum of two half-years. Not tested.
5. **The call.** `pettm` and the GuruFocus pass-through go. The tool `pe_history` is a GuruFocus
   read: whether it goes, or serves the built series, is a ruling for the build.
6. **The documents.** `method.md` 16.7, `docs/agents.md` and the playbook's tool list, which call
   the series GuruFocus's and name the refusal "no GuruFocus key".

The limits, to read again when it is built:

- **An EPS near zero.** The P/E is then very large and the two series part. On CRM the ten-year
  averages are far apart and the medians within 4%. The median is the safe statistic.
- **Two companies differ more.** V's median difference is 2.3%, with 99% of days within 5%. OMC
  differs over the last year, after a merger, and agrees before it. Neither cause was looked for.
- **The sample.** 25 companies over a year and 10 over ten years.

## 5. Altman's Z″

GuruFocus's `summary` answer holds a Z″ figure, `z2score`. Fairband stores it at each refresh and
reads it nowhere. Checked on 2026-11-19:

- The one reader of the stored GuruFocus scores is assembly (`refresh/inputs.py`), and it reads
  the Moat Score and the ADR ratio only.
- No route, no page, no MCP tool and no report ref reads `z2score`.
- The Decline route and the reports compute Z″ from FMP's statements (`engine/distress.py`), and
  the company page shows FMP's own Altman Z.

**The decision.** The founder, 2026-11-19: drop it. Fairband stops storing the figure.

**The work that follows,** not started: take the field out of the summary's rows in
`vendors/normalize_gf.py`, with its tests. The rows already stored stay. `method.md` does not name
the figure, so no method version changes.

## 6. The Moat Score

### 6.1 What Fairband does with it

The score sets the moat class: 8 or more Wide, 4 or more Narrow, less or no score None. The class
sets the runway years (5, 10 or 20), the terminal return and the margin of safety (45%, 35% or
25%). It is the one GuruFocus item that moves most values. On refresh 68 the valued rows are 145
Wide, 1,132 Narrow and 86 None.

### 6.2 What the score is

GuruFocus describes it as a judgment, not a formula: a rating of ten business factors, among them
market leadership, network effects, switching costs, brand, cost advantages and pricing power.
Three things follow.

- **No rule on statements can reproduce it.** A rule can only stand in its place.
- **A return on capital is a result of a moat, not a source of one.** A company can have the
  sources and an ordinary return.
- **GuruFocus's classes are not the target** (the founder). GuruFocus itself calls a 7 a wide moat,
  where Fairband's policy starts Wide at 8; 236 valued rows hold a 7.

The playbook's five sources of a moat, brand name, switching costs, network effect, cost
advantages and efficient scale, cover GuruFocus's ten factors.

### 6.3 What was tested and left

Each form was run on the 1,363 valued rows of refresh 68, with the returns the engine computes
(ROIC: operating income after tax over the year's average invested capital).

| Form | Wide, Narrow, None | Why it was left |
|---|---|---|
| The rule of the note of 2026-10-30 as its review revised it: Narrow above 9%, Wide above 14%, else None | 236, 235, 892 | Most companies earn less than 9% on capital that holds goodwill, so two rows in three are None, and the buy level falls on 836 rows. Its cash-flow test moves about 10 rows. |
| Narrow by default; Wide on a ROIC above one bar, 14% or 20% | 231 or 136, 1,047 or 1,142, 85 | Amazon is Narrow at every bar: its ten-year ROIC is 12.4% and its five-year median 10.7%, because it invests far ahead of its profit. |
| The same on the capital of the year before | | It lifts Amazon above 14%, and every fast-growing company with it. The founder took the ROIC back to the engine's own. |
| A Wide bar by size | 177, 1,101, 85 | Amazon's five-year median is below the lowest bar. |
| ROIC without goodwill | | Too many rows are Wide, and it agrees no better. |
| The final rule with one more condition: a ROIC above 9% in at least seven of the ten years | 158, 1,149, 56 | The founder left it out. It makes THC and SMCI Narrow, which a correction by hand does too, and it also makes AVGO, MRK, IBM, BMY, ABT and DE Narrow. All ten years is too strict: Amazon's 2022 fails it. |

The founder's rulings on the way, 2026-11-19: a rule that leaves Amazon out of Wide is wrong; an
agent's review is not a safe place to correct the class, since nothing makes the agent do it; one
size does not fit all, a very large company with steady profits is not a mid-size one with the
same return.

### 6.4 The decision: Fairband's own table of moat classes

The founder, 2026-11-19. A moat is a judgment, and GuruFocus's score is one. So Fairband keeps its
own classes in a file in the repository, as it keeps the tax table, and reads the class from it.

**The file.**

1. **The file holds Fairband's own classes.** The rule of 6.5 writes the first draft, so the method
   is Fairband's. No class is copied from GuruFocus, Morningstar or another vendor.
2. **The anomalies are corrected in the file.** A class the rule gets wrong is one edited line,
   with its reason, not one more condition in the rule.
3. **The file holds every company.** Each company of the universe has its own entry with its
   class, Narrow included: no class is left to a default. Narrow is what the rule gives a company
   that reaches neither Wide nor None, and it is written out like the others.
4. **The file is a versioned table, read into the database at every refresh,** not once at the
   start, so a later file reaches every user. A snapshot names where its class came from: the
   file's version, the owner or an agent.

**The database's table, which the engine reads.**

5. **The engine reads the class from one table in the user's database,** for the mechanical value
   as for every other figure (the founder). There is one class in force for a company, and one
   value under it. Nobody but the maintainer changes the file: it belongs to the repository, and a
   local write would conflict with its next version.
6. **At every refresh the file is read into the database's table, and a local change takes
   priority.** A row that the owner or an agent changed keeps its class; every other row takes the
   file's class. Each row records where its class comes from, the file's version, the owner or an
   agent, with its date, so that a new version of the file replaces the file's rows alone. The
   maintainer moves a good local change into the file with a commit.
7. **The owner can change any company's class,** whether the file holds one for it or not, since
   an owner may disagree with Fairband's class. The page offers it: the owner picks Wide, Narrow or
   None, and the change is written to the database's table.
8. **An agent can change the class in a review,** and its change is written to the database's
   table too.
9. **Owner against agent: the newest judgment is in force,** whoever made it, and the page says
   whose it is. An owner who asks for research after their own change may get another class, with
   the agent's reasons, and can set theirs again.
10. **The reason.** An agent must give its reason, as today. The owner need not: the row still
    holds who changed the class, when, and from what to what, and the owner may add a reason.
11. **A company with no row is refused,** "no moat class": a company that entered the universe
    after the file was written. Fairband does not give it a class by default or by the rule. An
    agent's valuation, the owner's own class, or the file's next version lifts the refusal.

**The agent's judgment.**

12. **A review judges the moat.** It is a standing step of a review, and the five sources are its
    guide: brand name, switching costs, network effect, cost advantages and efficient scale. They
    are a help, not a hard rule. The agent is not limited to them: it weighs what else the
    business shows and applies its own judgment, and it states its reasons. No fixed rule turns
    the five into a class.
    The review records its verdict every time, also when it agrees with the class it found (the
    founder), so that a judged class is never mistaken for one carried through. The row is then
    the agent's, with its reason.

**No input of the user is overridden** (the founder): a class set by the owner or by the owner's
agent, a confirmed class too, stays in force whatever a later version of the file holds. It is the
user's own judgment, newer and closer than Fairband's file.

**The file's upkeep** (the founder, on Claude's proposal). The maintainer cuts a new version each
quarter, in which the rule drafts the companies that entered the universe since, so that a
refused new company waits a quarter at most; and reads the whole file again once a year, since a
moat changes slowly. Each entry carries the date it was judged.

Considered and left: a default of Narrow for a company the file does not hold; the rule run by
the engine on such a company, which needs the industry ranks stored at each refresh and gives
almost every new company Narrow (15 of the 16 that entered between 2026-11-01 and 2026-11-18).
Also left: Claude's first form, in which the mechanical value read the file's class alone and only
the reviewed value followed a local change. It kept one mechanical value for every user, but a
user's settings already move the mechanical value, and it gave two values for one judgment.

### 6.5 The rule that drafts the table

The founder took the rule as it stands (2026-11-19). Its numbers are Claude's, with no source.
The rule writes the file's draft and is not the engine's rule. What it gets wrong is corrected by
hand in the file, not by one more condition. At each new version of the file the rule drafts the
class of the companies that entered since, and the maintainer checks them.

**Narrow** is the class the rule gives a company that reaches neither Wide nor None, and a company
with fewer than ten years of returns.

**Wide** needs all three conditions and one of the two routes.

Conditions:

1. At most one loss year in the ten, and none in the last five.
2. A ROIC above 9% on the ten-year total and on the five-year median.
3. A phase of Mature Growth or Mature Stable. A company in Decline is never Wide, and neither is
   one in Start-up, Young Growth or High Growth.

Routes:

- **The scale route.** Two of four marks: revenue above $50 billion; first or second by revenue
  in its industry (in its sector, where the industry has fewer than five companies); revenue above
  $12 billion with growth of 10% a year or more over ten years; a steady gross margin, no year
  below 80% of its own ten-year median.
- **The return route,** for a company of any size: a ROIC above 20% on the ten-year total and on
  the five-year median, with the steady gross margin.

**The cyclical list.** A company in one of these industries stops at Narrow, whatever its record
(the founder: none of them has a wide moat). The rule of the list: the company sells a commodity,
or a large purchase that follows the economy or the credit cycle.

- Housing and construction: Residential Construction; Engineering & Construction; Construction
  Materials; Real Estate - Services.
- Autos: Auto - Dealerships; Auto - Manufacturers; Auto - Recreational Vehicles.
- Commodities: the six Oil & Gas industries; Coal; Steel; Copper; Gold; Other Precious Metals;
  Industrial Materials; Chemicals; Agricultural Inputs; Paper, Lumber & Forest Products. Aluminum,
  Silver and Uranium belong here too and were not in the run; they hold no Wide row.
- Transport capacity: Airlines, Airports & Air Services; Marine Shipping.

Semiconductors are left out on purpose: the industry is cyclical, and it holds NVDA, TSM and ASML.

**None:** a ROIC below 3% on the ten-year total and on the five-year median.

**A year with no capital.** A profitable year whose invested capital is at or below zero counts as
above any bar. Apple is the case.

Size is revenue, never market value: a class read from the market value would make the value
depend on the price.

### 6.6 What the draft gives on refresh 68

| | Wide | Narrow | None |
|---|---|---|---|
| GuruFocus's score, as the policy reads it | 145 | 1,132 | 86 |
| The rule's draft | 169 | 1,138 | 56 |

- **Values:** 133 go up, 79 go down and 1,151 stay; 88 move by 20% or more. Buy levels: 173 up,
  119 down.
- **By size, the Wide rows:** 45 of 105 above $50 billion of revenue, 50 of 303 from $12 to $50
  billion, 59 of 619 from $2 to $12 billion, 15 of 336 below.
- **The seven largest:** AAPL, MSFT, GOOG, AMZN, NVDA and META are Wide; TSLA, with six profitable
  years in ten, is Narrow.
- **Mid-size companies reach Wide by the return route:** MCO, MSCI, FICO, IDXX, ISRG and VRSN among
  them.
- **The list stops 21 rows at Narrow:** DHI, LEN, PHM, NVR, CVCO, EME, FIX, EXPO, CRH, TGLS, TREX,
  CBRE, LAD, TM, RACE, DOO, MPLX, TPL, SCCO, BHP and RIO.
- **Against the 28 reviewed classes** the draft gives the same class on 21.

The rule's anomalies are corrected by hand: section 6.7.

### 6.7 The corrections by hand: the log

The founder reads the anomalies, not the whole lists, and overrides them in the file (2026-11-19).
Claude read the whole draft, from general knowledge of the businesses and from each company's ten
years of statements, and proposed the corrections; the founder ruled on them. This log is the
history of every class that differs from the rule's, and of every class that was questioned and
kept. Each row gives the logic of the change and who decided it. All of it is of 2026-11-19; the
figures are those of refresh 68.

**How the corrections were judged.**

- **None** is for a company that sells what a rival can supply as well, with no source of
  protection in sight; a thin margin and returns that follow a cycle are the signs. Where None was
  only arguable, the class is Narrow.
- **Wide outside the rule** is for a business whose protection is plain and whose record misses a
  route for a reason that is not a weakness: one loss year from a purchase charge, a gross margin
  that rose, a size below the scale marks, fewer than ten years on file, an industry it is not
  typical of.
- **A low return after large purchases.** Wide when the ROIC on all capital, purchases included,
  was at or above 9% in each of the last two years and is rising; else Narrow, since the
  shareholders have not yet earned the hurdle on the price paid.
- **Software with accounting losses.** Narrow when the business makes cash, free cash flow above
  nil in each of the last three years, and customers keep paying; the loss is stock pay.
- **An agent's judgment takes precedence** (the founder): where a review judged the class, the
  file takes that class. Only three of the 28 reviews did: TTMI, NVO and RELX. In the other 25 the
  review's class is GuruFocus's score carried through, which says nothing.

**The classes changed: 74 companies.**

*From Wide to None (5):*

| Ticker | Company | Why | Decided by |
|---|---|---|---|
| SMCI | Super Micro Computer, Inc. | It assembles servers from other companies' parts, and rivals sell the same. Its size and growth marks come from one boom: revenue was $3.6 billion in 2021. Its ROIC was 7% to 9% until 2021, and its gross margin fell from 18.0% to 10.8% while revenue grew more than ten times, so it has no pricing power. | the founder |
| VIPS | Vipshop Holdings Limited | Discount online retail in China against much larger rivals, with an operating margin of 5%. Nothing protects it. | the founder, on Claude's proposal |
| NRG | NRG Energy, Inc. | It sells electricity, a commodity. One loss year, and its gross margin fell to 8% in one year. | the founder, on Claude's proposal |
| INGM | Ingram Micro Holding Corporation | Distribution with a gross margin of 7% and an operating margin of 1.6%. Its ROIC was below 9% in three of the ten years. | the founder, on Claude's proposal |
| JBL | Jabil Inc. | Contract manufacturing with a gross margin of 8% and an operating margin of 4%. Its customers own the products. The same reasoning as SMCI. | the founder, on Claude's proposal |

*From Wide to Narrow (28):*

| Ticker | Company | Why | Decided by |
|---|---|---|---|
| THC | Tenet Healthcare Corporation | A hospital operator, Wide by the leader and steady-margin marks. Its ROIC was 4% to 8% until 2020 and above 9% in five of the ten years. None was arguable; local hospital networks have some scale, so Narrow. | the founder, on Claude's proposal |
| WPP | WPP plc | An advertising agency with falling revenue and a ROIC above 9% in six of the ten years. None was arguable; long client relationships keep it at Narrow. | the founder, on Claude's proposal |
| OMC | Omnicom Group Inc. | An advertising agency, Wide by the leader and steady-margin marks. Client relationships give some protection, and the business is under pressure. | the founder, on Claude's proposal |
| IBM | International Business Machines Corporation | Its revenue fell 1.9% a year over the ten years and its ROIC is 10%, above 9% in six of the ten years. Its enterprise customers face a high cost to switch, so Narrow and not None. | the founder, on Claude's proposal |
| WIT | Wipro Limited | Outsourcing, Wide by the return route. Its customers stay and its ROIC was above 14% in all ten years, but the service is one that rivals also sell. | the founder, on Claude's proposal |
| SQM | Sociedad Química y Minera de Chile S.A. | Lithium, a commodity. Its industry label is Chemicals - Specialty, so the cyclical list did not stop it. Its low-cost deposits are a real cost advantage, so Narrow and not None. | the founder, on Claude's proposal |
| VTMX | Corporación Inmobiliaria Vesta, S.A.B. de C.V. | A property developer. Its ROIC figures are not meaningful, and Real Estate - Development was not on the cyclical list. None was arguable; its industrial land is well placed, so Narrow. | the founder, on Claude's proposal |
| CORT | Corcept Therapeutics Incorporated | One drug, and rivals challenge its patents. None was arguable; it is still protected today, so Narrow. | the founder, on Claude's proposal |
| EXEL | Exelixis, Inc. | One drug franchise. Its patents still protect the drug, so Narrow. | the founder, on Claude's proposal |
| FIZZ | National Beverage Corp. | One brand of sparkling water. Its ROIC was 40% or more in all ten years, so Narrow and not None. | the founder, on Claude's proposal |
| BKE | The Buckle, Inc. | A mall clothing chain, easy to copy. None was arguable; its ROIC was 16% or more in all ten years, so Narrow. | the founder, on Claude's proposal |
| LRN | Stride, Inc. | Online schooling that depends on state contracts and funding; its ROIC was below 9% in the early years. None was arguable; it has scale and rising returns, so Narrow. | the founder, on Claude's proposal |
| NVO | Novo Nordisk A/S | An agent's review of 2026-11-11 judged the moat Narrow (override 34). The rule reads the past record alone, which is Wide. | an agent's review, which takes precedence |
| CROX | Crocs, Inc. | One fashion product. Its newest ROIC is 4%. | the founder, on Claude's proposal |
| BBWI | Bath & Body Works, Inc. | A mall retailer of one brand, with falling revenue. | the founder, on Claude's proposal |
| ACLS | Axcelis Technologies, Inc. | A small supplier of chip-making equipment. Its ROIC ranged from 7% to 62% with the chip cycle. | the founder, on Claude's proposal |
| CAMT | Camtek Ltd. | A small supplier of chip-making equipment. Its ROIC ranged from −5% to 101% with the chip cycle. | the founder, on Claude's proposal |
| CRUS | Cirrus Logic, Inc. | A chip maker that depends on one customer. | the founder, on Claude's proposal |
| FN | Fabrinet | Contract manufacturing with a gross margin of 12%; its customers own the products, as at JBL. Its ROIC was 20% or more in all ten years and its operating margin is 10%, so Narrow and not None. | the founder, on Claude's proposal |
| URI | United Rentals, Inc. | Equipment rental, which follows construction. Its ROIC was 8% to 10% for six of the ten years. | the founder, on Claude's proposal |
| BCO | The Brink's Company | Cash transport. Its ROIC is 10% over the ten years and was below 9% in four of them. | the founder, on Claude's proposal |
| SBS | Companhia de Saneamento Básico do Estado de São Paulo - SABESP | A regulated water utility. Its returns are uneven, 8% to 24%. | the founder, on Claude's proposal |
| FMX | Fomento Económico Mexicano, S.A.B. de C.V. | A ROIC of 10% to 14%, near the hurdle, with one year at 1%. | the founder, on Claude's proposal |
| GPC | Genuine Parts Company | Parts distribution with an operating margin of 5% to 8%. Its ROIC ranged from 7% to 19%, and the newest year is 7%. | the founder, on Claude's proposal |
| EEFT | Euronet Worldwide, Inc. | Payment and cash machines in competitive markets. Its ROIC fell to 2% in 2020. | the founder, on Claude's proposal |
| DECK | Deckers Outdoor Corporation | Two brands, UGG and HOKA, each above $2.5 billion, with a gross margin that rose from 47% to 58%. But its operating margin was nil in 2017, when UGG was out of fashion: the protection is a fashion's, and it can turn. | Claude, after the closer look the founder asked for |
| NTAP | NetApp, Inc. | Customers keep their data on its systems, and support is 38% of revenue. But it is second in storage with about a tenth of the market, and its revenue grew 2.6% a year over the ten years. | Claude, after the closer look the founder asked for |
| LOGI | Logitech International S.A. | Over half the market in mice. But a buyer can change brand at no cost, its revenue fell by a fifth after 2022, and three resellers make 44% of its sales. | Claude, after the closer look the founder asked for |

*From Narrow to Wide (25):*

| Ticker | Company | Why | Decided by |
|---|---|---|---|
| TPL | Texas Pacific Land Corporation | Stopped by the cyclical list as an oil and gas producer. It earns royalties on land it owns, with a ROIC of 89% or more in all ten years, and is not typical of the industry. | the founder |
| ROST | Ross Stores, Inc. | The same business and record as TJX, which is Wide. One year, 2020, puts its gross margin one point under the steady-margin floor. | the founder, on Claude's proposal |
| ODFL | Old Dominion Freight Line, Inc. | A freight network that is hard to copy. Its ROIC was 13% or more in all ten years and 20% or more in eight. It fails the steady-margin mark only because its gross margin rose. | the founder, on Claude's proposal |
| MAR | Marriott International, Inc. | A hotel brand that lives on franchise fees, with a ROIC of 14% to 18% since 2022. The return route asks for 20%, and it has one scale mark. | the founder, on Claude's proposal |
| HLT | Hilton Worldwide Holdings Inc. | The same business as MAR, with a ROIC of 30% to 43% since 2022. Its ten-year ROIC is 16%, under the return route's 20%, and it has one scale mark. | the founder, on Claude's proposal |
| IHG | InterContinental Hotels Group PLC | The same business as MAR and HLT, so it follows them. Its ROIC was 35% or more in every year but 2020. | the founder, on Claude's proposal |
| MELI | MercadoLibre, Inc. | The leading marketplace and payment network in Latin America, with a ROIC of 18% to 37% since 2020. Two loss years, 2018 and 2019, stop it. | the founder, on Claude's proposal |
| MCD | McDonald's Corporation | A ROIC above 9% in all ten years and an operating margin of 46%. Its gross margin rose from 41% to 57%, so the steady-margin mark fails. | the founder, on Claude's proposal |
| HSY | The Hershey Company | A ROIC of 21% to 26% for nine years. The newest year fell to 11% on cocoa costs, and the steady-margin mark fails. | the founder, on Claude's proposal |
| RACE | Ferrari N.V. | Stopped by the cyclical list as a car maker. Ferrari's brand is not typical of the industry: its operating margin rose from 19% to 29%, and its ROIC is 21%. | the founder, on Claude's proposal |
| TDG | TransDigm Group Incorporated | The only maker of many aircraft parts, with an operating margin of 34% to 47% and a ROIC above 9% in all ten years. At its size and a ROIC below 20% it has no route. | the founder, on Claude's proposal |
| SHW | The Sherwin-Williams Company | Its own paint shops and its hold on professional painters. A ROIC of 9% to 15% since a large purchase in 2017; no route. | the founder, on Claude's proposal |
| SYK | Stryker Corporation | Surgeons train on its tools and robots. A ROIC of 10% to 14% in all ten years; no route. | the founder, on Claude's proposal |
| CNI | Canadian National Railway Company | A railway cannot be copied. An operating margin of 35% to 42%; UNP is Wide by the rule; no route. | the founder, on Claude's proposal |
| VRSK | Verisk Analytics, Inc. | Insurers share their data through it. A ROIC of 28% to 34% since 2022; the ten-year figure is 17%, under the return route's 20%. | the founder, on Claude's proposal |
| SNPS | Synopsys, Inc. | One of two makers of chip-design software; CDNS, the other, is Wide by the rule. A large purchase in 2025 lowered its newest ROIC to 3%. | the founder, on Claude's proposal |
| CME | CME Group Inc. | The market's trading volume sits there. An operating margin of 53% to 65% and a ROIC of 22% to 24% since 2022; the ten-year figure is 10%. | the founder, on Claude's proposal |
| VRTX | Vertex Pharmaceuticals Incorporated | It has the only drugs for its disease, with a ROIC of 51% to 102% since 2018 in every year but one. That year, 2024, is a loss from a purchase charge, and it stops it. | the founder, on Claude's proposal |
| OTIS | Otis Worldwide Corporation | The largest elevator service base, with a ROIC of 43% to 72% in all eight years on file. Listed in 2020, so it has fewer than ten years. | the founder, on Claude's proposal |
| GE | GE Aerospace | Aircraft engines with a very large installed base, and a ROIC of 20%, 42% and 56% in the last three years. The old conglomerate's years weigh on the ten-year record. | the founder, on Claude's proposal |
| ADSK | Autodesk, Inc. | Design software that customers cannot easily leave, with a ROIC of 29% over ten years and 45% over five. Three early loss years, from its move to subscriptions, stop it. | the founder, on Claude's proposal |
| NOW | ServiceNow, Inc. | Workflow software with very high renewal and very high returns. Three early loss years stop it. | the founder, on Claude's proposal |
| LIN | Linde plc | Industrial gases. Its goodwill comes from a merger of equals in 2018, not from a cash purchase. Its ROIC on all capital rose from 4% to 9%, 10%, 10% and 11%, and its operating margin from 12% to 27%. | the founder, on Claude's proposal |
| ECL | Ecolab Inc. | Its service staff work at the customers' sites. Its ROIC on all capital was 7% to 9% until 2023, then 11% and 12%; its operating margin rose from 11% to 18%. | the founder, on Claude's proposal |
| DIS | The Walt Disney Company | Its parks and characters cannot be copied. Its ROIC on all capital fell to 2% in 2020, in the pandemic and at the start of streaming, and rose each year since to 9% and 13%. | the founder, on Claude's proposal |

*From Narrow to None (1):*

| Ticker | Company | Why | Decided by |
|---|---|---|---|
| TTMI | TTM Technologies, Inc. | An agent's review of 2026-11-11 judged that it has no moat (override 31). | an agent's review, which takes precedence |

*From None to Narrow (15):*

| Ticker | Company | Why | Decided by |
|---|---|---|---|
| TEAM | Atlassian Corporation | Software that customers keep: revenue up 23% a year, a gross margin of 82% to 85% and free cash in all ten years. The accounting loss is stock pay, 24% of revenue. | Claude, after the closer look the founder asked for |
| HUBS | HubSpot, Inc. | Software that customers keep: revenue up 22% a year, a gross margin of 84% and free cash of 23% of revenue. The accounting loss is stock pay. | Claude, after the closer look the founder asked for |
| OKTA | Okta, Inc. | Software that customers keep: revenue up 16% a year, free cash of 30% of revenue and its first accounting profit in the newest year. | Claude, after the closer look the founder asked for |
| GWRE | Guidewire Software, Inc. | Insurers run their core systems on it. Revenue up 18% a year, free cash of 26% of revenue and an operating margin of 10% in the newest year. | Claude, after the closer look the founder asked for |
| FRSH | Freshworks Inc. | Software with revenue up 19% a year, a gross margin of 85% and free cash in each of the last three years, 28% of revenue in the newest. | Claude, after the closer look the founder asked for |
| WIX | Wix.com Ltd. | Customers build their websites on it and stay. Revenue up 13% a year and free cash of 29% of revenue. | Claude, after the closer look the founder asked for |
| QTWO | Q2 Holdings, Inc. | Banks rarely change this software. Revenue up 12% a year and free cash of 24% of revenue. | Claude, after the closer look the founder asked for |
| RNG | RingCentral, Inc. | Business phone systems, which customers rarely change. Free cash of 23% of revenue; growth is slowing, at 8% a year. | Claude, after the closer look the founder asked for |
| TWLO | Twilio Inc. | Customers build its services into their own software. Free cash of 19% of revenue and a first accounting profit; its gross margin, 49%, is low for software. | Claude, after the closer look the founder asked for |
| TTWO | Take-Two Interactive Software, Inc. | It owns Grand Theft Auto and NBA 2K, which nobody can copy. Its losses are write-downs after a large purchase in 2022. | Claude, after the closer look the founder asked for |
| FWONA | Formula One Group | It holds Formula One's commercial rights. Its ROIC is low for the price paid for them; its operating margin rose to 13%. | Claude, after the closer look the founder asked for |
| MRVL | Marvell Technology, Inc. | It designs chips with its customers. Free cash of 10% to 24% of revenue in each of the last nine years; its losses are the cost of purchases. | Claude, after the closer look the founder asked for |
| TAK | Takeda Pharmaceutical Company Limited | A large drug maker with patents. Its ROIC is 2%: goodwill and intangibles, most of them from one purchase, are 60% of its assets. | Claude, after the closer look the founder asked for |
| IFF | International Flavors & Fragrances Inc. | It makes flavours and scents to each customer's product. Its margins fell after a merger, so the judgment is less sure. | Claude, after the closer look the founder asked for |
| ALNY | Alnylam Pharmaceuticals, Inc. | Patented drugs, revenue up 53% a year, and its first profit in the newest year. | Claude, after the closer look the founder asked for |

**Questioned and kept as the rule has them: 15 companies.**

| Ticker | Company | Class | Why it stays | Decided by |
|---|---|---|---|---|
| SONY | Sony Group Corporation | Wide | First doubted as a mixed group. Games, music and image sensors make most of its profit, and each leads its market; its sensors hold over half of theirs. | Claude, after the closer look the founder asked for |
| RELX | RELX Plc | Wide | An agent's review of 2026-11-11 judged it Wide (override 45), and the rule gives Wide too. | an agent's review, which takes precedence |
| APPN | Appian Corporation | None | It burned cash in nine of the ten years, so it fails the test that made the other loss-making software companies Narrow. | Claude, after the closer look the founder asked for |
| BF.B | Brown-Forman Corporation | Narrow | A strong spirits brand, but it is in Decline, which the phase limit stops. Its ROIC fell from 22% to 13% and its revenue falls. | the founder, on Claude's proposal |
| FNV | Franco-Nevada Corporation | Narrow | Royalties, as TPL, but it pays for them: a ROIC below 9% in six of the ten years, and a loss in 2023. | the founder, on Claude's proposal |
| SBUX | Starbucks Corporation | Narrow | Its ROIC fell from 49% to between 8% and 11%, and its operating margin from 18% to 10%. | the founder, on Claude's proposal |
| AMGN | Amgen Inc. | Narrow | A steady fall: its ROIC went from 28% to 14% and its operating margin from 43% to 25%. Other large drug makers are Wide by the rule, so this is not fully consistent. | the founder, on Claude's proposal |
| HON | Honeywell International Inc. | Narrow | The company is splitting up, so its ten-year record describes a company that no longer exists in that form. | the founder, on Claude's proposal |
| CRM | Salesforce, Inc. | Narrow | A ROIC of 5% over ten years and 7% over five, after large purchases. Its review's Wide was GuruFocus's score carried through, not a judgment. | the founder, on Claude's proposal |
| MDT | Medtronic Plc | Narrow | Its ROIC on all capital was 6% to 8% for nine years and 9% in the newest: the price of one purchase in 2015 is still not earned. Revenue grew 2.3% a year. | the founder, on Claude's proposal |
| TMO | Thermo Fisher Scientific Inc. | Narrow | It spent $44 billion on purchases in the ten years, and its ROIC on all capital stays at 7% to 8%. | the founder, on Claude's proposal |
| DHR | Danaher Corporation | Narrow | It spent $46 billion on purchases, with a ROIC on all capital of 5% to 8%. It is also in Decline, which the phase limit stops. | the founder, on Claude's proposal |
| ICE | Intercontinental Exchange, Inc. | Narrow | Exchanges as strong as CME's, with an operating margin of 36% to 41%. A purchase in 2023 lowered its ROIC on all capital from 8% to 10% down to 6% to 7%. The closest call of the nine. | the founder, on Claude's proposal |
| MDLZ | Mondelez International, Inc. | Narrow | Strong brands. Its ROIC on all capital reached 9% and 10% in 2023 and 2024, and the cocoa cost took it back to 5%. | the founder, on Claude's proposal |
| MKC | McCormick & Company, Incorporated | Narrow | Its ROIC on all capital is 7% to 9% since a purchase in 2017, and its revenue grows 2.5% a year. | the founder, on Claude's proposal |

**What the corrected table gives on refresh 68.**

| | Wide | Narrow | None |
|---|---|---|---|
| GuruFocus's score, as the policy reads it | 145 | 1,132 | 86 |
| The rule's draft | 169 | 1,138 | 56 |
| The draft with the corrections | 161 | 1,155 | 47 |

Against today's values: 109 go up, 57 go down and 1,197 stay; 66 move by 20% or more. Buy levels: 146
up, 91 down.


### 6.8 What is open

Any other anomaly the founder finds in the draft. The data fault found on the way, ELC, a utility's
bond that the universe holds as a company, is filed as B-253.

### 6.9 The work that follows

None of it is started.

1. **The draft.** Run the rule on the current universe and apply the corrections of 6.7.
2. **The table.** A packaged, versioned file with one entry for every company of the universe,
   1,558 on refresh 68. Each entry holds the ticker, the class, the date and where the class
   comes from: the rule, or a correction by hand. A corrected entry is flagged as one and also
   holds the class the rule gave, the reason and who decided it, from the log of 6.7, so the
   history stays with the value. The 15 classes that were questioned and kept carry a note of
   why.
3. **The engine and the store.** A table in the database with one row for each company: the class,
   where it comes from, its date, and for a local change the class before it and the reason. A
   refresh reads the file into it under the priority of 6.4, item 6. The engine reads the class
   from the table; a company with no row is refused, "no moat class". `moat_score` and its
   thresholds go.
4. **The owner's change and the agent's.** The company page gets a control beside the moat stamp:
   Wide, Narrow or None, and a reason the owner may leave empty. An agent's `moat.class` in a
   review writes the table too, with its reason. After either change the company is valued again
   at once, so the new class shows without a full refresh (the founder).
5. **The playbook.** The moat is a standing step of a review, with the five sources as a guide
   and the agent's own judgment and reasons (6.4, item 12).
6. **The documents.** `method.md`'s moat section and the Methodology page in the same commit,
   under a new method version.
7. **The call.** With the ADR ratio (section 3) and Altman's Z″ (section 5) gone too, `summary` is
   no longer needed, and Fairband makes no GuruFocus call.
