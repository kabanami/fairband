# The agents' tools and cites: a fixed number in arithmetic, a threshold on a kill criterion, a currency on a record, one stored copy of a filing, and the tools' debt: design

Status: written 2026-11-15. This is theme 5 of the research agents' issues (the founder's review
of 2026-11-13), the last theme of the round: the tools an agent works with and the cites a
report carries. The founder ruled on its four questions on 2026-11-15 (section 6). Every other
choice below is Claude's, marked *my call* where it is more than a reading of a backlog row, and
can be overturned as any other. Not built.

No valuation moves. Nothing here touches the engine, the classifier, the universe rule or a
policy value: the method stays `fairband-mechanical/1.5` and the policy v16. The changes are in
`src/fairband/store/` (one migration), `src/fairband/reports/`, `src/fairband/web/`,
`src/fairband/mcp/`, `src/fairband/refresh/passthrough.py`, one loader check in
`src/fairband/policy/`, and the playbook.

This document amends `docs/method.md` (the method as built) in sections 14.9, 16.2, 16.3, 16.4,
16.6 and 16.8, and the playbook with them. Every earlier spec stands for what it does not
mention.

## 1. What this is

A report is refused if a number in it has no stored source (the number check, method 16.3). The
rule stops an agent from inventing a number. It is too strict in three places, one storage
setting is wasteful, and five backlog rows hold small faults of the tools:

1. **Plain arithmetic** (B-99). `derive` takes two stored figures. An agent that needs "1 minus
   the tax rate", an average of two figures or a figure a filing states in millions has no way
   to enter the 1, the 2 or the 1,000,000, so it divides a revenue by itself to make a 1.
2. **A threshold the agent chose** (B-99). A kill criterion (an event that ends the thesis)
   cannot state "growth below 5%" in the report, since the 5% has no source. The agent names a
   stored figure instead or uses words.
3. **A figure in another currency** (B-161). A finding and a guidance record store no currency,
   and every reader takes the company's reporting currency. TSM reports in TWD and guides its
   revenue and capital spending in US dollars, so no record could hold the guidance.
4. **A second copy of a filing** (B-167). A filing report an agent reads is stored whole and a
   new copy is stored on the first read after thirty days, though a filing does not change.
5. **The tools' debt**: B-103, B-105, B-142, B-117, B-118, and four faults the code map met on
   the way (section 12).

## 2. Goals

- An agent's arithmetic needs no workaround for a fixed number.
- A kill criterion can state its threshold as a number, cited, and marked as the author's own.
- A record holds a money figure in the currency the company states, and every reader of the
  record shows that currency.
- One stored copy of a filing report serves every later read.
- The eight backlog rows of the theme close, but for two clauses of B-103 (section 3).

## 3. Non-goals

- No engine change and no new input. No value, level, flag or review moves.
- No general loosening of the number check. A number from a filing, a statement, an estimate or
  a call still needs its source (the founder, 2026-11-15).
- No `peg` operation: the fixed number 100 gives a PEG in two derivations (section 7.5).
- No currency on a derivation, and no currency known for a ref that is not a record (a `fact:`,
  an `estimate:`, a `snapshot:` input): the resolver learns the currency of findings, guidance
  records and kill criteria only. The check's `$` rule for the other refs stays the playbook's
  (filed, section 14).
- No pruning of stored responses, and no change to how often a cited filing report is parsed.
- No stored copy of the rate at a record's date: a figure in another currency is converted, when
  an agent needs it converted, with the snapshot's rate (`snapshot:<id>/inputs/fx_rate`).
- Two clauses of B-103 stay filed. A `close:` ref after a split-adjusted re-fetch has no small
  fix (the ref would need a response id in it). And the agents' routes go on mapping any
  `ValueError` to a 400 and any `KeyError` to a 404: a narrower map needs every refusal of the
  store and the symbol rule (`exchange_symbol`) moved to classes of their own, a change across
  the store with more risk to the refusals an agent meets than the fault it corrects, which no
  case on file shows (*my call*, after the builder check).

## 4. Anti-goals

- A door for a chosen number. A fixed number comes from a short list the server holds, never
  from the agent; a threshold is cited only where kill criteria are stated and the references
  list says whose number it is.
- A US-dollar figure shown or computed as if it were in the reporting currency, or the reverse.
- A stored record or derivation that reads differently after the change. Every record on file
  means what it meant: a record with no currency is in the reporting currency. A stored report
  reads as it did but for one table of the export, Appendix A's "Guidance on file", which gains
  the currency the page already shows (section 9.5).
- An answer that an agent meets today changing its status or its words, but for those this
  document orders: clauses 1, 3, 6, 7 and 9 of section 12.1; a `growth` or a `cagr` from a base
  at or below zero, which has no value (7.4); the wrong-unit detail of a record's cite, which
  names the record's currency (9.4; the controller's Ruling 3).

## 5. The evidence (the live database, read-only, 2026-11-15; main `138ef49`)

- **Derivations**: 1,590 on file (`growth` 596, `ratio` 543, `difference` 222, `sum` 185, `cagr`
  44, `product` 0). Sixteen have the same ref as both operands, in 13 of the 30 researched
  companies: nine are a figure over itself, the number 1; MU and three others built a 2 for an
  average; V built a 0 to change a sign; AMD doubled a count. They feed "1 minus a rate",
  "1 over a multiple" and "a sum over 2".
- **Kill criteria**: 132 on file, all open. None holds a `%` and none a ref; 65 hold a digit,
  nearly all a fiscal year. A record's text is never checked: only a report's sections are.
- **Currencies**: 4 of the 30 researched companies do not report in US dollars (ASML in EUR,
  NVO in DKK, RELX in GBP, TSM in TWD); in the store 174 of 1,787 companies with annual
  statements. Their reports cite 22 money findings and 31 guidance figures, none with a `$`.
- **Filing reports**: 42 stored, of 18 companies, 34.4 MB of the database's 6,429 MB (the price
  histories are 2,185 MB), the median 0.70 MB and the largest 3.15 MB; none is stored twice,
  since the first was stored on 2026-11-11. Reports cite 15 of them 180 times and 112
  derivations read their cells. A `filing:` ref names the stored copy by its response id.
- **Growth below −100%** (a base below zero): none among the 596 `growth` derivations.
- **A derivation resting on two snapshots**: none among the 1,590.

## 6. The founder's rulings (2026-11-15)

The founder asked for the problem "in simple terms", then asked why the rule is not loosened,
and ruled "yes" on the four as Claude advised, each a narrow loosening and not a general one:

1. `derive` takes a fixed number from a short list the server holds (section 7).
2. A kill criterion can store one threshold the agent chose, cited in the report and marked as
   the author's own (section 8).
3. A finding and a guidance record carry the currency the company states (section 9).
4. A stored filing report is reused without a time limit, and nothing is deleted (section 10).

## 7. A fixed number in `derive` (B-99)

### 7.1 The operand

One operand of a derivation may be a fixed number, written `number:<n>` where a ref goes:
`{"operation": "difference", "a": "number:1", "b": "snapshot:412/inputs/tax_rate"}`. The other
operand is a ref, as today. `<n>` is written in digits alone, with no sign, separator, point or
exponent.

The list (*my call*, from the evidence and the uses the playbook names): the whole numbers 0 to
12, then 52, 100, 365, 1000 and each further power of ten up to 1,000,000,000,000. They serve a
complement (1), a change of sign (0), an average or an annual rate (2 to 12, 52, 365), a ratio
with no unit made a PEG (100) and a unit scale (a power of ten). A percent times 100 is still a
percent by the table of 7.2, so it is not a way to points (the controller's Ruling 1).

Refused, each a 400 that stores none of the call's derivations, as an unresolved reference is
today:

- a number outside the list or written another way (`number:15`, `number:1.5`, `number:1e6`,
  `number:1,000`): "a fixed number is one of 0 to 12, 52, 100, 365 or a power of ten up to
  1,000,000,000,000, not <what was written>";
- two numbers in one derivation: "a derivation needs a stored figure".

### 7.2 Its unit

A number has no unit. The result's unit follows the stored figure (*my call*):

| Operation | Unit |
|---|---|
| `sum`, `difference`, `product` with a number | the stored figure's unit |
| `ratio` of a figure over a number | the figure's unit |
| `ratio` of a number over a figure | none |
| `growth`, `cagr` | `percent`, as ever |

So 1 less a tax rate is a percent, a figure a share over 2 is a figure a share, and a filing
cell times 1,000,000 has no unit, as the cell has none. A derivation with no unit is cited at
the cite's own precision with any suffix, as today (method 16.3).

### 7.3 Where a number is read

`number:` is an operand of `derive` alone. As a cite's ref in a report it names nothing: the
check answers `unresolved reference`, with the detail "number:100 is an operand of derive: cite
the derivation". The stored derivation keeps the operand as written (`derivations.a`,
`derivations.b`; no migration). A number rests on no snapshot.

The references list words a derivation as today and writes a number without its prefix, with
separators: "derivation 1602: the product of filing:95122/… and 1,000,000".

### 7.4 Two faults of `derive` corrected with it

- **Growth from a base at or below zero has no value.** `growth` of 50 over −100 reads −150%
  today, a wrong sign. `growth` and `cagr` give no value where `b` is at or below zero, as the
  guidance step refuses such a base (`store/guidance.py`). A stored derivation keeps its value.
- **A derivation rests on every snapshot its operands rest on.** The snapshot test of the check
  reads one snapshot for a derivation, that of its first operand that rests on any
  (`refs.rests_on`), so a derivation with a later operand on an older snapshot passes. The test
  fails for a `derived:` cite when any operand, through nested derivations, rests on a snapshot
  that is not the company's latest.

### 7.5 What the playbook says

- The recipes: a complement, an average, a change of sign, a cell of a sheet in millions scaled
  to full units before it meets a `fact:` figure (the rule "do not derive a cell with a figure
  in full units" becomes "scale the cell first"), and a PEG as the `ratio` of the P/E over the
  growth, then the `ratio` of that over `number:100`.
- A number is a fixed number of arithmetic, never a figure the agent chose: the server refuses
  any other, and a multiple or a rate the agent assumes is not arithmetic.
- A figure a filing states is still cited from its cell; a finding in full units is no longer
  the way to compute with it.

### 7.6 A derivation with a number depends on a stored figure (after the whole-branch review)

The whole-branch review built a chosen figure in two derivations: a figure times `number:0` is
nought in the figure's unit, and a number added to it is that number, cited as sourced. So (the
controller's Rulings 6 and 8):

- A derivation with a `number:` anywhere in its tree (its operands and those of a `derived:`
  operand, nested ones too) must depend on a stored figure. The tree is evaluated from its
  leaves; each group of leaves of one value is scaled by 1.5 in turn; the derivation depends on
  a figure when a scaling moves the result from a value to a value, beyond float rounding and a
  billionth of the result. A nested derivation that no longer evaluates to its stored value is
  a constant.
- One that does not is a 400 that stores nothing of the call: "a derivation with a fixed number
  must depend on a stored figure: this one has the same value whatever its figures are", with
  ", or rests on an earlier derivation whose figures changed: derive it again" where that is
  the case.
- A derivation with no number in its tree is not tested: a figure over itself, plus itself and
  minus itself compute as before, as section 15 asks.
- A figure that is nought moves nothing, so a derivation of it with a number is refused in the
  same words; the figure itself is cited.

The rule refuses a constant. It cannot refuse a figure an agent sets out to construct (filed,
section 14): a near-constant that rounds to a chosen number (a figure over a large number, plus
a number); stored figures that cancel among themselves (the price-to-value times the value,
less the price); a stored figure scaled by numbers chosen to land on a figure (a price of $150
times 2 over 3). The same was open before this design, through a figure over itself. The number
check stops a slip and an improvisation, and the references list shows each cited derivation.

## 8. A threshold on a kill criterion (B-99)

### 8.1 The record

A kill criterion may hold one threshold: a number, its unit (one of a finding's units) and, for
a money figure, its currency (section 9.1). The number and the unit come together. The text
stays the criterion's statement and stays unchecked.

- The tool: `kill_criterion_add(symbol, text, threshold=None, unit=None, currency=None)`; the
  route's body takes the same three. The answer and the `kill_criteria` read carry them.
- A report's own list (`killCriteria`, stored at publish) takes text alone, as today. A
  criterion with a threshold is recorded with the tool before the report is written, since the
  report cites it by its id; the agent leaves it out of the report's list, where it would be
  recorded twice (*my call*: no form that ties an existing criterion to a report; the criterion
  keeps no report id, as every criterion the tool records).
- If the report is not published, the criterion stays on file, open; the agent retires it with
  `kill_criterion_set`, as it retires any criterion that no longer holds.

### 8.2 The ref and the check

- `kill:<id>` resolves to the threshold with its unit and its currency: no period, no snapshot.
  It names nothing for a criterion of another company or one with no threshold. It resolves
  whatever the criterion's state, so a published report's references keep their words.
- The check takes a `kill:` cite as it takes a `finding:` cite: the number at the unit's
  rounding, the unit's suffix, the currency rule of section 9.4.
- A `kill:` cite passes in one section alone, "Risks and kill criteria" (section 11 of a full
  report, the ninth of a valuation review). Elsewhere it is an `unresolved reference`, as a
  `number:` cite is, with the detail "kill:12 is the author's own threshold: cite it in Risks
  and kill criteria" (*my call*: without this, any chosen number could enter any section as a
  criterion's threshold). No failure word is added, so the list of checks in Appendix A of
  every report, which is read from the code when a report is read, stays as it is (*my call*,
  after the builder check).
- `derive` takes no `kill:` operand: 400 "unresolved reference: kill:12", as for a ref that
  names no number. A chosen number does not enter arithmetic.
- The references list: "kill criterion 12, a threshold the author chose".

### 8.3 What the playbook says

The rule of `citations.md` on a chosen threshold changes: a threshold the agent chooses goes on
the kill criterion and is cited from it in section 11; it is still never a finding. An event
tied to a stored figure is still cited from that figure, and is the better criterion where one
serves, since a reader can follow it to its source. The template's section 11 row and its
example gain one criterion with a threshold.

## 9. A currency on a record (B-161)

### 9.1 The stored currency

Migration 008 adds a nullable `currency` column to `findings`, `guidance` and `kill_criteria`,
and `threshold` and `unit` to `kill_criteria`. A null currency means the company's reporting
currency, which is what every record on file means today; no row is rewritten.

- The tools: `finding_add(..., currency=None)`, `guidance_add(..., currency=None)`,
  `kill_criterion_add(..., currency=None)`, and their routes.
- A currency is three capital letters (`USD`, `TWD`); it is checked for its form, not against a
  list (*my call*). It goes with a money figure alone: a finding or a threshold of unit
  `currency` or `per-share`, a guidance record of a metric whose unit is one of the two
  (`revenue`, `net_income`, `free_cash_flow`, `capex`, `eps`). Else 400 "a currency goes with a
  money figure". It is stored as given, also when it is the reporting currency.
- Every read of a record answers `currency` for a money figure: the stored code, else the
  reporting currency; null for a figure that is not money.
- **The reporting currency of a record with no stored currency is the one its reader labels it
  with today** (*my call*, after the builder check): the currency of the company's latest
  snapshot as `money_of` reads it, USD where the company has no snapshot, for the tools'
  answers, the drawer, the resolver, the check and `derive`; the currency of the report's own
  snapshot in a report's Appendix A. A snapshot refused before its currency was read says USD,
  as today (filed, section 14).
- A guidance record supersedes the company's current record of the same metric, period and
  basis whatever the currency of either (*my call*): one current record a metric, period and
  basis, as today.

### 9.2 The guidance step

A guidance record's step is its midpoint over the actual of the year before, read from the
statements (method 14.9). A record with a stored currency that is not the currency of that
actual (`facts.currency`) takes no step: `step` is null and `guidance:<id>/step` names nothing.
A record with no stored currency steps as today. The engine reads no guidance
figure, and the server still checks an override's guidance evidence by the record, not by its
figure (method 14.9); the playbook tells the agent to convert the figure before it sets an
input from it (section 9.6).

### 9.3 The resolver and `derive`

`Resolved` gains `currency`: for a `finding:`, a `guidance:` or a `kill:` money figure, the
record's currency as section 9.1 reads it; `None` for every other ref.

A record in a currency that is not the reporting currency is kept out of money arithmetic until
it is converted (*my call*). Two rules:

1. A derivation has no value where one operand is such a record's money figure and the other
   is a money figure (unit `currency` or `per-share`) that is not a record in that same
   currency.
2. A derivation with such an operand never has a money unit: where the unit rules give
   `currency` or `per-share`, it has none. A derivation is stored with no currency, so a money
   unit on it would read as the reporting currency (*my call*, after the builder check).
3. A `derived:` operand carries the currency of the record it was derived from, read from the
   stored rows when it is used, and the two rules above read it as they read the record. It is
   freed in three cases alone: the `product` of a US-dollar operand with the rate; a `growth`
   or a `cagr`; a `ratio` of two operands in that same currency (the controller's Rulings 7
   and 9, after the whole-branch review, which mixed dollars and kronor one derivation deep).

So a US-dollar finding of a TWD reporter:

- with another US-dollar record gives a growth (a percent), a ratio (a multiple), or a sum or a
  difference with a value and no unit;
- times the rate (`fx_rate`, which has no unit) is the figure in TWD, with no unit, which then
  combines with anything; over `number:4`, or averaged with another US-dollar record, it is
  still in US dollars and still has no value with a figure in TWD;
- with a `fact:` revenue in TWD has no value, where today it would read as a ratio.

A derivation with no unit is cited at the cite's own precision with any suffix (method 16.3),
so the agent writes its currency in the text. Known edge, accepted: a US-dollar record of a
foreign filer has no value with the price or a close, which are in US dollars but whose
currency the resolver does not know.

### 9.4 The check

For a cite of a record's money figure (`finding:`, `guidance:`, `kill:`):

- a `$` in the cite passes only where the record's currency is USD; else `wrong unit`, with the
  detail "finding:812 reads TWD 1,000,000,000: write the number without $ and name TWD before
  it". This is the rule method 16.3 states and the server does not enforce; no cite on file
  breaks it (section 5).
- the wrong-unit detail writes such a figure with its code, not with `$`.

For every other ref the check is as today.

### 9.5 The page and the export

- The drawer's Findings block and its guidance table write each record's money in the record's
  currency (`$` for USD, the code before the number otherwise, as `findingFigure` does today
  with the company's code).
- Appendix A's "Guidance on file" writes each figure in its record's currency on the report
  page. The export's table keeps its bare numbers and gains a Currency column after the
  midpoint, the record's code for a money metric and empty for a percent (*my call*: the
  table's numbers are raw today, and a column names the currency without a new format).
- A cite's text is the agent's, as ever.

### 9.6 What the playbook says

One rule in the three places that state it today (`SKILL.md`, `citations.md`, `tools.md`):
record a money figure in the currency the company states it in, and pass `currency` when that
is not the reporting currency. In the report such a figure takes `$` where it is in US dollars
and its code in the plain text before a bare cite otherwise. To set an input from it or to
compare it with a statement, convert it first: `product` of the figure and
`snapshot:<id>/inputs/fx_rate` for a US-dollar figure (the rate is the reporting currency per
US dollar). A figure in a third currency is stated and cited in its own currency and enters no
arithmetic with the company's figures.

## 10. One stored copy of a filing report (B-167)

`filing-report` reuses the newest usable stored copy whatever its age
(`refresh/passthrough.py`, `FILING_REPORT_REUSE_HOURS`, thirty days today). A copy that cannot
be read (stored with an error) is never reused, as today. The filing list and the list of
reports keep their window (`reuse_hours`). Nothing is deleted: a `filing:` ref names its copy by
the response id, and a published report's references must keep resolving.

Left as it is (*my call*): each cited report is parsed once on a read of a report that cites it.
An export takes 0.17 s at the median across the 32 reports on file.

## 11. The tools' answers (B-117, B-118)

- **B-118, a revenue split that ends early.** Each of the two splits in the `segments` answer
  (`product`, `geographic`) gains `newestYear`, the largest fiscal year among its rows, null
  with no rows. The playbook: where a split's newest year is before the company's newest fiscal
  year, read the 10-K's segment note with `filing_search` and `filing_report` and cite its
  cells.
- **B-117, a call after the close.** Every session starts with a scoped refresh, which fetches
  the closes again, so the row's fix is in place but for one case: the next trading day has no
  close yet. The playbook's call section says: where no close is on file for the trading day
  after the call, state no move and say that the close is not on file yet.

## 12. The debt rows

### 12.1 B-103, web, inbox and read debt (nine of its eleven clauses)

1. A kill criterion moved to the state it is in answers 409, not 400; its words stay.
2. `post_expiry_items` writes its ledger rows itself; the route stops writing them.
3. `POST /api/inbox/claim` with no body claims the next item, as an empty body does.
4. A blank client header is stored as null.
5. (Filed, section 3: the map of the store's refusals.)
6. `/estimates`, `/price-history` and `/peers` answer 404 for a symbol that has no snapshot, with
   the words the company read (`GET /api/companies/{symbol}`) answers such a symbol with. A
   company with a snapshot and nothing of the read's own kind answers 200 with its empty lists,
   as today (*my call*, after the builder check).
7. `fmpCounted` leaves the `peers` answer (*my call*: nothing reads it and it has no ref).
8. `/financial-tables` reads the statements once less: the route passes what it read to
   `financial_tables`. The read inside `build_inputs` stays (B-200).
9. The newest aggregate ROIC cell says "over <n> years" in its note where fewer than ten years
   are usable.
10. A policy whose ranges name a tag the engine does not know is refused when it is loaded, and
    the two refusals of a malformed range gain tests. `engine.overrides` imports the policy
    package, so the loader cannot import the tags at its top: the builder chooses a local
    import or a check where both are known.

The clause on `close:` refs stays filed (section 3).

### 12.2 B-105, playbook debt

- The register's "Means" on snapshot, news item and work item takes the brand book's words. The
  judgment row keeps the register's, which match the product; the brand book's row is filed.
- "The sales class" is explained at its first use.
- The playbook test stops repeating two assertions that `structure_refusal` makes.
- The review log's stance is left as stored (*my call*): it is the stance in force when the
  review was written, none before a company's first report. Filling it at publish would mix
  two meanings in one column. `tools.md` and method 14.7 say what it is.

### 12.3 B-142, filings and sources

- `citations.md`: a figure taken from a secondary analysis names that source in its finding,
  and the report says that the filing itself was not read.
- `SKILL.md`: where sec.gov refuses a fetch, read the filing's text on the company's investor
  site.

The row's other two clauses were closed by the filings access build and by `74a1302`.

### 12.4 Two faults of the reports' code, met on the way

Both are in sections 9.4 and 9.5: the `$` in a refusal's detail on a figure in another
currency, for a record; the export's guidance table without a currency.

## 13. The documents

- `docs/method.md`: 14.7 (the log's stance), 14.9 (the step of a record in another currency),
  16.2 (the forms `number:` and `kill:`, `Resolved.currency`), 16.3 (the `kill:` section rule,
  the `$` rule for a record, the snapshot test of a derivation), 16.4 (the fixed number, its
  list and units, growth from a base at or below zero, the currency rule), 16.6 (the guidance
  table's currency), 16.8 (the filing report's reuse). The method version stays 1.5: no rule of
  the valuation changes.
- The playbook: `SKILL.md`, `reference/tools.md`, `reference/citations.md`,
  `reference/report-template.md`, `reference/register.md`, as sections 7.5, 8.3, 9.6, 11 and 12
  say. Every research session must restart its MCP process after the merge.
- `docs/backlog.md`, at the end: B-99, B-161, B-167, B-103, B-105, B-142, B-117 and B-118 to
  Done, B-103's two remaining clauses and the other items of section 14 filed in new rows.

## 14. Filed, not built

- The check knows the currency of a record alone. A `$` on a foreign filer's `fact:` or
  `estimate:` figure still passes, and a refusal's detail still writes `$` on it.
- `close:` refs after a split-adjusted re-fetch, and the map of the store's refusals (B-103's
  two remaining clauses).
- The reporting currency of a record with no stored currency is the latest snapshot's, which
  says USD for a snapshot refused before its currency was read.
- A derivation of records in another currency has no unit.
- The brand book's judgment row, and its words for a news item and a work item beside the
  product's.
- A US-dollar record of a foreign filer has no derived value with the price, the value a share,
  the levels, a close or a grid's cells.
- **A question for the founder: a figure an agent sets out to construct** (section 7.6). Three
  ways the dependence rule cannot refuse, and the older one through a figure over itself. Two
  ways to go further: test every derivation, with or without a number, so that a figure over
  itself is refused too; and word a cited derivation's whole tree in the references list, so
  that a reader sees every step.
- The drawer's Kill criteria block shows neither a criterion's id nor its threshold.
- Where a company's inputs cannot be assembled, a `derive` call with a `derived:` operand whose
  tree holds an `estimate:` or a `close:` leaf answers 500 where it answered 201.
- `annual_lines` still rebuilds the year join inside `financial_tables` (B-103's row named it).
- The policy loader does not check the secondary valuation's driver range names (the
  controller's Ruling 5).

## 15. Tests the builder must write

- **The number.** Each number of the list resolves in `derive`; each refused form answers its
  400 and stores nothing of the call; two numbers are refused; the unit table of 7.2, row by
  row; a `number:` cite in a section is `unresolved reference`; the references list's words.
  The sixteen workaround shapes of section 5 still compute as they do (a figure over itself).
- **Growth and the snapshots.** `growth` and `cagr` at a base of zero and below; a derivation
  whose second operand, and one whose nested operand, rests on an older snapshot fails the
  snapshot test; one whose operands all rest on the latest passes.
- **The threshold.** A criterion with and without a threshold; a number without a unit and the
  reverse refused; `kill:` resolves by state and names nothing for another company; a `kill:`
  cite passes in section 11 of a full report and the ninth section of a valuation review and
  is an `unresolved reference` in every other; `derive` refuses a `kill:` operand; the
  references list's words; `check.CHECKS` and Appendix A's list of checks are unchanged.
- **The currency.** Migration 008 on a store with rows: every row reads as before, its currency
  the reporting currency. A currency on a figure that is not money, and a malformed code,
  refused. A US-dollar guidance record of a company that reports in another currency has no
  step; one with no currency keeps it; a US-dollar record supersedes a current record with no
  currency of the same metric, period and basis. The two rules of 9.3 and each of its three
  bullets. The check: `$` on a US-dollar record of a foreign filer passes, `$` on a record in
  the reporting currency of a foreign filer fails with the code in the detail, a US company is
  as before. The drawer's figure, Appendix A's guidance table on the page and in the export.
- **The filing report.** A usable copy older than thirty days is reused and no call is made; an
  unusable copy is not reused.
- **The debt.** One test for each built clause of 12.1.
- **Every stored report still renders**: the acceptance of section 16.

## 16. Acceptance

On a copy of the live database (SQLite's backup API), with the branch's server and no vendor
key:

1. `fairband migrate` applies 008 and nothing else; every table's row count is unchanged.
2. Every report on file answers 200 on the page's reads and the export. An export differs from
   the same report's export under main only in the "Guidance on file" table of Appendix A (the
   currency).
3. Every finding and guidance record reads with the value and unit it had and the reporting
   currency; every stored derivation reads with its value.
4. On the copy, by the routes the tools call: a `number:` derivation, a kill criterion with a
   threshold whose `kill:` ref resolves, and a US-dollar finding and guidance record on TSM that
   read back in US dollars, the guidance record with no step. The filing report's reuse is
   proved by its tests alone: without a vendor key the filing routes answer 503 before they
   read the store, and every copy on file is younger than thirty days.

The live step needs the founder's word: a backup, the merge and the push, the migration, the
server's restart from main. No revalue: nothing the engine reads changes.

## 17. Left to the builder

- The names inside the code, and where the shared currency rule lives.
- How "no window" is written for the filing report's reuse.
- How the check learns which section a cite is in.

## 18. Order of work

The number and the two `derive` faults; the migration with the currency on the three records;
the threshold and its ref; the currency in the resolver, `derive`, the check, the page and the
export; the filing report and the segments; the debt rows; the playbook; then the documents'
last read, the whole-branch review and the acceptance.

## Decision log

| Date | Decision |
|---|---|
| 2026-11-15 | The founder said "proceed" on theme 5. Claude asked four questions with advice; the founder did not follow them ("I don't understand the issue at all") and asked for the problem in simple terms, then asked "why don't we loosen the rule?". Claude: the fix loosens it at three named points and no further, since a general loosening lets an agent write any number unchecked. The founder: "yes". So: a fixed number from a list in `derive`, a threshold on a kill criterion, a currency on a finding and a guidance record, a filing report reused without a limit. |
| 2026-11-15 | Settled by Claude while writing, on a map of the code and counts from the live database, each marked *my call* above. The list of numbers. A number's unit rule. `number:` is an operand alone. A threshold is cited in one section and enters no arithmetic. A criterion with a threshold is recorded with the tool first. A currency is checked for its form alone. A record in another currency is kept out of money arithmetic until converted. The resolver learns the currency of records alone. No `peg` operation. `fmpCounted` leaves. The review log's stance is documented, not filled. Two faults of `derive` and two of the reports' code are corrected with the theme. |
| 2026-11-15 | The builder check (Opus 5.5, xhigh), one round, six questions, all settled by Claude; none was the founder's. (1) A misplaced `kill:` cite is an `unresolved reference`: a new failure word would add a row to the list of checks in every stored report's Appendix A. (2) A derivation of a record in another currency has no money unit, since a derivation carries no currency. (3) The acceptance does not read a filing report twice: the filing routes need a vendor key; the tests prove the reuse. (4) A record with no stored currency is in the currency its reader labels it with today, the latest snapshot's, or the report's own snapshot's in Appendix A. (5) The currency does not join the key by which a guidance record supersedes another. (6) The three reads answer 404 for a symbol with no snapshot. Corrected: four statements about the code. Narrowed: B-103's clause on the map of the store's refusals is filed, since `exchange_symbol`'s refusal and every store refusal would need classes of their own; the policy loader's check of tag names is left to the builder, since the engine imports the policy package. |
| 2026-11-16 | The build and its reviews. Eight tasks, subagent-driven (Opus 5.5, xhigh), each reviewed alone; then one whole-branch review, one fix wave and its re-review. **Claude's rulings during the build**, each open to the founder: (1) a percent times `number:100` keeps the unit percent, so the 100 serves the PEG and not points; (2) `charts.py` joined Task 4 so that one function writes money in another currency; (3) the wrong-unit detail of a record's cite names the record's currency; (4) the new 404 writes the symbol in its exchange form; (5) the policy loader checks the override ranges' names and not the secondary valuation's driver ranges. **The whole-branch review** found two faults in `derive`. A chosen figure passed in two derivations (a figure times `number:0`, then a number added); and the currency guard held one derivation deep (a US-dollar finding over `number:4`, then its growth over a krona revenue). Rulings (6) and (8): the dependence rule of section 7.6, hardened after the implementer broke its first form six ways and tested a repair that closes five. Rulings (7) and (9): the carried currency of section 9.3. Ruling (10): what the dependence rule cannot refuse (three deliberate constructions, and the older one through a figure over itself) is filed as one question for the founder and is not built; a cap of one number a tree would refuse an honest average of scaled cells. If any of these is wrong, the cost is one rule or one sentence, named in the build's readout. |
| 2026-11-16 | The readout. 3,463 tests; nothing under `engine/` changed; the method stays 1.5 and the policy v16; migration 008 adds five columns and rewrites no row. **The acceptance**, on a copy of the live database at refresh 63 with the branch's server and no vendor key, against main's answers: the migration applied alone (schema 7 to 8, no other count changed); 32 reports, every page read, export and report JSON 200, no fault; 28 exports differ from main's in the "Guidance on file" table alone, each with the Currency column, and 4 are equal (no guidance on file); of that table's 114 money rows USD 106, EUR 4 (ASML), DKK 4 (NVO), each the company's statements' currency; 1,022 findings, 140 guidance records and 132 kill criteria answer as main's but for the new keys; the money records answer USD 614, EUR 7, DKK 13, GBP 9, TWD 12; the 1,590 derivations read with their stored values; a tables read takes 0.03 s and an export 0.19 s at the median. Writes, on the copy alone: `number:1` less the hurdle rate is 0.91, a percent; `number:15`, two numbers, a figure times nought and a number over "a figure over itself" are refused; a figure over itself with no number is 1.0, as before; a threshold of 5% is stored and read back and a `kill:` operand is refused; a US-dollar finding on TSM answers USD, has no value with the TWD revenue, and times the rate is 1,642,950,000,000, which then combines; a US-dollar guidance record takes no step. **Not seen** in a browser: a record's currency in the drawer and in Appendix A. Closed: B-99, B-161, B-167, B-103 (nine clauses), B-105, B-142, B-117, B-118; filed: B-201, the founder's question on a figure an agent sets out to construct, and B-202. The founder gave his word for the live step on 2026-11-16 ("yes proceed"): a backup of the live database (`fairband-before-008-2026-11-16.db`), the branch merged to main with this commit, migration 008 applied, and the server restarted from main on 8470, with no revalue. Every research session must restart its MCP process, since the tools and the playbook changed. |
