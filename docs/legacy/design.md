# Fairband: design

| | |
|---|---|
| Project name | **Fairband** (decided 2026-10-27). Before this date the project was called "the hybrid project". On 2026-10-27, `fairband` was free on PyPI and as a GitHub account name, and no GitHub repository used it. fairband.com was registered; fairband.io and fairband.dev were not. Trademarks were not checked. |
| Version | 1.0, 2026-10-27; source-selection clarification 2026-10-28 |
| Written by | Claude, from a design conversation with the project owner, 2026-10-25 to 2026-10-27 |
| Decisions by | The project owner, called "the user" in this document |
| Purpose | The starting input for the agent that builds this project in a new repository |
| Main literature report | `/mnt/c/users/kaban/documents/workspace/openalice/reports/Valuation methods by life cycle phase.md` |

---

## 0. How to use this document

### 0.1 Status labels

Every rule in this document carries one of these labels.

| Label | Meaning | What the next agent does |
|---|---|---|
| **Decided** | The user decided it. The date is in the decision log at the end. | Build it. Ask the user before you change it. |
| **Proposed** | Claude suggested it. The user did not reject it, but did not confirm it explicitly either. | Confirm it with the user before you build it, or build it behind a policy setting. |
| **Deferred** | The user chose to decide it later, at build time. | Ask the user when the build needs the answer. |
| **Open** | A design gap. Nobody has proposed an answer yet, or the answer needs research. | Research it, propose one answer, and let the user decide. |

### 0.2 Working rules for the next agent

1. **Follow the literature. Do not invent methodology.** The user said: "use what the literature is suggesting, I don't want to invent a new methodology". When a rule needs a number that no source gives, call it a policy value, put it in a versioned policy file, and tell the user that it has no source.
2. **Take one decision at a time with the user.** First explain the variables in plain words. Then give one recommendation and the reason. Then let the user decide. The user asked for focused, short answers and complained when the conversation moved between several topics at once.
3. **Scripts compute every number. Agents change only tagged inputs, and each change carries a written reason.**
4. **Write every report for a human reader.** Section 9 gives the rules. The user found the reports in the stocks repo unreadable, and readability is a hard requirement.
5. **Do not reuse the portfolio approach of the stocks repo** (section 10).
6. **Keep vendor data, API keys and private source copies out of the repository** (section 13).

---

## 1. Goal and user

**The goal (Decided).** The project is an open-source Python project. It combines two things:

- the expectations-based valuation method from the user's `stocks` repo, extended to every phase of the corporate life cycle; and
- the multi-agent research style of TradingAgents, without technical analysis.

The project gives the user a value for every listed company of a useful size. It then gives a deep, agent-researched report on any company that the user picks.

**The user (Decided).**

- A long-term value investor. The valuation uses a 3-year repricing horizon.
- The user approves and places every trade. The project never connects to a brokerage.
- The user has paid GuruFocus and FMP (Financial Modeling Prep) subscriptions. The FMP account is on the Premium tier (stocks `fmpclient/registry.py`, docstring).
- The user likes many price data points, such as the 52-week range, the 1-, 3- and 5-year price change, the drawdown, and trailing and forward P/E. The user does not want price targets from technical analysis.

**Why two tiers (the user's words, 2026-10-26).** "I need to have a value for any ticker, and use it as a starting point for exploring value pockets. Where I find something interesting, then I can assign an agent to do deep analysis and valuation."

---

## 2. Scope

| Item | Status | Rule |
|---|---|---|
| Universe | Decided | Mega, Large and Mid caps traded on a U.S. stock exchange. This includes foreign companies listed on a U.S. exchange, such as ADRs. |
| Cap bands | Proposed | Use the bands of the stocks mechanical valuation: Mega from $200 bn, Large from $10 bn, Mid from $2 bn (stocks `docs/mechanical-valuation.md`). The market cap comes from FMP in USD. |
| OTC listings | Decided | Excluded. OTC markets are not stock exchanges. |
| Banks, insurers and REITs | Decided | Excluded for now. A later stage can add them. They need their own methods in every phase. |
| Listings that are not operating companies | Proposed | Exclude ETFs, closed-end funds, SPACs, preferred shares, warrants, units and rights. |
| Share classes | Proposed | Value each company once. Show each share class with its own price, for example GOOGL and GOOG. |
| Technical analysis | Decided | Out. No technical analysis agent and no technical price target. |
| Portfolio strategy | Decided | Out. The portfolio layer is a ledger and current values only (section 10). |
| Brokerage connection | Decided | Never. |
| EquityEval | Decided | Not related to this project. Ignore it. |

**Why technical analysis is out (agreed 2026-10-26).**

- The horizons do not match. Technical signals work over days to months. The valuation uses a 3-year horizon.
- Two prices from two methods would conflict. In the old TradingAgents reports, 10 of 11 "price targets" were chart levels, such as a moving average or a Bollinger band, and not valuations.
- The stocks method already rejects it. Design rule 1 says "No borrowed moods".

If a later version wants short-term users, add a technical view as a separate optional module. It must have its own report section, it must never change the stance, and it must first pass a backtest. This is an idea only, not a plan.

---

## 3. Architecture

```
Tier 1: a script, for every company in the universe, on request
  data -> phase classifier -> valuation route for the phase -> mechanical value
       -> levels and stance -> screen table (one row per company)

Tier 2: agents, for one company that the user picks, on request
  tier-1 snapshot + data
   -> analysts: Fundamentals, News (includes social), Valuation
   -> bull and bear debate about the judgments: phase, moat, belief, ROIC, kill criteria
   -> research manager decides the judgments -> input overrides, each citing a finding
   -> engine recomputes -> reviewed value, levels, value bridge
   -> report (reader part + audit appendix)

Portfolio: a ledger table in the database; values updated at each refresh;
           a portfolio review by an agent only when the user asks
```

**Core principles.**

1. **Scripts compute, agents judge (Decided).** This is principle 3 of stocks `workflow-outline.md`: "Scripts compute; agents judge." An agent never writes a value. It changes an input, and the engine recomputes.
2. **One price target (Decided).** The only price target is the engine's value at belief, with the levels around it. No agent can write a different target.
3. **Every input has a tag (Decided):** DATA (from a vendor or a filing), RULE (a versioned policy with a source) or JUDGMENT (an agent's choice with a written reason).
4. **Refresh only on request (Decided).** Nothing runs on a schedule.
5. **Every output says what it is (Proposed):** a value, a price or a probability. This comes from the literature report, section "The engine needs one core".
6. **One engine (Decided, from the literature).** Damodaran keeps one cash-flow method for all phases and changes its inputs by phase. The engine has one core and one route per phase. The same mixing formula, V = V_a × (1 − p) + V_b × p, appears three times: failure in the early phases, a change of management in Mature Stable, and distress in Decline.

---

## 4. Tier 1: the deterministic screen

### 4.1 What a refresh does

1. Build the universe (section 2).
2. Fetch the data for every company (section 11).
3. Compute the deciles across the universe that the classifier needs (section 5).
4. Classify every company into a phase (section 5).
5. Compute the target-margin defaults. This step needs the phases of the peers, so it runs after step 4 (section 6.7).
6. Run the valuation route of each company's phase (section 6).
7. Compute the levels, the stance and the price facts (sections 6.3 and 9.5).
8. Store one row per company, with its history (section 12).

### 4.2 What each row shows (Proposed)

These suggestions come from the conversation of 2026-10-26.

- **Every company gets a row.** When the engine cannot value a company, the row says why: out of scope, Start-up (price-implied requirement only), no target margin (price-implied margin only), or missing data. A missing row cannot be told apart from "not cheap".
- **The phase, the route and the classifier evidence:** the growth word, the margin direction and any check flag (section 5).
- **The value, the price, price ÷ value, the levels and the stance.**
- **Three dates:** the price date, the data date, and the end of the validity window (section 8).
- **Flags that warn about a mechanical value.** The top of any mechanical screen collects errors, so rank by "cheap and clean", not by "cheap" alone:
  - a large non-recurring item that nobody reviewed (stocks `mech/1.2` says "Nobody reviews it");
  - few analysts behind the consensus path;
  - a large price fall with no change in the estimates;
  - distress signals: the Altman Z-score and the distance to default;
  - a classifier check flag;
  - a value that changes a lot across the three ROIC values or the three runways;
  - the margin flag of stocks `mech/1.2` ("Possible cycle peak", "Newly profitable", "Margin above history"; stocks `docs/mechanical-valuation.md`, section "The margin flag").
- **Group views for finding value pockets.** Group by sector, phase and cap band. Show the median price ÷ value and the share of companies below the buy level. When a whole group looks cheap, either the market is wrong about the group, or the rules miss a problem that affects the whole group.

An earlier suggestion was to compute two routes when the classifier cannot decide between two phases. Classifier decision 4 replaced it (section 5.5).

### 4.3 Refresh types (Proposed)

- **A price refresh.** It is fast. It updates the prices, price ÷ value, the stance and the portfolio values.
- **A full refresh.** It is slow. It fetches new fundamentals and recomputes everything.

The user decided "refresh only on request". The two types are a proposal on top of that decision.

---

## 5. The life-cycle phase classifier

Decided 2026-10-27, in four decisions. The design was complete on that date.

### 5.1 The phases and the source

The phase list is Damodaran's six phases from *The Corporate Life Cycle* (2024): Start-up, Young Growth, High Growth, Mature Growth, Mature Stable and Decline.

**Damodaran gives no numeric cut-offs.** The literature report says: "No numeric cut-off for any phase appears in his slides, papers or spreadsheet." He describes each phase by the direction of four variables (CLC chapter 3, slide 7, <https://pages.stern.nyu.edu/~adamodar/pdfiles/CLC/slides/Ch3.pdf>):

| Phase | Revenue growth | Operating margin | Reinvestment | Free cash flow |
|---|---|---|---|---|
| Start-up | "NA at pre-revenue, Very high for initial revenues" | "Very negative" | "High" | "Very negative" |
| Young Growth | "Very High" | "Negative, perhaps becoming more so over time." | "Very high" | "Very negative, perhaps getting more so." |
| High Growth | "High" | "Negative, but getting less so over time" | "High, but stable, relative to revenues" | "Negative, but getting less so over time" |
| Mature Growth | "Moderate" | "Positive, and getting more so over time" | "High, but declining relative to revenues" | "Positive, and growing faster than revenues and earnings" |
| Mature Stable | "Low" | "Stable and predictable" | "Low, and a function of revenues" | "Positive and stable" |
| Decline | "Close to zero or negative" | "Positive, but declining" | "Divestment and shrinkage" | "More positive that earnings." |

His only measured test is a decile grid (CLC chapter 3, slide 8, "Figure 3.3: A Operating Metrics Breakdown of Global Companies in July 2022"). It crosses deciles of revenue growth (CAGR 2019-2021) with deciles of operating margin, for global companies of every size. It labels five cells:

| Cell | Revenue growth deciles | Operating margin deciles |
|---|---|---|
| "Young growth, with high revenue growth & negative operating margins" | 9-10 | 1-2 |
| "Superstar growth, with high revenue growth & high operating margins" | 9-10 | 9-10 |
| "Mature firms, with average revenue growth & average operating margins" | 4-7 | 4-6 |
| "Declining & in trouble, with no or low revenue growth & negative operating margins" | 1-2 | 1-2 |
| "Declining, but very profitable, with no or low revenue growth & very high operating margins" | 1-2 | 9-10 |

His duration test for Decline (CLC chapter 2, slide 20): "One or even two years of revenue decline can be explained away as extraordinary, but a string that lasts five or ten years is indicative of decay in the underlying business." He also warns: "There are mature or even growth companies that can extended streaks of declining revenues, if those revenues are driven by a macro variable that moves in cycles."

### 5.2 Decision 1: the variables

| Variable | Role |
|---|---|
| Revenue growth: the average yearly growth over 3 years (CAGR) | Names the phase |
| Operating margin: operating profit ÷ revenue, its sign and its direction | Names the phase |
| Free cash flow: its sign | Check only. It flags the company but never changes the phase. |
| Reinvestment | Not used. Free cash flow already contains it, and its words ("High", "Very high", "High, but stable") are hard to tell apart with numbers. |
| Dickinson cash-flow stage | Shown next to the phase. It does not flag and does not decide, because its five stages do not map exactly to the six phases. |

**Why these two.** Revenue growth and operating margin each separate all six phases in Damodaran's table, and they are the two variables of his decile grid. Free cash flow separates only the first three phases (negative) from the last three (positive). If it decided, a company with heavy capital spending would get the wrong phase. Example: Amazon in 2022 had a positive operating margin but negative free cash flow.

**The Dickinson stage (for display).** Dickinson (2011), "Cash Flow Patterns as a Proxy for Firm Life Cycle", *The Accounting Review* 86(6): 1969-1994, assigns a stage from the signs of operating (CFO), investing (CFI) and financing (CFF) cash flow:

| Stage | CFO | CFI | CFF |
|---|---|---|---|
| Introduction | − | − | + |
| Growth | + | − | + |
| Mature | + | − | − |
| Decline | − | + | + or − |
| Shake-out | every other pattern | | |

Check this table against the original paper before you build it. The research notes read only abstracts and a secondary table. Mauboussin and Callahan ("Trading Stages in the Company Life Cycle", 2023) first move stock compensation to financing and remove marketable-securities flows.

### 5.3 Decision 2: Damodaran's words as numbers

**Revenue growth words: deciles of the universe.** Rank all companies in the tier-1 universe by 3-year revenue growth. Compute the deciles again at every refresh. Use two deciles for each word:

| Deciles | Word |
|---|---|
| 9-10 | Very High |
| 7-8 | High |
| 5-6 | Moderate |
| 3-4 | Low |
| 1-2 | Close to zero or negative |

This split agrees with Damodaran's grid at the top (9-10) and the bottom (1-2). The middle split is a translation, because his grid has one middle label only ("average", deciles 4-7). Damodaran ranked companies of every size. This project ranks the tier-1 universe, so "High" means high compared with other large U.S.-listed companies.

A side effect: deciles always put 20% of the companies under each word.

**Margin words: the sign.** "Negative" means below zero. "Positive" means above zero.

**Start-up: growth that cannot be measured.** A company is a Start-up when its 3-year revenue growth cannot be measured: its revenue is zero now, or it was zero 3 years ago. This follows Damodaran's Start-up words, "NA at pre-revenue, Very high for initial revenues". No margin number is needed. A company that had small revenue 3 years ago is ranked like any other.

### 5.4 Decision 3: how to measure a direction

| Variable | Rule |
|---|---|
| Window | 5 years. It is the shorter of the two durations in Damodaran's Decline test ("five or ten years"). A 10-year window would react more slowly when a company moves to a new phase. |
| Measure | A trend line: the least-squares slope through the last 5 yearly values. Every year counts, so one unusual year moves the result less. This follows his point that one or two years "can be explained away". |
| Negative margin | The sign of the margin trend only. Improving (slope above zero) means High Growth. Worsening means Young Growth. |
| Positive margin | Rank the positive-margin companies by their margin trend. Deciles 8-10 are "Rising", 4-7 "Stable", 1-3 "Declining". |
| Safeguard | "Rising" also needs a slope above zero, and "Declining" a slope below zero. Otherwise the company counts as "Stable". Without this, in a year when most margins fall, a falling margin could be called "Rising". |

The 4-7 middle group copies the "average" group of Damodaran's grid. His grid uses it for revenue growth, not for margin trends, so this split is a translation.

### 5.5 Decision 4: the rules and the checks

**The rules.** The script applies them in this order. The first rule that fits decides the phase.

1. If the 3-year revenue growth cannot be measured, the phase is **Start-up**.
2. If revenue growth is "Close to zero or negative" **and** the 5-year revenue trend line falls, the phase is **Decline**, whatever the margin. The second condition is Damodaran's duration test. It keeps one or two bad years at a cyclical company out of Decline. Both low-growth corners of his grid are labeled "Declining".
3. If the operating margin is negative, the phase is **Young Growth** when the margin worsens and **High Growth** when it improves.
4. If the operating margin is positive, the growth word decides: "Very High", "High" or "Moderate" gives **Mature Growth**; "Low" or "Close to zero or negative" gives **Mature Stable**. His table gives positive margins only to Mature Growth, Mature Stable and Decline. His grid calls high growth with a high margin "Superstar growth", not Young Growth.

Examples: NVIDIA (positive and rising margin, very high growth) goes to Mature Growth. A loss-making company whose revenue falls for 5 years goes to Decline.

**The checks.** A check flags the company but never changes the phase.

| Check | When it flags |
|---|---|
| Growth word, for a negative margin | The growth word points to a different phase than the rule gave. Map: Very High → Young Growth, High → High Growth, Moderate → Mature Growth, Low → Mature Stable, Close to zero or negative → Decline. Example: High Growth with "Low" growth. |
| Margin direction, for a positive margin | The direction points to a different phase. Map: Rising → Mature Growth, Stable → Mature Stable, Declining → Decline. Example: Mature Stable with a "Rising" margin. |
| Free cash flow sign | Negative in Mature Growth, Mature Stable or Decline, or positive in Start-up, Young Growth or High Growth. |

**A flagged company.** Tier 1 uses the phase from the rules and shows the flag with its reason. In tier 2, the bull and bear debate decides the phase.

### 5.6 Pseudo-code

```python
def classify(co, universe):
    """co holds fiscal-year series, oldest first. universe holds the
    distributions computed at this refresh."""
    if co.revenue[-1] == 0 or co.revenue[-4] == 0:
        return "Start-up"

    g3 = (co.revenue[-1] / co.revenue[-4]) ** (1 / 3) - 1
    growth_word = decile_word(g3, universe.growth_deciles)   # 5.3 table

    if growth_word == "Close to zero or negative" and slope(co.revenue[-5:]) < 0:
        return "Decline"

    margin = co.operating_margin[-1]
    m_slope = slope(co.operating_margin[-5:])
    if margin < 0:
        return "High Growth" if m_slope > 0 else "Young Growth"

    if growth_word in ("Very High", "High", "Moderate"):
        return "Mature Growth"
    return "Mature Stable"


def margin_direction(co, universe):      # positive-margin companies only
    m_slope = slope(co.operating_margin[-5:])
    d = decile(m_slope, universe.positive_margin_slope_deciles)
    if d >= 8 and m_slope > 0:
        return "Rising"
    if d <= 3 and m_slope < 0:
        return "Declining"
    return "Stable"
```

`slope` is the least-squares slope against the year index. `decile` returns 1 to 10.

### 5.7 Build details that are not fixed yet (Open)

Decide each one with the user, or propose a policy value:

- Whether the last point of each series is the last fiscal year or the trailing twelve months (TTM).
- Which free cash flow the sign check reads: the last fiscal year, TTM, or the sum of several years.
- A company with fewer than 5 years of history. A suggestion from the ROIC discussion: use the years that exist and flag the row.
- A margin trend slope of exactly zero for a negative-margin company, and a margin of exactly zero.
- Revenue measured in another currency (foreign filers). Growth ratios are not affected, but check the series for mixed currencies (stocks `issue-log.md`, I290).
- Whether the deciles include the excluded sectors (banks, insurers, REITs). Suggestion: no, rank only the companies that the engine values.

### 5.8 Calibration (Decided, after the build)

After the script exists, run it on the universe and count the flagged companies. If the count is high, revisit the rules with the user.

A second test (Proposed): the stocks repo notes name a phase in their old five-phase scheme. 75 of the 114 notes in `stocks/analysis/cycles/2026-10-03/notes/` name a phase, and 171 notes across all cycles do. Map the old labels to the new phases and measure how often the classifier agrees. A rough map, from the conversation of 2026-10-26: Startup → Start-up; Hyper Growth → Young Growth; Operating Leverage → High Growth; Capital Return → Mature Growth or Mature Stable; Decline → Decline. The old scheme is in stocks `docs/valuation-method.md`, section 2.

The stocks method warns that "Classifiers lag" (stocks `docs/valuation-method.md`, section 2). A rule that reads past data shows where the company was. The tier-2 debate exists partly to correct this. Mauboussin and Callahan also find that stages run both ways: within three years, 25% of mature companies move back to growth. So the classifier runs again at every refresh.

---

## 6. The valuation engine

### 6.1 Principles

- **One core, one route per phase (Decided).** The methods per phase come from the literature report. The user accepted them on 2026-10-26 because "they are based on damodaran and others so it seems to me this is best practice".
- **Agents change inputs, never arithmetic (Decided).**
- **The engine refuses when it cannot value (Proposed).** A route returns a value, or a refusal with a reason. Every route returns the same result shape: the value or values, the levels, the stance and the price-implied requirement. Stocks `docs/new-platform-concept.md` section 10 describes a result object that can refuse.
- **No technical inputs (Decided).**

### 6.2 Policy values (Decided, carried from the stocks method v1.7)

| Policy value | Value | Source in the stocks repo |
|---|---|---|
| Required return r | 9% | `docs/valuation-method.md` section 3; `docs/valuation-template.xlsx` |
| Terminal growth gT | 3% | same |
| Runway N by moat class | None 5, Narrow 10, Wide 20 years | same |
| Margin of safety by moat class | None 45%, Narrow 35%, Wide 25% | `docs/valuation-method.md` Step 10 |
| Fair band | 0.85 to 1.15 × the value at belief | Step 10 |
| Trim level | 1.5 × the value at belief | Step 10 |
| Terminal ROIC excess cap | r + 4 points = 13% (Wide moat only) | Decided 2026-10-26, section 6.6 |
| Minimum mature peers for the target-margin default | 3 | Decided 2026-10-26, section 6.7. No source gives this number. |

The literature report checks these values. The 9% fits mature, average-risk companies. The 3% is a legal ceiling when the risk-free rate is at least 3%, and Decline must allow growth at or below zero. The margin-of-safety tiers sit close to Greenwald's "one-third to one-half".

### 6.3 Levels and stance (Decided for the mature routes)

From stocks `docs/valuation-method.md` Step 10 and `gfclient/valuation.py` (lines 307-327):

- **Buy level (the "buy gate")** = value at belief × (1 − margin of safety for the moat class).
- **Fair band** = value at belief × [0.85, 1.15].
- **Trim level** = value at belief × 1.5.

| Price | Stance |
|---|---|
| below the buy level | BUY |
| from the buy level to the bottom of the fair band | ACCUMULATE / HOLD |
| inside the fair band | HOLD |
| above the fair band, below the trim level | HOLD — above fair band |
| at or above the trim level | TRIM |

The stance comes from the valuation levels. It is part of the valuation method, not a portfolio strategy (the user agreed, 2026-10-27).

**Open: levels for the phases without one value.** Start-up shows a price-implied requirement and no value. Young Growth gives a range of values (10th, 50th and 90th percentiles). Decline gives a floor and a distress-weighted value. The literature report notes Damodaran's 2024 view that a margin of safety suits portfolios of mature and declining companies, not venture-like ones, and suggests that the early-phase band width should come from the simulation. A rule for these phases is still needed.

### 6.4 The routes by phase

| Phase | Method | Tier-1 output with no agent | Main agent judgments in tier 2 |
|---|---|---|---|
| Start-up | DCF weighted by failure probability, run as three weighted scenarios | The price-implied requirement (the market share × margin the price needs) and a cash floor. No value. | Market size and its source, eventual share, target margin, scenario weights, failure probability |
| Young Growth | Damodaran's revenue, margin and sales-to-capital DCF, with failure probability and a simulation of 2-3 drivers | A value range when a target margin exists (company target or peer default, 6.7). Else the price-implied margin only. | Revenue story, target margin and the year it is reached, distributions, failure probability |
| High Growth | Three-stage FCFF DCF: a high-growth phase, a 5-year linear fade, and a year-specific cost of capital that falls to 9% | A value when a target margin exists. Else the price-implied margin only. | Length of high growth, target margin, terminal excess return |
| Mature Growth | The stocks reverse DCF, with a reinvestment charge and net income growth (6.5) | A value. This exists today as stocks `mech/1.2`, without the charge. | The growth belief, moat, ROIC |
| Mature Stable | Earnings power value (EPV) plus a stable-growth value that charges reinvestment, reported as the status-quo value; an optional control layer | A value. This is the most reliable phase. | Only the optional control value: the probability of a management change |
| Decline | Run-off DCF of shrinking cash flows with divestiture cash; the higher of going concern and orderly liquidation, weighted by a distress probability; a floor at net current asset value | A floor and a distress-weighted value | Whether the decline can be reversed, and how management responds |

The full engine table, with the scripts' work, the cross-checks and the outputs for each phase, is in the literature report, section "The engine needs one core, six input sets and three probabilities".

### 6.5 Mature Growth: the existing method with three changes

**What stays (Decided).** The stocks method v1.7 (stocks `docs/valuation-method.md`), implemented in stocks `gfclient/valuation.py`:

- the main question: what growth does the price imply?
- r = 9%, terminal growth 3%, the moat runways of 5, 10 and 20 years;
- the three-year consensus path and the guidance ceiling;
- the base-rate check (Step 5) and the written growth belief (Step 6);
- the margin-of-safety tiers, the fair band, the trim level and the expected-return check (Step 9);
- less weight on EPV, the own-history multiple zones and the downside anchor.

**Change 1, a reinvestment charge (Decided).** Discount the cash to equity, not the full earnings:

cash to equity = earnings × (1 − g ÷ ROIC)

The current Step 4 discounts the full EPS and also grows it. That implies an infinite return on new capital. McKinsey marks this form "Overly aggressive" because it "Assumes RONIC equals infinity!" (stocks `docs/growth-duration-research.md` G16; `docs/terminal-rate-research.md` T30 and T39). The corrected formulas are already in stocks `docs/valuation-notes.md`: V98, P/E = (1 − g/ROE)/(ke − g), and V99, Value/NOPLAT = (1 − g/ROIC)/(WACC − g). Every author in the literature report charges growth for its capital: Damodaran, McKinsey, Greenwald and Penman.

The terminal value changes from

EPS_N × (1 + 3%) ÷ (9% − 3%)

to

EPS_N × (1 − 3% ÷ terminal ROIC) × (1 + 3%) ÷ (9% − 3%).

| Terminal ROIC | Terminal multiple of final-year EPS (r 9%, gT 3%) |
|---|---|
| Infinite (the current method) | 17.2× |
| 30% | 15.5× |
| 15% | 13.7× |
| 13% (the Wide-moat cap) | 13.2× |
| 9% (= r) | 11.4× |

The error of the current method always points toward buying. The value at belief is too high, so the levels are too high, and the implied growth is too low. Example from the conversation (Wide moat, N = 20, consensus path 12% then 10%, belief 8%): the current method gives 31.7× NTM EPS. With the charge, the value is 25.5× at a 30% ROIC, 22.4× at 20% and 19.3× at 15%. At a 20% ROIC, the price needs 11.8% growth, not 8%. Recompute these numbers in the tests.

Timing convention (Proposed, as in that example): each year's reinvestment pays for the next year's growth, so cash in year t = earnings in year t × (1 − g in year t+1 ÷ ROIC).

**Change 2, grow net income, not EPS (Decided).** Hold one share count for every year. Per-share EPS growth already includes buybacks. If the model also treats all earnings as paid out, buybacks count twice. Stocks section 1b already holds one share count for stock compensation. The same double count is in Step 9, which adds the buyback yield to per-share growth; fix it there too (Proposed).

**Change 3, more outputs (Proposed).** Show the implied growth at three ROIC values, in the same way as Step 4a shows it at three runways. Add a flag when a 20-year runway carries double-digit growth. Damodaran calls growth periods over ten years at high rates "uncommon". The literature report also suggests a linear fade of growth. That was not adopted for Mature Growth, because Damodaran says a two-stage model "is more appropriate for firms with moderate growth rates" (stocks `docs/growth-duration-research.md` G6).

### 6.6 ROIC rules for the reinvestment charge (Decided)

| Period or case | ROIC used |
|---|---|
| Runway years | The company's 10-year aggregate ROIC: the sum of NOPAT ÷ the sum of operating invested capital, over 10 fiscal years |
| Terminal, Wide moat | The lower of the 10-year aggregate ROIC and 13% (r + 4 points), but never below 9% |
| Terminal, Narrow or no moat | 9% (= r) |
| Invested capital of zero or below | The charge is set to zero, and the row gets a flag |
| High ROIC | No cap |

**Why the aggregate.** The average lets one year with very little capital pull the result up. The median ignores a real bad year, such as a recession, so it overstates ROIC for cyclical companies. The aggregate weights each year by its capital. Example: seven years earn 20 on capital of 100; year 8 earns −10 on 100; year 9 earns 20 on 20; year 10 earns 22 on 110. The average is 25.0%, the median 20.0%, and the aggregate 18.5% (172 ÷ 930). Ten years usually covers a full business cycle; stocks Step 1a says "For cyclical businesses, average over a full cycle."

**Why no cap.** A high ROIC is not a problem in itself. If a company needs little capital to grow, a small charge is correct. Asset-light companies also expense most of the spending that drives their growth (R&D and marketing), so their earnings already carry that cost.

**Invested capital.** Compute it from the operating side: working capital, plus net property and equipment, plus goodwill and acquired intangibles. Do not compute it as debt plus equity, because large buybacks can make equity negative. Include goodwill, because acquisitions are reinvestment (Damodaran). Compute ROIC from its components, so that one definition applies to every company. Do not use a vendor's ROIC field.

**The terminal ROIC literature (stocks `docs/terminal-rate-research.md` and `docs/growth-duration-research.md`).**

- Damodaran (T6): the default is ROIC = cost of capital. A strong and sustainable advantage allows an excess return forever, but it "should be modest (<4-5%)". The 4 points is the low end.
- McKinsey (G16, T30): ROIC = cost of capital is "Overly conservative?" for companies with strong brands.
- Mauboussin (T25) and Morningstar (T36): ROIIC = cost of capital in the terminal period.
- McKinsey (G42): companies that earn less than the cost of capital move up to it. So the terminal ROIC is never below 9%.

**Design rule 3 changes (Decided).** Stocks design rule 3 says "One place per input". Its new form: the moat enters the valuation in two places, the runway N and the terminal ROIC. The two inputs answer different questions: how long growth lasts, and what new capital earns afterwards. The margin-of-safety tier still uses the moat class, as before.

**Cross-check (Proposed).** Show the return on new capital as well: the change in NOPAT ÷ the change in invested capital. It is too unstable to use as a default, but if it is far below the aggregate ROIC, new investment earns less than the old business.

**Build details (Open):** the tax rate for NOPAT; year-end or average invested capital; how to treat leases and excess cash.

### 6.7 Target-margin default for Young Growth and High Growth (Decided)

1. Use the company's own published long-term margin target, if it has one (an investor day or a filing).
2. Else, take the FMP `stock-peers` list. Keep only the peers that are in the tier-1 universe and that the classifier puts in Mature Growth or Mature Stable. For each peer, compute its 10-year aggregate operating margin: total operating income ÷ total revenue. The default is the median across those peers. Damodaran sets mature margins at "averages over the last five or ten years".
3. If fewer than 3 such peers remain, the row shows only the margin that the price needs. It shows no value.
4. The largest peer's margin is the success scenario, not the default. The agent can use it as the optimistic case in tier 2.

**The rule change (Decided).** Stocks `docs/valuation-method.md` section 8, item 4 (line 361) says "A peer's margin is not a source." The new form: "A single peer that an agent chooses is not a source. The median of the vendor's peer list, filtered by a fixed rule, is." Note that stocks `gfclient/preprofit_template.py` cites design rule 1 for the old rule. Design rule 1 bans peer multiples, which are market prices. A peer median margin is an operating statistic, not a price, so it does not break design rule 1. Tell the user about this link when you write the new policy.

**Why not the largest peer.** The largest company usually won on scale and often has the highest margin. In the pre-profit route, value is proportional to the target margin. Example with 5-year aggregate operating margins from FMP: Rivian's mature peers in the universe were Tesla 9.5%, GM 5.4% and Ford 2.9%. The largest-peer rule gives 9.5%, the median 5.4%, so the largest-peer value would be 76% higher. For Snowflake: Oracle 28.8% and SAP 20.4%; the median is 24.6%, 17% below Oracle.

**What FMP peer lists contain.** Rivian: Hyundai (005380.KS), BYD (BYDDY), Ford, GM, Lucid, Li Auto, NIO, Tesla, VinFast, XPeng. Snowflake: MongoDB, Oracle, SAP, Teradata. The lists mix young and mature companies and include companies outside the universe. FMP reports a foreign market cap in local currency (Hyundai's in won), so a "largest" sort without the universe filter is wrong. How FMP chooses peers is not documented in the stocks repo. The GuruFocus API documentation in the stocks repo has no peer endpoint.

**Build order.** Tier 1 must classify every company before it computes these defaults, because the filter uses the peers' phases.

**Rejected options (2026-10-26):** no default for every company (the user wanted a value where possible); Damodaran's industry averages (the user excluded this option); the Base Rate Book sector median (it would make the Step 5 check always pass, which breaks design rule 4, and the book cannot ship in an open-source repo).

### 6.8 Start-up (Decided method; details Open)

From the literature report, section "Start-up and Young Growth":

- **Method:** Damodaran's narrative FCFF DCF, run as three weighted scenarios (McKinsey). Free cash flow = revenue × operating margin × (1 − tax) − reinvestment. Revenue is built from total market × market share. Reinvestment = change in revenue ÷ sales-to-capital.
- **Failure:** value = going-concern value × (1 − p) + distress proceeds × p. The failure probability p comes from survival tables by age and sector, or from default tables by bond rating. Damodaran's spreadsheet holds both (<https://pages.stern.nyu.edu/~adamodar/pc/fcffsimpleginzu.xlsx>). A trap: his age rule subtracts survival rates, which gives an unconditional probability. The conditional probability for a firm that already survived is higher (report: 11.7% against about 31.5% for a six-year-old information firm).
- **Tier 1:** no value. The row shows the price-implied requirement (the market share × margin that the price needs) and a floor at cash. Damodaran and the IPEV guidelines both require a best estimate, so tier 2 produces a scenario value.
- **Cross-checks:** EV/TAM; the VC method run in reverse to an implied IRR.

### 6.9 Young Growth (Decided method; details Open)

- **Method:** the same DCF with revenue history. Damodaran's spreadsheet path: year 1 growth, years 2-5 compounded, then a linear fade to the terminal rate by year 10. Margins converge to the target margin by a target year. A simulation of 2-3 correlated drivers gives the 10th, 50th and 90th percentile values. In tier 1, use a fixed random seed, so the result is deterministic.
- **Inputs from data:** revenue history, the 3-year consensus revenue, the company's own margin target if published.
- **Inputs from rules:** the target margin (6.7), growth after year 3, sales-to-capital, the cost-of-capital path, the failure probability.
- **Cross-checks:** EV/forward sales; the market share implied at the horizon; a Schwartz-Moon stress test.

### 6.10 High Growth (Decided method; details Open)

- **Method:** a three-stage FCFF DCF on revenue, margins and sales-to-capital. Damodaran's template: five high-growth years, then a linear fade over the next five. The cost of capital is "a year-specific number": high while revenue growth peaks, falling to the mature level. Terminal growth is at most the risk-free rate (here at most 3%). Terminal reinvestment = g ÷ ROIC. Flags: a projected ROIC far above the sector's; a high-growth period over 10 years.
- **Tier 1 rules:** five plus five years; terminal growth 3%; the terminal ROIC rule (6.6); the moat from the GuruFocus Moat Score; the target-margin default (6.7).
- **Cross-checks:** a reverse solve on two inputs (growth × duration; margin × sales-to-capital); forward P/E and PEG.

### 6.11 Mature Stable (Decided method; details Open)

- **Method:** EPV = normalized earnings ÷ r, plus a stable-growth value = E × (1 − g ÷ ROIC) ÷ (r − g), reported as the status-quo value. Margins at their 5- to 10-year norm. Damodaran's dividend-to-FCFE test: use FCFE instead of dividends when dividends fall outside 80% to 110% of FCFE over five years. Augmented payout = (dividends + buybacks − long-term debt issued) ÷ net income, averaged over four or five years.
- **Control layer (tier 2 only):** expected value = status quo + (optimal − status quo) × the probability of a management change. Damodaran rejects fixed control premiums.
- **Own-history multiple zones:** a sentiment layer only, behind a test for structural breaks. No author in the literature report supports them as a valuation control.
- **Open:** which of EPV and the stable-growth value is the value at belief for the levels, and which is the cross-check.
- **Proposed:** use the ROIC rules of 6.6 in this formula too. The literature report wrote it with ROE, and the user decided ROIC only for Mature Growth.

### 6.12 Decline (Decided method; details Open)

- **Method:** a run-off DCF with growth at or below zero, including the cash from divestitures. Take the higher of the going-concern value and the orderly-liquidation value. Weight it by a separate distress probability π: going concern × (1 − π) + distress-sale value × π. Add a floor at net current asset value (NCAV) and a value-trap flag.
- **Tier 1 rules:** the decline rate = the 5-year revenue trend; distress-sale value = EBIT × (1 − t) ÷ 9% − debt; recovery rates from Moody's averages; π from a rating table, bond prices or a "naive" distance to default (price, equity volatility and debt).
- **Data:** NCAV, debt, the revenue trend, the Altman Z-score (Z″), the Piotroski F-score.
- **Agent judgments:** whether the decline can be reversed; how management responds (Damodaran's acceptance, denial, desperation or reinvention).
- **Warnings from the literature:** declining firms "look cheap" against their past, and forward multiples "work only if you assume that good health is guaranteed". Do not count divestiture proceeds and also keep the divested earnings in the forecast.

### 6.13 Tier-1 default rules carried from stocks `mech/1.2` (Proposed basis)

The stocks mechanical valuation is a first version of tier 1 for the earnings routes (stocks `docs/mechanical-valuation.md`; code `gfclient/mechanical.py`; command `python3 -m gfclient mechanical NVDA,KO,ASML`).

| Judgment input | `mech/1.2` rule |
|---|---|
| Growth belief, years 4 to N | The median 10-year net income CAGR for the company's sales class, plus 2% for inflation. Source: the Base Rate Book (Mauboussin and Callahan 2016), exhibit 4, printed page 72. |
| Forward EPS (NTM) | The GuruFocus consensus for the four quarters after the last reported quarter, with an SBC correction. Foreign filers use the annual route (I388). |
| Years 2 and 3 | The FMP annual consensus EPS |
| Moat class | The GuruFocus Moat Score: 8 to 10 Wide, 4 to 7 Narrow, 0 to 3 None. No score gives None. |
| Non-recurring items | The vendor's gap: EPS TTM minus EPS without NRI. "Nobody reviews it." |
| Gate | FAIL on an equity raise, a negative TTM FCF, or capex above 50% of OCF |

Two problems for the new project:

- **The Base Rate Book cannot ship.** Stocks `docs/sources/README.md` lists it as a private reference copy: "never redistribute". The belief rule needs a source that an open-source user can get, or each user supplies their own copy (Open).
- **The gate's purpose changes.** The stocks Step 0 gate answers "is this a capital-return company?". The phase classifier now answers that question. Decide whether the gate becomes a set of flags or is retired (Open).

---

## 7. Tier 2: the agent analysis

### 7.1 The roles (Decided, adapted from TradingAgents)

| TradingAgents role | In this project |
|---|---|
| Market Analyst (technical) | Replaced by a **Valuation Analyst**. It reads the engine's output and explains it in plain words. It proposes the judgment inputs, such as the growth belief and the moat. |
| Fundamentals Analyst | Kept. It feeds the phase, the moat and the growth belief. In the full report it also writes the business, industry and financial sections (Proposed). |
| News Analyst | Kept, with social media merged into it. It finds kill criteria and explains large price moves. |
| Social Media Analyst | Merged into the News Analyst. |
| Bull and bear researchers | Kept. They argue about the judgments (phase, moat, belief, ROIC, kill criteria), not only about buy or sell. |
| Research Manager | Kept. It decides the judgments and turns them into input overrides. |
| Trader, risk team, Portfolio Manager | See 7.2. The stance comes from the engine's levels. |

Proposed additions: guru trades, insider trades and analyst estimate revisions from GuruFocus and FMP as News Analyst inputs.

### 7.2 The flow

```
tier-1 snapshot (frozen: rules version, data date, price date)
 -> analysts: Fundamentals, News (includes social), Valuation
 -> bull and bear debate about the judgments: phase, moat, belief, ROIC, kill criteria
 -> research manager decides the judgments -> input overrides, each citing a finding
 -> engine recomputes -> reviewed value, levels, value bridge
 -> risks and kill criteria
 -> stance from the engine's levels
 -> report (reader part + Appendix A + Appendix B)
```

**A conflict to confirm with the user (Proposed resolution).** On 2026-10-26 the flow had a risk review and a portfolio-manager step that read the user's holdings and suggested a transaction. On 2026-10-27 the user parked the portfolio strategy and dropped the "Your position" section from the stock report. The holdings now appear only in the portfolio review that the user asks for (section 10). So the stock analysis should not read the holdings: the risk step writes the risks and kill criteria, and the stance comes from the levels. Confirm this with the user.

### 7.3 Overrides

- **An override changes one input (Decided).** It records the input, the old value, the new value, the reason and the evidence (a filing, a transcript, a base rate). Every override cites the analyst finding that supports it.
- **Tags (Decided):**
  - **Lasting:** the growth belief, the moat, ROIC, the target margin. They stay until the user asks for an updated valuation.
  - **Tied to a period or a data point:** for example, a one-off legal settlement in one quarter, or a correction of a vendor error. They drop at the next full refresh. An override also drops when the data it corrected changes, for example when the vendor fixes the error. To detect this, store the value that the override corrected.
- **Limits (Proposed):**
  - Locked inputs: r, the terminal growth ceiling and reported data.
  - Inputs that need extra evidence: for example, a belief above the base-rate 90th percentile, or a ROIC above the company's own 10-year high.
- **Logging (Proposed).** Log the mechanical value and the reviewed value at every update. After some time, the log shows whether the agents' overrides beat the mechanical value in each phase. The literature report notes that no study has tested which method is most accurate at each life-cycle stage, so this log would be new evidence. Also log the phase, the method and the prediction.

### 7.4 The value bridge (Decided)

The report shows a bridge from the mechanical value to the reviewed value, one override per line. Apply the overrides in a fixed order, the order of the method's steps, because their effects do not add up exactly. Example with made-up numbers:

| Step | Value per share |
|---|---|
| Mechanical value | $180 |
| Growth belief 7% → 9%: new product line, guidance raised | +$28 |
| ROIC 25% → 18%: acquisitions raise the capital needed for growth | −$17 |
| Legal settlement reclassified as non-recurring | +$4 |
| Reviewed value | $195 |

### 7.5 Two modes (Decided)

| Mode | What it includes |
|---|---|
| **Valuation review** | Every report section except "The business" and "Industry and competition" |
| **Full report** | Every section |

The business changes slowly, but the valuation inputs change every quarter. So a valuation review reuses the last full report, if one exists. It shows the date of that report, and the moat judgment starts from it. If no full report exists, the review says so, and the moat judgment starts from the tier-1 moat class.

---

## 8. The validity window (Decided)

- The whole result for a stock is valid until the company's next earnings report: the tier-1 value and phase, the tier-2 report, the stance and all overrides.
- When no report date is known, the window is 3 months.
- After the window ends, the result stays visible with an "expired" mark. Nothing refreshes by itself.
- GuruFocus and FMP both publish earnings dates (FMP `earnings-calendar` is in stocks `fmpclient/registry.py`).
- Foreign filers that report twice a year or once a year get a window of about 6 or 12 months, because the window ends at their next report.

**Known limit.** Events between reports, such as a guidance cut, an acquisition or a CEO exit, do not end the window. This is the cost of refreshing only on request. The user can ask for a refresh at any time. The screen can show the price change since the valuation as a hint (Proposed).

---

## 9. The report

### 9.1 Why readability is a hard requirement

The user called the stocks reports "terrible from a readability standpoint". A stocks note, for example `stocks/analysis/cycles/2026-10-03/notes/CRM.md`, shows five faults:

- The answer comes after a dense table of 13 rows.
- Internal codes fill the prose, such as "I382", "row 41" and "C13".
- Numbers have four decimals, such as "8.9145".
- Some sentences run longer than 80 words.
- Terms such as "gate", "carrier" and "4c" appear with no meaning given.

The user liked the readability of the TradingAgents reports (examples in `/mnt/c/users/kaban/documents/workspace/TradingAgents/reports/`), but not their missing valuation.

### 9.2 Rules (Decided)

- **Two parts.** The reader part holds only plain text and rounded numbers. Appendix A holds the codes, sources, cell values and formulas. Every number in the reader part has a matching row in Appendix A.
- Put the answer first in each section.
- Keep sentences short, with one idea in each.
- Explain each term the first time it appears.
- Round numbers: prices to cents, values to whole dollars, percentages to one decimal.
- Keep the summary to one page and the reader part to about five pages.
- The layout is the same for every stock. Only the valuation section changes with the phase.
- **Number check (Proposed).** Code checks that every number in the report text comes from a tool output, and rejects the report if one does not. Stocks `gfclient/verify.py` checks a verdict against its workbook and can be a model.

### 9.3 Sections (Decided)

| # | Section | Mode | Content |
|---|---|---|---|
| 1 | Summary | both | One page: the stance; the value against the price and the levels; the phase in one sentence; three reasons for; three risks; what would change the view; the end of the validity window |
| 2 | The business | full report | Products (10-K Item 1); revenue mix by product and region over 3 years (segment data); revenue drivers (price, volume, users, contracts; recurring or one-time); customers (including any customer at 10% or more of revenue, which companies must disclose); unit economics (gross margin; incremental margin: the share of each extra dollar of revenue that became operating profit) |
| 3 | Industry and competition | full report | Value chain (suppliers, customers, where the profit goes); industry size and growth; competitors (vendor peer list and 10-K); position (market share and rank); moat by Damodaran's five sources: brand name, switching costs, network effect, cost advantages, efficient scale (CLC chapter 3, slide 13). It ends with a plain answer to "are the economics favorable?", based on the gross margin, the incremental margin against the average margin, and ROIC against the 9% cost of capital. The frame follows the industry analysis in Mauboussin and Callahan, "Measuring the Moat". |
| 4 | Financial performance and health | both | Six parts, each a 5-year table plus two or three plain sentences: growth and profitability (revenue, growth, gross, operating and net margin, EPS); cash flow (operating cash flow, capital spending, free cash flow, free cash flow ÷ net income, stock compensation ÷ revenue); balance sheet and solvency (cash, debt, net debt ÷ EBITDA, interest coverage, current ratio, and the cash runway for a company that loses money); returns on capital (ROIC and ROE by year, the 10-year aggregate ROIC against 9%); capital allocation (dividends, buybacks, share count change, acquisitions); quality scores (Piotroski F, Altman Z, Beneish M; GuruFocus publishes all three) |
| 5 | Life-cycle phase | both | The phase, the growth word and the margin direction behind it, any check flag, and the Dickinson stage. If tier 2 changed the phase, why. |
| 6 | Valuation | both | The growth the price needs; the belief and why; the value and the levels; the value bridge; a small sensitivity table. For Start-up: the price-implied requirement. For Decline: the floor and the distress-weighted value. |
| 7 | Price facts and multiples | both | Section 9.5 |
| 8 | Key judgments | both | For each judgment (phase, moat, growth belief, ROIC, target margin where used): the bull view, the bear view and the decision |
| 9 | Recent news | both | Dated items that matter to the value |
| 10 | Risks and kill criteria | both | Measurable events that would prove the view wrong |

In section 4, the measures that matter most for the phase come first. Damodaran's pricing table (CLC chapter 9, slide 15, <https://pages.stern.nyu.edu/~adamodar/pdfiles/CLC/slides/Ch9.pdf>) names them:

| Phase | What matters most |
|---|---|
| Start-up | "Potential Market, Capital Acccess" |
| Young Growth | "Revenue growth, Gross margins" |
| High Growth | "Revenue growth, Oper margins" |
| Mature Growth | "Earnings growth" |
| Mature Stable | "Earnings stability" |
| Decline | "Book Value" |

In tier 1, scripts compute all the numbers. In tier 2, the analysts write the sentences.

**Dropped (Decided 2026-10-27):** a "Your position" section. The user's holdings appear only in the portfolio review.

### 9.4 Appendixes (Decided)

- **Appendix A, the audit.** Every input with its tag (DATA, RULE or JUDGMENT), its source, its date and its value at full precision; the overrides with their tags and reasons; the formulas; the checks that ran; the rules version and the method version; the classifier evidence.
- **Appendix B, the glossary.** The plain meaning of each term in the report.

### 9.5 Price facts and multiples (Decided)

A script computes every item. None of them is a target.

| Group | Items |
|---|---|
| Price facts | Current price; 52-week high and low; 1-, 3- and 5-year change; drop from the last peak |
| Earnings multiples | Trailing and forward P/E, each on two bases side by side: the clean P/E (the method's earnings basis) and the reported P/E (the vendor's figure). Show them in every phase where earnings are positive. |
| Phase multiples | Damodaran's pricing metrics for the phase (below) |

The two P/E bases can differ a lot. In the stocks Alphabet example, the raw trailing P/E was 16.7× and the clean one was 33.5×.

| Phase | Multiples to show (Damodaran CLC chapter 9, slide 15) |
|---|---|
| Start-up | EV/TAM, EV/Users, EV/Subscribers |
| Young Growth | EV/Forward Sales |
| High Growth | EV/Sales |
| Mature Growth | PEG, Forward P/E |
| Mature Stable | P/E, EV/EBITDA |
| Decline | P/B, EV/Liquidation value |

Proposed: show each P/E against the company's own 5- and 10-year range as data. The literature report finds no support for own-history zones as a valuation control, so they never set the value or the stance.

### 9.6 Example summary page (invented company and numbers)

```
EXAMPLE CORP (EXMP)                                       27 Oct 2026
Valid until the next earnings report on 3 Dec 2026

STANCE: ACCUMULATE / HOLD
The price of $234.70 is below our value of $283,
but above the buy level of $212.

   Buy below      Fair band          Trim above
   $212           $240 to $325       $424
        ^ price $234.70

PHASE: Mature Growth
Revenue grew 11% a year over 3 years, which is high for its size.
The operating margin is positive and rising.

WHY WE LIKE IT
 1. ...
 2. ...
 3. ...

MAIN RISKS
 1. ...
 2. ...
 3. ...

WHAT WOULD CHANGE OUR VIEW
 - Revenue growth below 5% for two quarters in a row.
```

---

## 10. The portfolio layer (Decided)

The user's words (2026-10-27): "Keep the portfolio part simple, yes there is a transaction ledger, and prices / value of portfolio are updated on every refresh. Park the whole porfolio strategy side. I can ask an agent anytime to review the portfolio and provide advice, not need to put a set strategy."

- **A transaction ledger**, stored as a table in the project database, not in a flat file. It records only the trades that the user reports.
- **Positions and cash**, computed from the ledger.
- **Market value**, updated with current prices at every refresh.
- **A portfolio review**, by an agent, only when the user asks. It gives advice without fixed rules.
- **No strategy:** no sleeves, no size bounds, no concentration rules, no monitoring.
- **Do not reuse** the portfolio approach of the stocks repo: `stocks/screening-plan.md` (sleeves and sizing bounds) and `stocks/.claude/skills/portfolio-manager/SKILL.md`.
- **Append-only rows (Proposed).** Never change or delete a ledger row. To fix a mistake, add a row that reverses the wrong one. The table then keeps the full history.

---

## 11. Data

### 11.1 Vendors

**Source-selection clarification (Decided, 2026-10-28).** Map every required input against FMP first. If FMP supplies all required data with the needed definitions, history and company coverage, use FMP alone and drop GuruFocus from the integration and account requirements. Otherwise use GuruFocus only for the required gaps it can supply. Validate account entitlement separately. The outcome is not yet known; keep required method inputs, including moat and adjusted-earnings inputs, in that mapping. The named sources below record known reference endpoints, not a requirement to fetch the same dataset from both vendors.

The user already has paid GuruFocus and FMP subscriptions; this does not require every Fairband user to have both. Stocks has working clients for both, plus an SEC EDGAR client:

| Client | Location | Notes |
|---|---|---|
| GuruFocus | `stocks/gfclient/` (`client.py`, `registry.py`, `normalize.py`, `store.py`) | `stocks/docs/gf-api-notes.md` records the vendor traps. `stocks/docs/gf-api-documentation.md` is a verbatim copy of the vendor documentation: never edit it. |
| FMP | `stocks/fmpclient/` (`client.py`, `registry.py`, `store.py`, `test_scrub.py`) | CLI: `python3 -m fmpclient get <endpoint> key=value` |
| SEC EDGAR | `stocks/edgar/` | For 10-K text: Item 1 (business), customers at 10% or more, segment notes |

Other stocks documents about data: `stocks/data-contract.md`, `stocks/quirk-register.md`, `stocks/docs/client-design.md`, `stocks/docs/fallback-clients-design.md`, `stocks/docs/collection-design.md`.

### 11.2 Endpoints this design needs

| Need | Source | Status |
|---|---|---|
| Financial statements, 10+ years | FMP `income-statement`, `balance-sheet-statement`, `cash-flow-statement` preferred; GuruFocus `financials` only for required gaps | Validate depth, definitions and coverage (11.3) |
| Peer lists | FMP `stock-peers` (registry key `peers`) | Known. GuruFocus has no peer endpoint in the stocks docs. |
| Revenue mix | FMP `revenue-product-segmentation` and `revenue-geographic-segmentation`; GuruFocus segments data | Known |
| Consensus estimates | GuruFocus `analyst_estimate`, `estimate_history`; FMP `analyst-estimates` | Known (used by `mech/1.2`) |
| Moat score | GuruFocus Moat Score | Known (used by `mech/1.2`) |
| Earnings dates | FMP `earnings-calendar`; GuruFocus calendar | Known |
| Market cap, sector, industry | FMP `profile`, `company-screener` | Known |
| Quality scores | GuruFocus (Piotroski F, Altman Z, Beneish M) | Check the field names at build time |
| Prices and price history | GuruFocus `price`; FMP | Known |
| 10-K text | SEC EDGAR | Known |

### 11.3 History depth and one vendor per series

- **Source order decided; coverage validation pending (2026-10-28):** check FMP first for the required history series. Use GuruFocus only where FMP cannot supply required data and GuruFocus can. If FMP covers all required inputs, drop GuruFocus. Check plan access and actual annual depth during data mapping.
- **A correction to the conversation.** On 2026-10-26 Claude said that the FMP plan returns at most 5 years of statements. The stocks registry says otherwise: "limit above 5 returned 402 on the free tier; the Premium tier serves limit=20 (verified 2026-09-08, PG quarterly)" (`stocks/fmpclient/registry.py`, `income_statement` row). Twenty quarters is 5 years. Whether the Premium tier serves 10 or more years of annual statements is not checked. Check it before deciding.
- **Recommendation (Proposed).** Take every history series from one vendor: revenue, margins, NOPAT, invested capital. The two vendors can define operating income and invested capital differently. A target margin from one vendor applied to figures from the other could then differ only because of the definitions.

### 11.4 Foreign listings (Proposed)

Foreign companies on a U.S. exchange need four checks:

- **The ADR ratio.** One ADR can equal several ordinary shares, or a fraction of one. EPS and price must use the same unit.
- **Currency.** Fields can mix currencies (stocks `issue-log.md`, I290).
- **Report frequency.** Many report once or twice a year. They need the annual route for forward EPS (stocks `issue-log.md`, I388; `docs/mechanical-valuation.md`).
- **IFRS.** The earnings basis needs the same adjustments as under U.S. GAAP.

### 11.5 Point-in-time data (Proposed)

TradingAgents has point-in-time date rules in `tradingagents/dataflows/date_window.py` and a `backtest` command. Reuse the idea, so that a valuation can be rerun as of a past date for testing.

---

## 12. Storage (Decided)

- One database holds the screen rows with their history, the snapshots, the overrides, the reports, the prices and the ledger.
- The database technology is not chosen yet (Deferred). The user said: "no need to select specific techologies now, we agree we will use a db".
- The database file lives in a local data folder that git ignores. The repository holds only the code and the table definitions.

---

## 13. Open source, keys and private material

### 13.1 Rules (from stocks `CLAUDE.md`; keep them)

- **API keys.** Never print a key, never put one in a command, never print a URL that carries one, and never write one to a log. Keep key files outside the repository. Stocks has a URL scrub with a test (`stocks/fmpclient/test_scrub.py`); keep the scrub and its test.
- **Vendor data.** Never commit vendor data. Each user brings keys for the selected sources: FMP, plus GuruFocus only if data mapping identifies required gaps that it supplies. If FMP covers all required inputs, no GuruFocus integration or key is needed. The data stays on the user's machine. The stocks `data/` folder held 58,387 vendor files on 2026-10-26.
- **Raw files.** In the stocks repo, never `cat` a file under `data/raw/`; use `python3 -m gfclient read <path> --keys` or `--at`.
- **Private sources.** The files in `stocks/docs/sources/` are "Private reference copies; never redistribute" (`stocks/docs/sources/README.md`). This includes the Base Rate Book and the Greenwald slides. The literature report in this workspace links to `../../stocks/docs/sources/greenwald-epv-lecture-slides.pdf` four times. Remove those links before the report goes into a public repository.
- **Damodaran's data.** If the project uses Damodaran's spreadsheets or datasets, download them at run time and do not commit a copy. His redistribution terms are not checked.

### 13.2 Licenses

- TradingAgents is Apache-2.0 (`/mnt/c/users/kaban/documents/workspace/TradingAgents/LICENSE`). Copied files must keep the license notice and record their origin.

### 13.3 A free data path (Proposed)

The initial data path uses paid FMP, supplemented by paid GuruFocus only if required gaps remain; GuruFocus is dropped if FMP covers every required input (clarified 2026-10-28). A free path would broaden access. Consider SEC EDGAR, with Yahoo as the last fallback.

---

## 14. Deferred decisions

| Decision | Facts known |
|---|---|
| Required-data gaps after checking FMP | 11.3. Source order is decided: FMP first, GuruFocus only for required gaps it supplies; omit GuruFocus if none remain. Actual definitions, depth, coverage and account access still need validation. |
| The database technology | SQLite and DuckDB were mentioned. The user wants no choice now. |
| The LLM provider | Anthropic's terms do not let a third-party app use a Claude subscription, so Claude needs an API key. TradingAgents v0.7.0 supports a ChatGPT Plus or Pro sign-in in place of an OpenAI API key. |
| A new repository or a fork of TradingAgents | Claude recommended a new repository (2026-10-26): TradingAgents is built for a one-date trade decision, with Yahoo as the default data source and technical analysis at the center, so most of it would change and every upstream update would need a merge. Copy files under Apache-2.0 instead. Upstream FMP pull requests #1575 and #1576 add an FMP data source. |

---

## 15. Open design items

1. **Levels and stance for Start-up, Young Growth and Decline** (6.3).
2. **The High Growth cost-of-capital path.** Damodaran starts high and falls to the mature level, and he allows "the 90th or 95th percentile" of the cross-section of costs of capital when no usable beta exists. Stocks design rule 1 forbids market-derived discount rates. A rule is needed that fits both, for example a policy starting value.
3. **The sales-to-capital source** for Start-up, Young Growth and High Growth. Damodaran uses industry averages from his dataset; the user excluded that option for the target margin. Candidates: the same filtered peer median as the target margin, or the company's own history.
4. **Failure probability data** for Start-up and Young Growth: survival tables by age and sector, default tables by rating, and a source for company age.
5. **Decline inputs:** the source of π (rating, bond prices or distance to default), the recovery fraction, and the NCAV floor. The literature report suggests a distress override (below investment grade, or a ten-year π of about 20% or more, sends a company to Decline). It calls that threshold its own suggestion, and the user did not adopt it.
6. **The growth-belief source.** The `mech/1.2` rule needs the Base Rate Book, which cannot ship (6.13).
7. **The stocks Step 0 gate:** keep it as flags, or retire it (6.13).
8. **Mature Stable:** which value sets the levels (6.11).
9. **Valuation review mode:** which analysts run in it.
10. **The tier-2 flow and the holdings** (7.2).
11. **Classifier build details** (5.7).
12. **ROIC build details** (6.6).

---

## 16. Suggested build order (Proposed)

1. Move the data clients and the valuation code from the stocks repo into the new repository, with their tests.
2. Build the phase classifier. Run it on the universe and count the flags (5.8).
3. Add the Mature Growth changes (6.5, 6.6) and test them against the numbers in this document.
4. Write the report schema and the code that renders the report. Test it with a real company before you add any agent.
5. Add the other routes, one phase at a time, starting with Mature Stable.
6. Add the agents, one role at a time.
7. Add the number check, then the backtest.

---

## 17. Pointers to sources and documents

### 17.1 This workspace (`/mnt/c/users/kaban/documents/workspace/openalice/`)

| Path | What it holds |
|---|---|
| `reports/Valuation methods by life cycle phase.md` | The literature report: methods per phase, the engine table, the reinvestment-charge analysis, and every source link. Read it first. |
| `research_notes/Valuation methods by life cycle phase/damodaran_framework_and_early_phases.md` | Damodaran's phases, markers, decile grid, pricing tables, Start-up and Young Growth methods, failure tables |
| `research_notes/Valuation methods by life cycle phase/damodaran_high_and_mature_growth.md` | High Growth and Mature Growth: fade, return on capital, reinvestment |
| `research_notes/Valuation methods by life cycle phase/damodaran_mature_stable_and_decline.md` | Mature Stable, control value, Decline, distress |
| `research_notes/Valuation methods by life cycle phase/practitioner_methods_by_stage.md` | McKinsey, Mauboussin and Callahan, Greenwald, Penman, CFA; Dickinson's sign rules |
| `research_notes/Valuation methods by life cycle phase/early_stage_and_decline_methods.md` | VC methods, real options, Schwartz-Moon, liquidation and distress, academic evidence by stage |
| `design/hybrid-project-design.md` | This document |

### 17.2 The stocks repo (`/mnt/c/users/kaban/documents/workspace/stocks/`)

| Path | What it holds |
|---|---|
| `CLAUDE.md` | The key, raw-data and documentation rules (13.1) |
| `docs/valuation-method.md` | The expectations method v1.7: design rules (section 1), the old five phases (section 2), policy values (section 3), Steps 0-11 (section 4), the Alphabet worked example (section 5), known limits (section 7), the pre-profit route (section 8) |
| `docs/mechanical-valuation.md` | The `mech/1.2` rules, the command, the margin flag |
| `docs/valuation-notes.md` | Verified valuation claims with sources; V98 and V99 hold the reinvestment formulas |
| `docs/terminal-rate-research.md` | Terminal-period research; T6, T25, T30, T36, T39; open questions in section 6 |
| `docs/growth-duration-research.md` | Growth-period research; G6, G16, G42 |
| `docs/new-platform-concept.md` | An earlier concept paper. Section 10 (the valuation engine, a result object that can refuse) and section 11.2 (the agent contract) are relevant. Its web product, tenancy and billing sections are not. |
| `docs/valuation-method-adoption.md`, `docs/warranted-grid.md`, `docs/H_FACTOR_SPEC.md` | Method history and related specs |
| `docs/sources/README.md` and `docs/sources/` | Private copies of the primary sources. Never redistribute. |
| `docs/gf-api-notes.md`, `docs/gf-api-documentation.md` | GuruFocus traps; the vendor documentation (never edit) |
| `docs/client-design.md`, `docs/fallback-clients-design.md`, `docs/collection-design.md` | Client design |
| `gfclient/valuation.py`, `gfclient/mechanical.py`, `gfclient/preprofit.py`, `gfclient/preprofit_template.py` | The method in code, the mechanical valuation, the pre-profit route |
| `gfclient/test_valuation.py`, `gfclient/test_mechanical.py`, `gfclient/test_preprofit.py` | Their tests |
| `gfclient/verify.py` | The check of a verdict against its workbook; a model for the number check |
| `gfclient/normalize.py`, `gfclient/store.py`, `gfclient/registry.py` | The GuruFocus parser, store and endpoint table |
| `fmpclient/registry.py` | The FMP endpoint table, with tier notes |
| `edgar/` | The SEC EDGAR client |
| `workflow-outline.md` | Principle 3: "Scripts compute; agents judge." |
| `issue-log.md` | Issue history; I290 (currency mix), I388 (annual route) |
| `analysis/cycles/2026-10-03/notes/` | Old notes: examples of the unreadable style, and phase labels for calibration |
| `mechanical-valuations.xlsx` | The current mechanical screen output |
| `screening-plan.md`, `.claude/skills/portfolio-manager/SKILL.md`, `.claude/skills/ledger/SKILL.md` | The stocks portfolio approach. Do not reuse. |

### 17.3 TradingAgents (`/mnt/c/users/kaban/documents/workspace/TradingAgents/`)

Version 0.7.0, commit `e8f5503` (2026-10-16), Apache-2.0.

| Path | What it holds |
|---|---|
| `tradingagents/agents/analysts/` | The analyst roles, including `fundamentals_analyst.py` and `news_analyst.py` |
| `tradingagents/agents/researchers/` | The bull and bear researchers |
| `tradingagents/agents/managers/` | The research manager and `portfolio_manager.py` |
| `tradingagents/agents/risk_mgmt/`, `tradingagents/agents/trader/` | The risk team and the trader |
| `tradingagents/agents/schemas.py` | Typed outputs. `price_target` is optional (line 253), which is why recent reports have no target. |
| `tradingagents/agents/structured.py` | The structured-output helpers, including the rule "if something is missing, say so explicitly" |
| `tradingagents/agents/tools.py` | The 12 agent tools. None computes a valuation. |
| `tradingagents/dataflows/date_window.py` | Point-in-time date rules |
| `tradingagents/graph/trading_graph.py` | The agent graph |
| `reports/` | Example reports. Their readability is the model; their price targets were chart levels. |

### 17.4 External literature (main links; the literature report has the full list)

- Damodaran, *The Corporate Life Cycle* chapter slides: <https://pages.stern.nyu.edu/~adamodar/pdfiles/CLC/slides/Ch2.pdf>, `Ch3.pdf`, `Ch9.pdf` to `Ch13.pdf` in the same folder.
- Damodaran, CLC preface deck: <https://pages.stern.nyu.edu/~adamodar/pptfiles/CLC/CLCPreface.pdf>
- Damodaran, Ginzu spreadsheet (failure and default tables, cost-of-capital path): <https://pages.stern.nyu.edu/~adamodar/pc/fcffsimpleginzu.xlsx>
- Damodaran (2009), "Valuing Young, Start-up and Growth Companies": <https://pages.stern.nyu.edu/~adamodar/pdfiles/papers/younggrowth.pdf>
- Damodaran (2009), "Valuing Distressed and Declining Companies": <https://pages.stern.nyu.edu/~adamodar/pdfiles/papers/NewDistress.pdf>
- Damodaran, "Return on Capital": <https://pages.stern.nyu.edu/~adamodar/pdfiles/papers/returnmeasures.pdf>
- Damodaran, "The Value of Control": <https://pages.stern.nyu.edu/~adamodar/pdfiles/papers/controlvalue.pdf>
- Koller, Goedhart and Wessels, continuing-value deck: <https://finance.wharton.upenn.edu/~wessels/valuation5e/powerpoint/Chapter_10.ppt>
- Mauboussin and Callahan (2023), "Trading Stages in the Company Life Cycle": <https://web.archive.org/web/20260915034622/https://www.morganstanley.com/im/publication/insights/articles/article_tradingstagesinthecompanylifecycle.pdf>
- Dickinson (2011), "Cash Flow Patterns as a Proxy for Firm Life Cycle", *The Accounting Review* 86(6): 1969-1994 (abstract: <https://academicnewsletter.sufe.edu.cn/info/415904>)
- Mauboussin and Callahan, "Measuring the Moat" (industry analysis frame for report section 3; not in the research notes, so fetch and cite it before use)

---

## 18. Glossary

| Term | Meaning |
|---|---|
| Tier 1 | The script that values every company in the universe with fixed rules |
| Tier 2 | The agent analysis of one company that the user picks |
| Phase | One of Damodaran's six life-cycle phases |
| Route | The valuation method that the engine runs for a phase |
| Value at belief | The value per share at the growth belief; the single price target |
| Buy level ("buy gate") | Value at belief × (1 − margin of safety) |
| Fair band | 0.85 to 1.15 × the value at belief |
| Trim level | 1.5 × the value at belief |
| Stance | BUY, ACCUMULATE / HOLD, HOLD, HOLD — above fair band, or TRIM, from the price against the levels |
| Growth belief | The written growth rate for years 4 to N |
| Runway N | The years of above-terminal growth, set by the moat class (5, 10 or 20) |
| Moat class | Wide, Narrow or None |
| Price-implied requirement | What the price needs to be true, such as a growth rate, a margin or a market share |
| Reinvestment charge | The share of earnings that growth needs, g ÷ ROIC, taken out before discounting |
| NOPAT | Operating profit after tax |
| Invested capital | Working capital + net property and equipment + goodwill and acquired intangibles |
| Aggregate ROIC | The sum of NOPAT ÷ the sum of invested capital over 10 years |
| Terminal ROIC | The return on new capital assumed after the runway |
| EPV | Earnings power value: normalized earnings ÷ r, the value with no growth |
| FCFF | Free cash flow to the firm |
| Sales-to-capital | Revenue added per dollar of new invested capital |
| Failure probability p | The chance that a young company fails |
| Distress probability π | The chance that a declining company falls into distress |
| NCAV | Net current asset value: current assets minus all liabilities |
| Decile | One of 10 equal groups after ranking; decile 10 holds the top 10% |
| Trend line | The least-squares slope through the last 5 yearly values |
| DATA, RULE, JUDGMENT | The input tags: vendor or filing data; a versioned policy with a source; an agent's choice with a reason |
| Override | An agent's change to one input, with a reason and evidence |
| Lasting override | An override that stays until the user asks for an updated valuation |
| Period-tied override | An override that ends when its period or data point leaves the data |
| Value bridge | The table from the mechanical value to the reviewed value, one override per line |
| Validity window | The time until the company's next earnings report, or 3 months when no date is known |
| Check flag | A warning from the classifier checks; it never changes the phase |
| Kill criterion | A measurable event that would prove the investment view wrong |

---

## Appendix: decision log

| Date | Decision |
|---|---|
| 2026-10-25 | No brokerage connection. The user places every trade. |
| 2026-10-26 | Build a new open-source hybrid project from the stocks method and TradingAgents-style research. |
| 2026-10-26 | Damodaran's six phases. Dickinson's signs as one classifier input (narrowed on 2026-10-27 to display only). |
| 2026-10-26 | Banks, insurers and REITs out of scope for now. |
| 2026-10-26 | The methods per phase from the literature report are accepted as best practice. |
| 2026-10-26 | Mature Growth: keep the method, add the reinvestment charge, grow net income instead of EPS. |
| 2026-10-26 | No technical analysis and no technical price target. One price target from the engine. A price facts and multiples section, with trailing and forward P/E. |
| 2026-10-26 | Two tiers. Tier 1 covers Mega, Large and Mid caps on U.S. stock exchanges. Tier 2 is a complete TradingAgents-style analysis without technical analysis. |
| 2026-10-26 | Refresh only on request. Overrides stay until the user asks for an updated valuation. A validity window (the user's idea). |
| 2026-10-26 | ROIC: the 10-year aggregate, no cap, the charge floored at zero, invested capital from the operating side with goodwill. |
| 2026-10-26 | Terminal ROIC option A: 9% by default; Wide moat uses the lower of the aggregate ROIC and 13%, never below 9%. Design rule 3 changes. |
| 2026-10-26 | Target-margin default: the company's own target, else the median of mature FMP peers in the universe; fewer than 3 gives the price-implied margin only; the largest peer is the success scenario. |
| 2026-10-26 | History depth: an FMP upgrade or GuruFocus (vendor deferred). |
| 2026-10-27 | Classifier decision 1: revenue growth and operating margin name the phase; free cash flow sign is a check; reinvestment is not used. |
| 2026-10-27 | Classifier decision 2: revenue growth deciles of the tier-1 universe, two per word; margin words are the sign; Start-up when 3-year growth cannot be measured. |
| 2026-10-27 | Classifier decision 3: 5-year trend lines; sign only for negative margins; deciles 8-10, 4-7, 1-3 for positive margins, with the sign safeguard. |
| 2026-10-27 | Classifier decision 4: the four ordered rules and the three checks; Dickinson shown only; flagged companies decided in the tier-2 debate. |
| 2026-10-27 | The validity window covers the whole result for a stock and ends at the next earnings report; 3 months when no date is known. |
| 2026-10-27 | Portfolio: a ledger table, values at each refresh, an on-request portfolio review, no strategy, no reuse of the stocks portfolio approach. |
| 2026-10-27 | A database, technology not chosen; the data stays outside the repository. |
| 2026-10-27 | The report: readability rules, ten sections, two appendixes, two modes; the "Your position" section dropped. |
| 2026-10-27 | OTC listings excluded. EquityEval not related. |
| 2026-10-27 | The project name is Fairband. EquityEval stays reserved for another project. |
