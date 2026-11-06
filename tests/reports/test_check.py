"""The number check (spec 2026-11-06 Tier 2, 13.3 and 20.3) on the ``snapshots`` fixture of
``conftest.py``: AAPL, the Mature Growth golden renamed (a price of $150, a value of $133.37, price
÷ value 1.12, a ten-year aggregate ROIC of 22.7%), with ACME's synthetic statements (revenue $2,100
m in fiscal 2025, up 5.0%; capital spending −$126 m); AAL, refused. A clean report publishes; each
failure of spec 20.3 is one finding, located."""

import sqlite3
from dataclasses import replace
from datetime import date
from typing import Any

import pytest
from refresh.synthetic import NOW

from fairband.engine.route import reprice
from fairband.policy import Policy
from fairband.reports.check import (
    CHECKS,
    FAILURES,
    HEADINGS,
    NO_REFERENCE,
    NOT_EMITTED,
    UNRESOLVED,
    WRONG_PERIOD,
    WRONG_SNAPSHOT,
    WRONG_UNIT,
    Finding,
    check_sections,
    cited_records,
    headings,
    parse_cite,
    quantities,
    required_judgments,
    rounded_equal,
    shown,
    structure_refusal,
)
from fairband.store.ledger import Writer
from fairband.store.secondary import insert_derivation
from fairband.store.snapshots import insert_snapshot, snapshot_row

AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
SMALL_TALK = "Three reasons stand out in FY2025: the 10-K, Q3 and the plan for 2026."


def _cite(cite: str, ref: str, period: str | None = None) -> dict[str, Any]:
    return {"cite": cite, "ref": ref} | ({} if period is None else {"period": period})


def _clean(sid: int) -> list[Any]:
    """Section 1's parts: every cite resolves at the report's rounding."""
    s = f"snapshot:{sid}"
    return [
        "The price of ",
        _cite("$150.00", f"{s}/price"),
        " is above the value of ",
        _cite("$133", f"{s}/value"),
        " (",
        _cite("$133.37", f"{s}/value"),
        " a share), price ÷ value ",
        _cite("1.12x", f"{s}/price_to_value"),
        ". Revenue of ",
        _cite("$2,100,000,000", "fact:AAPL/revenue/2025", "FY2025"),
        " grew ",
        _cite("5.0%", "table:AAPL/growth/revenue_growth/2025", "2025"),
        "; capital spending was ",
        _cite("−$126,000,000", "fact:AAPL/capex/2025"),
        " or ",
        _cite("($126,000,000)", "fact:AAPL/capex/2025"),
        ". The ten-year return on capital of ",
        _cite("22.7%", f"{s}/inputs/aggregate_roic"),
        " clears the hurdle of ",
        _cite("9.0%", "policy:required_return"),
        "; free cash flow is ",
        _cite("1.27x", "table:AAPL/cash_flow/fcf_to_net_income/2025"),
        " net income, the moat ",
        _cite("Wide", f"{s}/inputs/moat_class"),
        ". ",
        SMALL_TALK,
    ]


def _report(first: list[Any]) -> list[dict[str, Any]]:
    """A full report whose section 1 holds ``first`` and every other section plain words."""
    rest = [{"heading": h, "parts": ["Plain words, no figures."]} for h in HEADINGS[1:]]
    return [{"heading": HEADINGS[0], "parts": first}, *rest]


def _check(conn: sqlite3.Connection, policy: Policy, sid: int, *bad: Any) -> list[Finding]:
    return check_sections(conn, "AAPL", sid, _report([*_clean(sid), *bad]), policy)


def _one(found: list[Finding], sid: int, text: str) -> Finding:
    """The one finding, located on the part after the clean ones."""
    assert len(found) == 1, found
    assert found[0].where == f"section 1, part {len(_clean(sid)) + 1}: {text}"
    return found[0]


def test_a_clean_report_has_no_findings(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    assert _check(conn, policy, snapshots["AAPL"]) == []


def test_wrong_snapshot(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid, aal = snapshots["AAPL"], snapshots["AAL"]
    found = _one(_check(conn, policy, sid, _cite("$133", f"snapshot:{aal}/value")), sid, "$133")
    assert found.what == WRONG_SNAPSHOT
    assert found.detail == (
        f"snapshot:{aal}/value rests on snapshot {aal}; the company's latest is snapshot {sid}:"
        " read it again"
    )


def test_wrong_unit_on_rounding(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    price = f"snapshot:{sid}/inputs/price"
    found = _one(_check(conn, policy, sid, _cite("$12.345", price)), sid, "$12.345")
    assert (found.what, found.detail) == (WRONG_UNIT, f"{price} reads $150.00")
    # the rounding itself: a price is written to cents, so $12.345 is not one, even of $12.345
    assert not rounded_equal(12.345, "$", 12.345, "per-share")
    assert rounded_equal(12.35, "$", 12.345, "per-share")
    assert not _check(conn, policy, sid, _cite("$150", price))  # whole dollars, as a value is


def test_wrong_unit_on_a_suffix(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    roic = f"snapshot:{sid}/inputs/aggregate_roic"
    found = _one(_check(conn, policy, sid, _cite("12.3x", roic)), sid, "12.3x")
    assert found.what == WRONG_UNIT
    assert found.detail == f"'12.3x' does not fit a percent figure: {roic} reads 22.7%"


def test_wrong_period(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    sid = snapshots["AAPL"]
    cite = _cite("$2,100,000,000", "fact:AAPL/revenue/2025", "2024")
    found = _one(_check(conn, policy, sid, cite), sid, "$2,100,000,000")
    assert (found.what, found.detail) == (
        WRONG_PERIOD,
        "fact:AAPL/revenue/2025 is for 2025, not 2024",
    )
    # a ref with no period takes no period
    on_price = _cite("$150.00", f"snapshot:{sid}/price", "2025")
    assert _one(_check(conn, policy, sid, on_price), sid, "$150.00").what == WRONG_PERIOD


def test_unresolved_reference(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    cite = _cite("$2,100,000,000", "fact:AAPL/revenue/2031")
    found = _one(_check(conn, policy, sid, cite), sid, "$2,100,000,000")
    assert (found.what, found.detail) == (
        UNRESOLVED,
        "fact:AAPL/revenue/2031 names no stored value",
    )
    # a cell the record holds with no figure
    runway = _cite("2.5 years", "table:AAPL/solvency/cash_runway_years/2025")
    found = _one(_check(conn, policy, sid, runway), sid, "2.5 years")
    assert (found.what, found.detail) == (
        UNRESOLVED,
        "table:AAPL/solvency/cash_runway_years/2025 holds no value",
    )


def test_a_number_with_no_reference(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    found = _one(_check(conn, policy, sid, "Revenue grew 11.2% last year."), sid, "11.2%")
    assert found.what == NO_REFERENCE


def test_a_derived_figure_the_engine_has_not_emitted(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    found = _one(_check(conn, policy, sid, _cite("1.5x", "derived:999")), sid, "1.5x")
    assert (found.what, found.detail) == (
        NOT_EMITTED,
        "derived:999 is no derivation of AAPL: derive the figure and cite its id",
    )
    # a ratio written out in a plain part
    found = _one(_check(conn, policy, sid, "Debt is 2.4x earnings."), sid, "2.4x")
    assert found.what == NOT_EMITTED
    # a stored derivation, cited at its rounding, passes; one with no value does not
    a, b = "fact:AAPL/revenue/2025", "fact:AAPL/revenue/2024"
    growth = insert_derivation(conn, "AAPL", "growth", a, b, None, 0.05, "percent", AGENT, NOW)
    undefined = insert_derivation(conn, "AAPL", "ratio", a, b, None, None, None, AGENT, NOW)
    assert _check(conn, policy, sid, _cite("5.0%", f"derived:{growth}")) == []
    found = _one(_check(conn, policy, sid, _cite("1.0x", f"derived:{undefined}")), sid, "1.0x")
    assert (found.what, found.detail) == (
        NOT_EMITTED,
        f"derived:{undefined} has no value: derive the figure and cite its id",
    )


def test_years_quarters_forms_and_small_counts_pass(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    plain = "three reasons; FY2025; the 10-K and an 8-K; Q3; 2026; on 27 Oct 2026; section 13.3"
    assert _check(conn, policy, sid, plain) == []


def test_the_cite_parser_reads_separators_and_minus_signs() -> None:
    assert parse_cite("$1,234.50") == (1234.5, "$") and parse_cite("−3.2%") == (-3.2, "%")
    assert parse_cite("(12.3%)") == (-12.3, "%")
    assert parse_cite("-3.2%") == (-3.2, "%")
    assert parse_cite("2.5 years") == (2.5, "years")
    assert parse_cite("12.3x") == (12.3, "x") and parse_cite("12.3×") == (12.3, "x")
    assert parse_cite("−$126,000,000") == (-126_000_000.0, "$")
    assert parse_cite("($3.20)") == (-3.2, "$")
    assert parse_cite("42") == (42.0, "")
    for text in ("$12%", "(3.2", "about 3", "3.2.1", "", "Wide"):
        assert parse_cite(text) is None, text


def test_findings_are_located(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    price = f"snapshot:{sid}/inputs/price"
    sections = _report(["The price ", "is ", _cite("$12.345", price)])
    sections[3] = {"heading": HEADINGS[3], "parts": ["Margins of 20.0% held."]}
    found = check_sections(conn, "AAPL", sid, sections, policy)
    assert [(f.where, f.what) for f in found] == [
        ("section 1, part 3: $12.345", WRONG_UNIT),
        ("section 4, part 1: 20.0%", NO_REFERENCE),
    ]


def test_a_reprice_keeps_the_cites_and_a_revalue_rejects_them(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    cited = snapshot_row(conn, sid)
    assert cited is not None and cited.value is not None
    repriced = reprice(cited.result, 160.0, date(2026, 11, 2), policy)
    latest = insert_snapshot(conn, repriced, cited.refresh_id, clock=lambda: NOW)
    assert check_sections(conn, "AAPL", latest, _report(_clean(sid)), policy) == []
    revalued = replace(repriced, value=cited.value + 1.0)
    latest = insert_snapshot(conn, revalued, cited.refresh_id, clock=lambda: NOW)
    found = check_sections(conn, "AAPL", latest, _report(_clean(sid)), policy)
    assert {f.what for f in found} == {WRONG_SNAPSHOT}
    assert all(f"the company's latest is snapshot {latest}" in f.detail for f in found)


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("revenue grew 11.2% in 2025", ["11.2%"]),
        ("a $12.345 price and (12.3%) and −3.2% and -12", ["$12.345", "(12.3%)", "−3.2%", "-12"]),
        ("a 1.5x ratio, 2.4× more, 3.5 percent", ["1.5x", "2.4×", "3.5 percent"]),
        ("1,000 employees and 0.5 of them", ["1,000", "0.5"]),
        ("a 10-year plan", ["10"]),
        ("three reasons, one 9, FY2025, Q3, 2026, (2025), 1990 to 2099", []),
        ("the 10-K, an 8-K, a 20-F, COVID-19, 5G, the 21st century, v1.7", []),
        ("on 27 Oct 2026, on 2026-10-30, Oct. 30, 2026, at https://x.com/2025/10", []),
        ("section 13.3, sections 14, Item 10, § 12, fairband-review/1", []),
        ("from 2024-2025; 1989 and 2100", ["1989", "2100"]),
    ],
)
def test_the_token_rule(text: str, found: list[str]) -> None:
    assert quantities(text) == found


@pytest.mark.parametrize(
    ("cite", "suffix", "value", "unit", "equal"),
    [
        (2_100_000_000, "$", 2.1e9, "currency", True),
        (2_100_000_000, "$", 2_100_000_400.0, "currency", False),  # whole dollars
        (133, "$", 133.3665, "per-share", True),  # a value to whole dollars
        (133.37, "$", 133.3665, "per-share", True),  # a price to cents
        (133.4, "$", 133.3665, "per-share", False),
        (22.7, "%", 0.22702, "percent", True),
        (23, "%", 0.22702, "percent", False),  # one decimal
        (1.12, "x", 1.12472, "multiple", True),
        (1.1, "x", 1.12472, "multiple", False),  # two decimals
        (2.5, "years", 2.46, "years", True),
        (8, "", 8.0, "score", True),
        (11, "", 11.0, "count", True),
        (22.7, "", 0.22702, "percent", False),  # a percent needs its sign
        (12.3, "x", 0.123, "percent", False),
        (5.4, "", 5.4321, None, True),  # no unit: the cite's own precision
        (5.5, "", 5.4321, None, False),
        (-3.2, "%", -0.032, "percent", True),
    ],
)
def test_rounded_equal(
    cite: float, suffix: str, value: float, unit: str | None, equal: bool
) -> None:
    assert rounded_equal(cite, suffix, value, unit) is equal


def test_shown_writes_the_value_as_its_cite_reads() -> None:
    assert shown(2.1e9, "currency") == "$2,100,000,000"
    assert shown(-126e6, "currency") == "−$126,000,000"
    assert shown(150.0, "per-share") == "$150.00"
    assert shown(0.22702, "percent") == "22.7%"
    assert shown(1.12472, "multiple") == "1.12x"
    assert shown(2.46, "years") == "2.5 years"


def test_the_structural_checks(policy: Policy) -> None:
    full, review = list(HEADINGS), list(headings("valuation review"))
    judged = ["phase", "moat", "belief", "roic"]
    assert len(review) == 8 and "The business" not in review
    assert structure_refusal("full report", "buy", full, judged, "mature-growth", policy) is None
    assert (
        structure_refusal("valuation review", "hold", review, judged, "mature-growth", policy)
        is None
    )
    assert (
        structure_refusal("valuation review", "buy", full, judged, "mature-growth", policy)
        == "a valuation review has 8 sections, not 10"
    )
    assert (
        structure_refusal("full report", "accumulate", full, judged, "mature-growth", policy)
        == "a stance is one of buy, hold, trim or avoid, not 'accumulate'"
    )
    assert (
        structure_refusal("full report", "buy", full, judged[:3], "mature-growth", policy)
        == "the report lacks the judgment roic"
    )
    assert (
        structure_refusal("full report", "buy", full, ["moat"], "revenue-growth", policy)
        == "the report lacks the judgments phase, belief and target_margin"
    )
    assert (
        structure_refusal("full report", "buy", full, [*judged, "moat"], "mature-growth", policy)
        == "one judgment of each kind: moat is given twice"
    )
    swapped = [full[0], full[2], full[1], *full[3:]]
    assert (
        structure_refusal("full report", "buy", swapped, judged, "mature-growth", policy)
        == "section 2 is headed 'The business', not 'Industry and competition'"
    )
    assert required_judgments("start-up") == ("phase", "moat", "belief", "target_margin")
    assert required_judgments("decline") == required_judgments(None) == ("phase", "moat", "belief")
    assert CHECKS[-6:] == FAILURES


def test_cited_records(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    sid = snapshots["AAPL"]
    assert cited_records(conn, _report(_clean(sid))) == (sid, None, None)
    assert cited_records(conn, _report(["no cites"])) == (None, None, None)
