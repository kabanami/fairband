# The held reviewed value: design

Status: written 2026-11-23 on the founder's decisions of that day, quoted in the decision log.
The founder decided that a reviewed value stays fixed until the next review, that a value which
is out of date keeps its number and is marked with the reason, that Fairband posts no work item
for it except as an early expiry on a watched company, and that a review is any deliberate write.
Every other choice below is Claude's, marked *my call* where it is more than a reading of those
decisions, and can be overturned as any other. The founder approved the design on 2026-11-23,
the secondary valuation's hold of section 5.9 with it. A builder's read of the first draft (an Opus 5.5 subagent, 2026-11-23) found the gaps
that sections 5.1, 5.2, 5.4, 5.6, 5.8 and 5.9 now close.

No mechanical value moves, and no policy value is added. The rule of a review changes, so
`docs/method.md` (sections 10 and 14) and the Methodology page change in the same commit, the
review method becomes `fairband-review/2`, and the store gains a migration. This design follows
`2026-11-23-thresholds-design.md` and reads a held value's levels and word by its section 5.3.

## 1. What this is

A reviewed value is the engine's value under the overrides an agent set. A report is published
on it. Today "a review follows its snapshot" (method 14.6): every full refresh, scoped refresh
and revalue computes it again on the new data, after dropping each period-tied override that no
longer matches. The screen shows the newest figure. Only the price refresh holds it.

So the figure a report was published on changes with no one deciding it, and nothing says so.

- **QCOM.** Report 2 of 8 Nov 2026 said $211. On 10 Nov a refresh dropped override 1, which had
  turned the charge for stock pay on, and the screen showed about $241 until 22 Nov.
- **CLS.** Report 20 of 11 Nov said $272.54. On 21 Nov a refresh dropped override 36 for the same
  charge, and the screen has shown $291.62 since.
- **AMD.** Report 30 of 11 Nov said $75.29. The engine changed since (the review ran under method
  1.1, the screen's figure under 1.8), and the screen shows $229.25. No review and no report
  stands behind that figure.

After this work the screen shows the figure of the last review until someone reviews the company
again. When that figure no longer fits the data, the row says "Expired early" and why, and shows
beside it what the review would give today.

## 2. Goals, non-goals, anti-goals

Goals:

- The Reviewed column, the drawer, the company page and the agents' tools show the value of the
  company's last made review (section 3), whatever a refresh computes.
- A held value that no longer fits the data reads as expired, with the mechanism in words (the
  brand book: "Name the mechanism, not the feeling").
- A watched company whose held value expired, by its date or early, gets one review item, by the
  rule that posts one today. No other company gets an item.
- An agent or the owner can make the review again with no change of an input.

Non-goals:

- A mechanical value that holds. A row with no review moves at every refresh, as today.
- Overrides the owner writes on the page. Only an agent adds or drops one (method 14.1); that
  stays.
- A check of whether a published report's stance still fits (the thresholds design, section 2).
- A change to the tests that drop an override. They run as today (5.5).
- A rule for a trough's lift in the playbook's cycle formula, which QCOM's review left open.

Anti-goals:

- A held value that hides news. Each reason of 5.3 must show on the row on the day it holds.
- A held number that changes by any act but a made review, a split or an exchange rate (5.2).
- An item in the inbox for a company on no watchlist.

## 3. Terms

- **A made review**: a review a person or an agent made by a deliberate act (5.1).
- **The held review**: the company's newest made review. Its value is **the held value**.
- **A reading**: what the review gives on a newer snapshot, computed by a refresh over the
  overrides still applied. It is what the screen shows as the reviewed value today.
- **Expired early**: the held value's window has ended before its date, for a reason of 5.3.

## 4. Approaches

- **A. Keep the refresh's computation as a reading, and show the held review.** A refresh that
  values still drops the overrides its tests name and still computes its review; the store marks
  which reviews are made, and every reader shows the newest made one. The reading feeds the
  reasons of 5.3 and stands beside the held value in the drawer.
- **B. Compute no reading at a refresh, only when someone asks.** Less is stored. But the third
  reason of 5.3 needs the reading for every reviewed company whenever the inbox is read, so the
  engine would run inside a page read.
- **C. Hold the overrides too.** No override drops between reviews; each is tested when the next
  review is made. A list of overrides would then show as applied an override that no longer
  matches its data, the playbook's rule for a period-tied override would change, and the reason
  for the mark would have no record.

**A is chosen** (*my call*). It changes which review the readers show and leaves the refresh, the
drop tests and the override records as they are.

## 5. The design

### 5.1 The acts that make a review

A review is made, and becomes the held review, when:

1. an agent adds, replaces or drops an override (the recompute of method 14.5);
2. an agent or the owner writes the moat class (`moat_set`, or the page's moat box), which values
   the company again: the review written there is made. That write runs the refresh's own follow
   with a refresh id (`refresh/run.py`, `revalue_company`; `follow_snapshot`), so the call itself
   says its review is made; a missing refresh id does not mark one;
3. an agent or the owner makes the review again with no change of an input (5.6).

A review a refresh writes is a reading and never the held review. A made review that refuses
holds no value, and its row reads as a row under a refusing review reads today.

When a person's act leaves no override applied (an agent drops the last one, or Review again
finds none, 5.6), the company has no review and its row is mechanical again. When a refresh drops
the last one, the held review stays, expired early.

### 5.2 What the held review keeps, and what still moves

Kept as made: the value in the company's currency, the bridge with the mechanical value of that
day, the overrides inside, the result's flags, and the validity window of the snapshot it was
made on (so the row's "valid until" is the date its report shows).

Moved, none of them a change of opinion:

- **The price.** Everything a price refresh moves on a review today (method 10): price ÷ value
  and the word, the implied growth and its sensitivities, the expected return, the multiples and
  the long-runway flag, so "what the price needs" (method 4.11) is solved at the latest price.
  The levels and the word read the settings in force (the thresholds design, 5.3).
- **A split.** The value a share is divided by ρ and the share count multiplied by it, ρ the
  product of the ratios of the splits that the latest snapshot's figures saw and the held
  review's did not, by the rule that scales an override (method 14.6), before the reprice.
- **An exchange rate.** A foreign company's value in US dollars is the held value in its currency
  at the latest snapshot's rate, as a price refresh moves it today.

*My call* on the mechanism: the held review is repriced onto each new snapshot, a price refresh's
and a valuing refresh's alike, as `reprice_review` reprices a review today. Then the screen's
rows, `counts_on` and the report check find it on the latest snapshot, for a foreign company too,
whose value in US dollars changes with each rate.

The Mechanical column shows the latest snapshot's value, as today. The row's flags are the held
review's; its warnings read the latest snapshot, as today.

### 5.3 When a held value expires early

The held value is expired when its window's date has passed, as any value is. It is expired
early while one of these holds, each shown as its sentence:

1. **A newer period is on file.** The latest snapshot's trailing period end is after the one the
   held review was made on, read as the drop test reads it (a snapshot from before method 1.3
   by the `as_of` of its share count). "The company has reported a newer period (to 26 Dec
   2026)."
2. **An override inside it no longer applies.** The system dropped it since the review was made;
   the ledger's row of the drop names the system as its writer. "Override 36 (non-recurring gap)
   no longer applies: the input the override corrected changed." This includes a period-tied
   share count or NTM EPS that drops at a split because its reading changed: the review cannot be
   made again as it was. An override an agent replaced or dropped is a made review of its own and
   never a reason. Nor is a `moat.class` override that method 1.8 moved to the moat table: the
   class is in force.
3. **Computed again, the value is outside the held value's fair band.** The newest reading ÷ the
   held value (both after 5.2's split) is under the band's low or over its high, 0.90 and 1.10 at
   the defaults. "Computed again on today's data, the review gives $229.25 (+204%)." A reading
   that refuses on the data counts: "Computed again, the review gives no value: <the refusal>."
   A reading that failed (a failed fetch or valuation, or "review failed: …") is no reason: the
   last good reading stands.

*My call* on reason 3's size: the fair band is the accuracy Fairband claims for a value, so a
reading inside it is the same value, and no new policy value is needed. *My call* on its life:
reasons 1 and 2 are facts and stay; reason 3 is read on the newest good reading, so it can end
without a review when the estimates move back.

The date of an early expiry is the day of the first refresh that found a reason.

### 5.4 The reading

A full refresh, a scoped refresh and a revalue compute the reading as they compute the review
today (`refresh/reviews.py`, `follow_snapshot`), with its log row. With no override left a
refresh computes none, and the reading is then the latest snapshot's mechanical value. The page
shows the reading only inside the opened detail of an expired value (5.7). A price refresh
computes none: 5.2 moves the price.

### 5.5 The overrides drop as today

The tests of method 14.6 run at each refresh and drop what they name, with the ledger row and the
reason. The override then reads as dropped in every list, and the held review still counts it:
that is reason 2. The next made review runs over the overrides still applied.

### 5.6 Review again

A new act for an agent (an MCP tool) and for the owner (a button in the drawer): make the review
on the latest snapshot over the overrides still applied, with no new input. It runs the recompute
of an override's write, with its refusals ("settings changed: run a revalue", "the store moved
since snapshot <id>: run a revalue"), writes the review, its log row and a ledger row naming who
did it, and answers as an override's write does.

With no override applied, Review again clears the held review, with its ledger row: the row is
mechanical again. *My call*: that is how a company leaves the held state after a refresh dropped
its last override (ADBE, RKLB and SYM hold period-tied overrides alone). It is refused only for
a company that holds no review.

For the owner it is how he accepts the reading: on CLS it would put $291.62 in place of $272.54,
and the drawer shows first which overrides no longer apply.

### 5.7 The page

The screen's row, the watchlist page's row and the company page's head show the held value. The
Freshness column reads the held review's state for a reviewed row: Current, Aging, Expired, or
Expired early. "Expired early" takes the glyph and the colour of Expired (`×`, `critical`: the
brand book gives those two to an expired value and to nothing else), and the filter that hides
expired rows hides it too. *My call*: no new colour and no new column.

```
TICKER   FAIR BAND     MECHANICAL  REVIEWED  PRICE    PRICE ÷ VALUE   FRESHNESS
CLS  ◆   $245 – $300   …           $272.54   $223.89  0.82 Below      × Expired early
```

(A sketch: the price is CLS's close of 10 Nov 2026, and the band is the held value's at the new
thresholds.)

The page is crowded already (the founder), so the drawer and the company page's Overview add
nothing for a value that is current, aging or expired by its date. For one expired early they add
one line under the reviewed value:

```
Reviewed  $272.54
× Expired early 14 Nov 2026 · 3 reasons  ▸
```

A click opens the detail, and nothing else on the page shows the reading:

```
× Expired early 14 Nov 2026 · 3 reasons  ▾
  Override 37 (consensus step 2) no longer applies: the input the override corrected changed.
  Override 38 (consensus step 3) no longer applies: the input the override corrected changed.
  Override 36 (non-recurring gap) no longer applies: the input the override corrected changed.
  Computed again on today's data, the review gives $291.62 (+7.0%).
  [Review again]
```

Request research stays where it is in the drawer. The bridge is the held review's, and its first
line says the day of its mechanical value.

### 5.8 The agents

- The tools that give a company's review (`company`, `screen`, `reviews`) give the held review,
  its state, the reasons of 5.3 as sentences, and the newest reading's value.
- A report, and a sensitivity reading, need a held review that no refresh has read again: where a
  valuing refresh ran after the review was made, the cite is refused, "the review was made before
  the latest refresh: make it again", and the agent makes it again by an override or by 5.6. A
  price refresh does not count: its repriced copy is the held review (5.2), as the check's rule
  "or the one that snapshot reprices" has it today.
- The playbook's valuation step starts by reading the state and the reasons: for each override
  that no longer applies it decides again from the filing, and it ends with a made review on the
  latest snapshot. Its sentence that a period-tied override is asked again at the next review
  stays true.

### 5.9 The secondary valuation

A secondary valuation fills the Reviewed column where neither the route nor the review values the
company (method 15; FRVO's $6.01, report 22). Today it stops counting, with no word, once the
snapshot it rests on is replaced by different data or another method version.

It holds by the same rule in its plain form (Claude's proposal, approved by the founder): the
newest secondary valuation fills the row until an agent makes a newer one or a made review values
the company. It expires by its window's date, and early when a newer period is on file, or when
the route now values the company: "The route now values the company, at $X." It has no reading
and no Review again: an agent makes it again.

### 5.10 The inbox

The expiry rule (`store/inbox.py`, `post_expiry_items`) reads, for a company on a watchlist that
has a held review or a held secondary valuation, that record's state in place of the latest
snapshot's window: expired by its date or early, it posts one valuation review whose note gives
the first reason ("expired early: override 36 no longer applies"). One item stands for one held
record, whatever becomes of it, as an expiry item stands for its window today; a second reason on
the same record posts nothing. A watched company with neither keeps today's rule. A company on no
watchlist gets no item, and a pending item drops when its company leaves every list, as today.

### 5.11 The method document, the versions and the store

`docs/method.md`: section 10 (what each refresh moves), 14.5 to 14.7 (a review is made, held and
read again; the log), 15 (the secondary valuation holds), 4.10 (a reviewed row's window is its
held record's) and the glossary. The Methodology page says in plain words that a reviewed value
holds until the next review and what "Expired early" means. The review method becomes
`fairband-review/2`; the mechanical method and the policy do not change. The store's migration
marks a made review and keys an expiry item to a held record; its form is the builder's.

### 5.12 Going live

At the migration a company's held review is its newest review that an override's write or drop
made, that a moat write made, or that a published report cites (ADBE's review 571 is a moat
write's, and report 36 cites it).

Read on the store of 23 Nov 2026, 32 companies have a review and 31 of those a value:

- 10 keep the figure the screen shows today.
- 21 go back to the figure of their last made review. For 18 the difference is under 10%.
- Six expire early at once: AMD ($75.29 held, $229.25 computed again), AVGO ($368.80, $471.30)
  and TTMI ($48.61, $55.08) by reason 3; CLS, RKLB and SYM by reason 2. Reason 1 adds no company.
  By the plain date, SYM's window ends on 23 Nov and ADSK's on 24 Nov.
- No item is posted: of the 32, AMZN, GOOG, META, MSFT and NVDA are on a watchlist, and none of
  them expires.

**Decided.** At go-live the screen goes back to these figures (the founder, 2026-11-23): AMD
reads $75.29, "Expired early", with $229.25 in its detail and a Review again button. No one
reviewed $229.25, so the rule does not hold it. The other way, to take the day's figures as held
with no mark, is not built.

A secondary valuation holds from go-live by the rule of 5.9: FRVO's newest one, $6.01, fills its
row again, expired or not as 5.9 reads it on that day.

## 6. Left to the builder

- How the store marks a made review, and whether a reading stays a row of the reviews table.
- Where the reasons are computed, at the refresh or at the read, and where the early expiry's
  date is kept.
- The MCP tool's name and answer, and the drawer's exact words and layout, within the brand book.
- How the review log tells a reading from a made review.
- The tests' form. They must hold the cases of section 7.

## 7. How we know it works

- A scoped refresh that drops a period-tied override leaves the Reviewed figure as it was, sets
  Freshness to "Expired early" with reason 2's sentence, and shows the reading in the drawer.
- A revalue under a new method version that moves the reading by 12% expires the held value early
  by reason 3; one that moves it by 8% does not, and the drawer still shows the reading.
- A refresh whose fetch fails changes neither the held value nor its state.
- A refresh after the company reports expires it early by reason 1.
- Review again, by an agent and by the owner, makes the reading the held value, clears the mark
  and gives the row the new snapshot's window. With no override applied it returns the row to the
  mechanical value.
- A price refresh moves the held review's price ÷ value, its word and its implied growth, and
  not its value; for a foreign company its value in US dollars moves with the rate, and a report
  on it is still accepted.
- A watched company expired early gets one item; declined, it gets no second for that held
  review; an unwatched company gets none.
- A 2-for-1 split halves the held value a share and its levels and changes no word; Freshness
  changes only where the split drops an override inside.
- A report submitted on a held review made before the latest valuing refresh is refused, and
  accepted after Review again.
- A secondary valuation stays on its row through a refresh that replaces its snapshot, and
  expires early when the route values the company.
- A mechanical row with no review and no secondary valuation behaves as before.

## 8. Decision log

| Date | Decision | Whose |
|---|---|---|
| 2026-11-23 | A reviewed value never moves without a review: "a reviewed value should never move, even if an override is dropped. The reviewed value is one that an agent and user agree on in the end, and that should remain static until an updated review" | the founder |
| 2026-11-23 | The row is marked and keeps its number; no work item is posted for it: "Automatic posting of work items occur for companies in watchlists only … the user might not be interested in the company after the report" | the founder |
| 2026-11-23 | On a watched company the mark counts as an early expiry: "yes, an early expiry for watched companies only" | the founder |
| 2026-11-23 | A review is any deliberate write, not only a published report: "A is ok". As built, the writes are an agent's override or drop, the moat class by an agent or the owner, and Review again by either; the owner writes no override (method 14.1) | the founder; the list of writes is Claude's reading of the code |
| 2026-11-23 | At go-live the reviewed figures go back to each company's last made review: "I thought we said for reviewed values, these would only be updated on a new review", then "Fine option (a)" | the founder |
| 2026-11-23 | The page gains one line in the drawer for a value expired early, its detail on a click, and no mockup is made: "the page is already cluttered with too many information", "don't make the mockup" | the founder; the one line is Claude's proposal, accepted |
| 2026-11-23 | The design is approved, and with it that a secondary valuation holds by the same rule (Claude's advice on the last open question): "approved" | the founder |
| 2026-11-23 | Approach A; the three reasons and their sentences; reason 3 on the fair band; a failed reading is no reason; "Expired early" as a state of Freshness with Expired's glyph and colour; Review again for the owner as well as the agent, clearing the review where no override is left; the held review repriced onto each snapshot; one item for one held record | Claude |
