"""Assemble the Overview mockup as one self-contained HTML file.

    python -I build_mock.py <static dir> <data.json> <page.css> <page.js> <out.html> [<tab>]

``<static dir>`` is ``src/fairband/web/static``; ``<data.json>`` is what ``gather.py`` writes;
the page is ``overview`` or ``drawer``; ``<tab>`` opens the overview page on that tab
(``Estimates``).

The app's fonts, tokens, components and React are inlined, so the file needs no server of its own.
The data is trimmed to what the page reads. The output holds vendor data: it stays in a folder git
ignores and is never committed.
"""

import base64
import json
import re
import sys
from pathlib import Path

static, data_path, page_css, page_js, out = (Path(arg) for arg in sys.argv[1:6])
ds = static / "design-system"
raw = json.loads(data_path.read_text(encoding="utf-8"))
stored, fmp, detail = raw["stored"], raw["fmp"], raw["detail"]


def one(route: str) -> dict:
    rows = fmp[route]
    assert isinstance(rows, list) and rows, route
    return rows[0]


prices = sorted(
    ([row["date"], row["close"], row["volume"]] for row in stored["price-history"]["payload"]),
    key=lambda row: row[0],
)
result = detail["result"]
report = detail["report"]
mock = {
    "profile": stored["profile"]["payload"][0],
    "quote": stored["quote"]["payload"][0],
    "prices": prices,
    "ratios": one("ratios-ttm"),
    "metrics": one("key-metrics-ttm"),
    "growth": one("financial-growth"),
    "scores": one("financial-scores"),
    "change": one("stock-price-change"),
    "targets": one("price-target-consensus"),
    "grades": one("grades-consensus"),
    "float": one("shares-float"),
    "dividends": fmp["dividends"],
    "earnings": stored["earnings"]["payload"],
    "estimates": stored["estimates-annual"]["payload"],
    "news": [
        {
            "date": story["publishedDate"][:10],
            "publisher": story.get("publisher") or story.get("site"),
            "title": story["title"].strip(),
            "url": story["url"],
        }
        for story in stored["news"]["payload"]
    ],
    "detail": {
        "result": {
            key: result[key]
            for key in (
                "phase",
                "value",
                "price",
                "price_to_value",
                "designation",
                "levels",
                "price_date",
                "data_date",
            )
        },
        "report": None
        if report is None
        else {
            key: report[key]
            for key in ("stance", "mode", "createdAt", "principal", "actor", "expired")
        },
    },
    "logo": raw["logo"],
    "dataDate": stored["profile"]["observedAt"][:10],
    "engineRanAt": detail["snapshot"]["createdAt"],
    "startTab": sys.argv[6] if len(sys.argv) > 6 else None,
}


def font_face(match: re.Match[str]) -> str:
    blob = base64.b64encode((ds / "fonts" / match.group(1)).read_bytes()).decode()
    return f'url("data:font/woff2;base64,{blob}")'


fonts = re.sub(
    r'url\("\./([^"]+\.woff2)"\)', font_face, (ds / "fonts" / "fonts.css").read_text("utf-8")
)
styles = "\n".join(
    [
        fonts,
        (ds / "tokens" / "tokens.css").read_text("utf-8"),
        (ds / "components" / "bundle.css").read_text("utf-8"),
        page_css.read_text("utf-8"),
    ]
)


def script(text: str) -> str:
    return "<script>\n" + text.replace("</script", "<\\/script") + "\n</script>"


page = "\n".join(
    [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Company page: Overview mockup</title>",
        "<style>\n" + styles + "\n</style>",
        "</head>",
        "<body>",
        '<div id="root"></div>',
        script((static / "vendor" / "react.production.min.js").read_text("utf-8")),
        script((static / "vendor" / "react-dom.production.min.js").read_text("utf-8")),
        script((ds / "components" / "bundle.js").read_text("utf-8")),
        script("window.MOCK = " + json.dumps(mock).replace("</", "<\\/") + ";"),
        script(page_js.read_text("utf-8")),
        "</body>",
        "</html>",
    ]
)
out.write_text(page, encoding="utf-8")
print("wrote", out, out.stat().st_size, "bytes")
