"""A report's appendixes, its references and its Markdown (spec 2026-11-06 Tier 2, 13.1 and 13.6;
design.md 9.4; ``method.md`` 16).

Neither appendix is stored: both are generated at read time from the stored records, so the agent
writes neither. Appendix A (``appendix_a``), the audit: the snapshot the report rests on, with
the reporting currency its money figures are in (``currency``, ``types.money_of``); every
input with its tag (DATA, RULE or JUDGMENT), its value at full precision and its provenance (its
source and its three dates: as of, observed, entered), the review's when the report rests on one
(its JUDGMENT entries beside the snapshot's own), else the snapshot's; the overrides inside the
review with their reasons and evidence, each with its stored pair and, where the review applied it
at a figure other than the one entered because a split fell between, the review's pair in force
and the words of the scaling (``inForce``, ``rescaled``; spec 2026-11-15 8), which the export's
row prints in place of the stored pair, the words after the new figure in brackets; the guidance
on file, the company's guidance records written by the report's time, newest first, each with its
figures and their currency (``currency``: the record's stored code, else the reporting currency of
the report's own snapshot, none for a percent; spec 2026-11-15 9.1, 9.5), which the export's
table names in a column of its own after the midpoint, its figures bare, its basis, its call's
date, whether a record on file by then superseded it, and the overrides inside the review that
cite it; the bridge, each line with its input's label in a reader's words
(``overrides.LABELS``); the secondary valuation's form, the currency of its totals
(the snapshot's reporting currency) and the rate it ran at (``currency``, ``fxRate``; the
export's line names both on a company in another currency, spec 2026-11-10 7.6), its drivers
with the trailing revenue and the terminal return and its projection year by year, or its parts
year by year, and its grid, the rows the terminal growths or, on the parts form, the shift in
every part's (``GRID_ROWS``), with the rows in words as the export's grid table writes them
(``rowWords``, for the report page's chart), or, for a report with none whose company can have
none on its snapshot, why, in the register's words (``noSecondary``, "No secondary valuation:
Fairband's own valuation gives the company a value" where ``store.secondary.no_secondary`` says the
route values it, "...: the review gives the company a value" (the report's review has a value), or
"...: " and the snapshot's refusal in its own words when it is one an agent cannot fix, "...: no
diluted share count" or "...: share basis unclear: ..." (spec 2026-11-10 7.6, spec 2026-11-15 7);
``no_secondary``'s own words stay as they are); the checks that ran
(``check.CHECKS``, each with its rule); the versions (method, policy, settings hash, review and
secondary methods); and the classifier's evidence. Appendix B (``appendix_b``), the glossary: the
terms of ``GLOSSARY`` that the sections' text uses, a term matched whole and in any case, a plural
counted, a term of two names (``Growth word, margin direction``) by either.

``GLOSSARY`` is ``docs/method.md`` section 13's table, term for term; its Note is the flag of
section 8 and also, in the brand book's word, the note an owner or an agent writes.

``references`` lists the refs the sections cite, numbered from 1 in the order each is first cited,
one entry a distinct ref whatever the period a cite names, each with its source in words
(``refs.Resolver.describe``).

``markdown`` renders the published report: a header line naming the company, the mode, the date
in words, the actor (the principal for the owner) and the revision; a line naming the stance and
what the report rests on in the reader's words (``resting_words``, "On the data of 4 Nov 2026,
priced that day, valid until 27 Jan 2027."), and for a valuation review the full report it reuses
by its date, "Reuses the full report of 3 Nov 2026." ("Reuses an earlier full report." where that
report's record is not on file), or that there is none: the lines above the sections name no part
of Fairband and write every date as the references do (spec 2026-11-15 7); the sections under
their headings as ``##``, each led by its chart tables (``charts.chart_tables``) as ``###``
tables, "No data on file." under one without rows, as the page writes under its chart, and the
line a table carries after its rows, then each part's text in order, a cite as its text and its
footnote mark, ``$150.00[^1]``, so no ref is in the text; then Appendix A, opening with the
snapshot the report rests on in one line in the order of the page's Appendix A, "Snapshot 412 ·
data 4 Nov 2026 · priced 4 Nov 2026 · valid until 27 Jan 2027 · price $150.00 · value $128.00",
its price and value with the export's thousands separator ("$1,507.85"), with "· in SEK" last on
a company in another currency, and its refusal after the line where it has one
(the lines above the sections name no record, so the export names its snapshot here), then its
other parts as tables, its inputs' "As of", a date input's note and its guidance's "Call" in
words, and Appendix B as a list; and last the references under ``## References``, ``[^n]: <ref> —
<source>``: GitHub-flavoured Markdown renders footnote definitions at the end of the document, so
the heading stands over its list there (spec 2026-11-15 9). The report page keeps its order, the
references after the last section.
"""

import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date
from typing import Any

from pydantic.alias_generators import to_camel

from fairband.engine.overrides import LABELS
from fairband.engine.types import money_of
from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.reports.charts import NO_DATA, ChartTable, grid_row_words, shift_words
from fairband.reports.check import (
    CHECKS,
    NO_REFERENCE,
    NOT_EMITTED,
    UNRESOLVED,
    WRONG_PERIOD,
    WRONG_SNAPSHOT,
    WRONG_UNIT,
    parts,
    shown,
)
from fairband.reports.refs import Resolver, day_words, guidance_cited
from fairband.store.currency import currency_of
from fairband.store.guidance import UNITS, guidance_for
from fairband.store.overrides import OverrideRow, override_row
from fairband.store.reports import ReportRow
from fairband.store.reviews import ReviewRow, review_row
from fairband.store.secondary import GRID_ROWS, SecondaryRow, no_secondary, secondary_row
from fairband.store.snapshots import snapshot_row

GLOSSARY: dict[str, str] = {
    "Value at belief": "The value a share at the growth belief; the one price target",
    "ADS": (
        "An American depositary share: the unit an ADR's quote prices, a number of ordinary "
        "shares, its ADR ratio; FMP states an ADR's count, EPS and consensus per ADS, and every "
        "per-share figure of an ADR is per ADS (section 7)"
    ),
    "Reporting currency": (
        "The currency of the newest annual income statement, else the universe row's; the "
        "currency the route values a company in (section 7)"
    ),
    "Pair": (
        "The FMP forex symbol `USD<code>`, whose close is the currency's units per USD: the rate "
        "a figure comes into the currency at (×) and goes back to USD at (÷) (section 7)"
    ),
    "Inflation differential": (
        "d = (1 + π_currency) ÷ (1 + π_USD) − 1, π the mean of the IMF projections in the "
        "inflation table; it restates a nominal USD rate in the currency as (1 + rate) × (1 + d) "
        "− 1 (section 7)"
    ),
    "Cadence": (
        "How often a company reports, read from its two newest quarterly statement rows: "
        "quarterly when they end 80 to 100 days apart, half-yearly when 170 to 195 and the row "
        "before them does not end a quarter before the older. The trailing figures sum four "
        "quarters or two half-years, and the NTM window reads the next four quarters or two "
        "half-years; the fiscal-year fallback keeps the cadence the rows gave, quarterly when "
        "they gave none (4.2, 5.2)"
    ),
    "Belief": (
        "The growth rate the value assumes after the analysts' forecast years: where year 3's "
        "growth is higher, growth eases down to it over the fade, then holds at it as far as "
        "the runway reaches; the base-rate median plus 2 points"
    ),
    "Runway N": "The years of growth above the terminal rate, set by the moat class",
    "Runway return": (
        "The return on new capital the charge starts at, held through the hold K, then faded to "
        "the terminal return in year N (4.8)"
    ),
    "Terminal return": "The return on new capital after the runway",
    "Charge": (
        "The share of earnings held back to pay for the next year's revenue growth, h ÷ return; "
        "above 100% when the growth outruns the return"
    ),
    "Charge off": (
        "The runway years are not charged, because measured capital is at or below zero"
    ),
    "Fade": (
        "The equal steps from the year-3 consensus growth down to the belief, one a year over the "
        "fade years, a setting, five at the defaults"
    ),
    "EPV": "Earnings power value: clean trailing earnings ÷ r, the value with no growth",
    "Designation": (
        "Where the price stands against the value at belief: one of five bands on price ÷ value "
        "(4.10); a fact about the price, never an action"
    ),
    "Non-recurring gap": "GuruFocus EPS trailing less EPS without non-recurring items",
    "Growth word, margin direction": (
        "The classifier's reading of the deciles for revenue growth and for the margin trend"
    ),
    "Check": "A classifier warning that never changes the phase",
    "Snapshot": (
        "One company's result under one refresh, with the versions and the settings hash that "
        "produced it"
    ),
    "Setting": "A policy value the user may change on the Settings view (4.1)",
    "Effective policy": (
        "The policy file's values with the user's settings applied over them; the policy the "
        "engine runs (4.1)"
    ),
    "Settings hash": (
        "The sha256 of the user's settings that change a result's figures; it names the settings "
        "a result was valued under, as the policy version names the file (4.1)"
    ),
    "Repricing horizon": (
        "H: the years over which the expected return assumes the price meets the value (5.10)"
    ),
    "Quality warning": (
        "One of the twelve flags that say the value may be wrong because the business or its "
        "figures are unusual; a row's flag count counts them (section 8)"
    ),
    "Note": (
        "Any other flag: shown, never counted (section 8). Also, as the brand book uses the word, "
        "a dated remark the owner or an agent writes on a company, which may carry an override's "
        "provenance"
    ),
    "Mature peers": (
        "The company's FMP `stock-peers` that the latest universe lists and the classifier puts "
        "in Mature Growth or Mature Stable; when fewer than `peer_min` of them count, the largest"
        " mature companies of the company's FMP industry"
    ),
    "Target margin": (
        "The operating margin the revenue-growth route moves to by year 10, and the Start-up ramp"
        " reaches in year 10: the median ten-year margin of the mature peers"
    ),
    "Sales-to-capital": (
        "The revenue a dollar of invested capital buys: the company's change in revenue ÷ its "
        "change in capital, its newest kept year's revenue ÷ that year's capital (6a.4), or a "
        "peer's revenue ÷ its capital. The revenue-growth route reinvests the next year's revenue"
        " increase ÷ sales-to-capital"
    ),
    "Margin the price needs": (
        "The target margin at which the revenue-growth value a share equals the price"
    ),
    "Return on new capital at the target": (
        "Target margin × (1 − tax rate) × sales-to-capital: the after-tax return on new capital "
        "once the margin reaches the target. It sets the terminal return by the moat's rule and "
        "is checked against the peers' ROIC"
    ),
    "Held rate": (
        "The growth the revenue path holds in years 4 and 5 before its fade: g_3 as resolved, or,"
        " for the implied growth, the rate at which the value equals the price. A held step is a "
        "missing consensus step that takes the rate of the year before"
    ),
    "Run-off": (
        "The Decline route's DCF: a firm that shrinks year by year, releasing the capital its "
        "lost revenue needed, until its decline fades to zero by year N, and is valued in the "
        "terminal as a business of year N's size that neither grows nor shrinks (6a)"
    ),
    "Decline rate": (
        "d: the five-year revenue slope over the last fiscal year's revenue, at most zero and "
        "floored at −50%; the run-off's rate after the consensus years, fading in a straight line"
        " to zero by year N (6a.2). The implied decline rate is the d at which the value equals "
        "the price (6a.9)"
    ),
    "Normalized margin": (
        "m_n: the median operating margin of the last five fiscal years when at least three have "
        "one, else the trailing margin; held in every year of the run-off (6a.3)"
    ),
    "Synthetic rating": (
        "The bond rating that a company's interest coverage, EBIT_n over the trailing interest "
        "expense, reads off Damodaran's table; its ten-year default probability is π (6a.7)"
    ),
    "Distress-sale value": (
        "What equity gets in a distress sale: 60% of the firm value plus cash, less debt and the "
        "minority interest, not below zero, a share (6a.7)"
    ),
    "NCAV": (
        "Graham's net current asset value: total current assets less total liabilities; less the "
        "minority interest and over the count in force, the diluted shares plus any committed "
        "shares, the run-off's floor when above zero (6a.6, 14.4)"
    ),
    "Requirement": (
        "A Start-up row's price-implied requirement: the revenue in year 10 at which a ten-year "
        "ramp to the mature peers' margin is worth the market cap plus debt and the minority "
        "interest, less cash (6b.2)"
    ),
    "Cash floor": (
        "A Start-up row's net cash a share, (cash − debt − minority interest) ÷ the count in "
        "force, the diluted shares plus any committed shares (6b.4, 14.4)"
    ),
    "Burn cover": (
        "The years a Start-up row's cash covers its trailing burn, the trailing operating cash "
        'flow plus capital spending when below zero; "not burning" otherwise (6b.4)'
    ),
    "Override": (
        "A change an agent makes to one tagged input, with its reason, its evidence and its "
        "lifetime (lasting, or tied to a period); applied, or refused with the rule it breaks, "
        "and stored either way. The engine, not the agent, computes the value it gives"
    ),
    "Review": (
        "The engine's valuation of a company under its applied overrides: the reviewed value, its"
        " levels and designation on the same edges, and the bridge from the mechanical value, one"
        " line per override. It follows the company's snapshots and cites `fairband-review/1`"
    ),
    "Finding": (
        "A dated fact an agent records with its source (a filing, a transcript, a URL, a vendor "
        "response or a base rate); a finding or a guidance record is the only way a number from "
        "outside Fairband enters a report"
    ),
    "Judgment": (
        "One of a report's key judgments (the phase, the moat, the belief, the ROIC, the target "
        "margin): the record of the decision, in words, and the override it produced, if one. An"
        " input an override sets is tagged JUDGMENT, beside DATA and RULE"
    ),
    "Secondary valuation": (
        "A second valuation the engine computes from an agent's inputs, in one of two forms: the "
        "standard form projects the free cash flow to the firm from the agent's drivers (the "
        "revenue growth and the operating margin year by year, the tax rate, sales-to-capital, "
        "the terminal growth); the parts form discounts an explicit free-cash-flow path, one part"
        " or a sum of parts. Both discount at r with a terminal at g_T or below and carry a "
        "three-by-three grid at other rates and growths, a display and not a value: the fallback "
        "where neither the route nor the review gives a value, refused where either does. It cites"
        " `fairband-secondary/2`"
    ),
    "Work item": (
        "A request in the inbox for an agent's research on one company, a valuation review or a "
        "full report, posted by the owner, an agent or the expiry rule; pending, claimed, done, "
        "declined or dropped"
    ),
}
# Terms matched by more than their own name.
_ALIASES: dict[str, tuple[str, ...]] = {"Runway N": ("runway",)}
_RULES: dict[str, str] = {
    "the mode's section count": "twelve sections for a full report, ten for a valuation review",
    "the required judgments": (
        "phase, moat and belief; roic on Mature Growth and Mature Stable; target_margin on High "
        "Growth, Young Growth and Start-up"
    ),
    "the headings in the spec's order": (
        "the twelve headings in order, sections 2 and 3 left out of a valuation review"
    ),
    "a secondary valuation on a refused snapshot": (
        "on a refused latest snapshot, the company's newest secondary valuation rests on it or on"
        " one it reprices; none where the route or the review values the company, or where the"
        " snapshot's refusal is one an agent cannot fix: no diluted share count, the reporting"
        " currency's or the share basis's"
    ),
    UNRESOLVED: "every cite's reference names a stored value",
    WRONG_UNIT: "every cite reads its value in its unit at the report's rounding",
    WRONG_PERIOD: "every cite's period, when it names one, is its reference's",
    WRONG_SNAPSHOT: "every cite rests on the company's latest snapshot, or one the latest reprices",
    NO_REFERENCE: "every quantity in the text is cited",
    NOT_EMITTED: "every derived figure is a stored derivation",
}
_DASH = "—"
# Each input's bridge label by its tag as a stored bridge line names it.
_LABELS: dict[str, str] = {tag: label for tag, label in LABELS.items()}
# ``no_secondary``'s reasons in the register's words where Appendix A writes them, "the route"
# being a name the register forbids (spec 2026-11-15 7); any other reason, a snapshot's refusal,
# keeps its own words.
_NO_SECONDARY: dict[str, str] = {
    "the route values the company": "Fairband's own valuation gives the company a value",
    "the review values the company": "the review gives the company a value",
}
# How the words of an override's scaling at a split begin, after the reason in the note of the
# review's JUDGMENT entry (``engine.route_steps``, method 14.6).
_ENTERED = "entered as "


def appendix_a(conn: sqlite3.Connection, report: ReportRow, policy: Policy) -> dict[str, Any]:
    """Appendix A of ``report`` from the stored records (module docstring); ``policy`` is the
    effective one, whose stance words the stance check names."""
    snapshot = snapshot_row(conn, report.snapshot_id)
    assert snapshot is not None  # a report is stored on its company's snapshot
    review = None if report.review_id is None else review_row(conn, report.review_id)
    secondary = None if report.secondary_id is None else secondary_row(conn, report.secondary_id)
    result = snapshot.result if review is None else review.result
    rules = _RULES | {"the stance word": f"one of {', '.join(policy.stance_words)}"}
    overrides = [] if review is None else _overrides(conn, review)
    why = no_secondary(snapshot, review) if secondary is None else None
    why = None if why is None else _NO_SECONDARY.get(why, why)
    currency = money_of(snapshot.result)[1]
    return {
        "snapshot": {
            "id": snapshot.id,
            "dataDate": snapshot.data_date.isoformat(),
            "priceDate": None if snapshot.price_date is None else snapshot.price_date.isoformat(),
            "validUntil": snapshot.valid_until.isoformat(),
            "currency": currency,
            "price": snapshot.price,
            "value": snapshot.value,
            "phase": snapshot.phase,
            "route": snapshot.route,
            "refusal": snapshot.refusal,
        },
        "inputs": [
            {
                "name": i.name,
                "value": i.value,
                "unit": i.unit,
                "tag": i.tag,
                "kind": i.kind,
                "source": i.provenance.source,
                "asOf": _iso(i.provenance.as_of),
                "observedAt": _iso(i.provenance.observed_at),
                "enteredAt": _iso(i.provenance.entered_at),
                "estimateMethod": i.estimate_method,
                "note": i.note,
            }
            for i in result.inputs
        ],
        "overrides": overrides,
        "guidance": _guidance(conn, report, overrides, currency),
        "bridge": None if review is None else _bridge(review),
        "secondary": None if secondary is None else _secondary(secondary, currency),
        "noSecondary": None if why is None else f"No secondary valuation: {why}",
        "checks": [{"check": check, "rule": rules[check]} for check in CHECKS],
        "versions": {
            "method": snapshot.method_version,
            "policy": snapshot.policy_version,
            "settingsHash": snapshot.settings_hash,
            "review": None if review is None else review.review_method,
            "secondary": None if secondary is None else secondary.secondary_method,
        },
        "classifier": {
            **{to_camel(k): v for k, v in asdict(snapshot.result.phase).items() if k != "checks"},
            "checks": [check.word for check in snapshot.result.phase.checks],
        },
    }


def appendix_b(sections: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """The terms of ``GLOSSARY`` the sections' text uses, in the glossary's order, each with its
    meaning."""
    text = " ".join(_text(part) for _, part in parts(sections))
    return [
        {"term": term, "meaning": meaning}
        for term, meaning in GLOSSARY.items()
        if any(_used(name, text) for name in _names(term))
    ]


def references(
    conn: sqlite3.Connection,
    report: ReportRow,
    policy: Policy,
    tax: TaxTable | None = None,
    *,
    section: int | None = None,
) -> list[dict[str, Any]]:
    """The refs ``report``'s sections cite, ``{n, ref, source}``, numbered from 1 in the order
    each is first cited; a ref cited again, with a period or without, keeps its number. ``policy``
    is the effective one and ``tax`` the statements' table; a ``policy:`` ref's source names the
    policy version the report's snapshot was valued under. With ``section`` (counted from 1), only
    the refs that section cites, each keeping its number in the whole list, so the company
    detail's report summary (spec 2026-11-06 Tier 2, 18.2), which the MCP ``company`` tool
    carries, numbers its cites as the report page does. No page draws that summary since the
    drawer's left (the company page's design, 11)."""
    numbered: dict[str, int] = {}
    for _, part in parts(report.sections):
        ref = _cited(part)
        if ref and ref not in numbered:
            numbered[ref] = len(numbered) + 1
    if section is not None:
        shown = report.sections[section - 1 : section] if section >= 1 else ()
        cited = {_cited(part) for _, part in parts(shown)}
        numbered = {ref: n for ref, n in numbered.items() if ref in cited}
    snapshot = snapshot_row(conn, report.snapshot_id)
    version = None if snapshot is None else snapshot.policy_version
    resolver = Resolver(conn, report.symbol, policy, tax, policy_version=version)
    return [{"n": n, "ref": ref, "source": resolver.describe(ref)} for ref, n in numbered.items()]


def resting_words(data_date: date, price_date: date | None, valid_until: date | None) -> str:
    """What a report rests on in the reader's words, the export's second line after its stance
    (spec 2026-11-15 7): "On the data of" and the data date; "priced that day" where the price
    date is the same day, "priced" and the price date where it is another, nothing without one;
    "valid until" and the date, nothing without one. Each date as the references write a day."""
    parts = [f"On the data of {day_words(data_date)}"]
    if price_date is not None:
        parts.append(
            "priced that day" if price_date == data_date else f"priced {day_words(price_date)}"
        )
    if valid_until is not None:
        parts.append(f"valid until {day_words(valid_until)}")
    return ", ".join(parts) + "."


def markdown(
    report: ReportRow,
    a: Mapping[str, Any],
    b: Sequence[Mapping[str, str]],
    refs: Sequence[Mapping[str, Any]],
    tables: Mapping[str, Sequence[ChartTable]],
    *,
    reused: date | None = None,
) -> str:
    """The report as Markdown (module docstring): its Appendix A ``a``, its Appendix B ``b``,
    its references ``refs`` and its chart tables by the heading of the section they lead;
    ``reused`` the day of the full report a valuation review reuses, which its line names, or
    ``None`` where that report's record is not on file, when the line names no day."""
    actor = report.actor or report.principal
    day = day_words(report.created_at.date())
    snapshot = a["snapshot"]
    header = f"{report.symbol} · {report.mode} · {day} · {actor} · revision {report.revision}"
    rests = resting_words(
        date.fromisoformat(snapshot["dataDate"]),
        _day(snapshot["priceDate"]),
        _day(snapshot["validUntil"]),
    )
    lines = [header, "", f"Stance: {report.stance}. {rests}"]
    if report.mode == "valuation review":
        if report.reuses_full_report_of is None:
            lines.append("No full report to reuse.")
        elif reused is None:  # the reused report's record is not on file: no day to name
            lines.append("Reuses an earlier full report.")
        else:
            lines.append(f"Reuses the full report of {day_words(reused)}.")
    marks = {str(entry["ref"]): int(entry["n"]) for entry in refs}
    for section in report.sections:
        heading = section["heading"]
        lines += ["", f"## {heading}"]
        for chart in tables.get(heading.strip(), ()):
            lines += ["", f"### {chart.title}", "", *_chart_table(chart)]
        lines += ["", "".join(_marked(p, marks) for p in section["parts"])]
    lines += ["", "## Appendix A", "", *_appendix_a_tables(a), "", "## Appendix B", ""]
    lines += [f"- **{entry['term']}**: {entry['meaning']}" for entry in b] or ["No terms used."]
    # last, where GitHub-flavoured Markdown renders the footnote definitions (spec 2026-11-15 9)
    lines += ["", "## References", ""]
    listed = [f"[^{entry['n']}]: {entry['ref']} — {entry['source']}" for entry in refs]
    lines += listed or ["No references."]
    return "\n".join(lines) + "\n"


def _overrides(conn: sqlite3.Connection, review: ReviewRow) -> list[dict[str, Any]]:
    """The overrides inside ``review``, as Appendix A lists them: each with its stored pair, and
    with the pair in force and the words of its scaling where the review applied it at a split
    (``_in_force``)."""
    found = []
    for override_id in review.override_ids:
        row = override_row(conn, override_id)
        if row is not None:
            in_force, rescaled = _in_force(review, row)
            found.append(
                {
                    "id": row.id,
                    "tag": row.tag,
                    "old": row.old,
                    "new": row.new,
                    "unit": row.unit,
                    "reason": row.reason,
                    "evidence": list(row.evidence),
                    "lifetime": row.lifetime,
                    "period": row.period,
                    "principal": row.principal,
                    "actor": row.actor,
                    "at": row.at.isoformat(),
                    "inForce": in_force,
                    "rescaled": rescaled,
                }
            )
    return found


def _in_force(review: ReviewRow, row: OverrideRow) -> tuple[dict[str, Any] | None, str | None]:
    """Where ``review`` applied the override ``row`` at a figure other than the one entered,
    because a split fell between (method 14.6, spec 2026-11-15 8): the pair in force, the old and
    new of the override's bridge line, both on the new share basis, and the words of the scaling,
    the clause "entered as $30.00 a share before the 2-for-1 split of 27 Jan 2027" that follows
    the reason in the note of the review's JUDGMENT entry for the input. A step that refused was
    applied at the figure in force and met its refusal there, so it has both too. Both are read
    from the stored review, never from the splits on file. ``(None, None)`` where the review
    applied it as entered, a review written before the scaling included, and where the override
    has no bridge line (the empty bridge of a failed fetch, valuation or review)."""
    line = next((x for x in review.bridge if x["override_id"] == row.id), None)
    judged = (i for i in review.result.inputs if i.tag == "JUDGMENT" and i.name == row.tag)
    note = next((i.note for i in judged), None) or ""
    lead = f"{row.reason}; "
    words = note[len(lead) :] if note.startswith(lead) else ""
    if line is None or not words.startswith(_ENTERED):
        return None, None
    return {"old": line["old"], "new": line["new"]}, words


def _guidance(
    conn: sqlite3.Connection,
    report: ReportRow,
    overrides: Sequence[Mapping[str, Any]],
    currency: str,
) -> list[dict[str, Any]]:
    """The company's guidance records on file when the report was published, newest first: each
    with the currency of its money (``store.currency.currency_of``), the stored code, else
    ``currency``, the reporting currency of the report's own snapshot, none for a percent (spec
    2026-11-15 9.1, 9.5); current, or superseded by a record on file by then; and the overrides
    inside the review whose evidence cites it."""
    on_file = [g for g in guidance_for(conn, report.symbol) if g.created_at <= report.created_at]
    listed = {g.id for g in on_file}
    cited_by: dict[int, list[int]] = {}
    for o in overrides:
        items = (e for e in o["evidence"] if e.get("kind") == "guidance")
        records = {guidance_cited(str(e.get("ref", ""))) for e in items}
        for record_id in sorted(r for r in records if r is not None):
            cited_by.setdefault(record_id, []).append(o["id"])
    return [
        {
            "id": g.id,
            "metric": g.metric,
            "period": g.period,
            "low": g.low,
            "high": g.high,
            "midpoint": g.midpoint,
            "currency": currency_of(g.currency, UNITS[g.metric], currency),
            "basis": g.basis,
            "asOf": g.as_of.isoformat(),
            "state": "superseded" if g.superseded_by in listed else "current",
            "citedBy": cited_by.get(g.id, []),
        }
        for g in on_file
    ]


def _bridge(review: ReviewRow) -> dict[str, Any]:
    return {
        "reviewId": review.id,
        "mechanicalValue": review.mechanical_value,
        "reviewedValue": review.value,
        "refusal": review.refusal,
        "lines": [
            {**{to_camel(key): value for key, value in line.items()}, "label": _label(line)}
            for line in review.bridge
        ],
    }


def _label(line: Mapping[str, Any]) -> str:
    """A bridge line's input in a reader's words."""
    tag = str(line["tag"])
    return _LABELS.get(tag, tag)


def _secondary(secondary: SecondaryRow, currency: str) -> dict[str, Any]:
    """The secondary valuation with ``currency``, the reporting currency of the snapshot it rests
    on, its totals' (spec 2026-11-10 7.6), and the rate it ran at, units of it per USD."""
    drivers, projection, grid = secondary.drivers, secondary.projection, secondary.grid
    return {
        "id": secondary.id,
        "form": secondary.form,
        "currency": currency,
        "fxRate": secondary.fx_rate,
        "valuePerShare": secondary.value_per_share,
        "firmValue": secondary.firm_value,
        "debt": secondary.debt,
        "debtSource": secondary.debt_source,
        "cash": secondary.cash,
        "cashSource": secondary.cash_source,
        "shares": secondary.shares,
        "equity": secondary.equity,
        "reason": secondary.reason,
        "evidence": list(secondary.evidence),
        "parts": [
            {
                "name": p["name"],
                "terminalGrowth": p["terminal_growth"],
                "note": p["note"],
                "years": [
                    {"year": t, "fcff": fcff, "pv": pv}
                    for t, (fcff, pv) in enumerate(zip(p["fcff"], p["pv"], strict=True), 1)
                ],
                "terminal": p["terminal"],
                "terminalPv": p["terminal_pv"],
                "value": p["value"],
            }
            for p in secondary.parts
        ],
        "drivers": None if drivers is None else _camel(drivers),
        "projection": None if projection is None else _camel(projection),
        "grid": None if grid is None else _grid(grid, GRID_ROWS[secondary.form]),
    }


def _grid(grid: Mapping[str, Any], rows_are: str) -> dict[str, Any]:
    """The grid with what its rows hold and the rows in words, as the export's grid table writes
    them (``charts.grid_row_words``), which the report page draws (spec 18.4)."""
    words = grid_row_words(grid["rows"], rows_are == "shifts")
    return {**grid, "rowsAre": rows_are, "rowWords": list(words)}


def _camel(record: Mapping[str, Any]) -> dict[str, Any]:
    """The drivers or the projection with its keys camelCase (a year's keys are single words)."""
    return {to_camel(key): value for key, value in record.items()}


def _chart_table(chart: ChartTable) -> list[str]:
    """A chart's table twin: its rows, or "No data on file." without any, as the page writes under
    a chart with no point; then its line, where it has one, as one plain line after a blank one,
    which ends the table."""
    out = _table(chart.header, chart.rows) if chart.rows else [NO_DATA]
    return out if chart.line is None else [*out, "", chart.line]


def _snapshot_line(snapshot: Mapping[str, Any]) -> str:
    """The snapshot the report rests on in one line, in the order of the report page's Appendix A
    (``report.js``, ``snapshotLine``): its id, its data date, its price date and the end of its
    window, each in words, its price and its value a share, both US dollars, as the export writes
    a figure a share elsewhere, with its thousands separator ("$1,507.85"), and, on a company in
    another currency, that currency last; a dash for what it has none of."""
    said = [
        f"Snapshot {snapshot['id']}",
        f"data {_day_words(snapshot['dataDate']) or _DASH}",
        f"priced {_day_words(snapshot['priceDate']) or _DASH}",
        f"valid until {_day_words(snapshot['validUntil']) or _DASH}",
        f"price {_money(snapshot['price'])}",
        f"value {_money(snapshot['value'])}",
    ]
    code = snapshot["currency"]
    return " · ".join([*said, f"in {code}"] if code and code != "USD" else said)


def _appendix_a_tables(a: Mapping[str, Any]) -> list[str]:
    """Appendix A's parts, each under its own heading: the snapshot the report rests on as one
    line, its refusal after it where it has one, as the page shows them; the others as Markdown
    tables."""
    snapshot = a["snapshot"]
    out = ["### Snapshot", "", _snapshot_line(snapshot)]
    if snapshot["refusal"]:
        out += ["", snapshot["refusal"]]
    out += ["", "### Inputs", ""]
    out += _table(
        ("Input", "Value", "Unit", "Tag", "Kind", "Source", "As of", "Note"),
        [
            (
                i["name"],
                i["value"],
                i["unit"],
                i["tag"],
                i["kind"],
                i["source"],
                _day_words(i["asOf"]),
                _note(i),
            )
            for i in a["inputs"]
        ],
    )
    out += ["", "### Overrides", ""]
    out += _table(
        ("Override", "Input", "Old", "New", "Reason", "Evidence", "Lifetime", "By"),
        [
            (
                o["id"],
                o["tag"],
                *_pair(o),
                o["reason"],
                "; ".join(_evidence(e) for e in o["evidence"]),
                o["lifetime"] if o["period"] is None else f"{o['lifetime']}, {o['period']}",
                o["actor"] or o["principal"],
            )
            for o in a["overrides"]
        ],
    )
    out += ["", "### Guidance on file", ""]
    # the figures bare, as before, and their currency in a column after the midpoint, empty for a
    # percent (spec 2026-11-15 9.5)
    keys = ("id", "metric", "period", "low", "high", "midpoint")
    header = ("Guidance", "Metric", "Period", "Low", "High", "Midpoint", "Currency", "Basis")
    guided = [
        (
            *(g[key] for key in keys),
            g["currency"] or "",
            g["basis"],
            _day_words(g["asOf"]),
            g["state"],
            g["citedBy"],
        )
        for g in a["guidance"]
    ]
    out += _table((*header, "Call", "State", "Cited by"), guided)
    out += ["", "### Bridge", ""]
    bridge = a["bridge"]
    if bridge is None:  # the mechanical value is the value, unless the snapshot refused
        none = a["snapshot"]["value"] is None
        out.append("No review." if none else "No review: the value is the mechanical one.")
    else:
        mechanical, reviewed = _cell(bridge["mechanicalValue"]), _cell(bridge["reviewedValue"])
        summary = f"Review {bridge['reviewId']}: mechanical value {mechanical}, reviewed value"
        out += [f"{summary} {reviewed}.", ""]
        rows = [
            (x["tag"], x["label"], x["overrideId"], x["old"], x["new"], x["delta"], x["refusal"])
            for x in bridge["lines"]
        ]
        out += _table(("Input", "Label", "Override", "Old", "New", "Delta", "Refusal"), rows)
    out += ["", "### Secondary valuation", ""]
    secondary, why = a["secondary"], a["noSecondary"]
    if secondary is not None:
        out += _secondary_tables(secondary)
    else:
        out.append("None." if why is None else why)  # as it arrives, as the page shows it
    out += ["", "### Checks that ran", ""]
    out += _table(("Check", "Rule"), [(c["check"], c["rule"]) for c in a["checks"]])
    out += ["", "### Versions", ""]
    out += _table(("Version", "Value"), list(a["versions"].items()))
    out += ["", "### Classifier evidence", ""]
    out += _table(("Field", "Value"), list(a["classifier"].items()))
    return out


def _secondary_tables(secondary: Mapping[str, Any]) -> list[str]:
    """The secondary valuation's figures; its drivers and its projection, or its parts; its
    grid."""
    figures = (
        f"firm value {_cell(secondary['firmValue'])}, debt {_cell(secondary['debt'])}"
        f" ({secondary['debtSource']}), cash {_cell(secondary['cash'])}"
        f" ({secondary['cashSource']}), equity {_cell(secondary['equity'])},"
        f" {_cell(secondary['shares'])} shares, value a share"
        f" {_cell(secondary['valuePerShare'])}"
    )
    lead = f"Secondary valuation {secondary['id']}, from {secondary['form']}"
    code = secondary["currency"]
    if code != "USD":  # its totals in the currency, its value a share in USD (spec 2026-11-10 7.6)
        rate = _cell(secondary["fxRate"])
        lead += f", in {code} at {rate} {code} per USD, its value a share in USD"
    out = [f"{lead}: {figures}. {secondary['reason']}", ""]
    if secondary["form"] == "drivers":
        out += _projection_tables(secondary["drivers"], secondary["projection"])
    else:
        out += _parts_table(secondary["parts"])
    grid = secondary["grid"]
    return [*out, "", *(["No grid."] if grid is None else _grid_table(grid))]


def _projection_tables(drivers: Mapping[str, Any], projection: Mapping[str, Any]) -> list[str]:
    """The drivers with the trailing revenue and the terminal return; the projection, year by
    year and the terminal."""
    out = _table(
        ("Driver", "Value"),
        [
            ("years", drivers["years"]),
            ("revenue growth", drivers["revenueGrowth"]),
            ("operating margin", drivers["operatingMargin"]),
            ("tax rate", drivers["taxRate"]),
            ("sales-to-capital", drivers["salesToCapital"]),
            ("terminal growth", drivers["terminalGrowth"]),
            ("trailing revenue", projection["trailingRevenue"]),
            ("terminal return", projection["terminalReturn"]),
        ],
    )
    years = [
        (y["t"], y["revenue"], y["ebit"], y["nopat"], y["reinvestment"], y["fcff"], y["pv"])
        for y in projection["years"]
    ]
    terminal = (
        "terminal",
        None,
        None,
        None,
        None,
        projection["terminalFcff"],
        projection["terminalPv"],
    )
    header = ("t", "Revenue", "EBIT", "NOPAT", "Reinvestment", "FCFF", "PV")
    out += ["", *_table(header, [*years, terminal])]
    value = _cell(projection["terminal"])
    return [*out, "", f"Terminal value {value} at year {drivers['years']}."]


def _parts_table(parts: Sequence[Mapping[str, Any]]) -> list[str]:
    """Each part year by year, then each part's terminal."""
    years = [(p["name"], y["year"], y["fcff"], y["pv"]) for p in parts for y in p["years"]]
    terminals = [
        (p["name"], f"terminal at g {_cell(p['terminalGrowth'])}", p["terminal"], p["terminalPv"])
        for p in parts
    ]
    return _table(("Part", "Year", "FCFF", "PV"), years + terminals)


def _grid_table(grid: Mapping[str, Any]) -> list[str]:
    """The grid with its headers: a rate a column, a terminal growth a row, or on the parts form
    the shift in every part's terminal growth."""
    shifts = grid["rowsAre"] == "shifts"
    corner = "Every part's terminal growth" if shifts else "Terminal growth"
    header = (corner, *(f"r {_percent(rate)}" for rate in grid["cols"]))
    rows = [
        (shift_words(g, top=i == 2) if shifts else _percent(g), *cells)
        for i, (g, cells) in enumerate(zip(grid["rows"], grid["cells"], strict=True))
    ]
    return _table(header, rows)


def _percent(x: float) -> str:
    return f"{'−' if x < 0 else ''}{abs(x):.1%}"


def _money(x: float | None) -> str:
    """A price or a value a share in US dollars as the export writes a figure a share
    (``check.shown``): "$1,507.85", "−$2.50"; an em dash for none."""
    return _DASH if x is None else shown(x, "per-share")


def _table(header: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    if not rows:
        return ["None."]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(_cell(x) for x in row) + " |" for row in rows]
    return lines


def _cell(x: Any) -> str:
    """A value at full precision, as a table cell holds it; an em dash for none."""
    if x is None:
        return _DASH
    if isinstance(x, list):
        return ", ".join(_cell(item) for item in x) or _DASH
    text = repr(x) if isinstance(x, float) else str(x)
    return text.replace("|", "\\|").replace("\n", " ")


def _iso(day: date | None) -> str | None:
    """A date or a time as ISO text; ``None`` for none."""
    return None if day is None else day.isoformat()


def _day(text: str | None) -> date | None:
    """An ISO date of Appendix A as a date; ``None`` for none."""
    return None if text is None else date.fromisoformat(text)


def _day_words(text: str | None) -> str | None:
    """An ISO date of Appendix A as the references write a day, "3 Nov 2026" (spec 2026-11-15
    7); ``None`` for none, which a table cell writes as its dash."""
    day = _day(text)
    return None if day is None else day_words(day)


def _note(i: Mapping[str, Any]) -> Any:
    """An input's note as the export writes it: a date input's, its date as ISO text (the next
    earnings date), in words, as Appendix A's other dates (spec 2026-11-15 7); any other as it
    is."""
    note = i["note"]
    if i["unit"] != "date" or not isinstance(note, str):
        return note
    try:
        return day_words(date.fromisoformat(note))
    except ValueError:
        return note


def _pair(o: Mapping[str, Any]) -> tuple[Any, Any]:
    """An override's Old and New cells: where the review applied it at a split, the pair in force
    and, after the new figure, the words of the scaling in brackets, "15.0 (entered as $30.00 a
    share before the 2-for-1 split of 27 Jan 2027)", so the pair reads on one basis (spec
    2026-11-15 8); else the stored pair."""
    in_force = o["inForce"]
    if in_force is None:
        return o["old"], o["new"]
    return in_force["old"], f"{_cell(in_force['new'])} ({o['rescaled']})"


def _evidence(item: Mapping[str, Any]) -> str:
    note = item.get("note")
    return f"{item.get('kind')}: {item.get('ref')}" + (f" ({note})" if note else "")


def _text(part: Any) -> str:
    """A part's text: a plain part as it is, a cite as its text."""
    if isinstance(part, Mapping):
        return str(part.get("cite", ""))
    return part if isinstance(part, str) else ""


def _cited(part: Any) -> str:
    """A cite's ref as the references list keys it; ``""`` for a plain part."""
    return str(part.get("ref", "")).strip() if isinstance(part, Mapping) else ""


def _marked(part: Any, marks: Mapping[str, int]) -> str:
    """A part's text, a cite's followed by its footnote mark."""
    mark = marks.get(_cited(part))
    return _text(part) if mark is None else f"{_text(part)}[^{mark}]"


def _names(term: str) -> tuple[str, ...]:
    return _ALIASES.get(term, tuple(term.split(", ")))


def _used(name: str, text: str) -> bool:
    pattern = rf"(?<![\w-]){re.escape(name)}(?:s|es)?(?![\w-])"
    return re.search(pattern, text, re.IGNORECASE) is not None
