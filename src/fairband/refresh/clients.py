"""The vendor clients a refresh uses, built from the keys.

Each key is a secret of its own client only (``VendorHttp(base_url, [key], ...)``), so each client
scrubs the key it sends from everything it emits; the fetch scrubs both from what it stores.
"""

import httpx

from fairband.config import Keys, require
from fairband.policy import Policy
from fairband.vendors import fmp as fmp_api
from fairband.vendors import gurufocus as gurufocus_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.gurufocus import GuruFocus
from fairband.vendors.http import VendorHttp


def build_clients(
    keys: Keys, policy: Policy, *, transport: httpx.BaseTransport | None = None
) -> tuple[Fmp, GuruFocus | None, tuple[str, ...]]:
    """The FMP client, the GuruFocus client (``None`` without a GuruFocus token) and the secrets
    the fetch scrubs. Raises ``MissingKey`` without an FMP key. The caller closes the clients;
    ``transport`` stands in for the network in tests."""
    fmp_key = require(keys, "fmp")
    fmp = Fmp(VendorHttp(fmp_api.BASE_URL, [fmp_key], policy.refresh, transport=transport), fmp_key)
    token = keys.gurufocus
    if token is None:
        return fmp, None, (fmp_key,)
    http = VendorHttp(gurufocus_api.BASE_URL, [token], policy.refresh, transport=transport)
    return fmp, GuruFocus(http, token), (fmp_key, token)
