"""The number check (spec 2026-11-06 Tier 2, 13.3 and 20.3) on the ``snapshots`` fixture of
``conftest.py``: AAPL, the Mature Growth golden renamed (a price of $150, a value of $127.68, price
÷ value 1.17, a ten-year aggregate ROIC of 22.7%), with ACME's synthetic statements (revenue $2,100
m in fiscal 2025, up 5.0%; capital spending −$126 m); AAL, refused. A clean report publishes; each
failure of spec 20.3 is one finding, located."""

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from typing import Any

import pytest
from refresh.synthetic import NOW, bodies
from support.engine_companies import (
    fx_inputs,
    mature_growth_inputs,
    universe_deciles,
    young_growth_inputs,
)
from support.payloads import store_payloads
from support.web import TODAY

from fairband.engine.overrides import Override
from fairband.engine.review import Review, review_company
from fairband.engine.route import reprice, value_company
from fairband.engine.types import Route, ValuationResult
from fairband.policy import Policy
from fairband.policy.settings import apply_overlay
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
from fairband.reports.filing_report import row_ref
from fairband.store.guidance import insert_guidance
from fairband.store.ledger import Writer
from fairband.store.overrides import applied_overrides, drop_override, insert_override
from fairband.store.research import add_finding, add_kill_criterion
from fairband.store.reviews import (
    clear_held,
    held_row,
    insert_review,
    review_row,
    set_held_state,
)
from fairband.store.secondary import insert_derivation, no_secondary
from fairband.store.snapshots import SnapshotRow, insert_snapshot, snapshot_row
from fairband.store.vendor import record_response

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


def test_sales_to_capital_is_cited_as_a_multiple(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The growth routes' sales-to-capital input carries the engine unit ``ratio`` and is revenue
    over capital, 1.38 on the Young Growth company: a report writes it "1.38x", and "138.4%" does
    not fit it."""
    stored = snapshot_row(conn, snapshots["AAPL"])
    assert stored is not None
    young = value_company(young_growth_inputs(), universe_deciles(), policy, TODAY)
    sid = insert_snapshot(conn, young, stored.refresh_id, clock=lambda: NOW)
    ref = f"snapshot:{sid}/inputs/sales_to_capital"

    def check(text: str) -> list[Finding]:
        sections = _report(["Revenue is ", _cite(text, ref), " the capital."])
        return check_sections(conn, "YGCO", sid, sections, policy)

    assert check("1.38x") == []
    (finding,) = check("138.4%")
    assert finding.what == WRONG_UNIT


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


def test_a_quarter_s_line_is_cited_by_its_fiscal_label(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-11, 7.2: a stored quarter's revenue ($340 m in the quarter to 2026-09-30)
    cited by its ``fact:`` ref, its period written with the dash or without, or not at all, passes
    the check; its capital spending may be cited by its size; another quarter's label is a wrong
    period."""
    sid = snapshots["AAPL"]
    ref = "fact:AAPL/revenue/2026-Q3"
    for period in ("2026-Q3", "2026Q3", None):
        assert _check(conn, policy, sid, _cite("$340,000,000", ref, period)) == [], period
    assert _check(conn, policy, sid, _cite("$340 million", ref)) == []
    assert _check(conn, policy, sid, _cite("$24 million", "fact:AAPL/capex/2026-Q3")) == []
    found = _one(
        _check(conn, policy, sid, _cite("$340,000,000", ref, "2026-Q2")), sid, "$340,000,000"
    )
    assert (found.what, found.detail) == (WRONG_PERIOD, f"{ref} is for 2026-Q3, not 2026-Q2")


def test_an_estimate_cell_is_cited_by_its_year_with_the_letter_or_without(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-15 6.3: the growth table's ``2026E`` column keeps the estimate apart from the
    fiscal year's column, while its revenue cites ``estimate:AAPL/2026/revenue``, whose period is
    ``2026``; so the check reads ``2026E`` as the year, with its ``FY`` or without, and a cite may
    give any of them, on the ``estimate:`` ref and on a ``table:`` ref alike. Another year is a
    wrong period, a column the table lacks an unresolved reference; the trailing column's cells
    are cited by ``ttm``; and a quarters-table cell (spec 13: a trailing, an estimate and a
    quarter cell pass) by its stored period, with its dash or without, or by none, while "Q3 2025"
    is a wrong period, as for a ``fact:`` quarter (the whole-branch review's M6)."""
    sid = snapshots["AAPL"]
    periods = ("2026E", "FY2026E", "fy2026e", "2026", "FY2026", None)
    revenue = ("estimate:AAPL/2026/revenue", "table:AAPL/growth/revenue/2026E")
    for ref in revenue:
        for period in periods:
            cite = _cite("$2,200,000,000", ref, period)
            assert _check(conn, policy, sid, cite) == [], (ref, period)
    growth = "table:AAPL/growth/revenue_growth/2026E"  # 2,200 over 2,100 − 1
    for period in periods:
        assert _check(conn, policy, sid, _cite("4.8%", growth, period)) == [], period
    margin = _cite("20.0%", "table:AAPL/growth/operating_margin/ttm", "ttm")
    assert _check(conn, policy, sid, margin) == []
    quarter = "table:AAPL/quarters/operating_margin/2025-Q3"  # $60 m over $300 m
    for period in ("2025-Q3", "2025Q3", None):
        assert _check(conn, policy, sid, _cite("20.0%", quarter, period)) == [], period
    found = _one(_check(conn, policy, sid, _cite("20.0%", quarter, "Q3 2025")), sid, "20.0%")
    assert (found.what, found.detail) == (WRONG_PERIOD, f"{quarter} is for 2025-Q3, not Q3 2025")
    found = _one(_check(conn, policy, sid, _cite("4.8%", growth, "2027")), sid, "4.8%")
    assert (found.what, found.detail) == (WRONG_PERIOD, f"{growth} is for 2026E, not 2027")
    absent = "table:AAPL/growth/revenue/2029E"
    found = _one(_check(conn, policy, sid, _cite("$2,200,000,000", absent)), sid, "$2,200,000,000")
    assert (found.what, found.detail) == (UNRESOLVED, f"{absent} names no stored value")


def test_a_table_cell_passes_when_the_consensus_cannot_be_read(
    conn: sqlite3.Connection,
    policy: Policy,
    snapshots: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fix wave's follow-up to the whole-branch review's M3: where the company's assembly
    raises, the resolver reads the tables with no consensus, so a section citing a fiscal table
    cell, the clean one's revenue growth and free cash flow over net income, a trailing cell and a
    quarter cell passes the check as before the tables read the consensus; a cite of an estimate
    cell is an unresolved reference."""

    def raising(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("assembly failed")

    monkeypatch.setattr("fairband.reports.refs.build_inputs", raising)
    monkeypatch.setattr("fairband.reports.tables.build_inputs", raising)
    sid = snapshots["AAPL"]
    trailing = _cite("20.0%", "table:AAPL/growth/operating_margin/ttm", "ttm")
    quarter = _cite("20.0%", "table:AAPL/quarters/operating_margin/2025-Q3", "2025-Q3")
    assert _check(conn, policy, sid, trailing, quarter) == []
    estimate = "table:AAPL/growth/eps/2026E"
    found = _one(_check(conn, policy, sid, _cite("$3.30", estimate)), sid, "$3.30")
    assert (found.what, found.detail) == (UNRESOLVED, f"{estimate} names no stored value")


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


def test_a_number_is_an_operand_of_derive_alone(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-15 7.3: a ``number:`` cite names nothing: the derivation is cited."""
    sid = snapshots["AAPL"]
    for cite, ref in (("100", "number:100"), ("13", "number:13")):
        found = _one(_check(conn, policy, sid, _cite(cite, ref)), sid, cite)
        assert (found.what, found.detail) == (
            UNRESOLVED,
            f"{ref} is an operand of derive: cite the derivation",
        )


KILL_SECTION = "Risks and kill criteria"


@pytest.mark.parametrize(("mode", "n"), [("full report", 11), ("valuation review", 9)])
def test_a_kill_threshold_is_cited_in_risks_and_kill_criteria_alone(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int], mode: str, n: int
) -> None:
    """Spec 2026-11-15 8.2: a ``kill:`` cite passes in "Risks and kill criteria" alone, section 11
    of a full report and the ninth of a valuation review, read by its heading; there it is checked
    as a ``finding:`` cite is, and anywhere else it is an unresolved reference that says where it
    goes."""
    sid = snapshots["AAPL"]
    names = headings(mode)
    assert names.index(KILL_SECTION) + 1 == n  # not at one index in the two modes

    def recorded(threshold: float | None, unit: Any) -> str:
        found = add_kill_criterion(
            conn, "AAPL", "growth below 5%", AGENT, NOW, threshold=threshold, unit=unit
        )
        return f"kill:{found}"

    ref, words = recorded(0.05, "percent"), recorded(None, None)
    source = {"kind": "filing", "ref": "10-K 2025, p. 12", "note": None}
    finding = add_finding(
        conn, "AAPL", TODAY, "growth", source, AGENT, NOW, value=0.05, unit="percent"
    )

    def check(heading: str, *cited: dict[str, Any]) -> list[Finding]:
        sections = [
            {"heading": h, "parts": list(cited) if h == heading else ["Plain words."]}
            for h in names
        ]
        return check_sections(conn, "AAPL", sid, sections, policy)

    assert check(KILL_SECTION, _cite("5%", ref), _cite("5.0%", f" {ref} ")) == []
    elsewhere = f"{ref} is the author's own threshold: cite it in Risks and kill criteria"
    for heading in (h for h in names if h != KILL_SECTION):  # every other section
        at = names.index(heading) + 1
        assert check(heading, _cite("5%", ref)) == [
            Finding(f"section {at}, part 1: 5%", UNRESOLVED, elsewhere)
        ], heading
    # in its section, as a finding's figure is: the rounding, the suffix, the period
    found = check(
        KILL_SECTION,
        _cite("5.5%", ref),
        _cite("5.5%", f"finding:{finding}"),
        _cite("5.0", ref),
        _cite("5.0%", ref, "2026"),
        _cite("5.0%", words),
    )
    assert [(f.where, f.what, f.detail) for f in found] == [
        (f"section {n}, part 1: 5.5%", WRONG_UNIT, f"{ref} reads 5.0%"),
        (f"section {n}, part 2: 5.5%", WRONG_UNIT, f"finding:{finding} reads 5.0%"),
        (
            f"section {n}, part 3: 5.0",
            WRONG_UNIT,
            f"'5.0' does not fit a percent figure: {ref} reads 5.0%",
        ),
        (f"section {n}, part 4: 5.0%", WRONG_PERIOD, f"{ref} has no period, not 2026"),
        (f"section {n}, part 5: 5.0%", UNRESOLVED, f"{words} names no stored value"),
    ]


def test_the_kill_cite_adds_no_failure_word() -> None:
    """Spec 2026-11-15 8.2: a ``kill:`` cite out of its section is an unresolved reference, so the
    list of checks Appendix A reads from the code is as it was."""
    assert FAILURES == (
        "unresolved reference",
        "wrong unit",
        "wrong period",
        "wrong snapshot",
        "a number with no reference",
        "a derived figure the engine has not emitted",
    )
    assert len(CHECKS) == 12  # the moat verdict's check joined the structure (spec 2026-11-19 8.7)


def test_a_derivation_rests_on_every_snapshot_of_its_operands(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-15 7.4: a ``derived:`` cite fails the snapshot test when any operand, through
    nested derivations, rests on a snapshot that is not the company's latest; a number rests on
    none."""
    sid = snapshots["AAPL"]
    cited = snapshot_row(conn, sid)
    assert cited is not None and cited.value is not None
    revalued = replace(cited.result, value=cited.value + 1.0)
    latest = insert_snapshot(conn, revalued, cited.refresh_id, clock=lambda: NOW)
    new, old = f"snapshot:{latest}/price", f"snapshot:{sid}/price"

    def derived(operation: str, a: str, b: str, value: float, unit: str | None) -> str:
        found = insert_derivation(conn, "AAPL", operation, a, b, None, value, unit, AGENT, NOW)
        return f"derived:{found}"

    second = derived("ratio", new, old, 1.0, "multiple")
    inner = derived("ratio", "fact:AAPL/revenue/2025", old, 14e6, None)
    nested = derived("sum", new, inner, 14_000_150.0, None)
    on_latest = derived("product", new, "number:2", 300.0, "per-share")
    for cite, ref in (("1.00x", second), ("14,000,150", nested)):
        found = check_sections(conn, "AAPL", latest, _report([_cite(cite, ref)]), policy)
        why = f"{ref} rests on snapshot {sid}; the company's latest is snapshot {latest}"
        assert [(f.what, f.detail) for f in found] == [(WRONG_SNAPSHOT, f"{why}: read it again")]
    found = check_sections(conn, "AAPL", latest, _report([_cite("$300.00", on_latest)]), policy)
    assert found == []


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
    # a money figure in another currency than USD with its code (spec 2026-11-15 9.4)
    assert shown(1e9, "currency", "SEK") == "SEK 1,000,000,000"
    assert shown(-126e6, "currency", "TWD") == "−TWD 126,000,000"
    assert shown(12.5, "per-share", "SEK") == "SEK 12.50"
    assert shown(2.1e9, "currency", "USD") == "$2,100,000,000"
    assert shown(12.5, "per-share", "USD") == "$12.50"
    assert shown(0.22702, "percent", "SEK") == "22.7%"
    assert shown(1234.0, "count", "SEK") == "1,234"


def _sek_company(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> int:
    """FXCO, whose snapshot names SEK (``fx_inputs``), with ACME's statements in SEK (revenue SEK
    2,100 m in fiscal 2025); its snapshot's id."""
    aal = snapshot_row(conn, snapshots["AAL"])
    assert aal is not None
    fxco = value_company(fx_inputs(), universe_deciles(), policy, TODAY)
    assert fxco.intermediates["currency"] == "SEK"
    sid = insert_snapshot(conn, fxco, aal.refresh_id, clock=lambda: NOW)
    statements = {e: p for e, p in bodies(currency="SEK").items() if e != "earnings"}
    store_payloads(conn, "FXCO", statements, NOW)
    return sid


def _records(conn: sqlite3.Connection, symbol: str, currency: str | None) -> list[str]:
    """A finding of ``symbol`` of 1,500 m, one of 12.50 a share, a revenue guidance record's
    midpoint of 1,500 m and a kill criterion's threshold of 1,500 m, each in ``currency`` (none
    naming none); their refs."""
    source = {"kind": "filing", "ref": "20-F 2025, p. 41", "note": None}
    total = {"value": 1.5e9, "unit": "currency", "currency": currency}
    a_share = {"value": 12.5, "unit": "per-share", "currency": currency}
    said, cited = "We guide.", "response:12/0/content"
    guided = insert_guidance(
        conn,
        symbol,
        "revenue",
        "2026",
        1.4e9,
        1.6e9,
        "gaap",
        TODAY,
        said,
        cited,
        AGENT,
        NOW,
        None,
        currency=currency,
    )
    threshold = {"threshold": 1.5e9, "unit": "currency", "currency": currency}
    return [
        f"finding:{add_finding(conn, symbol, TODAY, 'a total', source, AGENT, NOW, **total)}",
        f"finding:{add_finding(conn, symbol, TODAY, 'an EPS', source, AGENT, NOW, **a_share)}",
        f"guidance:{guided}/midpoint",
        f"kill:{add_kill_criterion(conn, symbol, 'below', AGENT, NOW, **threshold)}",
    ]


def _in_the_kill_section(
    conn: sqlite3.Connection, symbol: str, sid: int, policy: Policy, cites: list[Any]
) -> list[tuple[str, str, str]]:
    """The findings of a full report whose "Risks and kill criteria" holds ``cites``, where a
    ``kill:`` cite is checked as a ``finding:`` cite is."""
    sections = [
        {"heading": h, "parts": cites if h == KILL_SECTION else ["Plain words."]} for h in HEADINGS
    ]
    return [
        (f.where, f.what, f.detail) for f in check_sections(conn, symbol, sid, sections, policy)
    ]


def test_a_dollar_on_a_record_passes_where_the_record_is_in_us_dollars(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-15 9.4 on FXCO, whose snapshot names SEK: a ``$`` on a finding, a guidance
    record's figure or a kill criterion's threshold passes where the record is in US dollars, and
    is ``wrong unit`` on one that names no currency, in SEK, the detail writing the figure with its
    code; the same number bare passes, and any other wrong-unit detail of such a record writes the
    code. A ``fact:`` cite of FXCO takes ``$`` as before: the check knows a record's currency
    alone (spec 2026-11-15 14)."""
    sid = _sek_company(conn, policy, snapshots)
    dollars, kronor = _records(conn, "FXCO", "USD"), _records(conn, "FXCO", None)
    figures = ("1,500,000,000", "12.50", "1,500,000,000", "1,500,000,000")
    with_dollar = [_cite(f"${x}", ref) for x, ref in zip(figures, dollars, strict=True)]
    with_dollar += [_cite("$1.5 billion", dollars[0])]
    bare = [_cite(x, ref) for x, ref in zip(figures, kronor, strict=True)]
    assert _in_the_kill_section(conn, "FXCO", sid, policy, with_dollar + bare) == []
    revenue = "fact:FXCO/revenue/2025"
    as_before = [_cite("$2,100,000,000", revenue), _cite("2,100,000,000", revenue)]
    assert _in_the_kill_section(conn, "FXCO", sid, policy, as_before) == []
    on_kronor = [_cite(f"${x}", ref) for x, ref in zip(figures, kronor, strict=True)]
    on_kronor += [
        _cite("$1.5 billion", kronor[0]),
        _cite("1,600,000,000", kronor[0]),
        _cite("12.5%", kronor[1]),
        _cite("$2,000,000,000", revenue),
    ]
    found = _in_the_kill_section(conn, "FXCO", sid, policy, on_kronor)
    advice = "write the number without $ and name SEK before it"
    total, eps = "SEK 1,500,000,000", "SEK 12.50"
    where = "section 11, part"
    assert found == [
        (f"{where} 1: $1,500,000,000", WRONG_UNIT, f"{kronor[0]} reads {total}: {advice}"),
        (f"{where} 2: $12.50", WRONG_UNIT, f"{kronor[1]} reads {eps}: {advice}"),
        (f"{where} 3: $1,500,000,000", WRONG_UNIT, f"{kronor[2]} reads {total}: {advice}"),
        (f"{where} 4: $1,500,000,000", WRONG_UNIT, f"{kronor[3]} reads {total}: {advice}"),
        (f"{where} 5: $1.5 billion", WRONG_UNIT, f"{kronor[0]} reads {total}: {advice}"),
        (f"{where} 6: 1,600,000,000", WRONG_UNIT, f"{kronor[0]} reads {total}"),
        (
            f"{where} 7: 12.5%",
            WRONG_UNIT,
            f"'12.5%' does not fit a per-share figure: {kronor[1]} reads {eps}",
        ),
        (f"{where} 8: $2,000,000,000", WRONG_UNIT, f"{revenue} reads $2,100,000,000"),
    ]


def test_a_dollar_on_a_us_company_s_record(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-15 9.4 on AAPL, which reports in US dollars: a ``$`` on a record that names no
    currency, or names USD, passes as before; on a euro record it is ``wrong unit`` with EUR in
    the detail, and the same number bare passes."""
    sid = snapshots["AAPL"]
    plain, dollars, euros = (_records(conn, "AAPL", c) for c in (None, "USD", "EUR"))
    figures = ("1,500,000,000", "12.50", "1,500,000,000", "1,500,000,000")
    cites = [
        _cite(f"${x}", ref)
        for refs in (plain, dollars)
        for x, ref in zip(figures, refs, strict=True)
    ]
    cites += [_cite(x, ref) for x, ref in zip(figures, euros, strict=True)]
    assert _in_the_kill_section(conn, "AAPL", sid, policy, cites) == []
    on_euros = [_cite(f"${x}", ref) for x, ref in zip(figures, euros, strict=True)]
    advice = "write the number without $ and name EUR before it"
    readings = ("EUR 1,500,000,000", "EUR 12.50", "EUR 1,500,000,000", "EUR 1,500,000,000")
    assert _in_the_kill_section(conn, "AAPL", sid, policy, on_euros) == [
        (f"section 11, part {n}: ${x}", WRONG_UNIT, f"{ref} reads {reading}: {advice}")
        for n, (x, ref, reading) in enumerate(zip(figures, euros, readings, strict=True), 1)
    ]


JUDGED = ("phase", "moat", "belief", "roic")


def _refusal(
    policy: Policy,
    section_headings: list[str],
    mode: str = "full report",
    stance: str = "buy",
    judged: Sequence[str] = JUDGED,
    route: Route | None = "mature-growth",
    secondary_on_snapshot: bool = True,
    moat_on_snapshot: bool = True,
) -> str | None:
    """The structural refusal of a submission on snapshot 412."""
    return structure_refusal(
        mode,
        stance,
        section_headings,
        judged,
        route,
        policy,
        secondary_on_snapshot,
        412,
        moat_on_snapshot=moat_on_snapshot,
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
        "the moat verdict on the snapshot",
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


def test_a_report_needs_the_moat_verdict_on_the_snapshot(policy: Policy) -> None:
    """Spec 2026-11-19 8.7: the fifth structural check, on every report, valued snapshot or
    refused: the agent's verdict on the moat recorded on the snapshot the report would rest on,
    which the caller reads (``moat_on_snapshot``). Its sentence names that snapshot and the tool;
    the four checks before it answer first, and it answers before the secondary valuation's."""
    full, review = list(HEADINGS), list(headings("valuation review"))
    unrecorded = "the report needs the moat verdict recorded on snapshot 412: call moat_set"
    assert _refusal(policy, full, moat_on_snapshot=False) == unrecorded
    assert _refusal(policy, review, "valuation review", moat_on_snapshot=False) == unrecorded
    assert _refusal(policy, full, moat_on_snapshot=False, secondary_on_snapshot=False) == unrecorded
    swapped = [full[0], full[2], full[1], *full[3:]]
    assert _refusal(policy, swapped, moat_on_snapshot=False) == (
        "section 2 is headed 'The business', not 'Industry and competition'"
    )
    assert _refusal(policy, full, judged=JUDGED[:3], moat_on_snapshot=False) == (
        "the report lacks the judgment roic"
    )
    assert STRUCTURE.index("the moat verdict on the snapshot") == len(STRUCTURE) - 2


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


def test_a_report_rests_on_the_earliest_snapshot_of_a_derivation_s_operands(
    conn: sqlite3.Connection, snapshots: dict[str, int]
) -> None:
    """Method 16.1 with 16.2 (the whole-branch review's deferred minor 2): a report is stored on
    the earliest snapshot its cites rest on, a derivation's every operand counted through nested
    derivations, so a derivation whose second operand rests on the snapshot the latest reprices
    stores the report on that one, not on its first operand's."""
    sid = snapshots["AAPL"]
    cited = snapshot_row(conn, sid)
    assert cited is not None
    latest = insert_snapshot(conn, cited.result, cited.refresh_id, clock=lambda: NOW)  # a reprice
    new, old = f"snapshot:{latest}/price", f"snapshot:{sid}/price"
    second = insert_derivation(conn, "AAPL", "ratio", new, old, None, 1.0, "multiple", AGENT, NOW)
    nested = insert_derivation(
        conn, "AAPL", "product", new, f"derived:{second}", None, 150.0, "per-share", AGENT, NOW
    )
    for ref in (f"derived:{second}", f"derived:{nested}"):
        sections = _report([_cite("$150.00", new), _cite("1.00x", ref)])
        assert cited_records(conn, sections) == (sid, None, None), ref


@pytest.mark.parametrize(
    "ref",
    [
        "review:99999999999999999999/value",
        "review:²/value",
        "sensitivity:99999999999999999999/1/1",
        "sensitivity:²/1/1",
        "secondary:99999999999999999999/value",
        "secondary:²/value",
    ],
)
def test_a_cite_of_an_id_no_row_can_have_is_one_finding(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int], ref: str
) -> None:
    """The check reads a review's, a reading's and a secondary valuation's id itself, before and
    after it resolves the cite: a made-up id past the store's integers, or a digit that is not an
    ASCII one, is an unresolved reference, and the cited records leave it out. Nothing is raised,
    so a report that cites it is refused with the finding."""
    sid = snapshots["AAPL"]
    found = _one(_check(conn, policy, sid, _cite("$128", ref)), sid, "$128")
    assert found.what == UNRESOLVED
    sections = _report([*_clean(sid), _cite("$128", ref)])
    assert cited_records(conn, sections) == (sid, None, None)


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
    assert _check(conn, policy, sid, _cite("$102", f"snapshot:{sid}/levels/buy")) == []


def test_a_cited_level_is_the_one_in_force(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-23 thresholds, 5.3: a cite of a level checks against the level on the policy
    in force, the figure the page shows. AAPL's value of $127.68 on a Wide moat has a buy level
    of $102 at the default margin of 20%; under a margin of 15% it reads $109, and a cite of the
    default's figure is refused with the figure in force."""
    sid = snapshots["AAPL"]
    ref = f"snapshot:{sid}/levels/buy"
    assert _check(conn, policy, sid, _cite("$102", ref)) == []
    safety = {"None": 0.40, "Narrow": 0.30, "Wide": 0.15}
    wide = apply_overlay(policy, {"margin_of_safety": safety})
    assert _check(conn, wide, sid, _cite("$109", ref)) == []
    stale = _one(_check(conn, wide, sid, _cite("$102", ref)), sid, "$102")
    assert (stale.what, stale.detail) == (WRONG_UNIT, f"{ref} reads $108.52")


def test_a_policy_score_is_cited_to_its_decimals(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    assert policy.z_safe == 2.6
    assert _check(conn, policy, sid, _cite("2.6", "policy:z_safe")) == []
    assert _one(_check(conn, policy, sid, _cite("3", "policy:z_safe")), sid, "3").what == WRONG_UNIT
    whole = str(policy.f_score_low)  # a whole number on the score's grid
    assert _check(conn, policy, sid, _cite(whole, "policy:f_score_low")) == []


def test_the_belief_a_forward_p_e_is_read_beside_is_cited_by_its_input(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The playbook's report template reads a Mature Growth row's forward P/E beside the belief,
    the growth rate the value assumes after the analysts' forecast years, cited as
    ``snapshot:<id>/inputs/belief``: AAPL's belief is 6.3%."""
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
    carried = Review(stored.result, stored.mechanical_value, (), stored.override_ids)
    reprice_review = insert_review(  # the held review's copy, as a price refresh carries it
        conn, carried, "AAPL", repriced, cited.refresh_id, kind="held", made_id=current
    )

    def on_the_reprice(ref: str) -> list[Finding]:
        sections = _report([*_clean(sid), _cite(value, ref)])
        return check_sections(conn, "AAPL", repriced, sections, policy)

    assert on_the_reprice(f"review:{current}/value") == []
    # a review the company held before is not its current review on the reprice either
    assert _one(on_the_reprice(f"review:{older}/value"), sid, value).detail == (
        f"review:{older}/value is not the company's current review: cite review:{reprice_review}"
    )
    # with every override dropped by an agent the company holds no review (the web's write
    # clears it: spec 2026-11-23 held reviewed value, 5.1)
    for row in applied_overrides(conn, "AAPL"):
        drop_override(conn, row.id, "withdrawn", NOW)
    clear_held(conn, "AAPL")
    found = _one(on_the_reprice(f"review:{reprice_review}/value"), sid, value)
    assert found.detail == (
        f"review:{reprice_review}/value is not the company's current review: the company has none"
    )


def test_a_review_a_refresh_read_again_is_not_cited(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-23 held reviewed value, 5.8 and 7: a report needs a held review that no
    refresh has read again. A cite of the held review, or of a copy of it, is refused once a
    valuing refresh ran after the review was made, and accepted after the review is made
    again. A price refresh does not count: its copy on the repriced snapshot is the held review,
    and either id is cited."""
    sid = snapshots["AAPL"]
    made = _applied_review(conn, policy, sid)
    stored = review_row(conn, made)
    assert stored is not None and stored.value is not None
    value = f"${stored.value:,.2f}"
    cited = snapshot_row(conn, sid)
    assert cited is not None
    moved = reprice(cited.result, 160.0, date(2026, 11, 2), policy)
    repriced = insert_snapshot(conn, moved, cited.refresh_id, clock=lambda: NOW)
    review = Review(stored.result, stored.mechanical_value, (), stored.override_ids)
    copy = insert_review(
        conn, review, "AAPL", repriced, cited.refresh_id, kind="held", made_id=made
    )

    def on_the_reprice(ref: str) -> list[Finding]:
        sections = _report([*_clean(sid), _cite(value, ref)])
        return check_sections(conn, "AAPL", repriced, sections, policy)

    assert on_the_reprice(f"review:{made}/value") == []
    assert on_the_reprice(f"review:{copy}/value") == []
    held = held_row(conn, "AAPL")
    assert held is not None and held.review_id == made
    set_held_state(conn, replace(held, read_again_at=NOW))
    for ref in (f"review:{made}/value", f"review:{copy}/value"):
        found = _one(on_the_reprice(ref), sid, value)
        assert (found.what, found.detail) == (
            WRONG_SNAPSHOT,
            f"{ref}: the review was made before the latest refresh: make it again",
        )
    again = _applied_review(conn, policy, repriced)  # a made review: the state starts empty
    assert on_the_reprice(f"review:{again}/value") == []
    found = _one(on_the_reprice(f"review:{made}/value"), sid, value)
    assert found.detail == (
        f"review:{made}/value is not the company's current review: cite review:{again}"
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


def test_a_filing_report_s_cell_is_cited_with_its_scale_word_outside(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-11, 5.5 and 8: a number cell of a stored filing report is cited as it is
    stored, by its row's ref plus its column, the sheet's scale (``$ in Millions``) a plain word
    after the cite; another number is a wrong number."""
    sid = snapshots["AAPL"]
    sheet = "Leases - Additional Informatio"
    report = {
        "symbol": "AAPL",
        "period": "Q1",
        "year": "2027",
        sheet: [
            {"Leases - Additional Information (Detail) $ in Millions": ["3 Months Ended"]},
            {"Additional leases, primarily for warehouses, that have not yet commenced": [12.5]},
        ],
    }
    params = {"symbol": "AAPL", "year": "2027", "period": "Q1"}
    stored = record_response(
        conn, "fmp", "filing-report", params, "AAPL", 200, json.dumps(report), None, NOW
    )
    ref = f"{row_ref(stored, sheet, 1)}/0"
    assert _check(conn, policy, sid, _cite("$12.5", ref), " million") == []
    found = _one(_check(conn, policy, sid, _cite("$13.5", ref), " million"), sid, "$13.5")
    assert (found.what, found.detail) == (WRONG_UNIT, f"{ref} reads 12.5")
