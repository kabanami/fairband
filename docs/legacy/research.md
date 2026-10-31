# Release 1 — Planning decisions and evidence

**Status**: Phase 0 complete; source findings consolidated for Phase 1 on 2026-10-29.
**Date**: 2026-10-29

## D1 — Inherit the approved architecture

Decision: retain one Python process, one local SQLite store, shared application authority, original Fairband source clients and packaged web assets. No adopted Feature implementation or sibling-code dependency. The six selected Features remain `code · build`; confirmation in the macro register accompanies completed planning.

Rationale: these are founder-approved architecture boundaries. Alternatives: no new service, event broker, CLI or agent runtime is required by the release.

## D2 — Capital timing for ten-year ROIC

**Founder confirmed, 2026-10-29:** use the average of each year's opening and closing operating invested-capital balances. Keep the already-decided aggregate as the sum of ten annual after-tax operating profits divided by the sum of those ten average capital balances.

Data consequence: investigate eleven year-end balance-sheet dates for the valuation method. R1's runtime requirement remains ten actual annual periods of each statement type; this decision changes neither its story count nor its field catalog.

Rationale: match a full year's profit to capital employed across the year. Alternative: year-end balances. [Damodaran's worked accounting-return example](https://pages.stern.nyu.edu/~adamodar/pdfiles/acf2E/instrmanual.pdf) explicitly averages opening and closing capital. This closes the timing sub-question in design §6.6/§15.12, not its cash or lease sub-questions.

## D3 — Tax basis for historical ROIC

**Founder confirmed, 2026-10-29:** use the applicable statutory marginal tax rate to turn operating profit into after-tax operating profit for historical ROIC. Do not substitute stocks' fixed 21% shortcut or reuse the latest year across history without an explicit rule. Map the required jurisdiction/year tax-rate evidence and its provenance.

Rationale: avoids one-off effective-tax distortions; [Damodaran's corporate-finance explanation](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/cfemailspr11.html) prefers marginal rates while acknowledging effective rates as a defensible alternative. This decision is distinct from the accepted item-specific/latest-YTD tax convention for earnings adjustments. Detailed jurisdiction attribution and loss treatment remain to be pinned with sourced evidence rather than invented.

## D3a — Lease consistency

**Founder confirmed, 2026-10-29:** include leased operating assets in invested capital and apply the matching adjustment to operating profit. Preserve one consistent financing treatment across assets, liabilities, profit and the enterprise-to-equity bridge; do not add already-capitalized lease assets twice.

Data consequence: map lease assets and obligations, operating lease expense, interest/depreciation evidence and historical commitments where capitalization changed. Missing detail is an explicit limitation; a total-debt field alone is insufficient. [Damodaran's lease analysis](https://pages.stern.nyu.edu/~adamodar/pdfiles/papers/newlease.pdf) explains the matched income/capital treatment. Alternative rejected: leave operating lease expense treatment unmatched across the capital denominator.

## D3b — Cash in operating invested capital

**Founder confirmed, 2026-10-29:** exclude cash/cash equivalents and marketable securities by default. Any operating-cash exception needs evidence and a tagged judgment, not an invented revenue percentage.

Data consequence: retain separate cash/equivalent, investment and restricted/operating-cash disclosures so the later valuation can apply the rule without treating all current assets as operating. [Damodaran's non-cash working-capital guidance](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valquestions/noncashwc.htm) supports this convention and its operating-cash exceptions. Alternative rejected: include all cash automatically.

## D3c — Sales-to-capital source

**Founder confirmed, 2026-10-29:** use the filtered mature-peer set already selected for target margins as the sales-to-capital source for Start-up, Young Growth and High Growth. Investigate those peers' revenue and operating-capital histories on the same cash/lease basis.

Rationale: young companies may not have stable own-company history. Alternatives considered: own history and Damodaran's industry dataset. This selects the source population, not a new aggregation equation, outlier rule or minimum-years threshold. Investigate the bounded ten-year revenue/eleven-date capital envelope already needed by the related defaults; the route must stay within verified evidence or reopen sourcing. [Damodaran's scaling discussion](https://pages.stern.nyu.edu/~adamodar/pdfiles/country/narrative%26numbersDEShaw2024.pdf) supports assessing revenue against capital and comparable businesses; the selected peer population is the founder's decision.

## D3d — Early-phase failure evidence

**Founder confirmed, 2026-10-29:** use age/industry survival tables as the default for Start-up and Young Growth. Require sourced operating-age evidence and a justified mapping from the source population; disclose that BLS measures establishments rather than listed companies. If the mapping cannot be justified, probability is unavailable with a reason.

Rationale: many young companies have no credit rating. Alternative: rating/default tables. [BLS survival tables](https://www.bls.gov/bdm/bdmage.htm) and [age definitions](https://www.bls.gov/bdm/bdagefaq.htm) must be checked for the relevant cohort, industry and horizon. An IPO date does not establish operating age. A probability conditional on survival to the current age must not be replaced by an unconditional cohort failure fraction.

## D3e — Decline distress-probability source

**Founder confirmed, 2026-10-29:** use the published naive distance-to-default branch. Investigate equity market value, prior-year price returns/volatility and the model's current/long-term debt inputs, preserving its exact definitions.

Rationale: this branch can cover unrated companies. Alternatives: rating/default tables and company bond prices. [Bharath and Shumway's original model](https://web-docs.stern.nyu.edu/salomon/docs/Credit2006/T_Shumway.pdf) supplies the method; no generic vendor distress score is substituted. Its one-year probability must remain labelled one-year. A later route's longer-horizon transformation requires a sourced decision and cannot silently reuse it as a ten-year probability. This choice settles the observation family, not recovery or horizon arithmetic.

## D3f — Asset and creditor recovery are distinct

**Founder confirmed, 2026-10-29:** use company/asset-specific sale evidence for asset proceeds. Moody's averages apply only when measuring creditor recovery. Do not multiply operating assets or equity by a bond-recovery percentage without a method establishing that conversion.

This explicitly resolves the ambiguity in design §6.12/§15.5; it does not drop the creditor-recovery source from the inventory. [Moody's original definition](https://www.bu.edu/econ/files/2015/01/Moodys_Default_1920-2004.pdf), printed p39, measures a post-default debt price against principal. [Damodaran's distress analysis](https://pages.stern.nyu.edu/~adamodar/pdfiles/papers/NewDistress.pdf), printed pp44–45, discusses asset-sale evidence and existing-asset earnings power. Public [Moody's 2021 study](https://ma.moodys.com/rs/961-KCJ-308/images/Compilations%20-%20High-Yield-Interest-European-Edition-February-2021%20-%2018Feb21.pdf) supplies aggregate creditor-recovery evidence with a stated instrument class and measure; those definitions must travel with any use.

## D4 — Provision the activated engineering checks in Setup

Every row below fires in release 1. Provision it in Setup/Foundational, before story code relies on it; tasks supplies exact file ownership. Nothing below is claimed installed or green yet.

| Toolchain row | Decision and reason | Alternative considered |
|---|---|---|
| L1 Dependency manager + lockfile | uv, pyproject.toml and uv.lock; first Python package | Unlocked installation would not meet the inherited reproducibility boundary. |
| L1 Runtime version pin | Pin supported Python and actual linked SQLite, check at startup/test | Workstation version alone is insufficient. SQLite 3.45.1 on this workstation lacks the documented WAL-reset fix. |
| L1 Secrets / repo hygiene | Private config, producer-specific ignores and Gitleaks | No keys or vendor data in fixtures, logs or git. |
| L2 Lint | Ruff | Inherited tool. |
| L2 Format | Ruff formatter | Inherited tool. |
| L2 Type-check | mypy, strict boundary types | Inherited tool; no unchecked adapter boundary. |
| L2 Test runner | pytest with synthetic domain/contract/integration fixtures | Live vendors cannot provide deterministic failure tests. |
| L2 Dependency scan | pip-audit against locked installation | Explicit outage/vulnerability dispositions; never silently skip. |
| L2 Accessibility scan | Playwright + axe-core and separate keyboard/focus walkthrough | Automated scans alone cannot establish full accessibility. |
| L2 Security scan | Bandit and Gitleaks, plus authorization/canary tests | Scanners do not replace behavior tests. |
| L2 Schema/migration | Ordered checksummed SQL, empty/prior-schema tests | First durable store activates this row. |
| L3 Commit hooks | pre-commit fast checks | Full suites remain CI checks. |
| L3 CI | GitHub Actions with locked checks and installed-wheel smoke | Do not claim repository protection settings configured. |

Git is already present. [SQLite's WAL-reset advisory](https://sqlite.org/wal.html) identifies fixed versions as 3.51.3 or later, with backports 3.44.6 and 3.50.7. AQ-1 must verify the chosen Python distribution's actual SQLite library before a final pin.

## D4a — Verified runtime and web-stack candidate

Research verified uv-managed CPython **3.13.18** (Astral build 2026-10-26), linked SQLite **3.53.1**, on Ubuntu 24.04.3 / WSL2 x86_64 with glibc 2.39. SQLite source ID: `2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`. This proves the library version, not application recovery behavior. [Python release](https://www.python.org/downloads/release/python-31318/), [SQLite release history](https://sqlite.org/changes.html).

The workstation's uv 0.9.26 catalog is stale. The successful research command was `uvx --from uv==0.13.6 uv python install 3.13.18 --no-bin`; it added a managed runtime without replacing system Python/global uv. Candidate release tooling is uv 0.13.6, with `.python-version`, `requires-python` and CI aligned. [uv distributions](https://docs.astral.sh/uv/concepts/python-versions/).

An ephemeral resolution/import check passed FastAPI 0.162.0, Starlette 1.10.0, Pydantic 2.14.2, Uvicorn 0.54.0, Jinja2 3.1.6, HTTPX 0.28.1 and Hatchling 1.33.0 together. pytest 9.2.0 and Playwright 1.64.1 were confirmed in package metadata, not exercised. Actual dependency locks and all product checks belong to Setup.

Recommendation: Jinja server-rendered pages and small local JavaScript modules. Use the immutable exported tokens, CSS and fonts with their licences; no React runtime is required for these pages. [FastAPI templates](https://fastapi.tiangolo.com/advanced/templates/), [static files](https://fastapi.tiangolo.com/tutorial/static-files/). Package application templates and explicit design-asset mappings using Hatchling; include their source paths in the source distribution. Resolve packaged resources via importlib.resources rather than the checkout/current directory. [Hatch inclusion](https://hatch.pypa.io/latest/config/build/), [resources](https://docs.python.org/3.13/library/importlib.resources.html).

The recommended supported environment is Ubuntu 24.04 x86_64 including WSL2; workspace on the Linux filesystem, at an absolute per-user data path. D10–D13 resolve the supported-environment and session-enrollment decisions below.

## D5 — Source investigation (completed by D14)

Credentials were located through stocks' configuration references at private local token files. New investigation code in ignored `data/planning/probe.py` reads those files in-process, refuses redirects, sends each credential only to its vendor over HTTPS, scrubs response copies and prints safe metadata only. No sibling implementation was imported or copied.

FMP probes verify sampled access to normalized and as-reported statements, estimates, peers, scores, segments and prices. GuruFocus probes investigate the specific score/earnings gaps. The [source map](../input-source-map.md) records safe evidence and limits. One successful endpoint is not a full-input verdict. The misspelled transcript route's 404 is excluded as operator error; the corrected documented route returns 402 for AAPL FY2025 Q4.

## Data-requirement closure

Resolve one founder decision at a time, using existing literature. Capital timing, historical ROIC tax basis, consistent lease treatment and cash exclusion are confirmed above. The sales-to-capital population, early-phase survival source, Decline probability branch, recovery distinction, minimal cited growth-base-rate facts and retention of the personal-hurdle valuation design are also confirmed. The completed source map records the selected definitions, history, access and explicit capability limits. A missing field in inspected feeds is a feed limitation; it is not a claim that no primary source can supply it.

Phase 0 is complete under D14. Phase 1 pins the release contracts; implementation and tasks remain separate stages.

## D6 — Base-rate distribution premise under review

The founder asked why the Base Rate Book could not be redistributed; no user-supplied-copy requirement was approved. The earlier prompt conflated distributing the report with using selected statistics. Design §6.13 and stocks' private-reference policy forbid copying the private report; those rules remain in force.

The public report's final page reserves reproduction permission. The [U.S. Copyright Office](https://www.copyright.gov/help/faq/faq-protect.html) distinguishes facts from protected expression. This is not a verified licence to reproduce a complete table. Investigate the minimum factual statistics needed, with attribution and original representation, before imposing a local-copy requirement or declaring the source unavailable. No report or source table has been added to the repository, and no legal clearance is claimed.

### D6 resolution — minimal factual statistics

**Founder confirmed, 2026-10-29:** use the minimum cited statistics in Fairband's own data format. Do not distribute the PDF or copy its tables. No requirement for each user to supply a local report copy is imposed by this decision, and no separate redistribution licence or legal clearance is claimed.

The publicly accessible original report supplies eleven median ten-year net-income growth statistics and their sales-class boundaries: Michael J. Mauboussin, Dan Callahan and Darius Majd, *The Base Rate Book: Integrating the Past to Better Anticipate the Future*, Credit Suisse Global Financial Strategies, 2016-09-26, Earnings Growth Exhibit 4, printed pp72–73. [Public report](https://josephnoko.com/wp-content/uploads/2024/04/The-Base-Rate-Book-Michael-Mauboussin.pdf). No private reference-file link is published.

The source uses 2015-dollar amounts, starting annual sales, and net income before extraordinary items. The ten sales deciles and the additional largest-company class overlap; do not rename the broader upper class as an empirically measured disjoint band. The fixed inflation addition in the inherited rule is a policy choice, separate from the reported factual medians. Dollar-year/class mapping must be explicit; the inspected source does not identify an exact inflation index, so none is attributed to it.

## D7 — Required return versus valuation discount rate: retain original design

The founder questioned the recommendation to use policy-set High Growth discount rates. No approval of that recommendation was given. The owner withdrew its economic rationale: versioning preserves input history, but does not justify a discount-rate level.

The current product map's 2026-10-28 decision gives the required return both the discount-rate and expected-return-hurdle roles. The founder now distinguishes a personal investment hurdle from a market-informed valuation rate. [Damodaran's framework](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/background/valintro.htm) matches shareholder cash flows to cost of equity and firm cash flows to weighted average cost of capital. A personal-hurdle valuation can answer willingness-to-pay, but cannot silently stand in for that risk/cash-flow match.

**Earlier question, resolved below:** separate the personal hurdle from method-appropriate valuation discount rates, or retain explicitly personal-hurdle valuation. The feasibility investigation below took place before the founder decided. It did not amend the dual-role rule or adopt vendor rates.

### D7 feasibility check — cost-of-capital data is available

The founder asked whether separation is practical given the available data, without yet choosing separation. Actual FMP account calls for AAPL and MSFT returned WACC, cost of equity, cost of debt and their component assumptions. Treasury yields and country equity-premium endpoints also returned successfully. GuruFocus supplies current WACC for the samples; its sampled historical WACC arrays are empty, so historical coverage is not claimed. Public Damodaran datasets supply additional dated premiums, industry betas and borrowing-spread candidates. See [the DS-27 evidence](../source-evidence.md#ds-27--data-availability-if-hurdle-and-discount-rates-are-separated).

**Conclusion:** separation is feasible for the sampled ordinary U.S. companies; lack of cost-of-capital data does not justify forcing the personal hurdle into the discount-rate role. This is not a full-population coverage verdict or adoption of a vendor's methodology. Exact estimation choices, input vintages, debt/tax treatment and the High Growth rate transition remain to be pinned if separation is chosen. Versioning would retain the dated inputs and calculation rules; it would not require fixing the discount-rate number forever.

**FMP-only follow-up:** scripts reproduced cost of equity and WACC from the returned FMP components for all sampled AAPL/MSFT model rows. Thus an FMP-only calculation using its assumptions is feasible and does not require GuruFocus. This does not establish every input for a different chosen method: FMP excludes bond data, and statutory marginal-tax applicability, premium vintage and lease treatment still need resolution. The founder's question is a feasibility clarification, not approval of a particular method or the separation decision.

### D7 resolution — personal hurdle retained

**Founder confirmed, 2026-10-29:** after consultation, retain the original design using the user's hurdle rate as the valuation discount rate. Simplicity and investor-specific decision making are the stated reasons. The product map's 2026-10-28 dual-role decision remains in force: the required return determines valuation and is also the expected-return hurdle. The default remains the existing policy value; no market-derived WACC or cost-of-equity requirement is introduced for discounting.

Rationale: the output is a value under the user's required return and the model's cash-flow assumptions. [CFI's required-return explanation](https://corporatefinanceinstitute.com/resources/capital_markets/required-rate-of-return/) describes this use in equity valuation. A common hurdle does not itself measure differences in company risk. Retain explicit downside/failure assumptions and margin-of-safety treatment. Cash flows to shareholders and cash flows to all capital providers remain different: an FCFF route using a policy rate must not claim that it mechanically guarantees the same equity return after debt. This interpretation does not silently change any route formula.

The existing High Growth transition to the mature policy level remains part of the original design. D8 below resolves the starting-rate source; the exact interpolation remains the route's explicit §15.2 detail. No starting spread is invented and the path is not replaced with a flat rate.

Source consequence: retain the successful WACC probes as investigation history, but do not require their acquisition solely for the valuation discount rate. Keep independently required rates: the currency-consistent risk-free benchmark for the terminal-growth ceiling and borrowing-rate evidence for lease capitalization where needed. Versioning records the user's policy choice and later changes, rather than substituting vendor rates for that choice.

## D8 — High Growth starting return

**Founder confirmed, 2026-10-29:** the High Growth route takes a separate user-set starting required return, without an invented default, and retains the original fade to the main hurdle as the company matures. This is a policy input, not a vendor WACC estimate or a fixed market-risk premium. The later route must validate the starting/ending levels and disclose them; if the required starting input is absent, it cannot fabricate a numeric High Growth valuation.

Rationale: preserves the original maturity transition while keeping the investor's return requirements explicit. Alternative rejected: use the same hurdle in every year. Numeric interpolation and the eventual route's UI/refusal wording are later implementation detail; they introduce no additional observed-rate dataset. The source inventory therefore requires no vendor beta, equity premium or WACC solely for this path.

## D9 — Historical marginal-tax fallback

**Founder confirmed, 2026-10-29:** when the company's full marginal tax rate is not evidenced, use the published combined corporate-tax rate for its home country as an explicitly labelled estimate. Company-specific evidence takes precedence. This retains D3's statutory basis and does not substitute the accounting effective tax rate.

Map the country and applicable year, central-plus-subcentral rate definition, source/version and the benchmark nature of the estimate. Do not present a country benchmark as the company's actual marginal tax rate or silently use today's rate for earlier years. [OECD's corporate-income-tax database](https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html) is the investigated public source family. Country/year gaps, jurisdiction changes or insufficient issuer attribution remain visible. The separate earnings-normalization tax rule still uses item-specific/latest-YTD evidence.

Rationale: makes historical statutory-rate coverage practical without pretending federal-only or effective rates establish the combined rate. Alternative rejected: require company-specific marginal-rate evidence in every case.

## D10 — Supported runtime, packaging and web stack

**Decision:** pin the verified uv-managed CPython 3.13.18 / SQLite 3.53.1 combination, uv 0.13.6 and Hatchling on Ubuntu 24.04 x86_64, including WSL2 with application data on its Linux filesystem. Check the linked runtime at startup before opening the database. This resolves the D4a candidate for R1; broader platform support stays parked. Locked dependency versions are provisioned during Setup, not claimed installed by this plan.

Use FastAPI/Uvicorn, Jinja and small local JavaScript modules, one Uvicorn worker and one refresh worker. Package the wheel's templates, scripts, selected existing design assets and licences through explicit Hatch mappings and `importlib.resources`. Verify a wheel rebuilt from the source distribution as well as installation outside the checkout. Alternative: a React build adds no demonstrated benefit for this release's forms and inspector tables.

Resolve the default workspace from the absolute XDG data location, falling back to `~/.local/share/fairband`; private configuration uses the XDG config location, falling back to `~/.config/fairband`. Never depend on the checkout/current directory or silently move existing data. Refuse unsupported permissions/ownership or filesystem placement. [XDG specification](https://specifications.freedesktop.org/basedir/latest/), [Hatch inclusion](https://hatch.pypa.io/latest/config/build/).

## D11 — Owner enrollment and web sessions

**Decision:** local initialization reserves the single Owner and generates a cryptographically random 256-bit access secret into a private file, mode 0600 in a 0700 directory. Startup/Setup show only its path. The Owner reads that file privately and pastes the secret into web sign-in; the first browser does not claim ownership. Later sign-in uses the same private-file mechanism. Record enrollment/recovery/rotation outcomes without the secret. The shared setup contract pins rotation, OS-owner missing-file recovery and their crash boundaries; sessions are bound to durable Owner-auth revision.

Use fresh opaque server-side sessions, constant-time verification, 30-minute idle expiry, eight-hour absolute expiry and explicit logout. R1 keeps session verifiers in memory, so restart requires sign-in without changing stored data. The canonical origin is `http://localhost:<port>` with the socket bound only to 127.0.0.1. Enforce complete Host/Origin including port, reject null/absent/wrong Origin on protected POSTs, require synchronizer CSRF tokens, disable cross-origin access/proxy-header trust and expose no GET mutations. Apply to sign-in, credentials and job controls. Cookie: host-only, HttpOnly, SameSite=Strict, Secure and Path=/; validate the localhost exception in the supported browser checks. Tokens never enter URLs, browser local storage or logs.

These are engineering choices. [OWASP sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [localhost cookie behavior](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie). Alternatives rejected: first-browser ownership, secret-bearing launch links and client-only authority checks.

## D12 — Private credentials and durable publication

**Decision:** write each replacement credential to a new immutable private version file and fsync file/directory first. Then commit its nonsecret active-slot pointer, revision and audit event together in SQLite. The old credential remains active if that commit fails. Readers expose slot status only; adapters resolve the active private file. Track in-flight references before deleting old files; unreferenced crash orphans can be removed without vendor calls. Key saving does not test entitlement automatically. A file rename and an unrelated database write must never be claimed as one atomic transaction.

Acquire a lifetime nonblocking exclusive `flock` before migrations/recovery/worker startup. Keep the lock file in place; PID text is information, not ownership authority. One process owns the workspace. Pin WAL, foreign keys and synchronous=FULL; keep network work outside short write transactions. With Python `autocommit=True`, use explicit SQL BEGIN IMMEDIATE/COMMIT/ROLLBACK; connection commit/rollback methods are no-ops in that mode. Ordered checksummed migrations use a SQLite-consistent backup before changes, with explicit failure recovery.

Startup atomically marks requested/running jobs and existing unfinished attempts interrupted with audit; it creates no fictional attempt and contacts no vendor. Publication atomically includes versions, coverage, source/check references, audit and checkpoint. Compare captured content and check/evidence revisions before commit; stale responses become superseded without advancing successful-check evidence. [Python filesystem operations](https://docs.python.org/3.13/library/os.html), [locking](https://docs.python.org/3.13/library/fcntl.html), [SQLite durability](https://www.sqlite.org/pragma.html#pragma_synchronous), [Python transaction control](https://docs.python.org/3.13/library/sqlite3.html#transaction-control-via-the-autocommit-attribute).

## D13 — Finite reuse, corrections and retries

**Decision:** versioned operational configuration starts with 24-hour ordinary reuse for compatible identity, complete statement datasets and successful earnings lookups. Known due/published missing periods override statement reuse. A needed statement check re-fetches the entire resolved ten-period window; no unverified incremental/conditional-request mechanism. Compare normalized content while retaining new successful-check evidence. A successful lookup with unavailable timing remains successful with a limitation, as the spec requires.

At most three attempts per endpoint call: connect/write/pool five seconds, read inactivity fifteen seconds, and a separate thirty-second wall-clock deadline. Backoff two/four seconds; honor Retry-After only within remaining budgets. Retry transport failures, 408/429 and selected 5xx; never retry auth/entitlement, shape or basis failures automatically. Bound each dataset item to 180 seconds and an entire execution attempt, including identity, to 900 seconds. Use one dedicated worker thread with an asyncio loop/one in-flight source request across all providers. Stream under an endpoint-specific byte limit pinned in the source contract. These are operational defaults, not valuation assumptions or vendor guarantees.

Set HTTPX trust_env=False, verify TLS and refuse redirects before credential forwarding. HTTPX's read timeout limits inactivity, not total duration, so the outer deadline is mandatory. [Timeouts](https://www.python-httpx.org/advanced/timeouts/), [environment handling](https://www.python-httpx.org/environment_variables/).

Retry retains the operation's frozen window and successful checkpoints independently of ordinary reuse expiry. Rerun only failed/superseded/unfinished steps. Newly observed evidence invalidating the window produces the specified partial/new-refresh-needed result. Check cancellation before calls, after responses and before publication; an already committed final completion wins over late cancellation. No retry policy authorizes unattended polling or startup resumption.

## D14 — Sourcing verdict and release adapter boundary

**Decision:** neither inspected vendor feeds/current accounts supplies the entire required non-financial input set. The full definition/history/access inventory and evidenced capability blockers are recorded in [input-source-map.md](../input-source-map.md) and [source-evidence.md](../source-evidence.md). This is a completed investigation, not a claim of complete usable coverage. No unknown method choice is treated as proof of vendor absence.

FMP supplies the sampled annual financial history, period-linked earnings path and many broader inputs. GuruFocus supplies verified gaps including the security type needed for R1 common-equity eligibility and the exact proprietary moat/quality scores required later. Checked forecast feeds lack the reconciliation and forecast-share metadata required to establish the accepted earnings basis. Flattened historical filing fields do not establish all lease contexts/rates. Current FMP transcript entitlement is refused; a direct issuer source works for Microsoft but does not establish population-wide coverage. Public tax, survival and primary-document sources have their own recorded coverage/mapping limits. These remain explicit downstream capability blockers, never fabricated defaults or grounds to change the method.

**R1 binding:** FMP profile/sec-profile plus GuruFocus modern profile for eligibility; FMP normalized annual statements, the documented as-reported supplements, and earnings with report-time metadata. GuruFocus is required for the verified identity gap, not a blanket second financial source. Both slots are therefore required for a new live R1 identity check; local reads and qualifying reuse need neither key. Use AAPL as the live reference, MSFT as the independent eligible-ticker check. The runtime catalog remains the spec's ten-period slice with per-field explicit basis or gaps. No broader dataset is shipped by this investigation.

Rationale: respects FMP-first sourcing and the three-way exit gate without confusing sampled endpoint access with semantic completeness. Alternatives rejected: FMP-alone sufficiency; silent substitution of adjusted EPS/creditor recovery/generic Z-scores; requiring unrequested gross acquisition or issuance measures. The SONY peer join closes the final identity/history check, while retaining its 2026 placeholder identifier limitation. All source-requirement choices D2–D9 are resolved; numeric valuation-route refinements that introduce no new observed dataset remain with those later Features.

## D15 — Review refinements

The adversarial plan review pins the worker to one thread with its own asyncio loop and per-thread SQLite connections; bounded HTTP cancellation leaves the web loop responsive. Configuration-directory identity is bound to the workspace before missing-file Owner recovery. Transport refusals use bounded memory, while authenticated semantic refusals retain durable audit. Forms carry server-issued replay IDs, explicit revision targets and required Owner reasons; cancel uses payload-bound confirmation and terminal completion wins. R1 supports Linux Chromium/Firefox (including Linux browsers under WSLg); Windows-host forwarding needs separate evidence. These refine the existing scope and authority boundaries, not the valuation method.

## D16 — Retain both vendors; defer replacement review

**Founder confirmed, 2026-10-30:** use FMP and GuruFocus for now, proceed with delivery, and revisit vendor simplification later. Keep FMP primary and GF limited to the verified assignments in D14. The [dependency and replacement record](../../../../docs/gurufocus-dependencies.md) preserves the exact GF fields, candidate replacements, the founder's proposed moat rule and the unresolved validation questions.

The accepted GF moat default and required research inputs remain in force. Calculating replacement scores, adopting the moat proposal or making inputs optional is not authorized by this decision. The deferred review has no deadline and is not a prerequisite for R1 tasks, implementation or acceptance. D14's full-input coverage limitations remain explicit.

Change classification: confirmation of the current sourcing decision plus a deferred research record. No capability, release allocation, contract, architecture shape or surface changes; no PROD-CR/ARCH-CR/constitution/spec amendment is needed. The source map, macro integration/question records and roadmap carry the decision and link to the review. No new future-stage obligation or implementation task is created.

## D17 — Labelled estimates, BS-10 method, CF-08 retired and the vendor-zero rule

**Founder confirmed, 2026-10-30** (during the tasks stage, after the analyze gate showed that binding-v1's two permanent gaps made every production refresh partial; applied directly, without the change process, at the founder's instruction):

1. **Estimation principle.** Data sources will not map one to one onto every required input, and valuation is approximation. Where no source supplies a required field, Fairband may record a best-effort estimate. An estimate is computed by a documented, versioned method rule that cites its literature source (or is a labelled policy value), is stored with `value_kind` `estimate` and its `estimate_method`, and is never presented as a vendor observation or as a fabricated zero. A field with no sound method stays an explicit gap with its reason.
2. **CF-08 retired.** Separate disposal proceeds feed no decided formula: the Decline route's divestiture cash is a forecast from company-specific sale evidence (D3f), not this history. No source field exists and the contract forbids an investing residual. The ID is retired, never reused; catalog-v1 now holds 40 IDs.
3. **BS-10 method `bs10-intangibles-total-v1`.** Estimate acquired intangibles as the issuer's own reported total of intangible assets excluding goodwill, net of amortization. "Acquired" includes separately purchased intangibles.
4. **Vendor-zero rule.** A normalized balance-sheet value of exactly zero counts as `not-presented` unless the issuer's own same-period balance-sheet data presents the line.

**Why the BS-10 method follows the literature.** Mauboussin and Callahan, *Return on Invested Capital* (Morgan Stanley Investment Management, 6 October 2022), build invested capital as "+ Net property, plant, & equipment / + Acquired intangibles / + Goodwill / + Other" (p. 5, Exhibit 3), treat internal-use software "the same as PP&E" (p. 6) and add "any other long-term operating assets" (p. 6). Their worked Microsoft example fills the acquired-intangibles row with the reported "Intangible assets, net" (p. 7, Exhibit 4). Ewens, Peters and Wang (NBER w25960, rev. January 2020, p. 20) read the balance-sheet intangibles item as "externally purchased intangibles". Because design §6.6's invested capital includes goodwill, using the full non-goodwill total changes the label of the component, not the ROIC number. US GAAP expenses internally generated intangibles other than capitalized software (ASC 350-30-25-3); intangibles acquired in a business combination are recognized apart from goodwill (ASC 805-20-25-10). IFRS filers may capitalize development costs (IAS 38.57), which stay in capital with their amortization in NOPAT. Rejected: allocation by amortization share, a fixed haircut and a purchase-price roll-forward (no literature source; the inputs are not available; errors accumulate).

**Evidence.** A SEC XBRL sample of eight U.S. issuers (AAPL, MSFT, ADBE, ORCL, DHR, TMO, CRM, COST) found the issuer total for 69 of 88 year-ends. No sampled total contained internally capitalized items; internal-use software sat in property and equipment. The misses are years without a separate line: AAPL FY2018–2024 (inside other non-current assets) and COST (stated immaterial, inside other long-term assets). FMP's normalized `intangibleAssets` is not usable as the source: AAPL reads 0 for FY2018–2025 (and `goodwill` reads 0 too), AAPL's 2026 quarters omit the current part, and SONY's IFRS figure includes content assets. FMP's `balance-sheet-statement-as-reported` (local AAPL capture) carries period-matched annual rows with the issuer's `intangibleassetsnetexcludinggoodwill` and `goodwill` for FY2014–2017 and no line for FY2018–2025, matching the filings. Full as-reported captures show MSFT's total as `finitelivedintangibleassetsnet` and ADBE's as `finitelivedintangibleassetsnet` (to FY2021) and `otherintangibleassetsnet` (FY2022 on). SEC companyfacts is not adopted as a source; it remains an option that needs founder approval.

**Not decided here.** The "immaterial per issuer" zero estimate needs the issuer's text, which R1 does not parse, so R1 records `not-presented`; the valuation release applies that estimate (or an agent-supplied, tagged value) where the statement is evidenced. Gross versus net carrying amounts, impairment add-backs and the acquired-amortization add-back to NOPAT stay with the valuation release; total amortization is never a substitute for acquired-intangible amortization.

## D18 — Test-facing interfaces pinned before falsify

**2026-10-30.** The first falsify run of iteration 1.1 parked correctly: the plan pinned behavior but not the Python interfaces that the tests import (migration runner, unit of work construction and writes, receipt lookup, context construction, wiring, app composition, fault points), and the same gap waited in US1 (settings file, Owner functions) and in iteration 1.2 (three operations named only in tasks.md, the refresh policy functions, the executor protocol, the provenance and inspection services). The founder chose to pin them on `main` in the existing contracts rather than answer the run's questions with free text, so that falsify, implement and review read one record.

Decision: each contract has an `## Entrypoints — pinned interfaces` section with the types, the fixed fault-point names, the settings file, console output, HTTP field and cookie names, and a signature table. Every pinned operation is named on a task line, which arms `validate-tasks-shape.py`'s contract-operation leg. The pins realize the existing contracts; they change no behavior, story or acceptance criterion. Composition overrides are keyed by port type (`Clock`, `FaultPoints`, `HttpClientFactory`, `AttemptObserver`, `CredentialResolver`, `Executor`), so tests replace collaborators without product test routes.

Revision, same day: a read-only Codex review of the first pins (21 findings, 14 HIGH) found named types without fields, unpinned awaitability, a startup order that wrote the binding before the schema existed, missing inputs (accepted evidence for earnings corroboration, the requested scope for reuse, cancellation for publication, request origins, incremental progress, the cancel confirmation flow, the `as_of` refusal) and a per-thread connection conflict. All findings were verified and the sections were rewritten. Two placements moved: the parent-record fixture to US2 (it reads the schema built in iteration 1.1), and the publication-receipt legs from the `UnitOfWork` suite to US2's publication suite.

