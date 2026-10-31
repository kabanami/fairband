# Fairband — Data Model

**Status**: active · **Last Updated**: 2026-10-29 · **Layer**: macro
**Sources**: [map](../product-map.md), [components](components.md), design §§7–13.

One SQLite database holds the application records, history and audit trail. Records refer to immutable versions by ID. A later refresh appends evidence; it does not rewrite the basis of an earlier valuation.

Financial data is stored here, not fetched again for each screen, agent read or calculation. The local store is both the reusable source for current reads and the durable evidence behind historical valuations.

This is the durable shape. The release plan defines SQL tables, indexes and serialized field schemas.

## Core entities

| Entity | Owner | Identity and durable content | Realizes |
|---|---|---|---|
| Company; Listing | C2 | Stable company ID; dated listing/ticker aliases, exchange, share class, currency and share-unit basis. A ticker is not the primary key. | FT-001, FT-003 |
| UniverseVersion | C2 | Membership and exclusion reasons at a cutoff; policy version; exact company/listing references | FT-001, FT-009 |
| Acquisition; SourceObservation | C2 | Provider, endpoint identity without credentials, safe request parameters, retrieval time, source publication time when known, fiscal period, raw payload reference/hash, outcome and coverage | FT-002, FT-006, FT-007 |
| NormalizedFact; DataQualityFinding | C2 | Observation references, normalization version, quantity, unit, currency, period, share basis, availability time, missing reason or quality severity | FT-003–FT-005 |
| FinancialStatementVersion | C2 | Company, provider, statement kind (income, balance sheet, cash flow), annual/quarterly/semiannual basis, period start/end, publication/filing dates, observation IDs and normalized line-item facts; an amended version links to its predecessor | FT-002–FT-004 |
| AnalystEstimateSet | C2 | Provider/company, observation date, forecast periods, metric and accounting basis, values and available coverage/count metadata; a revision preserves the previous consensus snapshot | FT-002, FT-004 |
| DatasetCoverage | C2 | Provider/company or listing, dataset, safe request scope, resolved annual period window/comparison time and its selection-policy version, requested and received periods/fields, timing limitations, basis and normalization version, accepted observation IDs, last attempt, last successful check, last content change, freshness-policy version and refresh reason | FT-002, FT-005, FT-006 |
| EarningsEventObservation | C2 | Company/reporting period, source, expected date/time and timezone when supplied, date certainty (estimated/scheduled) versus separate actual-publication evidence, source/retrieval times and links to any matching dataset versions; an estimated date is never proof that new statements are available | FT-002, FT-006, FT-024 |
| SourceDocument | C2 | Source/company, document kind, SEC accession where applicable, safe original locator, publication/retrieval dates, content hash and locally stored document/text; references an acquisition and preserves corrections as versions | FT-007: the 10-K parts, the quarterly report, the earnings release and the earnings-call transcript; transcript entitlement remains AQ-14 |
| Quote; OwnershipObservation | C2 | Listing or holder identity, source/as-of/retrieval dates, units and evidence references | FT-022, FT-033, FT-039 |
| PolicyVersion | C4 | Immutable canonical content and hash; default/user provenance; source or explicit policy label per value; author and confirmation reference | FT-028, CC-06 |
| RunContext; CompanySnapshot | C4 | Exact scope/universe, fact and quote IDs, classifier cohort, peer set, policy hash, method version, normalization version, numerical environment and random seed where used | FT-025, FT-034 |
| ValuationResult; Metric | C4 | Snapshot, mechanical/reviewed basis, route and phase, structured result state, exact computed quantities, typed units, formula/input references, validity end and warnings | FT-012–FT-027, FT-051, FT-052 |
| OverrideRevision; ReviewRevision | C4 | Snapshot/base revision, tagged input path, old/new inputs, evidence and reason, lifetime, corrected-observation reference, principal, deterministic application order and bridge result | FT-026, FT-027 |
| Finding; Judgment; Note; NewsItem | C5 | Company, dated source/evidence, author, role claim, written reasoning and optional snapshot reference | FT-035, FT-037, FT-038 |
| ThesisRevision; KillCriterion | C5 | Immutable thesis revision, reasons, expected outcome and falsifying conditions; owner-confirmation reference for agent proposals | FT-053 |
| ReportRevision; NumericCitation | C5 | Mode, snapshot/review/thesis revisions, prose sections, references to server-issued facts/metrics, rendered audit and validation result | FT-036, FT-049 |
| WorkItem; WorkClaim | C5 | Company and requested scope, cause, triggering result, claim principal, state and completion evidence. Claim expiry is evaluated on access. | FT-040 |
| Watchlist; Membership; CompanyTag | C5 | User-owned names and company references; revision history of mutations | FT-032 |
| Portfolio | C6 | One record per workspace, with a stable ID and the user's versioned written strategy; the application supports one portfolio only | FT-041, FT-043, FT-054; founder decision, 2026-10-28 |
| TradeEntry; PortfolioReview | C6 | Portfolio ID; append-only reported trade or reversal, listing, quantities/currency, event date, thesis revision and confirmation; dated agent review referencing the strategy revision and its other inputs | FT-041, FT-043 |
| Job; JobItem; JobAttempt | C7 | Original request/principal, scope, idempotency key, attempts, per-item status, committed result IDs, progress and cancellation | FT-045 |
| Request; Proposal; Confirmation | C1 | Server-assigned principal, operation, payload hash, target revision, proposed changes, owner decision and consumption state | CC-07 |
| AuditEvent | C8 | Event ID, transaction/request/job correlation, principal and asserted role, time, subject revision, old/new nonsecret values or immutable references, reason and outcome | FT-046, CC-01 |
| SchemaVersion | C8 | Applied migration identities/checksums and application compatibility | FT-044 |

Input tags DATA, RULE and JUDGMENT describe provenance. A separate lifetime field describes lasting or period-tied overrides; these are different concepts.

## Relationships

```text
Company 1 ── * Listing
UniverseVersion * ── * Company
Acquisition 1 ── * SourceObservation 1 ── * NormalizedFact
FinancialStatementVersion ── SourceObservation + normalized line-item facts
DatasetCoverage ── accepted statement / estimate / quote / other dataset versions
EarningsEventObservation ── company + reporting period + optional matching versions
SourceDocument ── SourceObservation + local document/text content
RunContext 1 ── * CompanySnapshot
CompanySnapshot ── exact facts + quotes + UniverseVersion + PolicyVersion
CompanySnapshot 1 ── 1 mechanical ValuationResult
CompanySnapshot 1 ── * ReviewRevision ── * OverrideRevision
ReviewRevision ── reviewed ValuationResult + ordered bridge
ReportRevision ── CompanySnapshot + ReviewRevision? + ThesisRevision?
NumericCitation ── an exact SourceObservation / NormalizedFact / Metric
Workspace 1 ── 1 Portfolio ── * TradeEntry / PortfolioReview
TradeEntry ── Portfolio + Listing + ThesisRevision + Confirmation?
Proposal ── exact payload + target revision ── Confirmation
Job 1 ── * JobItem ── committed record IDs
AuditEvent ── transaction + subject revision + originating principal
```

The question marks mean a reference can be absent with a recorded reason, subject to the Feature's release contract. They do not waive the map's required thesis citation on a trade. The release must define behavior when importing or recording a trade for which no thesis exists (AQ-7).

## Stored financial data and reuse

Keep both the original nonsecret response and the normalized values used by Fairband. A financial statement's line items are `NormalizedFact` records grouped by `FinancialStatementVersion`; they are not embedded only in a valuation result. Examples are revenue, operating income, cash, debt, diluted shares, operating cash flow and capital expenditure. Prices, consensus estimates, segments, peers and vendor scores have their own dated dataset versions. C3 computes derived metrics from those stored inputs.

The logical names above do not mandate one physical table per entity or a generic key/value table for all queries. The release pins typed tables, constraints and indexes for company/provider, statement kind, period, metric, version and availability time. Repeated ticker/period reads must resolve locally without reparsing a vendor response or making a network call.

Reuse is scoped by provider, dataset, company/listing, requested periods/fields and compatible units/normalization. Prefer FMP for each financial dataset; record the required-data gap when GuruFocus is selected as a supplementary source. If data mapping confirms FMP covers every required input, drop GuruFocus; the model does not require paired FMP/GuruFocus records. A cached annual series cannot satisfy a quarterly request; partial coverage cannot count as complete; a different vendor's definitions cannot silently fill holes. Company data is shared across the screen, research, valuations and the single portfolio. The portfolio does not hold another copy of a company's financials.

`DatasetCoverage` is a mutable summary over immutable evidence. It distinguishes when the app last tried, last successfully checked the provider, and last received changed content. A check returning unchanged data updates check metadata, while preserving the original source dates and observation versions. Identical payload content can be stored once and referenced by subsequent acquisitions. Failed checks do not advance the last-success marker.

## Reads, freshness and requested refresh

Ordinary web/MCP reads and valuations use stored records. If required data is absent, unusable or too old for the requested operation, return the coverage/freshness reason and required refresh action. An explicit refresh, or an explicit combined refresh-and-value request, authorizes C2 to contact sources; opening a company page alone does not.

1. Resolve local coverage for the requested scope and dataset. Reuse data that satisfies the request's declared freshness policy. An explicit request to recheck a source bypasses that reuse decision for its chosen scope.
2. When a check is needed, use provider change metadata, a filing identity or conditional request where supported. This check can itself consume an API call. Where no change signal exists, re-fetch the bounded series needed to check for updates; do not assume every provider supports incremental retrieval.
3. A newly confirmed earnings announcement marks the relevant financial/estimate datasets as needing a check. An estimated or scheduled date becoming due is only a reason to check. After the relevant expected date has passed, a missing annual period without publication proof is `expected-update-missing`; the reader sees “Expected update not yet available”. Actual publication evidence with that period still missing is `awaiting-source-update`; the reader sees “Company has reported; awaiting vendor data”. A confirmed schedule is not confirmed publication. Announcement, formal filing and vendor availability are separate events. Both outcomes retain the fiscal period, date certainty and dated source evidence. Within an explicit refresh, an absent period now supported as due/published invalidates ordinary reuse of affected statements. Waiting requires a successful affected-statement check in the logical operation, including a preserved matching check after retry; new evidence cannot be claimed checked by an incompatible old checkpoint. Unrelated required field/period gaps take precedence as partial. Unknown period/time basis cannot establish an overdue report; planning pins the comparison rule. Neither time passing nor reading the status starts a vendor request, and HTTP success alone does not establish current coverage.
R1 selects ten consecutive annual fiscal periods under a versioned acquisition policy, ending at the latest supported reported or due completed period. Already reported periods need no historical calendar dates. Future reports are context rather than gaps. Successful but unavailable next-report timing remains a visible limitation alongside the latest reported period, never proof of currentness; actual lookup failures retain failure semantics. A well-formed correct-company lookup with no matching usable annual event is successful with a timing limitation and updated last-successful-check; transport/access/identity/shape failures do not advance that marker. The operation persists the resolved window and retry preserves it. If new evidence invalidates its frozen basis during retry, return partial with a new-refresh-needed reason, retaining both evidence versions; the future-period exclusion applies when a new operation resolves a window. Show unobserved intervening completed periods even if the latest completed period has a future expected date, with due evidence or an explicit timing/currentness limitation. Validated actual annual metadata from one statement type can establish that period was reported for the other types; a separate calendar publication flag is not required.

4. Fetch affected datasets, validate coverage and basis, then publish accepted versions and their audit records. Coalesce concurrent requests for the same acquisition scope, and reuse committed work within a job. In R1, equivalent active requests by the same Owner (same company/provider/datasets/selection policy and reuse mode) attach to one operation/job with each request ID/origin retained. Different scopes/modes do not merge; new requests after completion create new operations. Independent dataset failures remain visible and cannot create an apparently complete mixed snapshot.
5. Preserve prior versions and any results that cite them. Changed financials mark dependent current projections as needing reassessment; refresh does not recalculate a value or renew a review by itself.

R1 job progress has four items: income statements, balance sheets, cash-flow statements and the earnings observation. Finished counts include recorded terminal item outcomes, not only complete data. At normal completion, failed data outcome yields a failed job; the other six outcomes, including partial and waiting, yield done. Execution failure can fail a job after some publications committed; no completed overall data outcome is claimed, only execution failure and retained item evidence. Requested/running jobs are active; restart marks both interrupted even before an attempt exists. New requests after failure/interruption create new operations; retry of the old one is refused while an equivalent job is active. Failed/interrupted operations permit retry, including normally finished all-failed attempts. Retry preserves successful checkpoints/publications and reruns failed/superseded or unfinished steps; progress is per attempt, so failed items reset to pending while retained successful items count once. A stale-version conflict is superseded, aggregated like an item failure, not a successful unchanged check. Done/cancelled operations refuse retry and point to a new refresh; all committed work remains intact.

Financial statements also change through amendments, restatements and vendor corrections. Prices, estimates and corporate-action/share-basis data can change between earnings releases. Each dataset therefore has its own versioned freshness/check policy, pinned with FT-002/FT-006 (AQ-13), rather than one expiry time for all data. Bounded retries can run within the original requested job. After that job ends, a pending vendor update requires a new request; no unattended polling or automatic earnings-triggered refresh is introduced.

Refreshing current data never deletes evidence referenced by a snapshot, report or audit record. Retention of other raw content is a release policy, with coverage effects visible. Rebuilding normalized facts from retained raw data can use the local store and a new normalization version without another vendor call.

## Single portfolio

The founder chose **one portfolio only** on 2026-10-28. Its ledger produces positions, cash and market value; its reviews cite the user's strategy as it stood at review time. Application operations resolve that one portfolio. Multiple named watchlists remain company selections, without separate cash or trade ledgers. Additional portfolios would be a later product decision.

## Snapshot and historical access

The three displayed dates are labels, not the storage key. A reproducible calculation also needs the original universe for growth deciles, peer set for a default margin, exact policy content, method code version and all input revisions. A changed policy file cannot change an old snapshot.

Store both the period a fact describes and when that version became available. Historical access must exclude subsequently published or restated information. Retrieval time is the conservative availability bound when no reliable earlier timestamp exists. Ten years of today's restated financial history does not prove ten years of point-in-time coverage. FT-004 refuses unsupported historical cutoffs with a coverage reason; it does not manufacture old estimate or universe versions.

## Current value and expiry

C4 returns one selected-result reference with a `mechanical` or `reviewed` label and the mechanical baseline alongside it. The selected result's value, levels, stance, expected return and flags come from the same compatible input context. The view cannot mix a reviewed value with mechanical return or stance fields.

A valid reviewed result is preferred. Otherwise the mechanical result is shown with its own validity state; an expired result remains visible as expired. A request for an updated valuation makes a fresh baseline without overrides. Old reviews and lasting judgments remain historical evidence for reassessment; they do not acquire a new validity window by being copied. The refreshed review is a new revision.

A price refresh may create a new dated price-relative projection without changing the old intrinsic-value result or report. Both the valuation price and current quote remain identifiable. Exact invalidation on policy changes is pinned at FT-028/FT-024 planning (AQ-6).

## Atomic writes and ownership

Each acknowledged durable mutation commits its subject records, provenance and audit event in one transaction (INV-8). A rejected request has no applied business mutation; its safe refusal audit records the attempt. Engine calculation and network calls run outside write transactions. Publication then compares the expected input revision before committing; a concurrent change produces a conflict or a superseded result, never a silent overwrite.

Corrections append new observations, override revisions, thesis/report revisions or reversing trade rows. Mutable indexes and current-state pointers are projections, not the historical source. A migration may change physical representation only while preserving logical history and references.

Raw vendor payloads, when retained, are private database blobs or private local content-addressed objects. The first implementation uses database storage unless payload size measurements justify a separate blob adapter (AQ-4). No vendor payload or proprietary source excerpt enters version control. API keys never enter these domain records; key changes audit only the credential slot and success/failure, not old/new secret bytes.

## Numeric and missing-data rules

- Preserve source precision and explicit units; round only for presentation. Money in the trade ledger uses exact decimal representation. The valuation kernel's numerical representation and tolerance are pinned with its method/environment version.
- Distinguish missing, refused, failed and not applicable. None is silently converted to zero.
- Keep company economic shares separate from listed-share or ADR units. Normalized prices and per-share results must name compatible units.
- Derived report numbers reference engine-issued metrics. An agent may submit a sourced input for validation; it cannot label its own calculated result as a tool-computed metric.

The constitution-bound data properties are INV-1, INV-2, INV-8, INV-9 and INV-10 in [standards](standards.md). Performance indexes and retention limits remain release refinements, not new business rules.
