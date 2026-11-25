"""The FMP plans Fairband runs on: what each serves and how fast it may be called.

FMP names the plan of a key in no answer and in no header (checked live 2026-11-25), so the user
states it beside the key (``fairband.config``), and Fairband trusts this table: it never calls an
endpoint the plan does not serve, and it paces its calls under the plan's limit. A key that states
no plan is on Ultimate, the plan Fairband was built on.

The table is read from FMP's plan comparison of 2026-11-25. Its row "Earnings Transcript" is
Ultimate's alone, so on Premium the list of a company's calls and a call's transcript are not
served. Its rows of the statements, the as-reported statements, the analysts' estimates, the
earnings, the splits, the dividends, the ratios and the key metrics, the scores, the growth, the
price target, the grades, the filing reports and the two revenue splits carry on Premium no
limit but the exchange (US, UK and Canada; the universe lists US exchanges alone, ``method.md``
1): none on the period, so the statements and the estimates come by year and by quarter, and none
on the rows. Its SEC filings and its insider trades are served there whole. The rows of the
other endpoints Fairband calls were not read that day: the profile, the quote, the daily closes,
the screener, the forex pairs, the news, FMP's DCF and the price change, which FMP's own plan
cards put on Starter and so on Premium, and ``batch-quote`` (a price refresh asks one ``quote``
a symbol where the plan answers 402 or 403, ``run_price``), ``stock-peers`` and
``shares-float``, neither required. No refresh has run on a key that is on Premium
(``docs/backlog.md``). Starter and Basic are no plans of this table: both hold five years of
history, under the six balance sheets the return on capital needs (``method.md`` 4.5), and
neither serves the analysts' estimates by quarter, which the NTM anchor reads (5.2).

An endpoint is named as the store names it (``fetch.PAGE_ENDPOINTS``; the earnings calls' two,
``transcript-dates`` and ``transcript``, as their pass-throughs store them). A fetch asks
neither of those two on any plan (``refresh.fetch``): the Investor relations tab and the
agents' tools ask them, through the pass-throughs, which refuse them on Premium.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    """One FMP plan: its ``name`` as the keys file states it, ``calls_per_minute``, the pace its
    limit allows less 5% (``None``: no cap, the setting alone paces), and ``unserved``, the
    endpoints, as stored, that FMP does not serve on it."""

    name: str
    calls_per_minute: int | None
    unserved: frozenset[str]

    @property
    def label(self) -> str:
        """The plan as FMP writes it: ``Premium``."""
        return self.name.capitalize()

    def serves(self, endpoint: str) -> bool:
        """Whether FMP serves ``endpoint``, the store's name of it, on this plan."""
        return endpoint not in self.unserved

    def pace(self, calls_per_minute: float) -> float:
        """The pace a client on this plan runs at: the setting's ``calls_per_minute``, held at
        or under the plan's cap. A setting of 0, no pacing, runs at the cap where there is one."""
        cap = self.calls_per_minute
        if cap is None:
            return calls_per_minute
        return min(calls_per_minute, cap) if calls_per_minute > 0 else cap


# No cap: the policy's ``fmp_calls_per_minute`` is this plan's 3,000 a minute less 5% already.
ULTIMATE = Plan("ultimate", None, frozenset())
# 750 calls a minute less 5%, the margin the policy keeps under Ultimate's limit.
PREMIUM = Plan("premium", 712, frozenset({"transcript-dates", "transcript"}))

PLANS: dict[str, Plan] = {plan.name: plan for plan in (ULTIMATE, PREMIUM)}
PLAN_NAMES = " or ".join(PLANS)  # "ultimate or premium", for a sentence that refuses another word


def plan_named(word: str) -> Plan | None:
    """The plan ``word`` names, whatever its case and the space around it; ``None`` for any
    other word."""
    return PLANS.get(word.strip().lower())
