"""The report tests' publish helpers, which the Research tab's read tests share: the id of a
company's latest snapshot, a report's sections and body, and a submission through the report route
under an agent's headers, published or not."""

from typing import Any

from fastapi.testclient import TestClient

from fairband.reports.check import headings
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, PRINCIPAL_HEADER
from support.web import HEADER

AGENT = HEADER | {
    PRINCIPAL_HEADER: "agent",
    ACTOR_HEADER: "claude-opus-5-5",
    CLIENT_HEADER: "claude-code/2.1",
}
JUDGMENTS = [
    {"judgment": kind, "decision": f"keep the {kind}"}
    for kind in ("phase", "moat", "belief", "roic")
]


def snapshot_id(client: TestClient, symbol: str = "AAPL") -> int:
    found: int = client.get(f"/api/companies/{symbol}").json()["snapshot"]["id"]
    return found


def sections(sid: int, mode: str = "full report", *extra: Any) -> list[dict[str, Any]]:
    """The sections of ``mode``: section 1 cites the price, the value and r, then ``extra``."""
    s = f"snapshot:{sid}"
    first = [
        "The price of ",
        {"cite": "$150.00", "ref": f"{s}/price"},
        " is above the value at belief of ",
        {"cite": "$128", "ref": f"{s}/value"},
        ", discounted at ",
        {"cite": "9.0%", "ref": "policy:required_return"},
        ". Three reasons stand out in FY2025.",
        *extra,
    ]
    rest = [{"heading": h, "parts": ["Plain words."]} for h in headings(mode)[1:]]
    return [{"heading": "Summary", "parts": first}, *rest]


def body(sid: int, **changes: Any) -> dict[str, Any]:
    """A full report on snapshot ``sid``, a hold, with the four judgments; ``changes`` replace its
    keys."""
    plain = {
        "mode": "full report",
        "stance": "hold",
        "sections": sections(sid),
        "judgments": JUDGMENTS,
    }
    return plain | changes


def submit(client: TestClient, posted: dict[str, Any], symbol: str = "AAPL") -> Any:
    return client.post(f"/api/companies/{symbol}/reports", json=posted, headers=AGENT)


def published(client: TestClient, posted: dict[str, Any], symbol: str = "AAPL") -> Any:
    """The report ``posted`` publishes, as the route answers it; the test fails where it does
    not."""
    r = submit(client, posted, symbol)
    assert r.status_code == 201, r.text
    return r.json()["report"]
