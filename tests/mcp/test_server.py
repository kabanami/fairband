"""The MCP server's tools (spec 2026-11-06 Tier 2, 6, 7 and 15) on the web tests' app, called the
way a host calls them: through the SDK's in-process client (``mcp.Client`` on the server), which
runs the handshake with the client's name and version. Every tool of spec 15 is registered with a
one-sentence description; each reads or writes its route; a write before ``identify`` is refused
without a call; a refusal is the API's sentence and a server that does not answer is one
sentence."""

import socket
import threading
from contextlib import closing
from dataclasses import replace
from datetime import date
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import Implementation
from support.engine_companies import mature_growth_inputs, universe_deciles
from support.web import CREATED, HEADER, HOST

from fairband.mcp.client import NO_ANSWER, NOT_ASCII, NOT_RUNNING, TIMEOUT_S, FairbandClient
from fairband.mcp.server import BAD_SYMBOL, TOOL_NAMES, build_server, loopback
from fairband.reports.check import headings
from fairband.store.db import connect
from fairband.store.facts import FactRow, insert_facts
from fairband.store.refreshes import save_deciles
from fairband.store.vendor import record_response
from fairband.web import reviews_api
from fairband.web.identity import IDENTIFY_FIRST

PROBE = Implementation(name="probe", version="0")
AGENT = {"agent": "claude-opus-5-5"}
ITEM = {"symbol": "AAPL", "mode": "full report"}
FILING = {"kind": "filing", "ref": "10-K 2025, p. 41", "note": None}
# Spec 15.2 to 15.4, in its order.
SPEC_TOOLS = (
    "screen",
    "company",
    "financials",
    "financial_tables",
    "estimates",
    "price_history",
    "peers",
    "watchlists",
    "inbox_list",
    "reports",
    "report",
    "notes",
    "findings",
    "overrides",
    "reviews",
    "secondary",
    "kill_criteria",
    "news_items",
    "ledger",
    "review_log",
    "policy",
    "methodology",
    "refresh_status",
    "transcript",
    "news",
    "segments",
    "insider_trades",
    "identify",
    "inbox_post",
    "inbox_claim",
    "inbox_complete",
    "inbox_decline",
    "note_add",
    "finding_add",
    "override_add",
    "override_drop",
    "secondary_valuation",
    "sensitivity",
    "derive",
    "report_submit",
    "kill_criterion_add",
    "kill_criterion_set",
    "news_item_add",
    "refresh_start",
    "refresh_cancel",
)
# Each read tool with its arguments and the route it reads (``report`` and a ``methodology``
# without a section are read in their own tests).
READS: dict[str, tuple[dict[str, Any], str]] = {
    "screen": ({"sort": "price", "direction": "desc"}, "/api/screen?sort=price&dir=desc"),
    "company": ({"symbol": "AAPL"}, "/api/companies/AAPL"),
    "financials": ({"symbol": "AAPL"}, "/api/companies/AAPL/financials"),
    "financial_tables": ({"symbol": "AAPL"}, "/api/companies/AAPL/financial-tables"),
    "estimates": ({"symbol": "AAPL"}, "/api/companies/AAPL/estimates"),
    "price_history": ({"symbol": "AAPL", "years": 2}, "/api/companies/AAPL/price-history?years=2"),
    "peers": ({"symbol": "AAPL"}, "/api/companies/AAPL/peers"),
    "watchlists": ({}, "/api/watchlists"),
    "inbox_list": ({"state": "pending"}, "/api/inbox?state=pending"),
    "reports": ({"symbol": "AAPL"}, "/api/companies/AAPL/reports"),
    "notes": ({"symbol": "AAPL"}, "/api/companies/AAPL/notes"),
    "findings": ({"symbol": "AAPL"}, "/api/companies/AAPL/findings"),
    "overrides": ({"symbol": "AAPL"}, "/api/companies/AAPL/overrides"),
    "reviews": ({"symbol": "AAPL"}, "/api/companies/AAPL/reviews"),
    "secondary": ({"symbol": "AAPL"}, "/api/companies/AAPL/secondary"),
    "kill_criteria": ({"symbol": "AAPL"}, "/api/companies/AAPL/kill-criteria"),
    "news_items": ({"symbol": "AAPL"}, "/api/companies/AAPL/news-items"),
    "ledger": ({"symbol": "AAPL", "limit": 5}, "/api/ledger?symbol=AAPL&limit=5"),
    "review_log": ({"symbol": "AAPL"}, "/api/review-log?symbol=AAPL"),
    "policy": ({}, "/api/policy"),
    "methodology": ({"section": "value"}, "/api/methodology/value"),
    "refresh_status": ({}, "/api/refresh/current"),
    "transcript": (
        {"symbol": "AAPL", "year": 2025, "quarter": 3},
        "/api/vendor/transcript/AAPL?year=2025&quarter=3",
    ),
    "news": ({"symbol": "AAPL", "limit": 5}, "/api/vendor/news/AAPL?limit=5"),
    "segments": ({"symbol": "AAPL"}, "/api/vendor/segments/AAPL"),
    "insider_trades": ({"symbol": "AAPL"}, "/api/vendor/insider-trades/AAPL"),
}
# Each write tool with arguments of the right types.
WRITES: dict[str, dict[str, Any]] = {
    "inbox_post": ITEM,
    "inbox_claim": {},
    "inbox_complete": {"item_id": 1, "report_id": 1},
    "inbox_decline": {"item_id": 1, "reason": "no filing yet"},
    "note_add": {"symbol": "AAPL", "text": "The services segment carries the company."},
    "finding_add": {
        "symbol": "AAPL",
        "as_of": "2026-10-31",
        "text": "Services revenue",
        "source": FILING,
        "value": 96e9,
        "unit": "currency",
        "period": "FY2025",
    },
    "override_add": {
        "symbol": "AAPL",
        "tag": "terminal_growth",
        "new": 0.03,
        "reason": "guidance raised",
        "evidence": [FILING],
        "lifetime": "lasting",
    },
    "override_drop": {"override_id": 99, "reason": "the filing was restated"},
    "secondary_valuation": {
        "symbol": "AAPL",
        "parts": [
            {"name": "the business", "fcff": [1e10, 1.05e10, 1.1e10], "terminal_growth": 0.02}
        ],
        "reason": "the services segment carries the company",
        "evidence": [FILING],
    },
    "sensitivity": {
        "symbol": "AAPL",
        "row_tag": "growth.belief",
        "row_values": [0.05, 0.08],
        "col_tag": "moat.class",
        "col_values": ["Narrow", "Wide"],
    },
    "derive": {
        "symbol": "AAPL",
        "derivations": [
            {"operation": "ratio", "a": "policy:required_return", "b": "policy:terminal_growth"}
        ],
    },
    "report_submit": {
        "symbol": "AAPL",
        "mode": "full report",
        "stance": "hold",
        "sections": [],
        "judgments": [],
    },
    "kill_criterion_add": {"symbol": "AAPL", "text": "The services margin falls."},
    "kill_criterion_set": {"id": 99, "state": "retired", "reason": "the segment was sold"},
    "news_item_add": {
        "symbol": "AAPL",
        "date": "2026-10-30",
        "headline": "A recall",
        "source": "Reuters",
        "text": "A product recall.",
    },
    "refresh_start": {"kind": "price"},
    "refresh_cancel": {},
}
JUDGMENTS = [{"judgment": kind, "decision": "keep"} for kind in ("phase", "moat", "belief", "roic")]
SECTIONS = [
    "what",
    "life-cycle",
    "classifier",
    "value",
    "mature-growth",
    "mature-stable",
    "growth",
    "decline",
    "start-up",
    "flags",
    "sources",
    "your-settings",
]


def _session(
    server: MCPServer, *calls: tuple[str, dict[str, Any]], client_info: Implementation = PROBE
) -> list[dict[str, Any]]:
    """Each call's answer, in one session of the SDK's in-process client."""

    async def run() -> list[dict[str, Any]]:
        answers = []
        async with Client(server, client_info=client_info) as session:
            for name, arguments in calls:
                result = await session.call_tool(name, arguments)
                assert not result.is_error, result.content
                assert result.structured_content is not None
                answers.append(result.structured_content)
        return answers

    return anyio.run(run)


def _call(server: MCPServer, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    [answer] = _session(server, (name, arguments))
    return answer


def _sections(snapshot_id: int) -> list[dict[str, Any]]:
    """A full report's ten sections: the first cites the price and the value, the rest are plain
    words."""
    s = f"snapshot:{snapshot_id}"
    first = [
        "The price of ",
        {"cite": "$150.00", "ref": f"{s}/price"},
        " is above the value at belief of ",
        {"cite": "$133", "ref": f"{s}/value"},
        ".",
    ]
    rest = [{"heading": h, "parts": ["Plain words."]} for h in headings("full report")[1:]]
    return [{"heading": "Summary", "parts": first}, *rest]


def test_every_spec_tool_is_registered(api: FairbandClient) -> None:
    server = build_server(api)

    async def listed() -> list[Any]:
        async with Client(server) as session:
            return (await session.list_tools()).tools

    tools = anyio.run(listed)
    assert TOOL_NAMES == SPEC_TOOLS
    assert [tool.name for tool in tools] == list(SPEC_TOOLS)
    for tool in tools:  # one sentence each
        description = tool.description or ""
        assert description.endswith(".") and ". " not in description, tool.name
        assert description[0].isupper(), tool.name
    assert set(READS) | set(WRITES) | {"report", "identify"} == set(SPEC_TOOLS)


def test_a_write_before_identify_is_refused() -> None:
    called: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        called.append(request)
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(answer), base_url=HOST) as http:
        server = build_server(FairbandClient(http))
        answers = _session(server, *WRITES.items())
    assert answers == [{"refused": IDENTIFY_FIRST}] * len(WRITES)
    assert called == []


def test_identify_takes_the_client_from_the_handshake(api: FairbandClient) -> None:
    server = build_server(api)
    blank, identified, item = _session(
        server, ("identify", {"agent": " "}), ("identify", AGENT), ("inbox_post", ITEM)
    )
    assert blank == {"refused": IDENTIFY_FIRST}
    assert identified == {"agent": "claude-opus-5-5", "client": "probe/0"}
    assert (item["origin"], item["postedActor"], item["postedClient"]) == (
        "agent",
        "claude-opus-5-5",
        "probe/0",
    )


def test_inbox_list_calls_the_api(api: FairbandClient, client: TestClient) -> None:
    posted = client.post("/api/inbox", json=ITEM, headers=HEADER).json()
    server = build_server(api)
    every, pending, done = _session(
        server,
        ("inbox_list", {}),
        ("inbox_list", {"state": "pending"}),
        ("inbox_list", {"state": "done"}),
    )
    assert every == client.get("/api/inbox").json() == {"items": [posted]}
    assert pending == every and done == {"items": []}


def test_every_read_tool_reads_its_route(api: FairbandClient, client: TestClient) -> None:
    server = build_server(api)
    answers = _session(server, *[(name, arguments) for name, (arguments, _) in READS.items()])
    for (name, (_, url)), answer in zip(READS.items(), answers, strict=True):
        expected = client.get(url)
        if name == "watchlists":  # the route answers a list; a tool answers an object
            assert answer == {"watchlists": expected.json()}
        elif expected.is_success:
            assert answer == expected.json(), name
        else:
            refusal = {"refused": expected.json()["detail"], "status": expected.status_code}
            assert answer == refusal, name
    # the four pass-throughs reach the route, which has no FMP key here
    vendor = answers[-4:]
    assert vendor == [{"refused": "no FMP key", "status": 503}] * 4


def test_every_write_tool_reaches_its_route(api: FairbandClient) -> None:
    """After ``identify``, no write lands on a route that is not there: each answers the route's
    own words, a refusal included."""
    server = build_server(api)
    answers = _session(server, ("identify", AGENT), *WRITES.items())[1:]
    for name, answer in zip(WRITES, answers, strict=True):
        assert answer.get("refused") not in ("Not Found", "Method Not Allowed"), (name, answer)
    written = dict(zip(WRITES, answers, strict=True))
    assert written["note_add"]["actor"] == "claude-opus-5-5"
    # the part's key as spec 11 names it, sent as the API reads it
    assert written["secondary_valuation"]["parts"][0]["terminalGrowth"] == 0.02
    assert written["derive"] == {"derivations": [{"id": 1, "value": 3.0, "unit": "multiple"}]}


def _store_revenue(db_path: Path, revenue: float) -> None:
    """AAPL's fiscal 2025 revenue, its trailing revenue with no quarters on file."""
    with closing(connect(db_path)) as conn:
        response = record_response(
            conn, "fmp", "income-statement", {"symbol": "AAPL"}, "AAPL", 200, "[]", None, CREATED
        )
        fact = FactRow(
            symbol="AAPL",
            dataset="income-annual",
            period_end=date(2025, 9, 27),
            fiscal_year=2025,
            fiscal_period="FY",
            field="revenue",
            value=Decimal(repr(revenue)),
            unit="USD",
            currency="USD",
            kind="observed",
            estimate_method=None,
            missing_reason=None,
            as_of=date(2025, 9, 27),
            observed_at=CREATED,
            entered_at=CREATED,
            response_id=response,
        )
        insert_facts(conn, [fact])


def test_secondary_valuation_takes_drivers_or_parts(api: FairbandClient, db_path: Path) -> None:
    """The drivers' keys as spec 11 names them, sent as the API reads them; one form only."""
    _store_revenue(db_path, 22e9)
    drivers = {
        "years": 3,
        "revenue_growth": [0.10, 0.08, 0.05],
        "operating_margin": [0.20, 0.20, 0.20],
        "tax_rate": 0.25,
        "sales_to_capital": 2.0,
        "terminal_growth": 0.02,
    }
    common = {"symbol": "AAPL", "reason": "the cycle turns", "evidence": [FILING]}
    parts = WRITES["secondary_valuation"]["parts"]
    server = build_server(api)
    valued, both, neither = _session(
        server,
        ("identify", AGENT),
        ("secondary_valuation", common | {"drivers": drivers}),
        ("secondary_valuation", common | {"drivers": drivers, "parts": parts}),
        ("secondary_valuation", common),
    )[1:]
    assert (valued["form"], valued["parts"], valued["actor"]) == ("drivers", [], "claude-opus-5-5")
    assert valued["drivers"] == {
        "years": 3,
        "revenueGrowth": [0.10, 0.08, 0.05],
        "operatingMargin": [0.20, 0.20, 0.20],
        "taxRate": 0.25,
        "salesToCapital": 2.0,
        "terminalGrowth": 0.02,
    }
    assert valued["projection"]["trailingRevenue"] == 22e9
    assert both == {
        "refused": "a secondary valuation takes drivers or parts, not both",
        "status": 400,
    }
    assert neither == {"refused": "a secondary valuation needs drivers or parts", "status": 400}


def test_sensitivity_sends_its_axes_as_the_api_reads_them(
    api: FairbandClient, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The four axis arguments as spec 15.4 names them, sent camelCase; the store holds no
    statements, so the route builds AAPL's inputs as the fixture valued them."""
    with closing(connect(db_path)) as conn:
        save_deciles(conn, 1, universe_deciles(), CREATED)
    aapl = replace(mature_growth_inputs(), symbol="AAPL")
    monkeypatch.setattr(reviews_api, "build_inputs", lambda *args, **kwargs: aapl)
    server = build_server(api)
    found = _session(server, ("identify", AGENT), ("sensitivity", WRITES["sensitivity"]))[1]
    assert (found["rowTag"], found["rowValues"], found["colTag"], found["colValues"]) == (
        "growth.belief",
        [0.05, 0.08],
        "moat.class",
        ["Narrow", "Wide"],
    )
    assert found["current"] is None and found["actor"] == "claude-opus-5-5"
    assert all(isinstance(cell, float) for row in found["cells"] for cell in row)


def test_a_refusal_is_the_api_s_sentence(api: FairbandClient) -> None:
    server = build_server(api)
    _call(server, "identify", AGENT)
    _call(server, "inbox_post", ITEM)
    assert _call(server, "inbox_post", ITEM) == {
        "refused": "an item for AAPL is open",
        "status": 409,
    }
    locked = _call(server, "override_add", WRITES["override_add"])
    assert (locked["refused"], locked["status"]) == (
        "g_T is a locked input: the terminal growth ceiling",
        400,
    )
    assert locked["override"]["state"] == "refused-locked"  # the rest of the answer, beside it
    assert _call(server, "override_drop", WRITES["override_drop"]) == {
        "refused": "no override 99",
        "status": 404,
    }


def test_report_submit_passes_the_sections_through(api: FairbandClient, client: TestClient) -> None:
    snapshot_id = client.get("/api/companies/AAPL").json()["snapshot"]["id"]
    server = build_server(api)
    assert _call(server, "report", {"symbol": "aapl"}) == {
        "refused": "no report for AAPL",
        "status": 404,
    }
    _call(server, "identify", AGENT)
    item = _call(server, "inbox_post", ITEM)
    claimed = _call(server, "inbox_claim", {"item_id": item["id"]})
    assert (claimed["state"], claimed["claimedBy"]) == ("claimed", "claude-opus-5-5")
    criterion = _call(server, "kill_criterion_add", WRITES["kill_criterion_add"])
    sections = _sections(snapshot_id)
    submission = {
        "symbol": "AAPL",
        "mode": "full report",
        "stance": "hold",
        "sections": sections,
        "judgments": [j | {"override_id": None} for j in JUDGMENTS],
        "kill_criteria": [{"text": "A second product recall."}],
        "news_items": [
            {
                "date": "2026-10-30",
                "headline": "A recall",
                "source": "Reuters",
                "text": "A product recall.",
                "kill_criterion_id": criterion["id"],  # the spec's name, sent camelCase
            }
        ],
        "work_item_id": item["id"],
    }
    report = _call(server, "report_submit", submission)["report"]
    assert report["sections"] == sections
    assert (report["workItemId"], report["actor"], report["client"]) == (
        item["id"],
        "claude-opus-5-5",
        "probe/0",
    )
    assert [j["judgment"] for j in report["judgments"]] == ["phase", "moat", "belief", "roic"]
    assert _call(server, "report", {"symbol": "AAPL"}) == report  # the latest, whole
    assert _call(server, "report", {"symbol": "AAPL", "id": report["id"]}) == report
    done = _call(server, "inbox_list", {"state": "done"})["items"]
    assert [(i["id"], i["reportId"]) for i in done] == [(item["id"], report["id"])]
    news = _call(server, "news_items", {"symbol": "AAPL"})["newsItems"]
    assert [(n["headline"], n["killCriterionId"], n["reportId"]) for n in news] == [
        ("A recall", criterion["id"], report["id"])
    ]
    texts = [k["text"] for k in _call(server, "kill_criteria", {"symbol": "AAPL"})["killCriteria"]]
    assert sorted(texts) == ["A second product recall.", "The services margin falls."]


def test_a_rejected_report_carries_its_findings(api: FairbandClient, client: TestClient) -> None:
    snapshot_id = client.get("/api/companies/AAPL").json()["snapshot"]["id"]
    server = build_server(api)
    _call(server, "identify", AGENT)
    sections = _sections(snapshot_id)
    sections[1] = {"heading": sections[1]["heading"], "parts": ["Revenue grew 12% a year."]}
    rejected = _call(
        server,
        "report_submit",
        {
            "symbol": "AAPL",
            "mode": "full report",
            "stance": "hold",
            "sections": sections,
            "judgments": JUDGMENTS,
        },
    )
    assert (rejected["refused"], rejected["status"]) == ("rejected: 1 finding", 422)
    [finding] = rejected["findings"]
    assert finding["what"] == "a number with no reference"
    assert finding["where"] == "section 2, part 1: 12%"


def test_methodology_lists_the_sections_without_one(api: FairbandClient) -> None:
    server = build_server(api)
    listed, value, unknown = _session(
        server,
        ("methodology", {}),
        ("methodology", {"section": "value"}),
        ("methodology", {"section": "nope"}),
    )
    assert [s["id"] for s in listed["sections"]] == SECTIONS
    assert listed["sections"][4] == {"id": "mature-growth", "title": "Mature Growth"}
    assert (value["id"], value["title"]) == ("value", "What a value means here")
    assert unknown == {"refused": "no methodology section nope", "status": 404}


def test_a_symbol_outside_the_symbol_characters_is_refused_before_any_call() -> None:
    """A slash or a dot segment in a path would reach another route (``AAPL/../../policy`` the
    policy, ``..`` the route above), so a symbol is letters, digits, dots and dashes, with a
    letter or a digit among them; nothing is called."""
    called: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        called.append(request)
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(answer), base_url=HOST) as http:
        server = build_server(FairbandClient(http))
        symbols = ("AAPL/../../policy", "..", ".", "AAPL?x=1", "a b", "AAPL#")
        answers = _session(
            server,
            *[("company", {"symbol": s}) for s in symbols],
            ("financials", {"symbol": ".."}),
            ("report", {"symbol": ".."}),
            ("transcript", {"symbol": "..", "year": 2025, "quarter": 3}),
            ("identify", AGENT),
            ("note_add", {"symbol": "..", "text": "a note"}),
        )
    refused = {"refused": BAD_SYMBOL}
    assert BAD_SYMBOL == "a symbol is letters, digits, dots and dashes"
    assert answers[: len(symbols) + 3] == [refused] * (len(symbols) + 3)
    assert answers[-1] == refused
    assert called == []


def test_a_symbol_is_upper_cased(api: FairbandClient, client: TestClient) -> None:
    company, financials = _session(
        build_server(api), ("company", {"symbol": "aapl"}), ("financials", {"symbol": "aapl"})
    )
    assert company == client.get("/api/companies/AAPL").json()
    assert financials == {"refused": "no financial statements for AAPL", "status": 404}
    paths: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(answer), base_url=HOST) as http:
        _session(
            build_server(FairbandClient(http)),
            ("company", {"symbol": "brk.b"}),
            ("segments", {"symbol": "bf-b"}),
        )
    assert paths == ["/api/companies/BRK.B", "/api/vendor/segments/BF-B"]


def test_server_down_is_one_sentence(down: FairbandClient) -> None:
    answers = _session(
        build_server(down),
        ("screen", {}),
        ("report", {"symbol": "AAPL"}),
        ("identify", AGENT),
        ("note_add", WRITES["note_add"]),
    )
    assert answers == [
        {"refused": NOT_RUNNING},
        {"refused": NOT_RUNNING},
        {"agent": "claude-opus-5-5", "client": "probe/0"},
        {"refused": NOT_RUNNING},
    ]


def test_a_server_that_does_not_answer_in_time_is_its_own_sentence() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with httpx.Client(transport=httpx.MockTransport(answer), base_url=HOST) as http:
        answers = _session(
            build_server(FairbandClient(http)),
            ("screen", {}),
            ("identify", AGENT),
            ("note_add", WRITES["note_add"]),
        )
    assert answers[0] == answers[2] == {"refused": NO_ANSWER}


def test_identify_refuses_an_identifier_that_is_not_printable_ascii(api: FairbandClient) -> None:
    server = build_server(api)
    refused, write = _session(
        server, ("identify", {"agent": "claude-opus-5-5\nX-Other: 1"}), ("inbox_post", ITEM)
    )
    assert refused == {"refused": NOT_ASCII}
    assert write == {"refused": IDENTIFY_FIRST}  # the identity is not set


def test_identify_leaves_out_a_client_that_is_not_printable_ascii(api: FairbandClient) -> None:
    server = build_server(api)
    accented = Implementation(name="prøbe", version="0")
    identified, item = _session(
        server, ("identify", AGENT), ("inbox_post", ITEM), client_info=accented
    )
    assert identified == {"agent": "claude-opus-5-5", "client": None}
    assert (item["postedActor"], item["postedClient"]) == ("claude-opus-5-5", None)


class _Answer(BaseHTTPRequestHandler):
    """A web server on the loopback that answers every read with ``{"ok": true}``."""

    def do_GET(self) -> None:
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:  # quiet
        pass


def test_the_command_s_client_takes_no_proxy_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A proxy variable would send every loopback call to the proxy, so a running server would
    read as down; the command's client reads no setting from the environment."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        nothing = s.getsockname()[1]  # a proxy that is not there
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(name, f"http://127.0.0.1:{nothing}")
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
    web = HTTPServer(("127.0.0.1", 0), _Answer)
    thread = threading.Thread(target=web.serve_forever, daemon=True)
    thread.start()
    try:
        with loopback(web.server_address[1]) as http:
            assert http.timeout.read == TIMEOUT_S
            assert FairbandClient(http).get("/api/screen") == {"ok": True}
    finally:
        web.shutdown()
        web.server_close()
