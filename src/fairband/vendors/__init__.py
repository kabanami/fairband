"""The vendors: one HTTP client that scrubs keys, and an adapter per data vendor.

``fairband.vendors.http.VendorHttp`` is the only way out to a vendor. It refuses redirects, ignores
the environment's proxies, bounds every call in time and retries only what can succeed on a second
try. ``fairband.vendors.scrub.scrub`` replaces a key with ``<key>``; every URL, log line and error
message the client emits has passed through it.
"""
