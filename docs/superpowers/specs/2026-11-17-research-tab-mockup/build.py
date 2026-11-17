"""Build the Research tab's mockup page from the gathered answers of the running server.

    python -I build.py <data dir> <template.html> <out.html> <symbol> [<symbol> ...]

<data dir>/<symbol>/ holds one company's answers: detail.json, reports.json, report.json (the
report shown), research.json, tables.json, closes.json, logo.bin, each sensitivity the report
cites as sensitivity_<id>.json and, for a report that rests on a review, reviews.json.
The page holds them as JSON; the template draws them. A throwaway."""

import base64
import json
import re
import sys
from pathlib import Path

src, template, out = (Path(arg) for arg in sys.argv[1:4])
symbols = sys.argv[4:]
PHASES = {
    "Start-up": 1,
    "Young Growth": 2,
    "High Growth": 3,
    "Mature Growth": 4,
    "Mature Stable": 5,
    "Decline": 6,
}


def slim(table: dict) -> dict:
    return {
        "name": table["name"],
        "rows": [
            {
                "name": row["name"],
                "unit": row["unit"],
                "cells": [
                    {"period": c["period"], "value": c["value"], "note": c["note"]}
                    for c in row["cells"]
                ],
            }
            for row in table["rows"]
        ],
    }


def amount(cite: str) -> float:
    return float(re.sub(r"[^0-9.]", "", cite))


def company(symbol: str) -> dict:
    folder = src / symbol

    def load(name: str):
        return json.loads((folder / f"{name}.json").read_text())

    detail, report, tables = load("detail"), load("report"), load("tables")
    closes = load("closes")["closes"]
    result = detail["result"]
    snapshot = report["appendixA"]["snapshot"]
    # The report's call: the mechanical value of its snapshot, the value it uses and its levels.
    if report["reviewId"] is None:
        wrote: dict[str, str] = {}
        for section in report["sections"]:
            for part in section["parts"]:
                if isinstance(part, dict) and part["ref"].startswith(f"snapshot:{snapshot['id']}/"):
                    wrote.setdefault(part["ref"].split("/", 1)[1], part["cite"])
        value = snapshot["value"]
        levels = {
            "buy": amount(wrote["levels/buy"]),
            "low": amount(wrote["levels/fair_low"]),
            "high": amount(wrote["levels/fair_high"]),
            "trim": amount(wrote["levels/trim"]),
        }
    else:
        review = next(r for r in load("reviews")["reviews"] if r["id"] == report["reviewId"])
        value = review["value"]
        levels = {
            "buy": review["buyLevel"],
            "low": review["fairLow"],
            "high": review["fairHigh"],
            "trim": review["trimLevel"],
        }
    now = detail["review"] if detail["review"] and detail["review"]["refusal"] is None else None
    weekly = [[c["date"], c["close"]["value"]] for c in closes[::5]]
    if weekly[-1][0] != closes[-1]["date"]:
        weekly.append([closes[-1]["date"], closes[-1]["close"]["value"]])
    cited: list[str] = []
    for reference in report["references"]:
        found = re.match(r"sensitivity:(\d+)", reference["ref"])
        if found and found.group(1) not in cited:
            cited.append(found.group(1))
    print(
        symbol,
        "report",
        report["id"],
        "mechanical",
        round(snapshot["value"], 2),
        "the report's value",
        round(value, 2),
        "levels",
        {k: round(v, 2) for k, v in levels.items()},
        "grids",
        cited,
    )
    return {
        "company": {
            k: detail["company"][k] for k in ("symbol", "name", "exchange", "sector", "industry")
        },
        "logo": "data:image/png;base64,"
        + base64.b64encode((folder / "logo.bin").read_bytes()).decode(),
        "phase": {"n": PHASES[result["phase"]["phase"]], "label": result["phase"]["phase"]},
        "moat": detail["moat"],
        "now": {
            "price": result["price"],
            "priceDate": result["price_date"],
            "previous": closes[-2]["close"]["value"],
            "value": now["value"] if now else result["value"],
            "reviewed": now is not None,
        },
        "edges": detail["designationEdges"],
        "call": {"mechanical": snapshot["value"], "value": value, "levels": levels},
        "report": report,
        "reports": load("reports")["reports"],
        "research": load("research"),
        "tables": [slim(t) for t in tables["tables"]],
        "quarters": slim(tables["quarters"]),
        "closes": weekly,
        "grids": [load(f"sensitivity_{i}") for i in cited],
    }


data = {"order": symbols, "companies": {symbol: company(symbol) for symbol in symbols}}
page = template.read_text().replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
out.write_text(page, encoding="utf-8")
print("wrote", out.name, out.stat().st_size, "bytes")
