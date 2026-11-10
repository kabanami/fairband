"""The number check (spec 2026-11-06 Tier 2, 13.3 and 20.3) on the ``snapshots`` fixture of
``conftest.py``: AAPL, the Mature Growth golden renamed (a price of $150, a value of $127.68, price
÷ value 1.17, a ten-year aggregate ROIC of 22.7%), with ACME's synthetic statements (revenue $2,100
m in fiscal 2025, up 5.0%; capital spending −$126 m); AAL, refused. A clean report publishes; each
failure of spec 20.3 is one finding, located."""

import sqlite3
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from typing import Any

import pytest
from refresh.synthetic import NOW
from support.engine_companies import fx_inputs, mature_growth_inputs, universe_deciles
from support.web import TODAY

from fairband.engine.overrides import Override
from fairband.engine.review import review_company
from fairband.engine.route import reprice, value_company
from fairband.engine.types import Route, ValuationResult
from fairband.policy import Policy
from fairband.refresh.rates import NO_RATE
from fairband.reports.check import (
    CHECKS,
    FAILURES,
    FULL_ONLY,
    HEADINGS,
    NO_REFERENCE,
    NOT_EMITTED,
    STRUCTURE,
    UNRESOLVED,
    WRONG_PERIOD,
    WRONG_SNAPSHOT,
    WRONG_UNIT,
    Finding,
    check_judgments,
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
from fairband.store.guidance import insert_guidance
from fairband.store.ledger import Writer
from fairband.store.overrides import applied_overrides, drop_override, insert_override
from fairband.store.research import add_finding
from fairband.store.reviews import insert_review, review_row
from fairband.store.secondary import insert_derivation, no_secondary
from fairband.store.snapshots import SnapshotRow, insert_snapshot, snapshot_row

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
        _cite("$128", f"{s}/value"),
        " (",
        _cite("$127.68", f"{s}/value"),
        " a share), price ÷ value ",
        _cite("1.17x", f"{s}/price_to_value"),
        ". Revenue of ",
        _cite("$2,100,000,000", "fact:AAPL/revenue/2025", "FY2025"),
        " grew ",
        _cite("5.0%", "table:AAPL/growth/revenue_growth/2025", "2025"),
        " (",
        _cite("$2.1 billion", "fact:AAPL/revenue/2025"),
        "); capital spending was ",
        _cite("$126,000,000", "fact:AAPL/capex/2025"),
        ", ",
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
    found = _one(_check(conn, policy, sid, _cite("$128", f"snapshot:{aal}/value")), sid, "$128")
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
    assert (found.what, found.detail) == (
        WRONG_UNIT,
        f"a price is cited to cents: {price} reads $150.00",
    )
    # the rounding itself: a price is written to cents, so $12.345 is not one, even of $12.345
    assert not rounded_equal(12.345, "$", 12.345, "per-share")
    assert rounded_equal(12.35, "$", 12.345, "per-share")


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


def test_a_quarter_reads_the_same_with_its_dash_or_without(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """A guidance record writes a quarter ``2027Q1`` and the consensus ``2026-Q4``: a cite of
    either names the quarter either way, in any case."""
    sid = snapshots["AAPL"]
    at = NOW
    guided = insert_guidance(
        conn,
        "AAPL",
        "eps",
        "2027Q1",
        1.5,
        1.6,
        "gaap",
        at.date(),
        "We guide Q1.",
        "a 10-Q",
        AGENT,
        at,
        None,
    )
    ref = f"guidance:{guided}/midpoint"
    for period in ("2027-Q1", "2027Q1", "2027-q1"):
        assert _check(conn, policy, sid, _cite("$1.55", ref, period)) == [], period
    found = _one(_check(conn, policy, sid, _cite("$1.55", ref, "2027-Q2")), sid, "$1.55")
    assert (found.what, found.detail) == (WRONG_PERIOD, f"{ref} is for 2027Q1, not 2027-Q2")


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


def test_list_marks_and_a_table_row_are_marks(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 13.1 "The text's shape" and 13.3: a list's number at a line's start and a table's
    separator row are marks, not quantities, and the bold marks hold no number; a count of two
    digits in a sentence is still a quantity."""
    sid = snapshots["AAPL"]
    listed = "".join(f"{n}. A reason in words.\n" for n in range(1, 13))
    table = "| | The quarter |\n|---|---|\n| Revenue | in words |\n"
    plain = f"**Reasons.**\n\n{listed}\n{table}\n**The verdict.** Hold."
    assert _check(conn, policy, sid, plain) == []
    found = _one(_check(conn, policy, sid, "Coverage: 12 analysts follow it."), sid, "12")
    assert found.what == NO_REFERENCE


def test_the_cite_parser_reads_separators_and_minus_signs() -> None:
    assert parse_cite("$1,234.50") == (1234.5, "$") and parse_cite("−3.2%") == (-3.2, "%")
    assert parse_cite("(12.3%)") == (-12.3, "%")
    assert parse_cite("-3.2%") == (-3.2, "%")
    assert parse_cite("2.5 years") == (2.5, "years")
    assert parse_cite("12.3x") == (12.3, "x") and parse_cite("12.3×") == (12.3, "x")
    assert parse_cite("−$126,000,000") == (-126_000_000.0, "$")
    assert parse_cite("($3.20)") == (-3.2, "$")
    assert parse_cite("42") == (42.0, "")
    assert parse_cite("$2.1 billion") == (2.1e9, "$") and parse_cite("$126M") == (126e6, "$")
    assert parse_cite("$1.5bn") == (1.5e9, "$") and parse_cite("($1.5 bn)") == (-1.5e9, "$")
    assert parse_cite("$500k") == (500e3, "$") and parse_cite("8 billion") == (8e9, "")
    assert parse_cite("$1.5B") == (1.5e9, "$") and parse_cite("1.12X") == (1.12, "x")
    assert parse_cite("1.12 X") is None and parse_cite("$1.5bnX") is None
    for text in ("$12%", "(3.2", "about 3", "3.2.1", "", "Wide", "2.1 billion%", "$2bn x"):
        assert parse_cite(text) is None, text


def test_the_cite_parser_reads_a_plus_sign_and_percentage_points() -> None:
    """design.md 7.4's bridge writes a change with its sign, ``+$28``; a change of a percent is in
    points, a percent's suffix."""
    assert parse_cite("+$28") == (28.0, "$") and parse_cite("$+28") == (28.0, "$")
    assert parse_cite("+5.0%") == (5.0, "%") and parse_cite("+1.12x") == (1.12, "x")
    assert parse_cite("2.0 pp") == (2.0, "%") and parse_cite("+2.0pp") == (2.0, "%")
    assert parse_cite("2.0 percentage points") == (2.0, "%")
    assert parse_cite("1 percentage point") == (1.0, "%")
    assert parse_cite("−0.5 pp") == (-0.5, "%")
    for text in ("(+$28)", "+−$28", "+-5%", "++5%", "+$-28", "$2.0 pp", "2.0 pp%", "2.0 bps"):
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
        # a number after $, or before a scale or a unit word, whatever its digits
        ("$391bn", ["$391bn"]),
        ("capex of $1.5bn", ["$1.5bn"]),
        ("sales of $126M", ["$126M"]),
        ("margin of 11.2pp", ["11.2pp"]),
        ("a 50bps cut", ["50bps"]),
        ("8 billion dollars", ["8 billion"]),
        ("US$5 a share", ["US$5"]),
        ("$5 and 3 k and 2 years", ["$5", "2 years"]),  # a one-letter scale needs a $
        # led by $, whatever letters follow; the words in any case, with or without a space
        (
            "$5mm, $5MM, $3.2T, $5bil, $5bln, $5mln",
            ["$5mm", "$5MM", "$3.2T", "$5bil", "$5bln", "$5mln"],
        ),
        ("$ 5 and $5m and $1.5B", ["$ 5", "$5m", "$1.5B"]),
        ("5 percentage points, 5 basis points", ["5 percentage points", "5 basis points"]),
        (
            "5 per cent, 2 Years, 5 x, 5X, 10 bn, 2.5years",
            ["5 per cent", "2 Years", "5 x", "5X", "10 bn", "2.5years"],
        ),
        # an integer joined to one letter with no currency sign is a name
        ("3M Company, Phase 2b, 401k, a 4K screen, Rule 10b-5, 5G", []),
        ("150M users and 500k subscribers", []),  # the trade the ruling accepts
        # a decimal in a one-letter scale, and any currency sign, count
        ("1.5B shares, 2.3M users, 4.5k, 1.5b", ["1.5B", "2.3M", "4.5k", "1.5b"]),
        ("€1.5B, €126m, £5m, £126m, ¥300", ["€1.5B", "€126m", "£5m", "£126m", "¥300"]),
        # an upper-case X is a multiple joined to the number, never after a space
        ("15X and 1.12X", ["15X", "1.12X"]),
        ("In 2023 X lost advertisers; 5 X-ray machines", []),
        ("a Ryzen 9 7950X", ["7950X"]),  # joined: counted, as the ruling accepts
        # a day beside a month is a date, unless a decimal, a % or a scale follows it
        ("In March 12% of stores closed", ["12%"]),
        ("since June 30.5 million shares", ["30.5 million"]),
        ("the US$30 June quarter", ["US$30"]),  # a $ leads it: no day
        ("paid $5 June 30", ["$5"]),
        ("the 2 big ones, 5 more, on 30 June", []),
        # a list's number at a line's start is a mark; a number elsewhere on the line is not
        ("1. one\n 10. ten\n12) twelve\n|---|:---:|\n**bold**", []),
        ("10. The company has 12 analysts", ["12"]),
        ("12 analysts\n10.5% of revenue\n$10. Then", ["12", "10.5%", "$10"]),
        ("revenue rose 10. Then 12. Then", ["10", "12"]),
        ("100. A three-digit mark", ["100"]),
        # a number alone on its line is no mark: the reader shows it as prose
        ("Analysts:\n12.\nMore", ["12"]),
        ("Analysts:\r\n12)\r\nMore", ["12)"]),
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
        (150.0, "$", 150.0, "price", True),  # a price to cents; the check also reads the
        (150.01, "$", 150.0, "price", False),  # cents written, here the number alone
    ],
)
def test_rounded_equal(
    cite: float, suffix: str, value: float, unit: str | None, equal: bool
) -> None:
    assert rounded_equal(cite, suffix, value, unit) is equal


@pytest.mark.parametrize(
    ("cite", "suffix", "value", "unit", "scale", "equal"),
    [
        (391e9, "$", 391.3e9, "currency", 10**9, True),  # the cite's own precision
        (2.1e9, "$", 2.123e9, "currency", 10**9, True),
        (2.2e9, "$", 2.123e9, "currency", 10**9, False),
        (2_100e6, "$", 2.1e9, "currency", 10**6, True),
        (8e9, "", 8.04e9, "count", 10**9, True),
        (8e9, "$", 8.04e9, "count", 10**9, False),  # a count takes no $
        (1.5e9, "$", 1.5e9, "per-share", 10**9, False),  # a scale fits a total or a count
        (1.5e9, "%", 1.5e9, "currency", 10**9, False),
    ],
)
def test_rounded_equal_with_a_scale_word(
    cite: float, suffix: str, value: float, unit: str, scale: int, equal: bool
) -> None:
    assert rounded_equal(cite, suffix, value, unit, scale) is equal


def test_a_scaled_cite_is_compared_at_the_decimals_written() -> None:
    assert rounded_equal(2.1e9, "$", 2.14e9, "currency", 10**9, decimals=1)  # $2.1 billion
    assert not rounded_equal(2.1e9, "$", 2.14e9, "currency", 10**9, decimals=2)  # $2.10 billion
    assert rounded_equal(2.14e9, "$", 2.14e9, "currency", 10**9, decimals=2)
    assert not rounded_equal(5.4, "", 5.4321, None, decimals=2)  # 5.40 against 5.4321


def test_shown_writes_the_value_as_its_cite_reads() -> None:
    assert shown(2.1e9, "currency") == "$2,100,000,000"
    assert shown(-126e6, "currency") == "−$126,000,000"
    assert shown(150.0, "per-share") == "$150.00"
    assert shown(0.22702, "percent") == "22.7%"
    assert shown(1.12472, "multiple") == "1.12x"
    assert shown(2.46, "years") == "2.5 years"


JUDGED = ("phase", "moat", "belief", "roic")


def _refusal(
    policy: Policy,
    section_headings: list[str],
    mode: str = "full report",
    stance: str = "buy",
    judged: Sequence[str] = JUDGED,
    route: Route | None = "mature-growth",
    secondary_on_snapshot: bool = True,
) -> str | None:
    """The structural refusal of a submission on snapshot 412."""
    return structure_refusal(
        mode, stance, section_headings, judged, route, policy, secondary_on_snapshot, 412
    )


def test_the_structural_checks(policy: Policy) -> None:
    full, review = list(HEADINGS), list(headings("valuation review"))
    assert _refusal(policy, full) is None
    assert _refusal(policy, review, "valuation review", "hold") is None
    assert (
        _refusal(policy, full, "valuation review") == "a valuation review has 10 sections, not 12"
    )
    assert (
        _refusal(policy, full, stance="accumulate")
        == "a stance is one of buy, hold, trim or avoid, not 'accumulate'"
    )
    assert _refusal(policy, full, judged=JUDGED[:3]) == "the report lacks the judgment roic"
    assert (
        _refusal(policy, full, judged=["moat"], route="revenue-growth")
        == "the report lacks the judgments phase, belief and target_margin"
    )
    assert (
        _refusal(policy, full, judged=[*JUDGED, "moat"])
        == "one judgment of each kind: moat is given twice"
    )
    swapped = [full[0], full[2], full[1], *full[3:]]
    assert (
        _refusal(policy, swapped)
        == "section 2 is headed 'The business', not 'Industry and competition'"
    )
    assert required_judgments("start-up") == ("phase", "moat", "belief", "target_margin")
    assert required_judgments("decline") == required_judgments(None) == ("phase", "moat", "belief")
    assert CHECKS[-6:] == FAILURES


def test_the_twelve_and_ten_headings() -> None:
    """Spec 13.1's twelve sections, the call, the debate and the thesis after the financials and
    the judgments last; a valuation review leaves out the business and its industry."""
    assert HEADINGS == (
        "Summary",
        "The business",
        "Industry and competition",
        "Financial performance and health",
        "The last earnings call",
        "The bull case and the bear case",
        "The thesis",
        "Valuation",
        "Price and multiples",
        "Recent news",
        "Risks and kill criteria",
        "Key judgments",
    )
    assert FULL_ONLY == ("The business", "Industry and competition")
    assert headings("full report") == HEADINGS
    assert headings("valuation review") == (HEADINGS[0], *HEADINGS[3:])
    assert STRUCTURE == (
        "the mode's section count",
        "the stance word",
        "the required judgments",
        "the headings in the spec's order",
        "a secondary valuation on a refused snapshot",
    )
    assert CHECKS == STRUCTURE + FAILURES


def test_an_old_heading_names_the_new_one(policy: Policy) -> None:
    """A plan 1 report's ten headings are two short; one of them in a twelve-section report is
    named against the heading in its place."""
    plan_1 = [
        "Summary",
        "The business",
        "Industry and competition",
        "Financial performance and health",
        "Life-cycle phase",
        "Valuation",
        "Price facts and multiples",
        "Key judgments",
        "Recent news",
        "Risks and kill criteria",
    ]
    assert _refusal(policy, plan_1) == "a full report has 12 sections, not 10"
    old = [*HEADINGS[:4], "Life-cycle phase", *HEADINGS[5:]]
    assert _refusal(policy, old) == (
        "section 5 is headed 'The last earnings call', not 'Life-cycle phase'"
    )
    moved = [*HEADINGS[:7], "Key judgments", *HEADINGS[8:11], "Valuation"]
    assert _refusal(policy, moved) == "section 8 is headed 'Valuation', not 'Key judgments'"


def test_a_report_needs_a_secondary_valuation_on_the_snapshot(policy: Policy) -> None:
    """The last structural check, which the caller asks only on a refused latest snapshot (plan
    3): the refusal names the snapshot the report would rest on, and every earlier check answers
    first."""
    full = list(HEADINGS)
    assert (
        _refusal(policy, full, secondary_on_snapshot=False)
        == "the report needs a secondary valuation on snapshot 412"
    )
    review = list(headings("valuation review"))
    assert (
        _refusal(policy, review, "valuation review", secondary_on_snapshot=False)
        == "the report needs a secondary valuation on snapshot 412"
    )
    swapped = [full[0], full[2], full[1], *full[3:]]
    assert _refusal(policy, swapped, secondary_on_snapshot=False) == (
        "section 2 is headed 'The business', not 'Industry and competition'"
    )
    assert _refusal(policy, full, judged=JUDGED[:3], secondary_on_snapshot=False) == (
        "the report lacks the judgment roic"
    )


# The refusals an agent cannot fix (spec 2026-11-10 7.6), as the engine words them, and the
# foreign-filer refusal a snapshot valued before method 1.1 carries.
CANNOT_FIX = (
    "no diluted share count",
    "reporting currency unknown",
    NO_RATE.format(code="SEK"),
    "no inflation projection for XYZ",
    "ARS: expected inflation 12.1% above the 10% bound",
    (
        "share basis unclear: the newest period's count 1,680.7 m against the quote's 210.1 m (the"
        " ADR ratio 10)"
    ),
    "foreign filer: currency and share-unit handling not built yet",
)


def test_the_check_spares_a_refusal_an_agent_cannot_fix(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The last structural check is spared where the company can have no secondary valuation
    (``no_secondary``, which the caller reads): a refused snapshot whose refusal no call can meet,
    named in its own words, an old snapshot's foreign-filer refusal whole. A currency or the ADR
    flag is no ground of its own: FXCO in SEK refused for a reason a secondary valuation meets
    needs one on the snapshot."""
    aal = snapshot_row(conn, snapshots["AAL"])
    assert aal is not None

    def stored(result: ValuationResult) -> SnapshotRow:
        found = snapshot_row(conn, insert_snapshot(conn, result, aal.refresh_id, clock=lambda: NOW))
        assert found is not None
        return found

    full = list(HEADINGS)
    for refusal in CANNOT_FIX:
        snapshot = stored(replace(aal.result, refusal=refusal))
        why = no_secondary(snapshot, None)
        assert why == refusal
        assert _refusal(policy, full, secondary_on_snapshot=why is not None) is None
    fixable = replace(fx_inputs(), refusal="a test refusal")
    fxco = value_company(fixable, universe_deciles(), policy, TODAY)
    assert fxco.intermediates["currency"] == "SEK"
    why = no_secondary(stored(fxco), None)
    assert why is None
    assert _refusal(policy, full, secondary_on_snapshot=why is not None) == (
        "the report needs a secondary valuation on snapshot 412"
    )


def test_cited_records(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    sid = snapshots["AAPL"]
    assert cited_records(conn, _report(_clean(sid))) == (sid, None, None)
    assert cited_records(conn, _report(["no cites"])) == (None, None, None)


def test_a_scale_word_cites_a_total_at_its_own_precision(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    revenue, cfo = "fact:AAPL/revenue/2025", "fact:AAPL/cfo/2025"  # $2,100 m and $525 m
    for text in ("$2.1 billion", "$2.1bn", "$2,100M", "$2,100 million", "$525 million"):
        ref = cfo if text == "$525 million" else revenue
        assert _check(conn, policy, sid, _cite(text, ref)) == [], text
    found = _one(_check(conn, policy, sid, _cite("$0.5 billion", cfo)), sid, "$0.5 billion")
    assert (found.what, found.detail) == (
        WRONG_UNIT,
        f"a cite with a scale word gives two significant figures or more: {cfo} reads $525,000,000",
    )
    found = _one(_check(conn, policy, sid, _cite("$2.2 billion", revenue)), sid, "$2.2 billion")
    assert (found.what, found.detail) == (WRONG_UNIT, f"{revenue} reads $2,100,000,000")
    # at the decimals written: $2.10 billion is not 2,140,000,000, $2.1 billion is
    source = {"kind": "filing", "ref": "10-K 2025, p. 12", "note": None}
    sales = add_finding(
        conn,
        "AAPL",
        date(2025, 12, 31),
        "segment sales",
        source,
        AGENT,
        NOW,
        value=2.14e9,
        unit="currency",
    )
    assert _check(conn, policy, sid, _cite("$2.1 billion", f"finding:{sales}")) == []
    found = _one(
        _check(conn, policy, sid, _cite("$2.10 billion", f"finding:{sales}")), sid, "$2.10 billion"
    )
    assert found.what == WRONG_UNIT
    # a share count in its scale takes no $
    shares = f"snapshot:{sid}/inputs/shares_diluted"  # 1,000 m
    assert _check(conn, policy, sid, _cite("1.0 billion", shares)) == []
    found = _one(_check(conn, policy, sid, _cite("$1.0 billion", shares)), sid, "$1.0 billion")
    assert found.what == WRONG_UNIT


def test_a_signed_outflow_may_be_cited_by_its_size(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    capex = "fact:AAPL/capex/2025"  # −$126 m, signed as an outflow
    for text in ("$126,000,000", "$126 million", "−$126,000,000", "($126,000,000)", "−$126M"):
        assert _check(conn, policy, sid, _cite(text, capex)) == [], text
    dividends = "table:AAPL/capital_allocation/dividends/2025"  # −$40 m
    assert _check(conn, policy, sid, _cite("$40,000,000", dividends)) == []
    assert _check(conn, policy, sid, _cite("$60 million", "fact:AAPL/buybacks/2025")) == []
    # a signed cite must match the signed value; a net flow is not an outflow line
    found = _one(
        _check(conn, policy, sid, _cite("$126,000,000", "fact:AAPL/cfi/2025")), sid, "$126,000,000"
    )
    assert (found.what, found.detail) == (WRONG_UNIT, "fact:AAPL/cfi/2025 reads −$210,000,000")
    found = _one(
        _check(conn, policy, sid, _cite("−$126,000,000", "fact:AAPL/cfo/2025")),
        sid,
        "−$126,000,000",
    )
    assert found.what == WRONG_UNIT


def test_a_percentage_may_cite_a_ratio(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    sbc, net_income = "fact:AAPL/sbc/2025", "fact:AAPL/net_income/2025"  # $20 m over $315 m
    ratio = insert_derivation(
        conn, "AAPL", "ratio", sbc, net_income, None, 20 / 315, "multiple", AGENT, NOW
    )
    assert _check(conn, policy, sid, _cite("6.3%", f"derived:{ratio}")) == []
    assert _check(conn, policy, sid, _cite("0.06x", f"derived:{ratio}")) == []
    fcf = "table:AAPL/cash_flow/fcf_to_net_income/2025"  # 399 ÷ 315
    assert _check(conn, policy, sid, _cite("126.7%", fcf)) == []
    # a multiple that is not a derivation or a table's ratio keeps its x
    price_to_value = f"snapshot:{sid}/price_to_value"
    found = _one(_check(conn, policy, sid, _cite("112.5%", price_to_value)), sid, "112.5%")
    assert found.what == WRONG_UNIT


def test_a_price_is_cited_to_cents(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    for ref in (f"snapshot:{sid}/price", f"snapshot:{sid}/inputs/price"):
        found = _one(_check(conn, policy, sid, _cite("$150", ref)), sid, "$150")
        assert (found.what, found.detail) == (
            WRONG_UNIT,
            f"a price is cited to cents: {ref} reads $150.00",
        )
        assert _check(conn, policy, sid, _cite("$150.00", ref)) == []
    close = "close:AAPL/2025-11-03"
    assert _one(_check(conn, policy, sid, _cite("$190", close)), sid, "$190").what == WRONG_UNIT
    assert _check(conn, policy, sid, _cite("$190.00", close)) == []
    # a value a share and a level to cents or to whole dollars
    for text in ("$128", "$127.68"):
        assert _check(conn, policy, sid, _cite(text, f"snapshot:{sid}/value")) == []
    assert _check(conn, policy, sid, _cite("$96", f"snapshot:{sid}/levels/buy")) == []


def test_a_policy_score_is_cited_to_its_decimals(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    assert policy.z_safe == 2.6
    assert _check(conn, policy, sid, _cite("2.6", "policy:z_safe")) == []
    assert _one(_check(conn, policy, sid, _cite("3", "policy:z_safe")), sid, "3").what == WRONG_UNIT
    whole = str(policy.f_score_low)  # a whole number on the score's grid
    assert _check(conn, policy, sid, _cite(whole, "policy:f_score_low")) == []


def test_the_belief_a_forward_p_e_rests_on_is_cited_by_its_input(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The playbook's report template cites the growth rate beside a Mature Growth row's forward
    P/E as ``snapshot:<id>/inputs/belief``: AAPL's belief is 6.3%."""
    sid = snapshots["AAPL"]
    assert _check(conn, policy, sid, _cite("6.3%", f"snapshot:{sid}/inputs/belief")) == []


def test_a_figure_in_a_decision_is_a_finding() -> None:
    """A judgment is a record: its decision, in words, is the only text the check reads."""
    judgments = [
        {"judgment": "moat", "decision": "Keep Wide: the patents run to 2031."},
        {"judgment": "belief", "decision": "$5bn of buybacks"},
    ]
    assert check_judgments(judgments) == [
        Finding(
            "judgment belief, decision: $5bn",
            NO_REFERENCE,
            "a judgment's text holds no figure: cite it in a section",
        ),
    ]


def _applied_review(
    conn: sqlite3.Connection, policy: Policy, sid: int, symbol: str = "AAPL"
) -> int:
    """An applied belief override of 8% on ``sid`` and a review under it there."""
    override_id = insert_override(
        conn,
        symbol,
        "growth.belief",
        0.063,
        0.08,
        "ratio",
        "guidance raised",
        [{"kind": "transcript", "ref": "Q3 call", "note": ""}],
        "lasting",
        None,
        None,
        sid,
        AGENT,
        NOW,
        "applied",
        "",
    )
    inputs = replace(mature_growth_inputs(), symbol=symbol)
    deciles = universe_deciles()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    belief = Override(override_id, "growth.belief", 0.08, "agent", "claude-opus-5-5", NOW, "why")
    review = review_company(inputs, deciles, policy, TODAY, [belief], mechanical)
    return insert_review(conn, review, symbol, sid, None, clock=lambda: NOW)


def test_a_review_cite_must_be_the_current_review(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    older = _applied_review(conn, policy, sid)
    current = _applied_review(conn, policy, sid)  # a newer review on the same snapshot
    stored = review_row(conn, current)
    assert stored is not None and stored.value is not None
    value = f"${stored.value:,.2f}"
    assert _check(conn, policy, sid, _cite(value, f"review:{current}/value")) == []
    found = _one(_check(conn, policy, sid, _cite(value, f"review:{older}/value")), sid, value)
    assert (found.what, found.detail) == (
        WRONG_SNAPSHOT,
        f"review:{older}/value is not the company's current review: cite review:{current}",
    )
    # a price refresh reprices the review onto the new snapshot: the cited one still counts
    cited = snapshot_row(conn, sid)
    assert cited is not None
    moved = reprice(cited.result, 160.0, date(2026, 11, 2), policy)
    repriced = insert_snapshot(conn, moved, cited.refresh_id, clock=lambda: NOW)
    reprice_review = _applied_review(conn, policy, repriced)

    def on_the_reprice(ref: str) -> list[Finding]:
        sections = _report([*_clean(sid), _cite(value, ref)])
        return check_sections(conn, "AAPL", repriced, sections, policy)

    assert on_the_reprice(f"review:{current}/value") == []
    # with every override dropped the company has no current review
    for row in applied_overrides(conn, "AAPL"):
        drop_override(conn, row.id, "withdrawn", NOW)
    found = _one(on_the_reprice(f"review:{reprice_review}/value"), sid, value)
    assert found.detail == (
        f"review:{reprice_review}/value is not the company's current review: the company has none"
    )


def test_a_bridge_line_and_a_change_in_points_are_cited(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The bridge of design.md 7.4 cites each line's change with its sign, ``+$28``; a growth of
    ``+5.0%``; and a difference of two percents in points, ``2.0 pp``."""
    sid = snapshots["AAPL"]
    review = review_row(conn, _applied_review(conn, policy, sid))
    assert review is not None
    delta = review.bridge[0]["delta"]
    assert delta is not None and delta > 0  # a belief of 8% raises the value
    line = f"review:{review.id}/bridge/1/delta"
    for text in (f"+${delta:,.0f}", f"+${delta:,.2f}", f"${delta:,.0f}"):
        assert _check(conn, policy, sid, _cite(text, line)) == [], text
    growth = "table:AAPL/growth/revenue_growth/2025"  # 5.0%
    assert _check(conn, policy, sid, _cite("+5.0%", growth, "2025")) == []
    wider = insert_derivation(
        conn,
        "AAPL",
        "difference",
        growth,
        "policy:required_return",
        None,
        0.02,
        "percent",
        AGENT,
        NOW,
    )
    for text in ("2.0 pp", "+2.0pp", "2.0 percentage points"):
        assert _check(conn, policy, sid, _cite(text, f"derived:{wider}")) == [], text
    found = _one(_check(conn, policy, sid, _cite("2.0 pp", growth)), sid, "2.0 pp")
    assert (found.what, found.detail) == (WRONG_UNIT, f"{growth} reads 5.0%")
    # a plus sign is a sign: the signed value of an outflow is negative
    capex = "fact:AAPL/capex/2025"
    found = _one(_check(conn, policy, sid, _cite("+$126,000,000", capex)), sid, "+$126,000,000")
    assert found.what == WRONG_UNIT
