"""The currency a finding's or a guidance record's money figure is in (spec 2026-11-15 9.1): a
code of three capital letters the writer gives with a money figure alone, else the company's
reporting currency, the one its latest snapshot names as ``money_of`` reads it, USD where it has
none; a figure that is not money has none."""

import re
import sqlite3
from collections.abc import Callable
from datetime import date

import pytest
from support.engine_companies import fx_inputs, universe_deciles

from fairband.engine.route import refusal_result, value_company
from fairband.policy import load_policy
from fairband.store.currency import MONEY_UNITS, check_currency, currency_of, reporting_currency
from fairband.store.snapshots import insert_snapshot

TODAY = date(2026, 10, 31)
MONEY = "a currency goes with a money figure"


def test_the_money_units() -> None:
    assert MONEY_UNITS == frozenset({"currency", "per-share"})


@pytest.mark.parametrize("unit", ["currency", "per-share"])
def test_a_code_goes_with_a_money_figure(unit: str) -> None:
    for code in ("USD", "TWD", "SEK"):
        check_currency(code, unit)
    check_currency(None, unit)
    check_currency(None, "percent")
    check_currency(None, None)


@pytest.mark.parametrize("unit", ["percent", "multiple", "count", "score", "years", None])
def test_a_code_on_a_figure_that_is_not_money_is_refused(unit: str | None) -> None:
    with pytest.raises(ValueError, match=f"^{MONEY}$"):
        check_currency("USD", unit)


@pytest.mark.parametrize("code", ["usd", "US", "DOLLAR", "US$", "U5D", " USD", "USD\n", ""])
def test_a_code_is_three_capital_letters(code: str) -> None:
    """Checked for its form, not against a list (spec 9.1), before the figure it goes with."""
    refusal = f"a currency is three capital letters, not {code!r}"
    for unit in ("currency", "percent"):
        with pytest.raises(ValueError, match=f"^{re.escape(refusal)}$"):
            check_currency(code, unit)


def test_a_money_figure_is_in_its_code_else_the_reporting_currency() -> None:
    assert currency_of("USD", "currency", "TWD") == "USD"
    assert currency_of("TWD", "per-share", "TWD") == "TWD"  # stored as given
    assert currency_of(None, "currency", "TWD") == "TWD"
    assert currency_of(None, "per-share", "USD") == "USD"
    for unit in ("percent", "multiple", "count", None):
        assert currency_of(None, unit, "TWD") is None, unit


def test_the_reporting_currency_is_the_latest_snapshot_s(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    """FXCO, valued in SEK, reports in SEK, whatever case its symbol is written in; a company with
    no snapshot reports in USD; a snapshot refused before its currency was read names none, so it
    says USD, as today (spec 9.1); the latest snapshot is the one read."""
    policy = load_policy()
    assert reporting_currency(conn, "FXCO") == "USD"
    refresh_id = new_refresh()
    refused = refusal_result("FXCO", "valuation failed: ValueError: no", policy, TODAY)
    insert_snapshot(conn, refused, refresh_id)
    assert reporting_currency(conn, "FXCO") == "USD"
    insert_snapshot(conn, value_company(fx_inputs(), universe_deciles(), policy, TODAY), refresh_id)
    assert reporting_currency(conn, "FXCO") == reporting_currency(conn, "fxco") == "SEK"
    assert reporting_currency(conn, "AAPL") == "USD"
