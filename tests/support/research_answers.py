"""The Research tab's synthetic report for one made-up company, ``page_payloads``' Lanternfield
Optics (``LFOX``), which lists in US dollars and reports in New Taiwan dollars: its twelve
sections in the report template's shapes (``playbook/fairband-research/reference/
report-template.md``), which the layout rules' tests read (``tests/web/
test_company_research_text.py``), and the answer of the tab's read, ``GET /api/companies/LFOX/
page/research``, which the tab's later tests hand its script.

The sections, each a list of parts, a text or a cite ``{cite, ref}``:

- ``SUMMARY``: the stance line, ``Stance: hold.``; three paragraphs; the three named lists of the
  summary page in a row ("Reasons for", "Main risks", "What would change the view"); the window's
  closing sentence.
- ``BUSINESS``: a paragraph, a named table of three columns (revenue by product), a named list
  (what drives revenue), a paragraph.
- ``INDUSTRY``: a paragraph, a named list (the competitors), the answer on the economics.
- ``FINANCIAL``: six paragraphs, each led by the bold word of its table, in the tables' order.
- ``EARNINGS``: the call's parts, each led by its bold name, with the quarter's table of five
  columns and the claims' table of four whose cells run past 44 characters.
- ``BULL_BEAR``: two paragraphs that open "The bull case:" and "The bear case:".
- ``THESIS``, ``VALUATION``: paragraphs.
- ``PRICE``: a paragraph and a named table of three columns.
- ``NEWS``: a paragraph and a list of dated items.
- ``RISKS``: a paragraph and a named list, one item citing kill criterion 47's threshold.
- ``JUDGMENTS``: a paragraph a judgment.

``ANSWER`` holds the read's keys in its order, in the shapes the server gives them (``web/
company_api.py``, ``page_research``): the head's quote (``page_answers``' own); the company's two
reports, newest first, without their sections; report 31 whole, as ``GET /api/reports/31``
answers it: revision 2 of a full report, a hold, on snapshot 38 (data of 10 Nov 2026, priced that
day, valid until 12 Feb 2027) and on review 6, whose one override, 12, narrows the moat from Wide
to Narrow and takes the value from $196.50 to $182.00 a share; its four judgments, its references
in the order of their first cite, Appendix A and Appendix B (``render.appendix_b`` on the
sections). Its ``call``, the review's value and levels against the snapshot's price of $176.80
("near" on ``page_answers``' edges); ``ofReport``, criterion 52 that the report recorded and
criterion 47 that it cites, and the two news items it recorded; ``records``, the company's records
on file of every kind, newest first, report 19's own among them: override 12 and override 10 of
the runway return, dropped; three guidance records, an operating margin of 7% to 10%, revenue in
TWD and an older revenue record it superseded; three kill criteria, one triggered; three news
items, one whose source is no web address; a note; three findings, one in TWD, one a count and one
with no figure; reviews 7 and 6, each with override 12's line as the read gives it, and review 4,
which has no value; one secondary valuation; four ledger rows and their count.

The series the tab reads after the report lands (the Research tab's design, 8.2), each the body
its read answers: ``TABLES``, the six financial tables and the quarters, every chart of them with
points; ``CLOSES``, five quarters of closes; ``BAND``, the band's history; ``MULTIPLES``, the
trailing P/E by month and six readings of the forward P/E; ``READING``, sensitivity reading 9.
``SERIES`` holds each by the address the tab reads it at. Every company, figure and sentence is
invented: no vendor data and no report on file."""

import copy
from typing import Any

from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.reports.check import HEADINGS
from fairband.reports.render import appendix_b
from support import page_answers

SYMBOL = page_answers.SYMBOL
STANCE = "hold"
REPORT_ID = 31
SNAPSHOT_ID = 38
REVIEW_ID = 6
CREATED = "2026-11-11T14:05:00+00:00"
AGENT = {"principal": "agent", "actor": "claude-opus-5-5", "client": "claude-code/2.1"}


def _c(cite: str, ref: str) -> dict[str, str]:
    """A cite as a part: its text and its ref."""
    return {"cite": cite, "ref": ref}


SNAP = f"snapshot:{SNAPSHOT_ID}"
REVIEW = f"review:{REVIEW_ID}"
PRICE_CITE = _c("$176.80", f"{SNAP}/price")
RETURN_CITE = _c("9.0%", "policy:required_return")

SUMMARY: list[Any] = [
    (
        "Stance: hold.\n\nThe thesis: phone makers and carmakers put more cameras in each device, and "
        "Lanternfield's newest lens grade takes rivals years to match, so revenue keeps compounding. "
        "The price already counts on most of it.\n\nThe price of "
    ),
    PRICE_CITE,
    " is close to the value this report puts on the company, ",
    _c("$182.00", f"{REVIEW}/value"),
    " a share. Prices close to the value run from ",
    _c("$163.80", f"{REVIEW}/fair_low"),
    " to ",
    _c("$200.20", f"{REVIEW}/fair_high"),
    ".\n\nThe company is in its Mature Growth stage. Revenue grew ",
    _c("14.2%", f"table:{SYMBOL}/growth/revenue_growth/2025"),
    (
        " in fiscal 2025. The business is cyclical: its profits rise and fall with the phone cycle."
        "\n\nReasons for:\n\n1. Each new car carries more cameras.\n2. Its newest lens grade takes "
        "rivals years to match.\n3. It funds its plants from its own cash.\n\nMain risks:\n\n1. Two "
        "rivals now sell lenses of the same grade for less.\n2. Phone sales fall first in a downturn."
        "\n3. A large customer may make its own lenses.\n\nWhat would change the view:\n\n- Two "
        "quarters in a row of falling sensor revenue.\n\nThe value is valid until 12 Feb 2027, the "
        "date of the next earnings report."
    ),
]
BUSINESS: list[Any] = [
    (
        "Lanternfield designs and makes precision lenses and the optical sensors that sit behind "
        "them. It sells to phone makers and to the suppliers of carmakers.\n\nRevenue by product:\n\n"
        "| | Fiscal 2024 | Fiscal 2025 |\n|---|---|---|\n| Lenses | "
    ),
    _c("TWD 268.1 billion", f"segment:{SYMBOL}/product/Lenses/2024"),
    " | ",
    _c("TWD 291.4 billion", f"segment:{SYMBOL}/product/Lenses/2025"),
    " |\n| Sensors | ",
    _c("TWD 94.2 billion", f"segment:{SYMBOL}/product/Sensors/2024"),
    " | ",
    _c("TWD 121.2 billion", f"segment:{SYMBOL}/product/Sensors/2025"),
    (
        " |\n\nWhat drives revenue:\n\n- Volume: the cameras in each phone and each car.\n- Price: a "
        "new lens grade sells at a premium for two years.\n- Contracts: most sales run on yearly "
        "supply contracts.\n\nThe gross margin was "
    ),
    _c("48.8%", f"table:{SYMBOL}/growth/gross_margin/2025"),
    (
        " in fiscal 2025. Each extra dollar of revenue added more operating profit than the average "
        "one."
    ),
]
INDUSTRY: list[Any] = [
    (
        "Lens makers buy glass and resin from a few chemical firms and sell to a few large device "
        "makers, so the profit sits with whoever holds the hardest grade.\n\nThe competitors:\n\n- Two "
        "Japanese lens makers, each with a narrower range.\n- A maker that sells the older grades for "
        "less.\n\nThe economics are favorable. The ROIC of "
    ),
    _c("21.4%", f"table:{SYMBOL}/returns/roic/2025"),
    " is well above the yearly return of ",
    RETURN_CITE,
    " that investors require of any company's shares.",
]
FINANCIAL: list[Any] = [
    "**Growth.** Revenue grew ",
    _c("14.2%", f"table:{SYMBOL}/growth/revenue_growth/2025"),
    " in fiscal 2025 and the operating margin reached ",
    _c("31.6%", f"table:{SYMBOL}/growth/operating_margin/2025"),
    ".\n\n**Cash flow.** Free cash flow was ",
    _c("TWD 98.3 billion", f"table:{SYMBOL}/cash_flow/free_cash_flow/2025"),
    ", most of the net income.\n\n**Solvency.** Net cash covers the debt: net debt to EBITDA was ",
    _c("-0.4x", f"table:{SYMBOL}/solvency/net_debt_to_ebitda/2025"),
    ".\n\n**Returns.** The ROIC of ",
    _c("21.4%", f"table:{SYMBOL}/returns/roic/2025"),
    " cleared the hurdle rate of ",
    RETURN_CITE,
    ".\n\n**Capital allocation.** The share count fell ",
    _c("1.1%", f"table:{SYMBOL}/capital_allocation/share_count_change/2025"),
    " as buybacks ran ahead of the stock paid to staff.\n\n**Quality.** Piotroski's F was ",
    _c("7", f"table:{SYMBOL}/quality/piotroski_f/2025"),
    " and Altman's Z″ ",
    _c("6.2", f"table:{SYMBOL}/quality/altman_z/2025"),
    ".",
]
EARNINGS: list[Any] = [
    (
        "**The verdict.** The call of 22 Oct 2026, on the third quarter of fiscal 2026, confirmed the "
        "thesis.\n\n**The quarter against expectations.**\n\n| | The quarter | A year before | The "
        "analysts' average | The surprise |\n|---|---|---|---|---|\n| Revenue | "
    ),
    _c("TWD 112.5 billion", f"fact:{SYMBOL}/revenue/2026-Q3"),
    " | ",
    _c("TWD 98.7 billion", f"fact:{SYMBOL}/revenue/2025-Q3"),
    " | ",
    _c("TWD 109.9 billion", f"estimate:{SYMBOL}/2026-Q3/revenue"),
    " | ",
    _c("2.4%", "derived:412"),
    (
        ' |\n\n**The story management is telling.** Management\'s frame: "a lens in every camera".'
        "\n\n| Claim | Evidence | Driver | Test |\n|---|---|---|---|\n| Cars take a larger share of "
        "revenue each year. | Sensor sales to car suppliers rose for six quarters running. | The "
        "consensus | The share holds through fiscal 2027. |\n\n**What the thesis takes from it.** The "
        "kill criterion on sensor revenue was not touched."
    ),
]
BULL_BEAR: list[Any] = [
    (
        "The bull case: each new car carries more cameras, and the newest lens grade takes rivals "
        "years to match. The company funds its plants from its own cash.\n\nThe bear case: two "
        "rivals now sell lenses of the same grade for less, and a large phone maker may make its own. "
        "Phone sales fall first in a downturn."
    ),
]
THESIS: list[Any] = [
    (
        "The thesis takes the call's claim in turn. Accepted: cars take a larger share of revenue, so "
        "growth holds up through a weak phone year. Held open: the price of the newest grade, which "
        "the next two quarters decide.\n\nThe stance is hold. The price sits close to the value, so "
        "the view waits for the newest grade's price to hold."
    ),
]
VALUATION: list[Any] = [
    (
        "Fairband puts the company in its Mature Growth stage, with a rising margin and no check "
        "flag. The mechanical value is "
    ),
    _c("$196.50", f"{SNAP}/value"),
    " a share. The review lowers it to ",
    _c("$182.00", f"{REVIEW}/value"),
    (
        ": the moat moves from Wide to Narrow, since two rivals now sell lenses of the same grade."
        "\n\nThe value rests on a belief of "
    ),
    _c("6.3%", f"{SNAP}/inputs/belief"),
    " a year after the analysts' forecast years.",
]
PRICE: list[Any] = [
    "The price of ",
    PRICE_CITE,
    (
        " sits near the middle of its band of the last five years.\n\nThe multiples against their "
        "history:\n\n| Multiple | Today | The five-year median |\n|---|---|---|\n| Forward P/E | "
    ),
    _c("24.1x", f"multiple:{SYMBOL}/forward_pe/2026-11-10"),
    " | ",
    _c("21.7x", f"multiple:{SYMBOL}/forward_pe/median"),
    " |",
]
NEWS: list[Any] = [
    (
        "Three dated items matter to the value.\n\n- 22 Oct 2026: the third quarter beat the "
        "analysts' average on revenue.\n- 28 Oct 2026: a rival launched a lens of the same grade.\n- "
        "3 Nov 2026: a new supply contract with a car supplier."
    ),
]
RISKS: list[Any] = [
    (
        "The risks are the rivals' prices and a weak phone year.\n\nThe kill criteria:\n\n- Sensor "
        "revenue falls two quarters in a row.\n- The gross margin falls below "
    ),
    _c("42.0%", "kill:47/threshold"),
    ".\n- A large customer moves its lenses in house.",
]
JUDGMENTS: list[Any] = [
    (
        "Phase: Mature Growth stands, as the classifier reads it.\n\nMoat: changed from Wide to "
        "Narrow by an override, since two rivals now sell lenses of the same grade.\n\nBelief: the "
        "base rate stands.\n\nReturn on new capital: the five-year return stands."
    ),
]

SECTIONS: list[dict[str, Any]] = [
    {"heading": heading, "parts": parts}
    for heading, parts in zip(
        HEADINGS,
        (
            SUMMARY,
            BUSINESS,
            INDUSTRY,
            FINANCIAL,
            EARNINGS,
            BULL_BEAR,
            THESIS,
            VALUATION,
            PRICE,
            NEWS,
            RISKS,
            JUDGMENTS,
        ),
        strict=True,
    )
]

# Each ref the sections cite, with the source its reference names.
_SOURCES: dict[str, str] = {
    f"{SNAP}/price": "snapshot 38, the price, priced 10 Nov 2026",
    f"{REVIEW}/value": "review 6, the reviewed value a share",
    f"{REVIEW}/fair_low": "review 6, the fair band's low end",
    f"{REVIEW}/fair_high": "review 6, the fair band's high end",
    f"table:{SYMBOL}/growth/revenue_growth/2025": "the growth table, revenue growth, fiscal 2025",
    f"segment:{SYMBOL}/product/Lenses/2024": "revenue by product, Lenses, fiscal 2024",
    f"segment:{SYMBOL}/product/Lenses/2025": "revenue by product, Lenses, fiscal 2025",
    f"segment:{SYMBOL}/product/Sensors/2024": "revenue by product, Sensors, fiscal 2024",
    f"segment:{SYMBOL}/product/Sensors/2025": "revenue by product, Sensors, fiscal 2025",
    f"table:{SYMBOL}/growth/gross_margin/2025": "the growth table, gross margin, fiscal 2025",
    f"table:{SYMBOL}/returns/roic/2025": "the returns table, ROIC, fiscal 2025",
    "policy:required_return": "policy required_return, fairband-policy-v17",
    f"table:{SYMBOL}/growth/operating_margin/2025": (
        "the growth table, operating margin, fiscal 2025"
    ),
    f"table:{SYMBOL}/cash_flow/free_cash_flow/2025": (
        "the cash flow table, free cash flow, fiscal 2025"
    ),
    f"table:{SYMBOL}/solvency/net_debt_to_ebitda/2025": (
        "the solvency table, net debt to EBITDA, fiscal 2025"
    ),
    f"table:{SYMBOL}/capital_allocation/share_count_change/2025": (
        "the capital allocation table, share count change, fiscal 2025"
    ),
    f"table:{SYMBOL}/quality/piotroski_f/2025": "the quality table, Piotroski's F, fiscal 2025",
    f"table:{SYMBOL}/quality/altman_z/2025": "the quality table, Altman's Z″, fiscal 2025",
    f"fact:{SYMBOL}/revenue/2026-Q3": "revenue, the third quarter of fiscal 2026",
    f"fact:{SYMBOL}/revenue/2025-Q3": "revenue, the third quarter of fiscal 2025",
    f"estimate:{SYMBOL}/2026-Q3/revenue": (
        "the analysts' average estimate of revenue, the third quarter of fiscal 2026"
    ),
    "derived:412": "derivation 412, the growth of two figures",
    f"{SNAP}/value": "snapshot 38, the value a share, priced 10 Nov 2026",
    f"{SNAP}/inputs/belief": "snapshot 38, the input belief",
    f"multiple:{SYMBOL}/forward_pe/2026-11-10": "the forward P/E on 10 Nov 2026",
    f"multiple:{SYMBOL}/forward_pe/median": "the forward P/E's five-year median",
    "kill:47/threshold": "kill criterion 47, its threshold",
}


def _references() -> list[dict[str, Any]]:
    """The refs the sections cite, each once, in the order of its first cite, numbered from 1."""
    refs: list[str] = []
    for section in SECTIONS:
        for part in section["parts"]:
            if isinstance(part, dict) and part["ref"] not in refs:
                refs.append(part["ref"])
    return [{"n": n, "ref": ref, "source": _SOURCES[ref]} for n, ref in enumerate(refs, 1)]


def _report_row(
    report_id: int,
    revision: int,
    stance: str,
    snapshot: int,
    review: int | None,
    work_item: int | None,
    created: str,
) -> dict[str, Any]:
    """A report's record as the reads give it, without its sections."""
    return {
        "id": report_id,
        "symbol": SYMBOL,
        "revision": revision,
        "mode": "full report",
        "stance": stance,
        "reusesFullReportOf": None,
        "snapshotId": snapshot,
        "reviewId": review,
        "secondaryId": None,
        "workItemId": work_item,
        **AGENT,
        "createdAt": created,
    }


def _judgment(judgment_id: int, kind: str, decision: str, override: int | None) -> dict[str, Any]:
    return {
        "id": judgment_id,
        "reportId": REPORT_ID,
        "symbol": SYMBOL,
        "judgment": kind,
        "decision": decision,
        "overrideId": override,
    }


JUDGMENT_RECORDS: list[dict[str, Any]] = [
    _judgment(101, "phase", "Mature Growth stands, as the classifier reads it.", None),
    _judgment(102, "moat", "Narrow: two rivals now sell lenses of the same grade.", 12),
    _judgment(103, "belief", "The base rate stands.", None),
    _judgment(104, "roic", "The five-year return on new capital stands.", None),
]

_EVIDENCE = [{"kind": "url", "ref": "https://lanternfield.example/q3-2026", "note": "page 4"}]
OVERRIDE: dict[str, Any] = {
    "id": 12,
    "symbol": SYMBOL,
    "tag": "moat.class",
    "old": None,
    "new": "Narrow",
    "unit": "class",
    "reason": "Two rivals now sell lenses of the same grade at lower prices.",
    "evidence": _EVIDENCE,
    "lifetime": "lasting",
    "period": None,
    "correctedValue": None,
    "snapshotId": SNAPSHOT_ID,
    **AGENT,
    "at": "2026-11-11T13:50:00+00:00",
    "state": "applied",
    "message": "",
    "reviewId": REVIEW_ID,
    "dropReason": None,
    "droppedAt": None,
}
_BRIDGE_LINE: dict[str, Any] = {
    "tag": "moat.class",
    "overrideId": 12,
    "old": "Wide",
    "new": "Narrow",
    "delta": -14.5,
    "refusal": None,
}
# The line as the read gives a review of ``records`` (``research_api.bridge_lines``): its label,
# its unit, and its override's reason and writer.
_RECORD_LINE: dict[str, Any] = _BRIDGE_LINE | {
    "label": "moat",
    "unit": "class",
    "reason": OVERRIDE["reason"],
    "principal": "agent",
    "actor": "claude-opus-5-5",
}
_RUNWAY: dict[str, Any] = OVERRIDE | {
    "id": 10,
    "tag": "return.runway",
    "old": 0.472,
    "new": 0.214,
    "unit": "ratio",
    "reason": "The return on new plants falls as the newest grade's premium fades.",
    "lifetime": "lasting",
    "snapshotId": 33,
    "at": "2026-10-02T10:10:00+00:00",
    "state": "dropped",
    "reviewId": 4,
    "dropReason": "superseded by report 31's review",
    "droppedAt": "2026-11-11T13:50:00+00:00",
}
_GUIDANCE_RECORD: dict[str, Any] = {
    "id": 14,
    "symbol": SYMBOL,
    "metric": "revenue",
    "period": "2026",
    "low": 440e9,
    "high": 455e9,
    "midpoint": 447.5e9,
    "step": 0.081,
    "basis": "gaap",
    "asOf": "2026-10-22",
    "text": "Revenue for fiscal 2026 of TWD 440 to 455 billion.",
    "source": "https://lanternfield.example/q3-2026",
    **AGENT,
    "createdAt": "2026-11-11T13:40:00+00:00",
    "supersededBy": None,
    "currency": "TWD",
}


def _input(
    name: str, value: Any, unit: str, tag: str, source: str, note: str | None
) -> dict[str, Any]:
    """An input as Appendix A lists it: a DATA input observed with the snapshot's data, a RULE
    the policy's, a JUDGMENT an override's, entered at the override's time."""
    observed = tag == "DATA"
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "tag": tag,
        "kind": {"DATA": "observed", "RULE": "rule", "JUDGMENT": "judgment"}[tag],
        "source": source,
        "asOf": "2026-11-10" if observed else None,
        "observedAt": "2026-11-10T21:00:00+00:00" if observed else None,
        "enteredAt": OVERRIDE["at"] if tag == "JUDGMENT" else None,
        "estimateMethod": None,
        "note": note,
    }


_POLICY = "policy fairband-policy-v17"
APPENDIX_A: dict[str, Any] = {
    "snapshot": {
        "id": SNAPSHOT_ID,
        "dataDate": "2026-11-10",
        "priceDate": "2026-11-10",
        "validUntil": "2027-02-12",
        "currency": "TWD",
        "price": 176.8,
        "value": 196.5,
        "phase": "Mature Growth",
        "route": "mature-growth",
        "refusal": None,
    },
    "inputs": [
        _input("price", 176.8, "USD", "DATA", "FMP quote", None),
        _input("shares_diluted", 2262000000.0, "shares", "DATA", "FMP income-statement", None),
        _input("revenue_ttm", 445.1e9, "TWD", "DATA", "FMP income-statement", None),
        _input("required_return", 0.09, "ratio", "RULE", _POLICY, None),
        _input(
            "moat.class",
            None,
            "class",
            "JUDGMENT",
            "override 12, agent claude-opus-5-5",
            f"Narrow: {OVERRIDE['reason']}",
        ),
        _input("belief", 0.063, "ratio", "RULE", _POLICY, "the base-rate median plus 2 points"),
    ],
    "overrides": [
        {
            key: OVERRIDE[key]
            for key in (
                "id",
                "tag",
                "old",
                "new",
                "unit",
                "reason",
                "evidence",
                "lifetime",
                "period",
                "principal",
                "actor",
                "at",
            )
        }
        | {"inForce": None, "rescaled": None}
    ],
    "guidance": [
        {
            key: _GUIDANCE_RECORD[key]
            for key in ("id", "metric", "period", "low", "high", "midpoint", "currency", "basis")
        }
        | {"asOf": _GUIDANCE_RECORD["asOf"], "state": "current", "citedBy": []}
    ],
    "bridge": {
        "reviewId": REVIEW_ID,
        "mechanicalValue": 196.5,
        "reviewedValue": 182.0,
        "refusal": None,
        "lines": [_BRIDGE_LINE | {"label": "moat"}],
    },
    "secondary": None,
    "noSecondary": "No secondary valuation: the review gives the company a value",
    "checks": [
        {
            "check": "the mode's section count",
            "rule": "twelve sections for a full report, ten for a valuation review",
        },
        {"check": "the stance word", "rule": "one of buy, hold, trim, avoid"},
        {
            "check": "the required judgments",
            "rule": "phase, moat and belief; roic on Mature Growth and Mature Stable; "
            "target_margin on High Growth, Young Growth and Start-up",
        },
        {
            "check": "the headings in the spec's order",
            "rule": "the twelve headings in order, sections 2 and 3 left out of a valuation review",
        },
        {
            "check": "a secondary valuation on a refused snapshot",
            "rule": "on a refused latest snapshot, the company's newest secondary valuation rests "
            "on it or on one it reprices",
        },
        {"check": "unresolved reference", "rule": "every cite's reference names a stored value"},
        {
            "check": "wrong unit",
            "rule": "every cite reads its value in its unit at the report's rounding",
        },
        {
            "check": "wrong period",
            "rule": "every cite's period, when it names one, is its reference's",
        },
        {
            "check": "wrong snapshot",
            "rule": "every cite rests on the company's latest snapshot, or one the latest reprices",
        },
        {"check": "a number with no reference", "rule": "every quantity in the text is cited"},
        {
            "check": "a derived figure the engine has not emitted",
            "rule": "every derived figure is a stored derivation",
        },
    ],
    "versions": {
        "method": "fairband-mechanical/1.7",
        "policy": "fairband-policy-v17",
        "settingsHash": EMPTY_SETTINGS_HASH,
        "review": "fairband-review/1",
        "secondary": None,
    },
    "classifier": {
        "phase": "Mature Growth",
        "reason": None,
        "yearsUsed": 10,
        "positiveYearsLastFive": 5,
        "positiveYearsOnFile": 10,
        "growth3Y": 0.142,
        "growthWord": "Fast",
        "growthDecile": 9,
        "revenueSlope": 31.4e9,
        "margin": 0.316,
        "marginSlope": 0.012,
        "marginDirection": "Rising",
        "fcfSign": "positive",
        "dickinson": "Mature",
        "checks": [],
    },
}

REPORTS: list[dict[str, Any]] = [
    _report_row(REPORT_ID, 2, STANCE, SNAPSHOT_ID, REVIEW_ID, 29, CREATED),
    _report_row(19, 1, "trim", 33, None, 17, "2026-10-02T10:40:00+00:00"),
]
REPORT: dict[str, Any] = REPORTS[0] | {
    "sections": SECTIONS,
    "judgments": JUDGMENT_RECORDS,
    "appendixA": APPENDIX_A,
    "appendixB": appendix_b(SECTIONS),
    "references": _references(),
}

CALL: dict[str, Any] = {
    "value": 182.0,
    "basis": "reviewed",
    "note": None,
    "levels": {"buy": 145.6, "fairLow": 163.8, "fairHigh": 200.2, "trim": 273.0},
    "priceToValue": 176.8 / 182.0,
    "designation": "near",
    "price": 176.8,
    "priceDate": "2026-11-10",
    "dataDate": "2026-11-10",
    "validUntil": "2027-02-12",
    "mechanicalValue": 196.5,
    "refusal": None,
}


def _at(report_id: int | None) -> str:
    """When a record a report wrote was written: report 31's time, else report 19's."""
    return CREATED if report_id == REPORT_ID else str(REPORTS[1]["createdAt"])


def _criterion(
    criterion_id: int, text: str, report_id: int, state: str, **extra: Any
) -> dict[str, Any]:
    return {
        "id": criterion_id,
        "symbol": SYMBOL,
        "text": text,
        "state": state,
        "reportId": report_id,
        **AGENT,
        "at": _at(report_id),
        "stateReason": None,
        "stateAt": None,
        "threshold": None,
        "unit": None,
        "currency": None,
    } | extra


def _news(
    item_id: int, day: str, headline: str, source: str, report_id: int | None
) -> dict[str, Any]:
    return {
        "id": item_id,
        "symbol": SYMBOL,
        "date": day,
        "headline": headline,
        "source": source,
        "text": f"{headline}.",
        "killCriterionId": None,
        "reportId": report_id,
        **AGENT,
        "at": _at(report_id),
    }


CRITERIA: list[dict[str, Any]] = [
    _criterion(52, "Sensor revenue falls two quarters in a row.", REPORT_ID, "open"),
    _criterion(
        47,
        "The gross margin falls below the threshold.",
        19,
        "open",
        threshold=42.0,
        unit="percent",
    ),
    _criterion(
        46,
        "A rival matches the newest lens grade.",
        19,
        "triggered",
        stateReason="A rival launched a lens of the same grade on 28 Oct 2026.",
        stateAt="2026-11-11T13:30:00+00:00",
    ),
]
NEWS_ITEMS: list[dict[str, Any]] = [
    _news(
        88,
        "2026-11-03",
        "A new supply contract with a car supplier",
        "https://lanternfield.example/contract",
        REPORT_ID,
    ),
    _news(87, "2026-10-28", "A rival launched a lens of the same grade", "trade press", REPORT_ID),
    _news(
        61,
        "2026-09-18",
        "The newest lens grade went into production",
        "https://lanternfield.example/grade",
        19,
    ),
]

_LEDGER: list[dict[str, Any]] = [
    {
        "id": row_id,
        "at": at,
        **AGENT,
        "kind": kind,
        "symbol": SYMBOL,
        "refTable": table,
        "refId": ref_id,
        "snapshotId": SNAPSHOT_ID,
        "workItemId": 29,
        "summary": summary,
    }
    for row_id, at, kind, table, ref_id, summary in (
        (905, CREATED, "report", "reports", REPORT_ID, "full report revision 2: hold"),
        (904, "2026-11-11T13:50:00+00:00", "override", "overrides", 12, "moat.class: Narrow"),
        (
            903,
            "2026-11-11T13:45:00+00:00",
            "finding",
            "findings",
            230,
            "Sensor sales to car suppliers rose for six quarters running.",
        ),
        (902, "2026-11-11T13:40:00+00:00", "guidance", "guidance", 14, "revenue 2026"),
    )
]

GUIDANCE: list[dict[str, Any]] = [
    _GUIDANCE_RECORD
    | {
        "id": 15,
        "metric": "operating_margin",
        "low": 0.07,
        "high": 0.10,
        "midpoint": 0.085,
        "step": None,
        "text": "An operating margin for fiscal 2026 of 7% to 10% on the new plants.",
        "createdAt": "2026-11-11T13:42:00+00:00",
        "currency": None,
    },
    _GUIDANCE_RECORD,
    _GUIDANCE_RECORD
    | {
        "id": 11,
        "low": 430e9,
        "high": 450e9,
        "midpoint": 440e9,
        "asOf": "2026-07-24",
        "text": "Revenue for fiscal 2026 of TWD 430 to 450 billion.",
        "createdAt": "2026-10-02T10:15:00+00:00",
        "supersededBy": 14,
    },
]


def _finding(finding_id: int, as_of: str, text: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": finding_id,
        "symbol": SYMBOL,
        "asOf": as_of,
        "text": text,
        "value": None,
        "unit": None,
        "period": None,
        **AGENT,
        "at": "2026-11-11T13:45:00+00:00",
        "currency": None,
        "source": {"kind": "url", "ref": "https://lanternfield.example/q3-2026", "note": None},
    } | extra


FINDINGS: list[dict[str, Any]] = [
    _finding(
        231,
        "2025-12-31",
        "Free cash flow in fiscal 2025 funded the new plants in full.",
        value=98.3e9,
        unit="currency",
        period="2025",
        currency="TWD",
        source={"kind": "filing", "ref": "annual report 2025", "note": "page 61"},
    ),
    _finding(
        230,
        "2026-10-22",
        "Sensor sales to car suppliers rose for six quarters running.",
        value=6.0,
        unit="count",
        period="2026-Q3",
        source={
            "kind": "transcript",
            "ref": "the call of 22 Oct 2026",
            "note": "the chief executive's remarks",
        },
    ),
    _finding(229, "2026-10-21", "The company named a new head of its car business."),
]

_REVIEW: dict[str, Any] = {
    "id": REVIEW_ID,
    "symbol": SYMBOL,
    "snapshotId": SNAPSHOT_ID,
    "refreshId": None,
    "createdAt": "2026-11-11T13:50:00+00:00",
    "value": 182.0,
    "buyLevel": 145.6,
    "fairLow": 163.8,
    "fairHigh": 200.2,
    "trimLevel": 273.0,
    "priceToValue": 176.8 / 182.0,
    "designation": "near",
    "refusal": None,
    "mechanicalValue": 196.5,
    "bridge": [_RECORD_LINE],
    "overrideIds": [12],
    "policyVersion": "fairband-policy-v17",
    "methodVersion": "fairband-mechanical/1.7",
    "reviewMethod": "fairband-review/1",
    "settingsHash": EMPTY_SETTINGS_HASH,
    "decilesRefreshId": 3,
}
REVIEWS: list[dict[str, Any]] = [
    _REVIEW
    | {
        "id": 7,
        "snapshotId": 41,
        "refreshId": 3,
        "createdAt": "2026-11-14T06:25:00+00:00",
        "priceToValue": 182.4 / 182.0,
    },
    _REVIEW,
    _REVIEW
    | {
        "id": 4,
        "snapshotId": 33,
        "createdAt": "2026-10-02T10:10:00+00:00",
        "value": None,
        "buyLevel": None,
        "fairLow": None,
        "fairHigh": None,
        "trimLevel": None,
        "priceToValue": None,
        "designation": None,
        "refusal": "The runway return leaves no value above zero.",
        "mechanicalValue": 171.2,
        "bridge": [
            {
                "tag": "return.runway",
                "overrideId": 10,
                "old": 0.472,
                "new": 0.214,
                "delta": None,
                "refusal": "The runway return leaves no value above zero.",
                "label": "runway return",
                "unit": "ratio",
                "reason": _RUNWAY["reason"],
                "principal": "agent",
                "actor": "claude-opus-5-5",
            }
        ],
        "overrideIds": [10],
    },
]

RECORDS: dict[str, Any] = {
    "overrides": [OVERRIDE, _RUNWAY],
    "guidance": GUIDANCE,
    "judgments": JUDGMENT_RECORDS,
    "killCriteria": CRITERIA,
    "newsItems": NEWS_ITEMS,
    "notes": [
        {
            "id": 9,
            "symbol": SYMBOL,
            "text": "Ask about the car contracts at the next call.",
            "principal": "owner",
            "actor": None,
            "client": None,
            "at": "2026-11-12T08:15:00+00:00",
            "overrideId": None,
        }
    ],
    "findings": FINDINGS,
    "ledger": _LEDGER,
    "reviews": REVIEWS,
    "secondaryValuations": [
        {
            "id": 5,
            "symbol": SYMBOL,
            "snapshotId": 33,
            "createdAt": "2026-10-02T10:20:00+00:00",
            **AGENT,
            "parts": [
                {
                    "name": "the business",
                    "fcff": [3.0e9, 3.2e9, 3.4e9],
                    "terminalGrowth": 0.03,
                    "note": None,
                    "pv": [2.75e9, 2.69e9, 2.63e9],
                    "terminal": 56.7e9,
                    "terminalPv": 43.8e9,
                    "value": 51.87e9,
                }
            ],
            "firmValue": 51.87e9,
            "debt": 0.0,
            "cash": 0.0,
            "shares": 2262000000.0 / 5.0,
            "equity": 51.87e9,
            "valuePerShare": 114.65,
            "buyLevel": 85.99,
            "fairLow": 97.45,
            "fairHigh": 131.85,
            "trimLevel": 171.98,
            "priceToValue": 1.32,
            "designation": "above",
            "reason": "A second view while the newest grade ramps.",
            "evidence": _EVIDENCE,
            "debtSource": "none",
            "cashSource": "none",
            "policyVersion": "fairband-policy-v17",
            "settingsHash": EMPTY_SETTINGS_HASH,
            "decilesRefreshId": None,
            "secondaryMethod": "fairband-secondary/2",
            "form": "parts",
            "drivers": None,
            "projection": None,
            "grid": {
                "rows": [-0.01, 0.0, 0.01],
                "cols": [0.08, 0.09, 0.1],
                "cells": [[121.2, 109.8, 100.4], [126.6, 114.65, 104.7], [133.1, 120.0, 109.3]],
                "rowsAre": "shifts",
            },
            "fxRate": 32.4,
        }
    ],
    "ledgerCount": len(_LEDGER),
}

ANSWER: dict[str, Any] = {
    "symbol": SYMBOL,
    "dataDate": None,
    "quote": page_answers.OVERVIEW["quote"],
    "reports": REPORTS,
    "report": REPORT,
    "call": CALL,
    "ofReport": {
        "killCriteria": [c for c in CRITERIA if c["id"] in (52, 47)],
        "newsItems": [n for n in NEWS_ITEMS if n["reportId"] == REPORT_ID],
    },
    "records": RECORDS,
}


def answer() -> dict[str, Any]:
    """A copy of ``ANSWER``."""
    return copy.deepcopy(ANSWER)


# ------------------------------------------------------------------------------- the series


def _column(period: str) -> dict[str, str]:
    """A table's column as the financial tables' read serves it, by its period."""
    if period == "ttm":
        return {"period": period, "kind": "trailing", "label": "12 months to 30 Sep 2026"}
    if period.endswith("E"):
        return {"period": period, "kind": "estimate", "label": f"{period[:-1]} estimate"}
    if "-Q" in period:
        year, quarter = period.split("-")
        return {"period": period, "kind": "quarter", "label": f"{quarter} {year}"}
    return {"period": period, "kind": "fiscal", "label": period}


def _table(
    name: str, periods: list[str], rows: dict[str, tuple[str, list[float | None]]]
) -> dict[str, Any]:
    """A table as the read serves it: its columns, and each row a cell under each column."""
    return {
        "name": name,
        "columns": [_column(period) for period in periods],
        "rows": [
            {
                "name": row,
                "unit": unit,
                "cells": [
                    {
                        "period": period,
                        "value": value,
                        "unit": unit,
                        "ref": f"table:{SYMBOL}/{name}/{row}/{period}",
                        "note": None,
                    }
                    for period, value in zip(periods, values, strict=True)
                ],
            }
            for row, (unit, values) in rows.items()
        ],
    }


_YEARS = ["2023", "2024", "2025", "ttm"]
TABLES: dict[str, Any] = {
    "symbol": SYMBOL,
    "currency": "TWD",
    "tables": [
        _table(
            "growth",
            [*_YEARS, "2026E"],
            {
                "revenue": ("currency", [362.3e9, 385.5e9, 412.6e9, 445.1e9, 452.0e9]),
                "operating_margin": ("percent", [0.29, 0.30, 0.316, 0.32, None]),
                "eps": ("per-share", [42.1, 45.8, 52.3, 55.0, 58.2]),
            },
        ),
        _table(
            "cash_flow",
            _YEARS,
            {
                "free_cash_flow": ("currency", [80.1e9, 91.2e9, 98.3e9, 101.0e9]),
                "stock_compensation_to_revenue": ("percent", [0.011, 0.012, 0.012, 0.013]),
            },
        ),
        _table(
            "solvency",
            _YEARS,
            {
                "net_debt_to_ebitda": ("multiple", [-0.2, -0.3, -0.4, -0.4]),
                "interest_coverage": ("multiple", [48.0, 52.0, 61.0, 63.0]),
            },
        ),
        _table(
            "returns",
            _YEARS[:3],
            {"roic": ("percent", [0.19, 0.20, 0.214]), "hurdle_rate": ("percent", [0.09] * 3)},
        ),
        _table(
            "capital_allocation",
            _YEARS,
            {
                "dividends": ("currency", [-20.1e9, -22.4e9, -25.0e9, -25.9e9]),
                "buybacks": ("currency", [-8.0e9, -9.5e9, -11.2e9, -11.8e9]),
                "share_count_change": ("percent", [-0.008, -0.009, -0.011, None]),
            },
        ),
        _table(
            "quality",
            _YEARS[:3],
            {"altman_z": ("score", [5.8, 6.0, 6.2]), "piotroski_f": ("score", [7.0, 6.0, 7.0])},
        ),
    ],
    "quarters": _table(
        "quarters",
        ["2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"],
        {
            "revenue": ("currency", [104.1e9, 99.8e9, 105.2e9, 112.5e9]),
            "operating_margin": ("percent", [0.31, 0.30, 0.32, 0.33]),
            "eps": ("per-share", [12.9, 12.2, 13.4, 14.6]),
        },
    ),
}
CLOSES: dict[str, Any] = {
    "symbol": SYMBOL,
    "closes": [
        {
            "date": day,
            "close": {"value": close, "unit": "per-share", "ref": f"close:{SYMBOL}/{day}"},
        }
        for day, close in (
            ("2025-09-30", 151.2),
            ("2025-12-31", 158.4),
            ("2026-03-31", 149.9),
            ("2026-06-30", 166.0),
            ("2026-09-30", 171.3),
            ("2026-11-10", 176.8),
        )
    ],
}
BAND: dict[str, Any] = {
    "symbol": SYMBOL,
    "points": [
        {
            "day": "2026-11-10",
            "price": 176.8,
            "fairLow": 176.85,
            "fairHigh": 216.15,
            "buyLevel": 147.38,
            "trimLevel": 294.75,
            "snapshotId": SNAPSHOT_ID,
        }
    ],
}


def _multiple(name: str, points: list[tuple[str, float]], since: str | None) -> dict[str, Any]:
    """A P/E series as the multiples history answers it, its statistics over its points."""
    ref = f"multiple:{SYMBOL}/{name}"
    values = [value for _, value in points]
    stats = {
        "avg10y": sum(values) / len(values),
        "median10y": sorted(values)[len(values) // 2],
        "high10y": max(values),
        "low10y": min(values),
    }
    return {
        "points": [{"day": day, "value": value, "ref": f"{ref}/{day}"} for day, value in points],
        "stats": {
            stat: {"value": value, "unit": "multiple", "ref": f"{ref}/{stat}"}
            for stat, value in stats.items()
        },
        "since": since,
        "responseId": None,
        "note": None,
    }


MULTIPLES: dict[str, Any] = {
    "symbol": SYMBOL,
    "pe": _multiple(
        "pe",
        [("2026-06-30", 22.1), ("2026-07-31", 23.4), ("2026-08-31", 24.0), ("2026-09-30", 23.2)],
        None,
    ),
    "peNote": None,
    "peForward": _multiple(
        "pe_forward",
        [(f"2026-11-{day:02d}", 23.5 + day / 10) for day in (5, 6, 9, 10, 11, 12)],
        "2026-11-05",
    ),
}
READING_ID = 9
READING: dict[str, Any] = {
    "id": READING_ID,
    "symbol": SYMBOL,
    "snapshotId": SNAPSHOT_ID,
    "reviewId": REVIEW_ID,
    "title": f"Sensitivity {READING_ID}: the belief by the runway return",
    "rowLabel": "belief",
    "colLabel": "runway return",
    "rowWords": ["5.3%", "6.3%", "7.3%"],
    "colWords": ["15.0%", "20.0%", "25.0%"],
    "cells": [[160.2, 171.9, 180.4], [170.6, 182.0, 191.3], [182.1, 193.8, 203.0]],
    "current": [2, 2],
}
READING_REF = f"sensitivity:{READING_ID}/2/2"
COMPANY = f"/api/companies/{SYMBOL}"
SERIES: dict[str, dict[str, Any]] = {
    f"{COMPANY}/financial-tables": TABLES,
    f"{COMPANY}/multiples-history": MULTIPLES,
    f"{COMPANY}/price-history?years=5": CLOSES,
    f"{COMPANY}/band-history": BAND,
    f"/api/sensitivities/{READING_ID}": READING,
}


def series_replies(**held: bool) -> dict[str, Any]:
    """The fetch's replies of ``tests/web/research.mjs`` for every series, each 200 with its
    body; an address in ``held`` (its key in ``SERIES``' order: ``tables``, ``multiples``,
    ``closes``, ``band``, ``reading``) waits until a ``release`` step lets it land."""
    keys = ("tables", "multiples", "closes", "band", "reading")
    return {
        url: {"status": 200, "body": body} | ({"held": True} if held.get(key) else {})
        for key, (url, body) in zip(keys, SERIES.items(), strict=True)
    }
