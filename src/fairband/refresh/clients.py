"""The vendor client a refresh and the agent's pass-throughs use, built from the keys: FMP's, the
one vendor Fairband calls (spec 2026-11-19 8.10).

The key is a secret of its client (``VendorHttp(base_url, [key], ...)``), so the client scrubs it
from everything it emits; the fetch scrubs it from what it stores.

The FMP client is paced to ``refresh.fmp_calls_per_minute``: its one limiter is shared by every
worker that calls through it. Given a ``limiter``, the FMP client takes its slots from that one
instead, so clients built apart (the server's runs and its pass-through) keep one pace.
"""

import httpx

from fairband.config import Keys, require
from fairband.policy import Policy
from fairband.vendors import fmp as fmp_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.http import VendorHttp
from fairband.vendors.limiter import RateLimiter


def build_clients(
    keys: Keys,
    policy: Policy,
    *,
    transport: httpx.BaseTransport | None = None,
    limiter: RateLimiter | None = None,
) -> tuple[Fmp, tuple[str, ...]]:
    """The FMP client (``build_fmp``) and the secrets the fetch scrubs. Raises ``MissingKey``
    without an FMP key. The caller closes the client; ``transport`` stands in for the network in
    tests."""
    fmp = build_fmp(keys, policy, transport=transport, limiter=limiter)
    return fmp, (require(keys, "fmp"),)


def build_fmp(
    keys: Keys,
    policy: Policy,
    *,
    transport: httpx.BaseTransport | None = None,
    limiter: RateLimiter | None = None,
) -> Fmp:
    """The FMP client, paced by ``limiter`` when given, else by one of its own at the policy's
    pace. Raises ``MissingKey`` without an FMP key. The caller closes it."""
    fmp_key = require(keys, "fmp")
    http = VendorHttp(
        fmp_api.BASE_URL,
        [fmp_key],
        policy.refresh,
        transport=transport,
        calls_per_minute=policy.refresh.fmp_calls_per_minute,
        limiter=limiter,
    )
    return Fmp(http, fmp_key)
