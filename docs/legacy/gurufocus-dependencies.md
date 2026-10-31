# GuruFocus dependencies and replacement options

**Decision date:** 2026-10-30 · **Authority:** founder · **Replacement review:** deferred; no date or release assigned

## Decision

Use **FMP as the primary financial-data vendor and GuruFocus for the verified gaps**. Proceed with the current release. Revisit reducing the vendor requirements later; that investigation is not a prerequisite for Release 1 tasks, implementation or acceptance.

This confirms the existing source assignments. The GuruFocus moat default remains in force. The proposed moat replacement, locally calculated scores and suggestions to make research inputs optional are proposals, not adopted changes. Both credentials are required for a new live Release 1 identity check; stored reads and qualifying reuse follow the existing credential rules.

Using both vendors does not mean they supply every required input. The [completed source map](../product/releases/1/input-source-map.md) retains explicit gaps and company/public-source requirements. Its **neither sufficient for the full input set** finding remains valid; the selected vendor pair and full data completeness are different questions.

## Key fields assigned to GuruFocus

Paths below were inspected in authenticated responses. Modern profile paths and legacy summary paths are different schemas. These are field names, not a claim of coverage for every company. Retain the requested listing, source identity, observation date and metric definition with each observation.

| Required input | GuruFocus response fields | Current use | Possible replacement and remaining work |
|---|---|---|---|
| Security classification | Modern profile: `general.type`, `general.class_descpt` | **Release 1.** Establish ordinary/common equity and exclude preferred or unsupported instruments. The tested FMP generic stock labels/flags did not distinguish common and preferred shares reliably. | Verify another FMP classification route, or use authoritative exchange/issuer evidence. Demonstrate exact listing joins and common/preferred/other cases before removing GF. An unknown type stays unsupported; a ticker-name heuristic is insufficient. |
| Moat score | Legacy summary: `summary.company_data.moat_score` | **Later valuation routes.** Seed Wide/Narrow/None under the accepted design; the class affects growth duration, terminal return on invested capital (ROIC), and margin of safety. | Investigate the founder's reinvestment-adjusted financial-record rule below. An evidenced agent/user judgment is another possible source, but does not by itself replace the automatic default. No equivalent FMP moat score was established. |
| Altman Z″ | Legacy summary: `summary.company_data.z2score` | **Later Decline route and research.** The specified financial-distress indicator; distinct from the selected distance-to-default probability model. | Calculate the published Z″ formula from FMP statement inputs after validating definitions, period alignment, preferred-equity treatment, signs and missingness. FMP's generic Altman Z is not interchangeable with Z″ or its thresholds. No equivalent local calculation has been validated yet. |
| Beneish M-score | Legacy summary: `summary.company_data.mscore`; modern profile: `fundamental.mscore`; key ratios: `Fundamental["Beneish M-Score"]` | **Later company research.** An accounting-manipulation warning indicator, not a finding of fraud. | Investigate computing the published model from FMP statements, including the necessary consecutive-year components. Alternatively propose making this research item optional. Neither the calculation nor the scope reduction is approved. Piotroski measures a different property and is not a replacement. |
| Current ADR conversion ratio | Legacy summary: `summary.company_data.depositary_receipt_ratio` | **Later foreign-filer/share-basis handling.** Ordinary shares represented by one American depositary receipt (ADR). Release 1 excludes ADRs. | Issuer/depositary disclosures supplied corroborating examples. Validate conversion direction, share class and effective dates. GF's inspected current ratio does not supply historical ratio changes; FMP's price/share adjustments alone did not establish every earnings/share basis. |

Evidence: [security classification](../product/releases/1/source-evidence.md#ds-01--eligibility-before-statement-acquisition), [foreign issuer/share-basis checks](../product/releases/1/source-evidence.md#ds-01030818--foreign-issuer-samples), and [exact score definitions](../product/releases/1/source-evidence.md#ds-1314--exact-vendor-score-definitions). The source-data contract remains the binding [Release 1 acquisition specification](../product/releases/1/spec/contracts/source-data.md).

## Guru holdings: a separate research dependency

For FT-033/FT-039, the inspected modern stock guru-holdings response supplies these fields on each record:

| Fields | Meaning needed by Fairband |
|---|---|
| `guru_id`, `guru_name` | Holder identity |
| `current_shares` | Reported shares held |
| `portdate` | Portfolio reporting date |
| `action`, `change` | Reported position change/action, not evidence of an executed trade date |

The inspected guru portfolio response also supplies `13F[].holdings[]` with `symbol`, `exchange`, `stockid`, `shares`, `share_change`, `action`, `change` and `portdate`. These are supplementary research fields, not Release 1 runtime requirements.

GF covers selected gurus, not all institutions. The checked payloads lack a separate filing-date field. A portfolio date or a change between reporting periods cannot stand in for publication or actual transaction timing. See [DS-28](../product/releases/1/input-source-map.md).

Possible replacements are FMP institutional holdings where account access and coverage are verified, or primary filings with an explicitly defined holder list and filing dates. FMP insider transactions are useful but describe a different population. Deferring guru research was discussed as a simplification; the founder has **not** approved removing that capability. The tested FMP institutional endpoint refused the current account, so no working equivalent is claimed.

## Proposed moat replacement retained for later review

The founder supplied a deterministic rule using FMP annual statements. Its ten-company results are preliminary, founder-supplied evidence; they were not independently reproduced in this review. No vendor observations or company result table are stored here.

The proposed calculation would:

1. Use fifteen annual observations to seed a ten-year evaluation window. Capitalize 100% of research and development spending over five years and 30% of selling, general and administrative spending over three years, both on a straight-line schedule. Add investment less amortization to net operating profit after tax (NOPAT), and the unamortized asset to invested capital.
2. Divide adjusted profit by beginning-of-year adjusted invested capital, flooring operating working capital at zero.
3. Estimate growth capital expenditure (CapEx) as the trailing five-year average net property, plant and equipment/revenue ratio multiplied by the positive part of the year's revenue increase. Maintenance CapEx is total CapEx less that estimate; maintenance free cash flow is operating cash flow less maintenance CapEx. The exact averaging window still needs pinning.
4. Assign the classes below. Gross profit/assets and gross-margin variability would provide companion evidence for agent review.

| Proposed class | Proposed conditions |
|---|---|
| Wide | Both ten-year aggregate and median adjusted ROIC above 14%; positive adjusted NOPAT in all ten years; positive maintenance free cash flow in at least nine years. |
| Narrow | Ten-year **or** five-year median adjusted ROIC above 9%; positive adjusted NOPAT in at least eight of ten years; positive maintenance free cash flow in at least seven. |
| None | The proposal assigns None when neither set passes. Missing or insufficient evidence needs a separate disposition before adoption. |

These are **unadopted candidate assumptions and thresholds**. The cited literature supports investigating intangible investment and persistent returns; it does not establish this combined classifier or its accuracy. Any adopted policy values need explicit provenance, a version and validation.

The review identified these unresolved issues:

- **Expense meaning and overlap.** Confirm that an FMP R&D field represents eligible research spending. Amazon's technology/infrastructure line includes depreciation, rent, utilities and operating costs; capitalizing the whole line could capitalize routine costs and count existing assets twice. Exclude R&D already included in SG&A before applying another capitalization adjustment. Reconcile acquired intangibles and the tax treatment too.
- **Useful lives are assumptions.** A universal five-/three-year schedule needs justification and sensitivity analysis. Damodaran varies research lives by business; Mauboussin's Microsoft example uses different spending allocations and lives.
- **Capital timing and supplier financing.** Beginning balances would change the founder's approved average-opening/closing convention in [D2](../product/releases/1/spec/research.md#d2--capital-timing-for-ten-year-roic). Flooring working capital removes real supplier/customer financing. Preserve the approved cash, lease and tax conventions unless separately changed.
- **Maintenance spending is estimated.** Price increases, acquisitions and spare capacity can grow revenue without the implied new equipment. The proposed equation can produce negative maintenance CapEx; falling revenue does not prove all spending is maintenance. Define these cases and the gross/net asset choice. Reclassifying investment does not create additional cash available while that investment continues.
- **Historical strength versus durability.** A ten-year record does not establish another twenty years of competitive advantage. The Narrow rule's ten-year **or** five-year condition can retain a class despite recent deterioration. Keep the classification benchmark distinct from changes in a user's personal hurdle; 9% is a chosen benchmark, not an observed company cost of capital.
- **Validation and coverage.** Check the scripts, source lines and dates; the supplied Micron explanation mentioned 2026 despite a stated 2016–2025 window. Verify fifteen-year account/field coverage rather than infer it from plan advertising. Test companies outside the original sample, younger firms, cycles and sensitivity to assumptions; insufficient history is not proof of no moat.

Public references reviewed: [Damodaran on research assets](https://pages.stern.nyu.edu/adamodar/New_Home_Page/AccPrimer/research.htm), [Mauboussin and Callahan, Return on Invested Capital, pp. 18–20](https://www.morganstanley.com/im/publication/insights/articles/article_returnoninvestedcapital.pdf), [Measuring the Moat](https://www.morganstanley.com/im/publication/insights/articles/article_measuringthemoat.pdf), and [Amazon's annual report](https://www.ezodproxy.com/amazon/2026/proxy/images/Amazon_AR2025.pdf). The proposal also cites Peters–Taylor and Greenwald; their names alone do not validate every parameter or implementation choice above.

## Inputs that should not be mistaken for reasons to require GF

- **Piotroski F-score:** FMP supplies it; this is not a GF-specific gap.
- **Discount-rate WACC:** not required under the founder's retained user-hurdle design. Independently needed interest-rate observations remain in the source map.
- **EPS without non-recurring items:** GF's field does not establish the full accepted earnings reconciliation or forecast share basis. Both providers retain these limitations.
- **Historical leases and capital:** the checked GF responses do not fill all missing lease contexts, rates or acquired-intangible details. Company notes may be needed.
- **Public reference inputs:** country tax benchmarks, survival tables and the accepted growth-base-rate statistics come from separate public sources. Company guidance, asset-sale evidence and filings also require source evidence beyond generic statement fields.
- **Transcripts and broader institutional holdings:** tested FMP account refusals are entitlement findings, not proof the vendor lacks the products. No complete GF replacement was established.

## When the review is reopened

The founder will choose when to revisit this. There is no new release gate or scheduled work. Start from this inventory and the source map, verify replacements at the field/definition/history/access level, and distinguish **one paid vendor plus public/company sources** from **FMP as the source of every input**. The former is a possible simplification; the latter has not been demonstrated.

A future decision to remove GF, replace the moat default or make a required research item optional goes through `sprokit-process-change`. Until then, implement the selected FMP/GF responsibilities and preserve explicit gaps.
