"""``build_clients`` and ``build_fmp``: each key travels with its own vendor client and is a secret
of that client, so the client scrubs it from the URL it reports. The keys here are fake."""

from datetime import timedelta

import httpx
import pytest

from fairband.config import Keys, MissingKey, utcnow
from fairband.policy import Policy
from fairband.refresh.clients import build_clients, build_fmp
from fairband.vendors.limiter import RateLimiter

FMP_KEY = "fake-fmp-key-0002"  # not a real key
GF_TOKEN = "fakegfhalf:fakegfhalf3"  # not a real token


def test_each_key_is_a_secret_of_its_own_client(policy: Policy) -> None:
    sent: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url))
        return httpx.Response(200, json=[{"symbol": "ACME"}])

    transport = httpx.MockTransport(answer)
    fmp, gf, secrets = build_clients(Keys(FMP_KEY, GF_TOKEN), policy, transport=transport)
    assert gf is not None
    try:
        quote, summary = fmp.quote(["ACME"]), gf.summary("ACME")
    finally:
        fmp.close()
        gf.close()
    assert secrets == (FMP_KEY, GF_TOKEN)
    assert sent == [
        f"https://financialmodelingprep.com/stable/quote?symbol=ACME&apikey={FMP_KEY}",
        f"https://api.gurufocus.com/public/user/{GF_TOKEN}/stock/ACME/summary",
    ]
    assert quote.url == "https://financialmodelingprep.com/stable/quote?symbol=ACME&apikey=<key>"
    assert summary.url == "https://api.gurufocus.com/public/user/<key>/stock/ACME/summary"


def test_fmp_is_paced_and_gurufocus_is_not(policy: Policy) -> None:
    fmp, gf, _ = build_clients(Keys(FMP_KEY, GF_TOKEN), policy)
    assert gf is not None
    fmp.close()
    gf.close()
    fmp_limiter, gf_limiter = fmp._http.limiter, gf._http.limiter
    pace = policy.refresh.fmp_calls_per_minute
    assert fmp_limiter.calls_per_minute == pace == 2850
    assert fmp_limiter.interval == timedelta(seconds=60 / pace)
    assert gf_limiter.calls_per_minute == 0 and gf_limiter.interval == timedelta(0)


def test_without_a_gurufocus_token(policy: Policy) -> None:
    fmp, gf, secrets = build_clients(Keys(FMP_KEY, None), policy)
    fmp.close()
    assert (gf, secrets) == (None, (FMP_KEY,))


def test_without_an_fmp_key(policy: Policy) -> None:
    with pytest.raises(MissingKey, match="no fmp key"):
        build_clients(Keys(None, GF_TOKEN), policy)


def test_a_given_limiter_paces_the_fmp_client_alone(policy: Policy) -> None:
    """The server hands its one limiter to each run's FMP client and to the pass-through's
    (``build_fmp``); the GuruFocus client keeps its own, unpaced."""
    limiter = RateLimiter(600, utcnow, lambda _: None)
    fmp, gf, _ = build_clients(Keys(FMP_KEY, GF_TOKEN), policy, limiter=limiter)
    alone = build_fmp(Keys(FMP_KEY, None), policy, limiter=limiter)
    assert gf is not None
    for client in (fmp, gf, alone):
        client.close()
    assert fmp.limiter is alone.limiter is limiter
    assert gf._http.limiter is not limiter and gf._http.limiter.calls_per_minute == 0
    paced = build_fmp(Keys(FMP_KEY, None), policy)
    paced.close()
    assert paced.limiter.calls_per_minute == policy.refresh.fmp_calls_per_minute


def test_build_fmp_needs_an_fmp_key(policy: Policy) -> None:
    with pytest.raises(MissingKey, match="no fmp key"):
        build_fmp(Keys(None, GF_TOKEN), policy)
