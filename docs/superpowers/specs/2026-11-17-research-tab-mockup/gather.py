"""Gather one company's answers for the Research tab's mockup from the running server.

    python -I gather.py <symbol> <out dir>

It writes <out dir>/<symbol>/: the company's detail, its reports, its latest report, its research
records, its financial tables, five years of closes, its logo, each sensitivity reading the
report cites and, for a report that rests on a review, the company's reviews. The server runs on
port 8470. The files hold vendor data and a report on file: they stay outside the repository."""

import json
import re
import sys
import urllib.request
from pathlib import Path

symbol, out = sys.argv[1], Path(sys.argv[2]) / sys.argv[1]
out.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8470/api/"


def fetch(path: str) -> bytes:
    request = urllib.request.Request(BASE + path, headers={"X-Fairband-Request": "1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def save(name: str, path: str) -> dict:
    body = fetch(path)
    (out / f"{name}.json").write_bytes(body)
    return json.loads(body)


company = f"companies/{symbol}"
save("detail", company)
reports = save("reports", f"{company}/reports")["reports"]
report = save("report", f"reports/{reports[0]['id']}")
save("research", f"{company}/research")
save("tables", f"{company}/financial-tables")
save("closes", f"{company}/price-history?years=5")
(out / "logo.bin").write_bytes(fetch(f"{company}/logo"))
cited: list[str] = []
for reference in report["references"]:
    found = re.match(r"sensitivity:(\d+)", reference["ref"])
    if found and found.group(1) not in cited:
        cited.append(found.group(1))
for reading in cited:
    save(f"sensitivity_{reading}", f"sensitivities/{reading}")
if report["reviewId"] is not None:
    save("reviews", f"{company}/reviews")
print(symbol, "report", report["id"], "readings", cited, "in", out)
