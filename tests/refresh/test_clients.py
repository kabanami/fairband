"""``build_clients`` and ``build_fmp``: the FMP key travels with its client and is a secret of
that client, so the client scrubs it from the URL it reports. FMP is the one vendor Fairband calls
(spec 2026-11-19 8.10). The key here is fake."""

from dataclasses import replace
from datetime import timedelta

import httpx
import pytest

from fairband.config import Keys, MissingKey, utcnow
from fairband.plans import PREMIUM, ULTIMATE
from fairband.policy import Policy
from fairband.refresh.clients import build_clients, build_fmp
from fairband.vendors.limiter import RateLimiter

FMP_KEY = "fake-fmp-key-0002"  # not a real key


def test_the_key_is_a_secret_of_its_client(policy: Policy) -> None:
    sent: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url))
        return httpx.Response(200, json=[{"symbol": "ACME"}])

    transport = httpx.MockTransport(answer)
    fmp, secrets = build_clients(Keys(FMP_KEY), policy, transport=transport)
    try:
        quote = fmp.quote(["ACME"])
    finally:
        fmp.close()
    assert secrets == (FMP_KEY,)
    assert sent == [f"https://financialmodelingprep.com/stable/quote?symbol=ACME&apikey={FMP_KEY}"]
    assert quote.url == "https://financialmodelingprep.com/stable/quote?symbol=ACME&apikey=<key>"


def test_fmp_is_paced(policy: Policy) -> None:
    fmp, _ = build_clients(Keys(FMP_KEY), policy)
    fmp.close()
    limiter = fmp._http.limiter
    pace = policy.refresh.fmp_calls_per_minute
    assert limiter.calls_per_minute == pace == 2850
    assert limiter.interval == timedelta(seconds=60 / pace)


def test_without_an_fmp_key(policy: Policy) -> None:
    with pytest.raises(MissingKey, match="no fmp key"):
        build_clients(Keys(None), policy)


def test_a_given_limiter_paces_the_fmp_client(policy: Policy) -> None:
    """The server hands its one limiter to each run's FMP client and to the pass-through's
    (``build_fmp``)."""
    limiter = RateLimiter(600, utcnow, lambda _: None)
    fmp, _ = build_clients(Keys(FMP_KEY), policy, limiter=limiter)
    alone = build_fmp(Keys(FMP_KEY), policy, limiter=limiter)
    for client in (fmp, alone):
        client.close()
    assert fmp.limiter is alone.limiter is limiter
    paced = build_fmp(Keys(FMP_KEY), policy)
    paced.close()
    assert paced.limiter.calls_per_minute == policy.refresh.fmp_calls_per_minute


def test_the_client_is_on_the_keys_plan_and_paced_under_its_cap(policy: Policy) -> None:
    """The plan travels with the key. A client on Premium is paced at the plan's cap, 712 calls a
    minute, under the policy's 2,850; one on Ultimate, the plan of a key that states none, at the
    policy's pace as before."""
    premium = build_fmp(Keys(FMP_KEY, PREMIUM), policy)
    ultimate, _ = build_clients(Keys(FMP_KEY), policy)
    for client in (premium, ultimate):
        client.close()
    assert premium.plan is PREMIUM and ultimate.plan is ULTIMATE
    assert premium.limiter.calls_per_minute == 712
    assert ultimate.limiter.calls_per_minute == 2850
    slow = replace(policy, refresh=replace(policy.refresh, fmp_calls_per_minute=600))
    paced = build_fmp(Keys(FMP_KEY, PREMIUM), slow)
    paced.close()
    assert paced.limiter.calls_per_minute == 600  # a pace set under the cap stands


def test_build_fmp_needs_an_fmp_key(policy: Policy) -> None:
    with pytest.raises(MissingKey, match="no fmp key"):
        build_fmp(Keys(None), policy)
