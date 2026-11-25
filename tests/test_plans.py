"""The FMP plans Fairband runs on (``fairband.plans``): what each serves, and its pace."""

import pytest

from fairband.plans import PLANS, PREMIUM, ULTIMATE, plan_named
from fairband.refresh.fetch import PAGE_ENDPOINTS, REQUIRED, STATEMENT_ENDPOINTS

# The list of earnings calls and a call's transcript, as the pass-throughs store them.
CALLS = ("transcript-dates", "transcript")


def test_the_plans_are_ultimate_and_premium() -> None:
    assert PLANS == {"ultimate": ULTIMATE, "premium": PREMIUM}
    assert (ULTIMATE.label, PREMIUM.label) == ("Ultimate", "Premium")


def test_ultimate_serves_every_endpoint_and_leaves_the_pace_to_the_setting() -> None:
    assert ULTIMATE.unserved == frozenset()
    assert all(ULTIMATE.serves(endpoint) for endpoint in (*PAGE_ENDPOINTS, *CALLS))
    assert ULTIMATE.calls_per_minute is None
    assert (ULTIMATE.pace(2850), ULTIMATE.pace(9000), ULTIMATE.pace(0)) == (2850, 9000, 0)


def test_premium_serves_everything_but_the_earnings_calls() -> None:
    """FMP's plan table of 2026-11-25: on Premium the earnings call transcripts alone, of the
    endpoints Fairband calls, are not served."""
    assert PREMIUM.unserved == frozenset(CALLS)
    assert not any(PREMIUM.serves(endpoint) for endpoint in CALLS)
    served = (*STATEMENT_ENDPOINTS, *REQUIRED, "estimates-annual", "estimates-quarter", "earnings")
    assert all(PREMIUM.serves(endpoint) for endpoint in served)
    # A fetch asks neither of the two (B-252), so Premium serves every page call of one.
    assert all(PREMIUM.serves(endpoint) for endpoint in PAGE_ENDPOINTS)


def test_premium_caps_the_pace_at_750_a_minute_less_5_percent() -> None:
    assert PREMIUM.calls_per_minute == 712
    assert PREMIUM.pace(2850) == 712  # the file's pace, Ultimate's: the plan's cap stands
    assert PREMIUM.pace(600) == 600  # a pace the user set under the cap stands
    assert PREMIUM.pace(0) == 712  # 0 is no pacing, which a plan with a cap never runs at


@pytest.mark.parametrize(
    ("word", "plan"),
    [("premium", PREMIUM), ("ultimate", ULTIMATE), (" Premium\n", PREMIUM), ("ULTIMATE", ULTIMATE)],
)
def test_a_plan_by_its_name_whatever_the_case(word: str, plan: object) -> None:
    assert plan_named(word) is plan


@pytest.mark.parametrize("word", ["starter", "basic", "", "premium plan"])
def test_another_word_names_no_plan(word: str) -> None:
    assert plan_named(word) is None
