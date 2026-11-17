"""Gather one company's data for the Financials tab's mockup: the stored statements and segments
from the database, read-only; FMP's ratios and key metrics by fiscal year, called with the key of
``keys.toml``; the company's detail and logo from the running server on port 8470.

    uv run python gather_fin.py <symbol> <database> <out.json>

It prints no key and no address. Its output is vendor data: it stays outside the repository. A
throwaway: it calls the client's private ``_get``, which product code never does."""

import base64
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

from fairband.config import load_keys, load_settings
from fairband.policy import load_policy
from fairband.refresh.clients import build_fmp
from fairband.vendors.http import VendorError

symbol, db, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
data: dict = {"symbol": symbol, "stored": {}, "fmp": {}}
STORED = (
    "income-annual",
    "balance-annual",
    "cashflow-annual",
    "income-quarter",
    "balance-quarter",
    "cashflow-quarter",
    "segments-product",
    "segments-geographic",
)
for endpoint in STORED:
    row = conn.execute(
        "SELECT observed_at, payload FROM vendor_responses WHERE symbol=? AND provider='fmp' AND endpoint=? "
        "AND payload IS NOT NULL AND error IS NULL ORDER BY id DESC LIMIT 1",
        (symbol, endpoint),
    ).fetchone()
    data["stored"][endpoint] = (
        None if row is None else {"observedAt": row[0], "payload": json.loads(row[1])}
    )
fmp = build_fmp(load_keys(load_settings()), load_policy())
try:
    for route in ("ratios", "key-metrics"):
        try:
            data["fmp"][route] = fmp._get(
                route, {"symbol": symbol, "period": "annual", "limit": "11"}
            ).json
        except VendorError as exc:
            data["fmp"][route] = {"failed": exc.status}
    for kind, route in (
        ("segments-product", "revenue-product-segmentation"),
        ("segments-geographic", "revenue-geographic-segmentation"),
    ):
        if data["stored"][kind] is None:
            try:
                data["stored"][kind] = {
                    "observedAt": None,
                    "payload": fmp._get(route, {"symbol": symbol}).json,
                }
            except VendorError as exc:
                print(kind, "failed", exc.status)
finally:
    fmp.close()
base = "http://localhost:8470/api/companies/" + symbol
with urllib.request.urlopen(base) as response:
    data["detail"] = json.load(response)
try:
    with urllib.request.urlopen(base + "/logo") as response:
        kind = response.headers.get_content_type()
        data["logo"] = f"data:{kind};base64," + base64.b64encode(response.read()).decode()
except OSError as exc:  # the mockup draws no logo then
    data["logo"] = None
    print("logo:", type(exc).__name__)
out.write_text(json.dumps(data), encoding="utf-8")
print("wrote", out.name, out.stat().st_size, "bytes")
for key, value in data["stored"].items():
    rows = value["payload"] if value else []
    print(f"stored {key}: {len(rows)} rows, {len(rows[0]) if rows else 0} fields")
for key, value in data["fmp"].items():
    if isinstance(value, dict):
        print(f"fmp {key}: {value}")
    else:
        print(f"fmp {key}: {len(value)} rows; fields: {', '.join(value[0].keys())}")
for key in ("balance-annual", "cashflow-annual"):
    print(key, "fields:", ", ".join(data["stored"][key]["payload"][0].keys()))
