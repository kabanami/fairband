"""The vendor clients a refresh and the agent's pass-throughs use, built from the keys.

Each key is a secret of its own client only (``VendorHttp(base_url, [key], ...)``), so each client
scrubs the key it sends from everything it emits; the fetch scrubs both from what it stores.

The FMP client is paced to ``refresh.fmp_calls_per_minute``: its one limiter is shared by every
worker that calls through it. Given a ``limiter``, the FMP client takes its slots from that one
instead, so clients built apart (the server's runs and its pass-through) keep one pace. The
GuruFocus client (``build_gurufocus``), the refresh's alone, is not paced.
"""

import httpx

from fairband.config import Keys, require
from fairband.policy import Policy
from fairband.vendors import fmp as fmp_api
from fairband.vendors import gurufocus as gurufocus_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.gurufocus import GuruFocus
from fairband.vendors.http import VendorHttp
from fairband.vendors.limiter import RateLimiter


def build_clients(
    keys: Keys,
    policy: Policy,
    *,
    transport: httpx.BaseTransport | None = None,
    limiter: RateLimiter | None = None,
) -> tuple[Fmp, GuruFocus | None, tuple[str, ...]]:
    """The FMP client (``build_fmp``), the GuruFocus client (``None`` without a GuruFocus token)
    and the secrets the fetch scrubs. Raises ``MissingKey`` without an FMP key. The caller closes
    the clients; ``transport`` stands in for the network in tests."""
    fmp = build_fmp(keys, policy, transport=transport, limiter=limiter)
    fmp_key = require(keys, "fmp")
    token = keys.gurufocus
    gurufocus = build_gurufocus(keys, policy, transport=transport)
    return fmp, gurufocus, (fmp_key,) if token is None else (fmp_key, token)


def build_gurufocus(
    keys: Keys, policy: Policy, *, transport: httpx.BaseTransport | None = None
) -> GuruFocus | None:
    """The GuruFocus client, not paced; ``None`` without a GuruFocus token. The caller closes
    it."""
    token = keys.gurufocus
    if token is None:
        return None
    http = VendorHttp(gurufocus_api.BASE_URL, [token], policy.refresh, transport=transport)
    return GuruFocus(http, token)


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
