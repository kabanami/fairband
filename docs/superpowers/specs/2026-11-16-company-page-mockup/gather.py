"""Gather one company's data for the mockups: the stored answers from the database, read-only,
the nine FMP routes the page adds, called with the key of ``keys.toml``, and the company's detail
and logo from the running server on port 8470.

    uv run python gather.py <symbol> <database> <out.json>

It prints no key and no address. Its output is vendor data: write it outside the repository or
into a folder git ignores, and never commit it. A throwaway: it calls the client's private
``_get``, which product code never does."""
import base64, json, sqlite3, sys, urllib.request
from pathlib import Path

from fairband.config import load_keys, load_settings
from fairband.policy import load_policy
from fairband.refresh.clients import build_fmp
from fairband.vendors.http import VendorError

symbol, db, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
data = {"symbol": symbol, "stored": {}, "fmp": {}}
for endpoint in ("profile", "quote", "price-history", "earnings", "estimates-annual", "news"):
    row = conn.execute(
        "SELECT observed_at, payload FROM vendor_responses WHERE symbol=? AND provider='fmp' AND endpoint=? "
        "AND payload IS NOT NULL AND error IS NULL ORDER BY id DESC LIMIT 1", (symbol, endpoint)).fetchone()
    data["stored"][endpoint] = None if row is None else {"observedAt": row[0], "payload": json.loads(row[1])}
ROUTES = ["ratios-ttm", "key-metrics-ttm", "financial-scores", "stock-price-change", "price-target-consensus",
          "grades-consensus", "shares-float"]
fmp = build_fmp(load_keys(load_settings()), load_policy())
try:
    for route, extra in [(r, {}) for r in ROUTES] + [("financial-growth", {"limit": "1"}), ("dividends", {"limit": "8"})]:
        try:
            data["fmp"][route] = fmp._get(route, {"symbol": symbol, **extra}).json
        except VendorError as exc:
            data["fmp"][route] = {"failed": exc.status}
    if data["stored"]["news"] is None:
        data["stored"]["news"] = {"observedAt": None, "payload": fmp._get("news/stock", {"symbols": symbol, "limit": "20"}).json}
finally:
    fmp.close()
base = "http://localhost:8470/api/companies/" + symbol
with urllib.request.urlopen(base) as response:
    data["detail"] = json.load(response)
try:
    with urllib.request.urlopen(base + "/logo") as response:
        kind = response.headers.get_content_type()
        data["logo"] = f"data:{kind};base64," + base64.b64encode(response.read()).decode()
except Exception as exc:  # the mockup draws no logo then
    data["logo"] = None
    print("logo:", type(exc).__name__)
out.write_text(json.dumps(data), encoding="utf-8")
print("wrote", out.name, out.stat().st_size, "bytes")
print("stored:", {k: (None if v is None else (v["observedAt"] or "")[:10]) for k, v in data["stored"].items()})
print("fmp:", {k: ("failed" if isinstance(v, dict) and "failed" in v else len(v)) for k, v in data["fmp"].items()})
d = data["detail"]
print("detail keys:", sorted(d.keys()))
print("snapshot:", {k: d["snapshot"].get(k) for k in list(d["snapshot"])[:40]})
