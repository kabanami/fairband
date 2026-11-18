"""Build the Investor relations tab's mockup page for one company. A throwaway.

    python -I build.py <symbol> <template.html> <out.html>

It reads the company's stored call dates, newest stored transcript, earnings rows and filing
list from the live store, read-only, and the head's facts from the server on port 8470, and
writes one self-contained HTML file. The store must hold a `transcript-dates`, a `transcript`,
an `earnings` and a `sec-filings` answer for the company (a research session on it leaves them).

The page holds a cut of the transcript: the first 14 turns, a long turn cut at about 1,700
characters. The file holds vendor data: write it outside the repository."""

import base64
import json
import os
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

symbol, template, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
BASE = "http://127.0.0.1:8470/api/"
STORE = "file:" + os.path.expanduser("~/.local/share/fairband/fairband.db") + "?mode=ro"
PHASES = {
    "Start-up": 1,
    "Young Growth": 2,
    "High Growth": 3,
    "Mature Growth": 4,
    "Mature Stable": 5,
    "Decline": 6,
}
TURNS, TURN_CHARS = 14, 1700


def fetch(path: str) -> bytes:
    request = urllib.request.Request(BASE + path, headers={"X-Fairband-Request": "1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def stored(db: sqlite3.Connection, endpoint: str) -> tuple[dict, object]:
    """The newest usable stored answer of one endpoint: its params and its payload."""
    row = db.execute(
        "select params, payload from vendor_responses where endpoint = ? and symbol = ?"
        " and http_status = 200 and error is null order by id desc limit 1",
        (endpoint, symbol),
    ).fetchone()
    if row is None:
        raise SystemExit(f"the store holds no {endpoint} answer for {symbol}")
    return json.loads(row[0]), json.loads(row[1])


def turns_of(content: str) -> list[dict]:
    turns: list[dict] = []
    for line in content.split("\n"):
        found = re.match(r"^([^:\n]{2,60}): (.*)$", line)
        if found and len(found.group(1).split()) <= 6:
            turns.append({"speaker": found.group(1), "text": found.group(2)})
        elif turns and line.strip():
            turns[-1]["text"] += "\n" + line.strip()
    return turns


db = sqlite3.connect(STORE, uri=True)
_, dates = stored(db, "transcript-dates")
_, earnings = stored(db, "earnings")
window, filings = stored(db, "sec-filings")
_, transcript = stored(db, "transcript")
call = transcript[0]
detail = json.loads(fetch(f"companies/{symbol}"))
overview = json.loads(fetch(f"companies/{symbol}/page/overview"))
logo = base64.b64encode(fetch(f"companies/{symbol}/logo")).decode()

company, phase = detail["company"], detail["result"]["phase"]["phase"]
quote = overview["quote"]
rows = {(e["fiscalYear"], e["fiscalPeriod"]): e for e in earnings}
calls = []
for date in dates:
    row = rows.get((date["fiscalYear"], f"Q{date['quarter']}"), {})
    calls.append(
        {
            "fiscalYear": date["fiscalYear"],
            "quarter": date["quarter"],
            "date": date["date"],
            "epsActual": row.get("epsActual"),
            "epsEstimated": row.get("epsEstimated"),
            "revenueActual": row.get("revenueActual"),
            "revenueEstimated": row.get("revenueEstimated"),
        }
    )
every = turns_of(call["content"])
shown = []
for turn in every[:TURNS]:
    text, cut = turn["text"], False
    if len(text) > TURN_CHARS:
        ends = list(re.finditer(r"[.!?] ", text[:TURN_CHARS]))
        text, cut = text[: ends[-1].end()].strip(), True
    shown.append({"speaker": turn["speaker"], "text": text, "cut": cut})
data = {
    "head": {
        "name": company["name"],
        "symbol": company["symbol"],
        "exchange": company["exchange"],
        "sector": company["sector"],
        "industry": company["industry"],
        "phase": phase,
        "phaseNumber": PHASES[phase],
        "moat": detail["moat"],
        "logo": "data:image/png;base64," + logo,
        "price": quote["price"],
        "change": quote["change"],
        "changePercent": quote["changePercent"],
        "day": quote["day"],
    },
    "dataDate": overview["dataDate"],
    "nextEarnings": min(
        e["date"] for e in earnings if e["epsActual"] is None and e["date"] >= overview["dataDate"]
    ),
    "calls": calls,
    "transcript": {
        "fiscalYear": int(call["year"]),
        "quarter": int(str(call["period"]).lstrip("Q")),
        "turns": shown,
        "allTurns": len(every),
        # The mockup's rule, the first turn by the operator; the design's 7.4 gives the tab's.
        "questionsAt": next(i for i, t in enumerate(every) if t["speaker"] == "Operator"),
    },
    "filings": [
        {
            "formType": f["formType"],
            "filingDate": f["filingDate"][:10],
            "link": f.get("link"),
            "finalLink": f.get("finalLink"),
        }
        for f in filings
    ],
    "filingsFrom": window["from"],
    "filingsTo": window["to"],
}
page = template.read_text()
assert page.count("/*DATA*/null") == 1
out.write_text(page.replace("/*DATA*/null", json.dumps(data).replace("</", "<\\/")))
print(symbol, len(calls), "calls,", len(shown), "of", len(every), "turns,", len(filings), "filings")
