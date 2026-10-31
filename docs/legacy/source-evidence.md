# Release 1 — Source evidence

**Status**: Phase 0 source investigation complete, 2026-10-29, with explicit capability blockers.

**Verdict: neither the inspected vendor feeds nor the current accounts supply the full required set.** FMP supplies the sampled statement histories and supporting datasets; GuruFocus fills identified security-class and score gaps. Missing reconciliation/context/history metadata and tested endpoint-entitlement refusals leave the capability blockers listed in the [completed coverage table](input-source-map.md). This is a bounded evidence conclusion, not universal absence from vendors or issuer documents. R1 uses FMP statements/earnings plus GuruFocus modern identity. Founder source decisions D2–D9 are closed; the investigated WACC alternative below remains history.

## Probe discipline

New investigation code reads credentials in-process from the private files referenced by stocks. FMP receives its key only at financialmodelingprep.com over HTTPS; GuruFocus receives its own key only at api.gurufocus.com over HTTPS. Redirects are refused. No key is in command arguments or this record. Raw responses and a detailed metadata manifest remain under ignored `data/planning/`. Checked-in rows contain safe source identifiers, sample scope and conclusions, never financial payloads.

All requests below ran on 2026-10-29 UTC. Historical stocks notes identify an earlier FMP Premium account, but current plan names were not independently verified; actual access is recorded per endpoint. No purchase or account change was made.

## Authenticated samples

| Evidence | Provider / endpoint | Sample parameters | Result | What it proves / limit |
|---|---|---|---|---|
| P01 | FMP `profile` | symbol=AAPL | HTTP 200 | 1 records returned; sampled access only. |
| P02 | FMP `income-statement` | symbol=AAPL, period=annual, limit=12 | HTTP 200 | 12 actual FY-labelled dates, 2014-09-27 through 2025-09-27; definition/field completeness separate. |
| P03 | FMP `balance-sheet-statement` | symbol=AAPL, period=annual, limit=12 | HTTP 200 | 12 actual FY-labelled dates, 2014-09-27 through 2025-09-27; definition/field completeness separate. |
| P04 | FMP `cash-flow-statement` | symbol=AAPL, period=annual, limit=12 | HTTP 200 | 12 actual FY-labelled dates, 2014-09-27 through 2025-09-27; definition/field completeness separate. |
| P05 | FMP `earnings` | symbol=AAPL, limit=12 | HTTP 200 | Event dates and actual/estimated values returned; no fiscal-period identifier in this response. |
| P06 | FMP `income-statement-as-reported` | symbol=AAPL, period=annual, limit=12 | HTTP 200 | 12 actual FY-labelled dates, 2014-09-27 through 2025-09-27; definition/field completeness separate. |
| P07 | FMP `cash-flow-statement-as-reported` | symbol=AAPL, period=annual, limit=12 | HTTP 200 | 12 actual FY-labelled dates, 2014-09-27 through 2025-09-27; definition/field completeness separate. |
| P08 | FMP `balance-sheet-statement-as-reported` | symbol=AAPL, period=annual, limit=12 | HTTP 200 | 12 actual FY-labelled dates, 2014-09-27 through 2025-09-27; definition/field completeness separate. |
| P09 | FMP `analyst-estimates` | symbol=AAPL, period=annual, limit=12 | HTTP 200 | 12 records returned; sampled access only. |
| P10 | FMP `analyst-estimates` | symbol=AAPL, period=quarter, limit=12 | HTTP 200 | 12 records returned; sampled access only. |
| P11 | FMP `stock-peers` | symbol=AAPL | HTTP 200 | 10 records returned; sampled access only. |
| P12 | FMP `financial-scores` | symbol=AAPL | HTTP 200 | 1 records returned; sampled access only. |
| P13 | FMP `revenue-product-segmentation` | symbol=AAPL, period=annual | HTTP 200 | 16 actual FY-labelled dates, 2010-09-25 through 2025-09-27; definition/field completeness separate. |
| P14 | FMP `revenue-geographic-segmentation` | symbol=AAPL, period=annual | HTTP 200 | 16 actual FY-labelled dates, 2010-09-25 through 2025-09-27; definition/field completeness separate. |
| P15 | FMP `historical-price-eod/full` | symbol=AAPL, from=2026-10-01, to=2026-10-28 | HTTP 200 | 20 records returned; sampled access only. |
| P16 | FMP `income-statement` | symbol=MSFT, period=annual, limit=12 | HTTP 200 | 12 actual FY-labelled dates, 2015-06-30 through 2026-06-30; definition/field completeness separate. |
| P17 | FMP `balance-sheet-statement` | symbol=MSFT, period=annual, limit=12 | HTTP 200 | 12 actual FY-labelled dates, 2015-06-30 through 2026-06-30; definition/field completeness separate. |
| P18 | FMP `cash-flow-statement` | symbol=MSFT, period=annual, limit=12 | HTTP 200 | 12 actual FY-labelled dates, 2015-06-30 through 2026-06-30; definition/field completeness separate. |
| P19 | FMP `earnings-call-transcript` | symbol=AAPL, year=2025, quarter=4 | HTTP 404 | Operator typo; not an official endpoint. Excluded from coverage/access conclusions. |
| P20 | FMP `earning-call-transcript` | symbol=AAPL, year=2025, quarter=4 | HTTP 402 | Correct documented transcript route denied access. Dataset absence is not established. |
| P21 | GuruFocus `stock/AAPL/summary` | none | HTTP 200 | Nonempty moat_score and z2score present; current observed fields, without an asserted original publication timestamp or universal company coverage. |
| P22 | GuruFocus `stock/AAPL/keyratios` | none | HTTP 200 | Quality and EPS-without-NRI field families returned; presence is not equivalence to Fairband normalization. |
| P23 | GuruFocus `stock/AAPL/financials` | none | HTTP 200 | AAPL includes nine actual fiscal years plus a separate TTM label, and 38 quarters. TTM does not supply the tenth annual year. |
| P24 | GuruFocus `stock/MSFT/keyratios` | none | HTTP 200 | Quality and EPS-without-NRI field families returned; presence is not equivalence to Fairband normalization. |
| P25 | GuruFocus `stock/AAPL/analyst_estimate` | none | HTTP 200 | Five annual and eight quarterly estimate slots; future coverage and missing basis/vintage metadata are resolved in DS-08/10/11 below. |
| P26 | GuruFocus `calendar` | date=2026-10-29, type=earnings | HTTP 200 | 564 earnings events with EventFiscalYear and Event. Evaluated alternative; R1 selects the verified FMP optional-period path below. |

## R1 statement field binding

These rows record the inspected FMP schema. The [normative release binding table](spec/contracts/source-data.md#binding-table-normative) pins exact runtime selection and gap rules for every catalog ID, including the narrower statement-specific supplements. The sample check counts non-null fields across twelve AAPL annual responses, not their accounting accuracy. Values of zero require source interpretation; non-null is not proof that a vendor did not default a missing observation. Annual periods, currency, identity and source metadata are validated separately.

Income definitions: [FMP income schema](https://site.financialmodelingprep.com/developer/docs/stable/income-statement) and [field guide](https://site.financialmodelingprep.com/how-to/fundamentals-at-your-fingertips-fmp-income-statement-api-essentials). Balance definitions: [FMP balance schema](https://site.financialmodelingprep.com/developer/docs/stable/balance-sheet-statement). Cash-flow definitions: [FMP cash-flow schema](https://site.financialmodelingprep.com/developer/docs/stable/cashflow-statement). Provider field identifiers below were also observed directly in P02–P04.

| ID | Requested observation | Inspected field / basis | Non-null AAPL periods | Finding / retained basis limitation |
|---|---|---|---|---|
| IS-01 | Revenue | `revenue` | 12/12 | Reported revenue; preserve statement currency and annual basis. |
| IS-02 | Gross profit | `grossProfit` | 12/12 | Provider-normalized gross profit; retain its documented derivation/reporting basis, without claiming an issuer-reported line or recomputing a gap in Fairband. |
| IS-03 | Operating income | `operatingIncome` | 12/12 | Keep separate from EBIT and pretax earnings. |
| IS-04 | Interest expense | `interestExpense` | 12/12 | Retain the source sign and distinguish netInterestIncome; no per-fact issuer gross/net-presentation annotation is supplied. |
| IS-05 | EBITDA | `ebitda` | 12/12 | Provider-derived: FMP documents net income + D&A + tax expense + interest expense; not issuer-reported EBITDA. |
| IS-06 | Pretax income | `incomeBeforeTax` | 12/12 | Do not confuse with operating income. |
| IS-07 | Income-tax expense | `incomeTaxExpense` | 12/12 | Reported expense; not automatically the statutory marginal rate. |
| IS-08 | Net income | `netIncome` | 12/12 | The checked contract does not supply a complete common/preferred/noncontrolling attribution reconciliation; do not relabel it common-shareholder earnings. |
| IS-09 | Basic EPS | `eps` | 12/12 | Basic period EPS; the response omits per-fact original/current split and listing-unit metadata. See DS-08 limitations. |
| IS-10 | Diluted EPS | `epsDiluted` | 12/12 | Diluted period EPS; the response omits per-fact split/listing-unit metadata. See DS-08 limitations. |
| IS-11 | Weighted-average basic shares | `weightedAverageShsOut` | 12/12 | Period average, not current shares. |
| IS-12 | Weighted-average diluted shares | `weightedAverageShsOutDil` | 12/12 | Period average diluted basis. |
| BS-01 | Cash/equivalents | `cashAndCashEquivalents` | 12/12 | Separate from short-term investments. |
| BS-02 | Short-term investments | `shortTermInvestments` | 12/12 | Do not silently add to cash field. |
| BS-03 | Accounts receivable | `accountsReceivables` | 12/12 | Use narrower accounts field; netReceivables also includes other receivables. |
| BS-04 | Inventory | `inventory` | 12/12 | Reported inventory. |
| BS-05 | Current assets | `totalCurrentAssets` | 12/12 | Reported total; operating-capital exclusions happen later. |
| BS-06 | Accounts payable | `accountPayables` | 12/12 | Do not equate total payables with accounts payable. |
| BS-07 | Current liabilities | `totalCurrentLiabilities` | 12/12 | Reported total; later capital calculation excludes financing items. |
| BS-08 | Net property/plant/equipment | `propertyPlantEquipmentNet` | 12/12 | The normalized field lacks a per-fact operating/finance-lease inclusion annotation; detailed evidence below is required for capital normalization. |
| BS-09 | Goodwill | `goodwill` | 12/12 | Separate goodwill from acquired intangibles. |
| BS-10 | Acquired intangible assets | `intangibleAssets` | 12/12 | Generic intangibles are not an acquired-only classification; that metadata is absent from the checked normalized field. |
| BS-11 | Current debt | `shortTermDebt` | 12/12 | Current-debt observation; the response does not fully identify the constituent borrowings/maturities/leases. Do not replace it with all current liabilities. |
| BS-12 | Noncurrent debt | `longTermDebt` | 12/12 | Noncurrent-debt observation; complete lease inclusion/context is not encoded in this normalized field. |
| BS-13 | Total assets | `totalAssets` | 12/12 | Reported balance-sheet total. |
| BS-14 | Total liabilities | `totalLiabilities` | 12/12 | Reported balance-sheet total. |
| BS-15 | Equity | `totalStockholdersEquity` | 12/12 | Distinguish parent-stockholder equity, common equity and totalEquity including minority interests. |
| BS-16 | Retained earnings | `retainedEarnings` | 12/12 | Reported retained earnings. |
| CF-01 | Depreciation/amortization | `depreciationAndAmortization` | 12/12 | Combined amount; does not establish acquired-intangible amortization separately. |
| CF-02 | Operating cash flow | `netCashProvidedByOperatingActivities` | 12/12 | Signed reported flow. |
| CF-03 | Investing cash flow | `netCashProvidedByInvestingActivities` | 12/12 | Signed reported flow. |
| CF-04 | Financing cash flow | `netCashProvidedByFinancingActivities` | 12/12 | Signed reported flow. |
| CF-05 | Capital expenditure | `capitalExpenditure` | 12/12 | Preserve vendor outflow sign; no arbitrary absolute-value transformation. |
| CF-06 | Stock compensation | `stockBasedCompensation` | 12/12 | Cash-flow adjustment amount, not necessarily all SBC expense definitions. |
| CF-07 | Acquisition cash outflows | inspected `acquisitionsNet`; runtime `data.paymentstoacquirebusinessesnetofcashacquired` under Rule A | 12/12 | Retain the evidenced cash-flow basis, including cash acquired. A line also combining disposal proceeds or other asset purchases cannot silently become a separate acquisition outflow. The spec does not require gross purchase price before acquired cash. |
| CF-08 | Disposal cash proceeds | `—` | not bound | No exact normalized field established; otherInvestingActivities is not a substitute. |
| CF-09 | Equity issuance proceeds | `commonStockIssuance` | 12/12 | Common-stock basis; no claim that all equity instruments are included. |
| CF-10 | Equity repurchase outflows | `commonStockRepurchased` | 12/12 | Common-stock basis and outflow sign retained. |
| CF-11 | Debt issuance proceeds | as-reported `proceedsfromissuanceoflongtermdebt` where present | per-year coverage below | Issuer proceeds, including a disclosed net-of-issuance-costs basis, are usable with that basis. netDebtIssuance offsets repayments and is not separate proceeds. No requirement for undisclosed gross commercial-paper turnover is added. |
| CF-12 | Debt repayment outflows | `data.repaymentsoflongtermdebt` under Rule A | per-year coverage below | Net debt issuance is not repayments. As-reported long-term repayment exists in the sample. |
| CF-13 | Dividends paid | `netDividendsPaid` | 12/12 | Retain the source sign and separately offered common/preferred components; do not silently relabel a total as common dividends. |

The [FMP parsing methodology](https://site.financialmodelingprep.com/developer/docs/parsing-statements) establishes its EBITDA derivation. P06–P08 as-reported responses contain nested issuer tags. The cash-flow sample includes `proceedsfromissuanceoflongtermdebt`, `repaymentsoflongtermdebt`, `paymentstoacquirebusinessesnetofcashacquired` and net commercial-paper flows. This narrows the binding search; it does not justify decomposing net flows or imply those tags exist for all years/companies.

## Consolidated disposition

The [30-family coverage table](input-source-map.md#completed-coverage-table) is the current source assignment and history requirement. The endpoint log above records the investigation sequence; later detailed sections below supersede early sample limitations. Successful HTTP status, field presence or a current period label alone does not prove normalized usability or historical availability.

| Demonstrated limitation | Evidence boundary | Affected capability |
|---|---|---|
| Accepted earnings/forecast reconciliation absent from checked estimate feeds | No constituent exclusions, SBC/amortization reconciliation or forecast-share denominator; GF EPS-without-NRI is not an equivalent definition. Primary issuer documents may resolve individual inputs. | FT-012/013/022; DS-07/08/10/11 |
| Capital/lease context and historical-rate gaps | Flat as-reported facts lack contexts/dimensions; identified historical company/year rate gaps and GF lease nulls remain. Generic acquired-intangible and capital components cannot certify the normalized capital definition. | FT-012/014/015/016/018; DS-05/07/26/27 |
| Historical unit and availability metadata absent | Current ADR ratios are not ratio histories; normalized filing dates may be period placeholders; estimates lack an observation-vintage archive. | FT-003/004/022; DS-03/08 |
| Tested document/holder access restrictions | Correct FMP transcript/institutional routes return 402; checked GF routes do not provide complete replacements. Issuer transcript retrieval is verified for Microsoft, not every company. | FT-007/033/039; DS-28/30 |
| Public-source applicability limits | BLS establishment-to-issuer mapping, creditor versus asset recovery, 2015-dollar sales classes and OECD country/year gaps remain explicit conditions. | DS-09/21/23/24 and their route consumers |

These limitations support **neither inspected feeds/current accounts sufficient**. The finding completes AQ-11/RA-01's investigation, while leaving the affected capabilities blocked wherever the required evidence is absent. It does not waive R1 acceptance or convert untested populations into dataset-absence claims. Source-defined acquisition cash flows net of acquired cash and issuance proceeds net of issuance costs remain valid observations; no extra gross-purchase-price or commercial-paper-turnover requirement is imposed.

## DS-19 correction — optional FMP fields, 2026-10-29

The initial default-response finding above is superseded for runtime design. A further live probe with `includeReportTimes=true` returned `confirmed`, `fiscalPeriod`, `fiscalYear`, `periodEnding` and `time` for AAPL and MSFT. FMP documents this option in its [2026-06-05 changelog](https://site.financialmodelingprep.com/developer/docs/changelog) and [version/optional-field explanation](https://site.financialmodelingprep.com/insights/platform/why-fmp-examples-may-show-different-api-versions-and-which-docs-to-use). The old FAQ/default schema alone was an incomplete investigation.

Scripts matched five sampled final-quarter events exactly to annual statement period ends: AAPL FY2024–2025 and MSFT FY2024–2026. Require company, fiscal-year, final-quarter and period-end agreement; an unrelated quarterly event or an inferred anniversary cannot establish the annual period. The optional `confirmed` field supplies schedule certainty, not proof of publication.

The live NASDAQ exchange-hours response supplies `America/New_York`. [Exchange-hours documentation](https://site.financialmodelingprep.com/developer/docs/stable/exchange-market-hours) identifies exchange-local timezone; [FMP's timezone FAQ](https://site.financialmodelingprep.com/faqs?code=data) states its exchange/region default, and [earnings documentation](https://site.financialmodelingprep.com/developer/docs/stable/earnings-company) defines `amc`/`bmo` relative to market close/open. Compose these documented meanings as an explicit mapping rule: retain the supplied timing category, but consider the expected date passed only after that date ends in the sourced exchange timezone. Do not invent a precise release timestamp. Missing or contradictory period/timezone evidence remains a visible limitation.

This provides an investigated FMP-only runtime path for annual expectation evidence; no state-production deferral is proposed. Actual annual statement metadata independently supplies publication evidence. AAPL FY2026 shows a cross-provider period-end conflict in the sampled FMP/GuruFocus fields; preserve and reject conflicts rather than silently adjusting a date. The live acceptance fixture/date must still be reconfirmed before its walkthrough.

## Further history and research-source probes

FMP returned 3,225 daily-price observations for each of AAPL and MSFT requested from 2014-01-01 through 2026-10-28; AAPL returned 45 quarterly observations for each statement type, five split events and one shares-float record. ADBE's twelve annual as-reported income rows expose purchased-intangible amortization and non-recurring-expense tags. AAPL full as-reported annual data exposes detailed lease commitments/assets/expense, amortization and deferred-tax fields. These findings establish candidate underlying evidence; exact dimensional context and missing-year coverage must be retained rather than inferred from a union of keys.

For DS-28, FMP insider search returned three AAPL records with issuer/insider identity, filing/transaction dates and transaction type. FMP institutional-holder analytics returned HTTP 402. The current documented GuruFocus authenticated API returned 38 AAPL guru-holding records and dated guru portfolio groups. These cover selected gurus, not all institutions; a portfolio date or quarter-to-quarter change is not a transaction or filing date. [FMP insider](https://site.financialmodelingprep.com/developer/docs/stable/search-insider-trades), [FMP institutional](https://site.financialmodelingprep.com/developer/docs/stable/filings-extract-with-analytics-by-holder), [GuruFocus holdings](https://www.gurufocus.com/data-api/stocks/guru-holdings).

For DS-29, FMP's SEC search returned AAPL 10-K/8-K discovery metadata, including filing/acceptance dates and document locators. This proves discovery, not retrieval of every required section. [FMP filing search](https://site.financialmodelingprep.com/developer/docs/stable/search-by-symbol).

For DS-30, GuruFocus offers transcripts on its website, but its investigated REST/MCP catalogs do not document a transcript-retrieval endpoint. Its News API promises recent commentary, not full transcript archives. Thus no supported programmatic alternative has been established for the FMP transcript-access refusal; do not state that GuruFocus has no transcripts. [GuruFocus REST catalog](https://www.gurufocus.com/data-api/pricing), [MCP catalog](https://www.gurufocus.com/data-api/mcp), [transcript website](https://www.gurufocus.com/search/transcripts).

These findings are included in the completed verdict above. The following WACC investigation records an alternative considered before D7/D8 retained user-policy discount rates; it creates no new required discount-rate source.

## DS-27 — Data availability if hurdle and discount rates are separated

**Checked 2026-10-29, in response to the founder's feasibility question.** Data access is not a reason to merge the personal investment hurdle with the valuation discount rate. These checks establish available candidates, not approval of a replacement method.

| Source / request | Actual account-access evidence | Interpretation and limits |
|---|---|---|
| FMP `custom-discounted-cash-flow`, AAPL and MSFT, default parameters apart from symbol | HTTP 200; ten model rows each. `wacc`, `costOfEquity`, `costofDebt`, `afterTaxCostOfDebt`, `beta`, `riskFreeRate`, `marketRiskPremium`, `taxRate`, `debtWeighting` and `equityWeighting` populated in every row. | Direct vendor WACC and component estimates are available. AAPL model years 2021–2030 and MSFT 2022–2031 mix historical and forecast periods; these are not ten dated historical WACC observations. No independent input vintages or suitability for another rate method are established; the evaluated alternative was not selected. |
| FMP `custom-levered-discounted-cash-flow`, AAPL | HTTP 200; ten model rows, same rate-component fields populated. | Endpoint naming is not authority for the discount rate Fairband should apply to a cash-flow definition. No vendor valuation output is adopted. |
| FMP `treasury-rates`, 2026-10-20 through 2026-10-28 | HTTP 200; seven dated rows, `year10` populated in all seven. | Accessible USD Treasury benchmark series; currency, maturity and any sovereign-default adjustment belong to the selected method. |
| FMP `market-risk-premium` | HTTP 200; 192 country rows including United States; `countryRiskPremium` and `totalEquityRiskPremium` supplied. | Response has no source-date field. Retrieval time alone cannot establish the premium's observation vintage. |
| GuruFocus AAPL summary/keyratios and MSFT keyratios | Previously authenticated responses contain numeric current WACC. | Current estimates available; vendor methodology differs from some candidate Fairband conventions. |
| GuruFocus AAPL financials, `common_size_ratios.WACC %` | Annual array has ten entries, all empty strings; quarterly array has 38 entries, all empty strings. | No usable historical WACC observations established by this sample. Annual period labels include nine fiscal years plus TTM. The initial progress-update claim of ten annual observations was withdrawn after checking values rather than field presence. |

Raw responses and safe probe summaries remain in ignored local planning data. No credentials or vendor financial values are reproduced here. [FMP custom DCF documentation](https://site.financialmodelingprep.com/developer/docs/stable/custom-dcf-advanced), [Treasury endpoint](https://site.financialmodelingprep.com/developer/docs/stable/treasury-rates), [equity-premium endpoint](https://site.financialmodelingprep.com/developer/docs/stable/market-risk-premium).

Independent public inputs also exist: [Damodaran's dated equity-premium estimates and monthly workbook](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/home.htm), [industry betas](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html), [interest-coverage/rating default spreads](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html), and [industry capital costs and weights](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/wacc.html). The monthly-premium and country-premium workbooks were accessible without an account. Industry averages are not issuer-specific rates. [OECD statutory corporate-tax data](https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html) supplies jurisdiction-level candidates; issuer applicability and debt tax-shield usability still matter.

[GuruFocus's WACC methodology](https://www.gurufocus.com/term/wacc) uses a fixed equity premium, headquarters-country Treasury rates with a U.S. fallback, interest expense divided by average debt, book-debt weights and a bounded effective tax rate. These are provider modeling choices, not directly observed market prices. They need not match a currency-consistent rate, current borrowing cost or statutory marginal-tax treatment. FMP's returned rate fields likewise require an explicit model/vintage assessment before adoption. No universal issuer coverage, point-in-time archive, complete market-value debt source or High Growth transition rule is established by these probes.

### FMP-only calculation check

The founder then asked specifically whether FMP alone supplies the calculation inputs. **Yes for a calculation using FMP's supplied assumptions, as demonstrated for AAPL and MSFT.** A script checked all ten rate-component fields as finite numbers and recomputed cost of equity as risk-free rate plus beta times equity premium, then WACC as the weighted cost of equity plus weighted after-tax cost of debt. All ten rows in each of the three sampled model responses matched the corresponding returned rate within 0.01 percentage point. Returned weights use percentage units and sum to 100. This establishes numerical reproducibility from FMP alone; it does not validate the economic assumptions or their observation dates.

For a more specific literature-based method, completeness remains conditional. FMP [expressly says it does not supply bond data](https://site.financialmodelingprep.com/faqs?code=data), so issuer bond yields/market debt values are not an available observed-data route there; a debt-cost estimate is a different input. Applicability of its tax field as a statutory marginal rate, premium observation vintage, lease treatment and company coverage remain unverified. GuruFocus is not required to reproduce the sampled FMP cost-of-equity/WACC calculations. No new discount-rate method is adopted by this feasibility finding.

### Subsequent founder decision

On 2026-10-29, the founder retained the original user-hurdle discount-rate design after consultation. See [research D7 resolution](spec/research.md#d7-resolution--personal-hurdle-retained). The subsequent D8 decision makes High Growth's starting return a separate user-set input, without a default, fading to the main hurdle. The preceding WACC investigation is an evaluated alternative, not a new required source family for discounting. These decisions do not remove interest-rate observations needed for other calculations.

## DS-01 — Eligibility before statement acquisition

FMP `profile` and `sec-profile` provide the initial listing/company identity, issuer CIK, exchange, fund/ETF/ADR flags, incorporation jurisdiction and SIC. Current country alone is not domicile evidence: active APXT has country US but incorporation code E9 (Cayman Islands). AAPL's SEC profile supplies CA. Use the [SEC jurisdiction codes](https://www.sec.gov/submit-filings/filer-support-resources/edgar-state-country-codes) and retain headquarters separately from incorporation. A contradictory/unresolved company identity is refused before statement acquisition.

The FMP samples demonstrate a common-equity gap: both AAPL and preferred AGNCM have assetType=stock, securityType=null and false fund/ETF/ADR flags. Company notes supply debt-note titles, not a common-share classification. Therefore FMP's generic stock label cannot admit the listing.

The modern GuruFocus profile supplies `general.type` and `general.class_descpt`. Authenticated AAPL/MSFT/AGNCM.PFD profiles returned HTTP 200; AAPL/MSFT use ST00000001, while preferred AGNCM.PFD uses ST00000002. AAPL's description says Ordinary Shares; MSFT's is empty. [GuruFocus documents](https://www.gurufocus.com/data-api/stocks/profile) type as Security Type. [Morningstar's primary taxonomy](https://www.postman.com/dynamic-services-morningstar-com/morningstar-direct-web-services/request/5436924-08c8132a-f406-4074-9459-385835c95d82) defines those common/preferred codes and other instrument codes. The cross-provider mapping is corroborated by these samples, not an asserted GuruFocus enum guarantee. Pin its provenance/version; unknown or conflicting codes remain unsupported.

FMP SEC profiles identify APXT with SIC 6770/Blank Checks and AGNCM with SIC 6798/REIT. [SEC SIC definitions](https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list) support explicit issuer-class exclusions; a whole financial sector label is too broad. Preserve the requested listing separately from GuruFocus primary_symbol, since preferred AGNCM.PFD points to common AGNC. An ambiguous listing join must not acquire the parent's common shares instead.

**Runtime source consequence:** FMP profile/SEC profile plus GuruFocus profile for the demonstrated security-class gap. These are bounded identity checks supporting the four dataset items, not a fifth progress item or universe build. No issuer filing-document adapter is required for this preflight.

## DS-05–09/20 — Detailed statement and reconciliation coverage

The year-level investigation covers twelve annual observations each for AAPL, MSFT and ADBE. It checks individual tags and years, not a union of keys. FMP full-as-reported returns a flat tag/value map without a namespace, XBRL dimensions or context for each fact. Consequently, a tag's presence does not establish its correct period/entity/column.

| Observation | Verified coverage / definition | Boundary |
|---|---|---|
| Operating leases: AAPL/ADBE | Modern operating-lease fields FY2020–2025; earlier rent expense and six undiscounted payment buckets FY2014–2019. | Earlier commitments lack a verified historical capitalization rate in the checked fields. The personal valuation hurdle is not a lease borrowing rate. |
| Operating/finance leases: MSFT | Modern detail FY2018–2026; older commitments/rent FY2015–2017. | FY2017 ROU/liability tags occur in a prospective adoption reconciliation. Do not treat an adjusted-column fact as the ordinary reported balance sheet. |
| Federal statutory tax: AAPL/MSFT | Reconciliation percent tags present throughout the twelve-year samples. | Federal-only rates do not establish combined local/state or multinational marginal rates. Use D9's sourced benchmark fallback where appropriate. |
| Federal statutory tax: ADBE | Standard tag FY2014–2018; issuer extension FY2018–2025. | The overlap and transition-year fiscal basis require the original disclosure; never substitute a state reconciliation effect for a statutory rate. |
| Acquired-intangible amortization: AAPL | Separate amortization tag FY2014–2017. | Later absence is not zero. A generic D&A total cannot fill it. |
| Intangible amortization: MSFT/ADBE | MSFT generic intangible amortization throughout; ADBE operating-expense, cost-of-sales and generic tags throughout. | Acquired-only basis is not established from the generic tag. ADBE's components do not consistently reconcile to its generic total; the expense-only component omits cost of sales. |
| AAPL acquisitions and disposal | Net-of-acquired-cash purchases FY2014–2022; absent FY2023–2025; no business-disposal proceeds tag. | Preserve net-of-acquired-cash as the reported purchase basis; gross purchase price is not an added requirement. Missing disposal does not mean zero. |
| AAPL debt | Separate long-term issuance absent FY2024; repayments absent FY2014–2015. | Long-term proceeds are reported net of issuance costs and may satisfy the requested observation on that explicit basis. Short commercial-paper flows are net; do not split them or impose an unrequested gross-turnover requirement. |
| MSFT acquisition cash | A combined acquisitions/intangibles/other-assets line FY2015–2026; pure business-purchase tags only selected years. | Preserve the combined observation and a pure-acquisition gap. No business-disposal proceeds tag was found in this sample. |
| MSFT/ADBE debt and disposal | MSFT repayments throughout; proceeds in selected years. ADBE debt tags are sparse and may combine leases/capital securities; its property-disposal field is not business disposal. | No net-to-gross split or classification by a similar field name. |
| GuruFocus AAPL gap check | Modern fundamentals HTTP 200; nine annual years FY2017–2025 plus separate TTM. | Lease-obligation fields null throughout; acquisition null FY2023–2025; business disposal null throughout. Debt fields match long-term FMP flows in overlapping periods; they do not supply an independently defined short-term breakdown. |

Primary context: [Microsoft 2017 annual report](https://www.microsoft.com/investor/reports/ar17/index.html), [Apple 2025 filing](https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm), [Adobe 2024 annual report](https://www.adobe.com/cc-shared/assets/investor-relations/pdfs/adbe-2024-annual-report.pdf). Definitions: [FMP full as-reported](https://site.financialmodelingprep.com/developer/docs/stable/as-reported-financial-statements), [FASB tax taxonomy guidance](https://xbrl.fasb.org/impdocs/IT_TIG/incometaxes.htm), [IRS fiscal transition](https://www.irs.gov/government-entities/2018-fiscal-year-blended-tax-rates-for-corporations), [GuruFocus effective-tax definition](https://www.gurufocus.com/term/tax-rate).

These are evidenced limitations of the checked structured sources. Original filings can establish missing context. R1 retains a correctly identified reported observation on its stated basis and identifies separate requested fields that cannot be established from a combined line. Do not strengthen the requirements to demand gross purchase prices before acquired cash, proceeds before issuance costs or undisclosed commercial-paper turnover merely to create a sourcing gap. Valuation cannot reinterpret the retained basis silently.

## DS-08/10/11 — Forward earnings and share basis

**Required meaning:** the accepted method uses four forward fiscal quarters for NTM and up to four forward fiscal years when a polluted FY1 is excluded. It requires revenue for SBC scaling, analyst counts, published guidance and one fixed diluted-share basis. Earnings normalization removes classified non-recurring items, adds back after-tax acquired-intangible amortization and retains recurring stock compensation. Item-specific or latest-YTD tax follows the existing earnings rule. These requirements are distinct from a generic non-GAAP estimate.

| Source/input | Verified access and periods | Finding |
|---|---|---|
| FMP annual estimates | AAPL and MSFT include FY2027–2030 EPS/revenue/net-income means and analyst counts. | AAPL's latter two years fall below the existing five-analyst threshold; data presence does not remove the flag. |
| FMP quarterly estimates | AAPL Sept2026–June2027 and MSFT Dec2026–Sept2027 cover sampled NTM windows anchored to current actuals. | MSFT limit=12 returns far-future rows; limit=40 reaches the required quarters. Select by fiscal periods and paginate, not by taking the first four rows. |
| FMP estimate currency | Official endpoint reference specifies reporting currency from financial statements; matched domestic samples are USD. | Estimate rows lack their own currency field; preserve the documented join and reject incompatible listing/share units. |
| FMP estimate basis | FAQ identifies non-GAAP projections. | No supplied constituent exclusions, SBC/amortization treatment, fixed forecast-share denominator or reconciliation. The checked feed cannot by itself establish Fairband's normalized basis. |
| GuruFocus legacy estimates | AAPL HTTP 200, annual Sept2026–Sept2030 and eight quarterly slots through June2028; distinct EPS and EPS-without-NRI series. | No analyst counts, currency, forecast-share denominator, observation/revision timestamp or reconciliation in the payload. It does not fill these FMP gaps. |
| GuruFocus estimate history | HTTP 200; four annual and eighteen quarterly actual/consensus pairs, surprises and release dates. | Ordinary actual EPS agrees with same-period financials in 4/4 annual and 17/18 quarterly samples; EPS-without-NRI agrees in 3/4 and 16/18. This disproves automatic interchangeability without claiming the reason for each mismatch. |
| Historical diluted shares | FMP statements and GuruFocus financials distinguish diluted period-average shares. | Historical shares are available; forecast shares and forecast split basis are not supplied by the checked estimate feeds. Dividing consensus net income by consensus EPS does not prove a shared analyst population or denominator. |
| Modern GuruFocus valuations | HTTP 200; 29 annual and 119 quarterly records with period and filing dates. | No estimate-vintage/basis fields; not a replacement for forecast reconciliation. |

[FMP API parameters/schema](https://site.financialmodelingprep.com/developer/docs), [FMP basis FAQ](https://site.financialmodelingprep.com/faqs?code=data), [GuruFocus valuations](https://www.gurufocus.com/data-api/stocks/valuations), [GuruFocus changelog](https://www.gurufocus.com/changelog). Counts and selected periods are investigation metadata; no vendor financial amounts are reproduced.

### Historical cutoffs: FT-004

FMP's documented standard estimate parameters are symbol, period, page and limit, with no as-of selector. Its [snapshot explanation](https://site.financialmodelingprep.com/education/calendar/build-an-earnings-revision-pressure-signal-estimate-drift-monitor) explicitly says the endpoint has no historical revision timeline and requires local snapshot accumulation. Both checked estimate feeds omit observation/revision times. A fiscal-period date or earnings-release date is not the time an estimate became available.

Disposition: estimates before Fairband's first capture have unsupported cutoffs in the checked feeds; immutable local snapshots can support cutoffs from actual capture onward. A generic FAQ reference to historical snapshots does not establish an accessible route or entitlement. Current/restated statements likewise do not prove all original historical versions. This is a coverage limitation for the future point-in-time consumer, not permission to rewrite history or claim a pre-acquisition backtest.

## DS-12/25/29/30 — Primary company evidence

Direct local HTTPS retrieval returned HTTP 200 for Microsoft's FY2026 annual report, Q4 earnings release and call transcript, with document hashes retained privately. The annual report exposes business, segments and financial notes. The release identifies its period/date and GAAP/non-GAAP reconciliation. The transcript includes management outlook and discussion. Their publication/call dates are distinct from local retrieval; do not infer a first-publication timestamp solely from a call date.

[Annual report](https://www.microsoft.com/investor/reports/ar26/index.html), [earnings release](https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast), [call transcript](https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4).

This verifies an issuer fallback for that company and period. It does not establish transcripts or margin targets for every company. A release, webcast or prepared remarks must not be labelled a complete transcript. FMP's AAPL transcript request remains a verified account-entitlement refusal. The inspected GuruFocus REST/MCP catalogs provide no documented transcript retrieval route; its website offering alone does not prove programmatic access.

FMP's filing discovery is verified separately from document retrieval. Primary SEC/issuer reports opened through web retrieval, while direct local requests for the sampled Apple SEC filing and Adobe PDF returned 403. Record those access refusals precisely rather than calling the documents absent or paywalled; the Microsoft issuer path is independently accessible. FT-007 must retain explicit per-document access/coverage failures.

Company operating age, market-size claims, customer concentration, guidance and margin targets come from dated primary evidence when published. The selected scenario/market-share assumptions remain tagged judgments. A vendor IPO date, market capitalization or analyst price target is not a substitute for those definitions. Absence of a published target is an explicit missing input, with the already-approved peer fallback used only where that rule permits it.

## DS-09 — Country statutory-rate benchmark

The founder's D9 fallback uses the published combined central/subcentral corporate statutory rate as an explicitly labelled estimate, with company-specific evidence taking precedence. OECD's public SDMX CSV returned HTTP 200 with twelve normal-status U.S. observations for 2014–2025. A second query without an end date returned the same coverage. **No U.S. 2026 observation was present**, despite the landing page's July 2026 update date; no carry-forward is authorized.

The verified series key is `USA.A.CIT_C.ST.PT_INC_TAX.S13._Z._Z`: combined corporate income tax, statutory, percentage of taxable income, general government. It is distinct from `CPITCIT`, which includes personal/shareholder taxation. The U.S. subcentral component is a weighted state benchmark; it is not the specific company's state-tax rate. The flow includes an unexplained `NonProductionDataflow=true` annotation, retained as source metadata rather than interpreted as a guarantee.

[Public CSV](https://sdmx.oecd.org/public/rest/data/OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,1.0/USA.A.CIT_C.ST.PT_INC_TAX.S13._Z._Z?startPeriod=2014&dimensionAtObservation=AllDimensions&format=csvfilewithlabels), [structure/code lists](https://sdmx.oecd.org/public/rest/dataflow/OECD.CTP.TPS/DSD_TAX_CIT@DF_CIT/1.0?references=all), [official API documentation](https://www.oecd.org/en/data/insights/data-explainers/2024/09/api.html), [2026 explanatory annex](https://www.oecd.org/content/dam/oecd/en/topics/policy-sub-issues/corporate-taxation/explanatory-annex-corporate-tax-statistics.pdf), printed p70. Checked 2026-10-29; private response/hash manifest retained locally. This supplies a public source independent of the financial-data vendors, with year/country gaps preserved.

## DS-01/03/08/18 — Foreign issuer samples

FMP returned twelve annual income/balance/cash-flow observations, FY2014–2025, for each of TSM and SAP. Both profiles identify NYSE ADR listings quoted in USD. Statement reporting currencies are respectively TWD and EUR. Basic/diluted EPS and period-average share fields are populated, but the tested normalized feeds do not carry an explicit ordinary-share/ADR unit or accounting-standard label for each fact.

The quote/share-float ADR adjustment documented in FMP's February 2025 changelog does not establish the same basis for annual weighted-average shares. Statement currency, quote currency, economic-share unit and listed unit are separate metadata. Primary issuer reports can establish accounting/share basis for their own disclosures; no complete historical conversion claim follows from a profile flag alone.

Publication checks also differ: TSM's normalized dates agree with the sampled FY2025 20-F filing, 2026-04-16. SAP's normalized filing dates equal fiscal year-end throughout and its acceptance timestamps precede that date, so they cannot prove publication. FMP SEC discovery independently returns SAP's actual FY2025 20-F filing, 2026-02-26. The FAQ's blanket international-filing-link absence is therefore not propagated to these tested ADRs. Earliest earnings publication remains distinct from a formal filing.

GuruFocus modern profiles returned both issuer/underlying-listing identities but omitted the documented depositary ratio. Its legacy summary supplied the current ordinary-shares-per-ADR ratio for both companies, corroborated by primary disclosures. Neither inspected response supplies historical ratio changes/effective dates. The current ratio is a verified supplementary input; it is not historical-ratio evidence.

[FMP FAQ](https://site.financialmodelingprep.com/faqs?code=data), [FMP changelog](https://site.financialmodelingprep.com/developer/docs/changelog), [GuruFocus field definition](https://www.gurufocus.com/data-api/stocks/profile), [GuruFocus legacy-endpoint changelog](https://www.gurufocus.com/changelog), [TSM 20-F](https://www.sec.gov/Archives/edgar/data/1046179/000162828026025362/tsm-20251231.htm), [SAP 20-F](https://www.sec.gov/Archives/edgar/data/1000184/000110465926020058/sap-20251231x20f.htm), [TSMC share-unit disclosure](https://investor.tsmc.com/english/encrypt/files/encrypt_file/reports/2025-04/ae894c20458e4885df6919511660de815cc6cf71/FS.pdf), [SAP depositary](https://adr.db.com/drwebrebrand/dr-universe/dr_details.html?identifier=1109).


## DS-13/14 — Exact vendor score definitions

GuruFocus's authenticated AAPL summary supplies the exact `company_data.moat_score` used by the accepted default and `z2score`; its key-ratio/financial responses expose the quality and Beneish families. The provider documents Z2 as Altman Z″. FMP's inspected score response supplies a generic Altman Z and Piotroski score, not an established equivalent of Z″ or the named moat score. Use the exact GF fields for these gaps, with their source definitions and captured observation date. No original publication timestamp or universal issuer coverage is inferred from a current response. [Moat definition](https://www.gurufocus.com/term/moat-score/AAPL), [Z″ definition](https://www.gurufocus.com/term/z2score), [Beneish definition](https://www.gurufocus.com/term/mscore), [FMP score endpoint](https://site.financialmodelingprep.com/developer/docs/stable/financial-scores).

## DS-15/16/26 — Actual peer-to-history join

FMP's ten returned AAPL peer candidates include SONY. New profile, annual income and annual balance calls returned HTTP 200 with twelve rows per statement. The fully matched sample supplies ten revenue/operating-income years ending March 2016–March 2025 and eleven balance dates March 2015–March 2025. Every selected row matches SONY's symbol and actual CIK, is FY-labelled and reports JPY; the NYSE ADR quote uses USD. Fiscal-year labels are retained separately from period-end years.

The newest March 2026 row carries a zero placeholder CIK and was excluded from that identity-matched sample window. This is a demonstrated anomaly, not a reason to silently attach it to a different issuer. Peer membership has no effective-date field; local capture dates the observed candidate list. Contrary to the documentation's same-exchange wording, the actual list includes international listings and a NYSE peer for NASDAQ-listed AAPL. Fairband performs its own universe/phase filters.

The raw components establish the ten-year/eleven-date source envelope, not complete normalized capital. The tested SONY schemas omit accounting-standard, acquired-only-intangible and complete operating-lease/profit-adjustment context. A capitalLeaseObligations field is not proof that all operating leases are included. No SONY detailed-filing absence was inferred from this bounded join, and no mature-phase qualification or three-peer minimum was claimed. [FMP peers](https://site.financialmodelingprep.com/developer/docs/stable/peers), [profile](https://site.financialmodelingprep.com/developer/docs/stable/profile-symbol), [income](https://site.financialmodelingprep.com/developer/docs/stable/income-statement), [balance](https://site.financialmodelingprep.com/developer/docs/stable/balance-sheet-statement).

## DS-18 — Foreign price and FX history

Current FMP quotes for EURUSD, TWDUSD and USDTWD returned HTTP 200 with timestamps. The separately retrieved forex list supplies base/counter currency direction: USD per EUR, USD per TWD and TWD per USD respectively. Profile provenance supplies each equity listing's quote currency; neither price-history nor quote schemas independently encode all currency/timing conventions.

Requests from 2014-01-01 through 2026-10-29 returned 3,226 distinct equity dates each for TSM/SAP and 3,413/3,430/3,431 distinct FX dates for EURUSD/TWDUSD/USDTWD. EURUSD and USDTWD cover every observed equity date; TWDUSD misses one, 2017-07-12. All sampled closes are positive finite numbers. FX histories include weekend observations. The documented 5,000-record response bound requires bounded date windows for longer requests.

FMP identifies the tested equity close as split-adjusted, not dividend-adjusted. Its FX FAQ gives EST/UTC−5; the payload has no exact daily fixing, bid/ask/mid designation, finality flag or per-row timezone. Do not reinterpret that as a verified DST-aware fixing. Current-day observations are not assured final closes. These are known source-contract limits, not account-access failures. The later route must explicitly apply the relevant spot/period conversion and day-matching rule; this investigation does not invent one. [Forex identity](https://site.financialmodelingprep.com/developer/docs/stable/forex-list), [quotes](https://site.financialmodelingprep.com/developer/docs/stable/forex-quote), [FX history](https://site.financialmodelingprep.com/developer/docs/stable/forex-historical-price-eod-full), [equity history](https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-full), [parameters](https://site.financialmodelingprep.com/developer/docs), [timing/adjustments](https://site.financialmodelingprep.com/faqs?code=data).

## DS-21 — Public survival evidence

The checked BLS annual age/industry cohort tables extend through March 2026, with cohort starts from 1994. Recent cohorts do not have a complete ten-year follow-up. BLS measures establishments; issuer operating age is separately sourced from company history, not a vendor IPO date. D3d requires a justified issuer/population mapping and a probability conditional on survival to the company's current age. If that mapping or follow-up cannot be established, probability is unavailable with its reason.

Industry cohort observations can reflect classification/population changes; an increase or a ratio above one must not be clipped into a survival probability. Preserve cohort, industry, reference year and denominator before applying the accepted method. This is a verified public source family with explicit applicability limits, not a claim that BLS directly measures listed-company failure. [BLS survival tables](https://www.bls.gov/bdm/bdmage.htm), [definitions](https://www.bls.gov/bdm/bdagefaq.htm), [all-industry cohort table](https://www.bls.gov/bdm/us_age_naics_00_table7.txt), [information-industry table](https://www.bls.gov/bdm/us_age_naics_51_table7.txt).

## DS-22/23 — Distress and recovery definitions

The selected naive distance-to-default model uses equity value, one prior year of daily equity returns for volatility, prior-year stock return as drift, and a debt barrier of debt in current liabilities plus half long-term debt. It does not require risk-free rates, beta, equity premiums or company bond prices. Its published forecasting horizon is one year; neither the formula nor the chosen source authorizes an implicit ten-year transformation. FMP's sampled price/debt families provide the candidate observations; lease/debt classifications and share units retain the specific limitations above. [Bharath and Shumway's published paper](https://www.tylergshumway.org/Bharath-ForecastingDefaultMerton-2008.pdf), PDF pp 14 and 28.

D3f separates two evidence types. Company/asset-specific sale evidence supports asset proceeds, with divested earnings removed from the continuing forecast. Moody's historical averages support creditor recovery only, with the instrument class, study window and measurement convention retained. The public 2004 study defines post-default debt price relative to principal; the public 2021 compilation supplies additional aggregate creditor-recovery evidence. Neither is an automatic recovery fraction for operating assets or common equity. These public reports establish an accessible reference family; no proprietary database subscription, unrestricted redistribution right or new numeric default is asserted. [Moody's 2004 study](https://www.bu.edu/econ/files/2015/01/Moodys_Default_1920-2004.pdf), printed p 39; [Moody's 2021 compilation](https://ma.moodys.com/rs/961-KCJ-308/images/Compilations%20-%20High-Yield-Interest-European-Edition-February-2021%20-%2018Feb21.pdf); [Damodaran's asset/distress analysis](https://pages.stern.nyu.edu/~adamodar/pdfiles/papers/NewDistress.pdf), printed pp 44–45.

## DS-24 — Minimal growth-base-rate facts

D6 authorizes the minimum cited factual statistics in Fairband's own format, without distributing a report or copied table. The public original report supplies eleven median ten-year net-income-growth facts and sales-class boundaries: Mauboussin, Callahan and Majd, *The Base Rate Book: Integrating the Past to Better Anticipate the Future*, Credit Suisse Global Financial Strategies, 2016-09-26, Earnings Growth Exhibit 4, printed pp 72–73. This finding uses the [public report](https://josephnoko.com/wp-content/uploads/2024/04/The-Base-Rate-Book-Michael-Mauboussin.pdf), not a private reference copy.

The source defines starting annual sales in 2015 dollars and net income before extraordinary items. Its top classes overlap; they must not be renamed disjoint empirical bands. The inspected report does not identify the exact inflation index, so automatic current-dollar class matching is not established. Keep that limitation and the inherited fixed inflation addition separate; do not attribute an invented deflator to the authors. The factual source is accessible, while any unsupported company/class mapping remains explicit. No blanket copyright clearance is claimed.

## DS-27 — Rates retained after D7/D8

The tested FMP Treasury endpoint returned HTTP 200 with seven dated observations and populated one-month through thirty-year maturity fields, including the ten-year nominal USD benchmark used for this planning source check. A currency-consistent risk-free observation remains necessary for the terminal-growth ceiling. The U.S. series does not itself establish a non-USD benchmark; such currencies remain unsupported until explicitly mapped. [FMP Treasury endpoint](https://site.financialmodelingprep.com/developer/docs/stable/treasury-rates), [Damodaran's stable-growth constraint](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valquestions/stablegrowthrate.htm).

Historical lease reconstruction needs an evidenced pretax borrowing/lease discount rate and matching operating-profit treatment, independently of the user's valuation hurdle. The inspected earlier AAPL/ADBE FY2014–2019 and MSFT FY2015–2017 fields do not establish those historical capitalization rates; existing commitments alone do not close the gap. Current WACC or mixed forecast-model rows do not supply a historical-rate archive. Modern reported lease balances must not be capitalized twice. [Damodaran's lease method](https://pages.stern.nyu.edu/~adamodar/pdfiles/papers/newlease.pdf).

## Completion and retained evidence

The investigation is complete at the finite source-contract/sample level required by RA-01. Every DS family is assigned in [input-source-map.md](input-source-map.md); limitations identify the affected source, period, population or account. No unperformed universal issuer survey is represented as evidence. Private safe manifests retain endpoint parameters, observation times, schema/coverage checks and response hashes under ignored local planning data; vendor financial payloads and credentials are not published.

R1's source assignment is FMP statements/annual-period earnings evidence plus GuruFocus modern identity. Later source families and capability blockers remain recorded rather than silently implemented or removed. Release acceptance still must reconfirm the live reference company's ten-period fixture and walk the authorized source flow; this completed investigation does not claim those implementation checks have run.

## Unreported annual-period evidence — review follow-up

A minimal FMP earnings request for AAPL with limit=1 and includeReportTimes=true returned HTTP 200 at 2026-10-29T19:46:07Z. It directly identifies Q4/FY2026, periodEnding 2026-09-27, expected date 2026-11-02, confirmed=true and time=amc; actual earnings/revenue fields are null and inspected annual statements stop at FY2025. This establishes that annual-period identifiers can be supplied before the matching annual statement exists; no anniversary inference or circular statement prerequisite is needed. [FMP optional metadata documentation](https://site.financialmodelingprep.com/insights/platform/why-fmp-examples-may-show-different-api-versions-and-which-docs-to-use).

This specific candidate conflicts with the separately inspected GuruFocus expected fiscal end 2026-09-26 and must remain excluded while that conflict is unresolved. It is also future at retrieval: the date-only due boundary would be 2026-11-03T05:00:00Z in America/New_York. This is source-path/field evidence, not an admitted live overdue fixture or a guarantee for every issuer. The release contract now explicitly admits a conflict-free source-supplied unreported Q4 identity without a same-period statement. Controlled tests establish the passed-date behavior; live acceptance reconfirms whatever evidence and limitations the provider supplies. No waiting-state production deferral is justified by this single conflicted example because the required source fields and semantics exist.

## Addendum 2026-10-30 — BS-10, CF-08 and vendor zeros

Founder decisions and the method rationale are in [research D17](spec/research.md). This addendum updates the field rows above without rewriting them.

| Field | Change | Evidence |
|---|---|---|
| BS-10 | Bound under Rule E (`bs10-intangibles-total-v1`): the issuer's intangible assets excluding goodwill from `balance-sheet-statement-as-reported`, labelled an estimate of acquired intangibles | Local AAPL capture: `intangibleassetsnetexcludinggoodwill` FY2014–2017, no line FY2018–2025. Full as-reported captures: MSFT `finitelivedintangibleassetsnet`; ADBE `finitelivedintangibleassetsnet` then `otherintangibleassetsnet`. SEC XBRL sample: issuer total for 69 of 88 year-ends across eight U.S. issuers. |
| CF-08 | Retired from catalog-v1 | No decided formula uses separate disposal proceeds; no source field; no residual allowed. |
| Balance-sheet zeros | Rule Z: a normalized zero counts as `not-presented` unless the same-period as-reported balance sheet presents the line | FMP normalized `goodwill` and `intangibleAssets` read 0 for AAPL FY2018–2025, where Apple presented neither line. |

Consequence for the live fixture: AAPL's resolved window keeps `not-presented` goodwill and intangibles for FY2018–2024, so a live AAPL refresh ends partial. That is a disclosure gap, not a mapping gap. Issuers that present every requested line can reach complete coverage under the production binding.

**Statement-specific confirmation (T055, 2026-10-30).** FMP `balance-sheet-statement-as-reported` (symbol=MSFT and symbol=ADBE, period=annual, limit=12) returned HTTP 200 with 12 period-matched FY rows each, carrying `symbol`, `fiscalYear`, `period`, `date`, `reportedCurrency` and `data`. MSFT presents `finitelivedintangibleassetsnet` and `goodwill` in FY2015–2026. ADBE presents `finitelivedintangibleassetsnet` in FY2014–2021, `otherintangibleassetsnet` in FY2022–2025 and `goodwill` throughout. No row carries `indefinitelivedintangibleassetsexcludinggoodwill`. The binding question does not reopen. Raw responses stay under ignored `data/planning/`.
