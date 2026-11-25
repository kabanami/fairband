"""The MCP server's tools (spec 2026-11-06 Tier 2, 6, 7 and 15) on the web tests' app, called the
way a host calls them: through the SDK's in-process client (``mcp.Client`` on the server), which
runs the handshake with the client's name and version. Every tool of spec 15 is registered with a
one-sentence description; each reads or writes its route; a write before ``identify`` is refused
without a call; a refusal is the API's sentence and a server that does not answer is one
sentence."""

import json
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
from support.engine_companies import ars_refused_inputs, mature_growth_inputs, universe_deciles
from support.web import CREATED, HEADER, HOST
from support.web import TODAY as WEB_TODAY

from fairband.engine.route import value_company
from fairband.mcp.client import NO_ANSWER, NOT_ASCII, NOT_RUNNING, TIMEOUT_S, FairbandClient
from fairband.mcp.server import BAD_SYMBOL, TOOL_NAMES, build_server, loopback
from fairband.policy import Policy
from fairband.reports.check import headings
from fairband.store.db import connect
from fairband.store.facts import FactRow, insert_facts
from fairband.store.refreshes import save_deciles
from fairband.store.snapshots import insert_snapshot
from fairband.store.vendor import record_response
from fairband.web import reviews_api
from fairband.web.identity import ACTOR_HEADER, IDENTIFY_FIRST, PRINCIPAL_HEADER

PROBE = Implementation(name="probe", version="0")
AGENT = {"agent": "claude-opus-5-5"}
ITEM = {"symbol": "AAPL", "mode": "full report"}
FILING = {"kind": "filing", "ref": "10-K 2025, p. 41", "note": None}
# Spec 15.2 to 15.4, in its order, with ``quarters`` after ``financials``, the filing reads after
# the pass-throughs (spec 2026-11-11, 6) and ``moat_set`` before ``override_add`` (spec 2026-11-19
# 8.6).
SPEC_TOOLS = (
    "screen",
    "company",
    "financials",
    "quarters",
    "financial_tables",
    "estimates",
    "price_history",
    "multiples_history",
    "peers",
    "watchlists",
    "inbox_list",
    "reports",
    "report",
    "notes",
    "findings",
    "guidance",
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
    "transcript_dates",
    "dcf",
    "filings",
    "filing_report",
    "filing_search",
    "identify",
    "inbox_post",
    "inbox_claim",
    "inbox_complete",
    "inbox_decline",
    "note_add",
    "finding_add",
    "guidance_add",
    "moat_set",  # spec 2026-11-19 8.6, before the overrides
    "override_add",
    "override_drop",
    "review_again",  # spec 2026-11-23 held reviewed value, 5.6
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
    "quarters": ({"symbol": "AAPL"}, "/api/companies/AAPL/quarters"),
    "financial_tables": ({"symbol": "AAPL"}, "/api/companies/AAPL/financial-tables"),
    "estimates": ({"symbol": "AAPL"}, "/api/companies/AAPL/estimates"),
    "price_history": ({"symbol": "AAPL", "years": 2}, "/api/companies/AAPL/price-history?years=2"),
    "multiples_history": ({"symbol": "AAPL"}, "/api/companies/AAPL/multiples-history"),
    "peers": ({"symbol": "AAPL"}, "/api/companies/AAPL/peers"),
    "watchlists": ({}, "/api/watchlists"),
    "inbox_list": ({"state": "pending"}, "/api/inbox?state=pending"),
    "reports": ({"symbol": "AAPL"}, "/api/companies/AAPL/reports"),
    "notes": ({"symbol": "AAPL"}, "/api/companies/AAPL/notes"),
    "findings": ({"symbol": "AAPL"}, "/api/companies/AAPL/findings"),
    "guidance": ({"symbol": "AAPL"}, "/api/companies/AAPL/guidance"),
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
    "transcript_dates": ({"symbol": "AAPL"}, "/api/vendor/transcript-dates/AAPL"),
    "dcf": ({"symbol": "AAPL"}, "/api/vendor/dcf/AAPL"),
    "filings": (
        {
            "symbol": "AAPL",
            "forms": "10-K,10-Q",
            "from_date": "2026-01-01",
            "to_date": "2026-11-11",
            "from_row": 50,
        },
        "/api/companies/AAPL/filings?forms=10-K%2C10-Q&from=2026-01-01&to=2026-11-11&fromRow=50",
    ),
    "filing_report": (
        {
            "symbol": "aapl",
            "year": 2027,
            "period": "Q1",
            "sheet": "Revenue by Product/Region",
            "from_row": 100,
        },
        (
            "/api/companies/AAPL/filing-report"
            "?year=2027&period=Q1&sheet=Revenue+by+Product%2FRegion&fromRow=100"
        ),
    ),
    "filing_search": (
        {"symbol": "AAPL", "year": 2027, "period": "Q1", "text": "not yet commenced"},
        "/api/companies/AAPL/filing-report/search?year=2027&period=Q1&text=not+yet+commenced",
    ),
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
    "guidance_add": {
        "symbol": "AAPL",
        "metric": "eps",
        "period": "2026",
        "low": 6.3,
        "high": 6.6,
        "basis": "gaap",
        "as_of": "2026-10-28",
        "text": "We expect EPS of $6.30 to $6.60 for fiscal 2026.",
        "source": "response:12/0/content",
    },
    "moat_set": {
        "symbol": "AAPL",
        "moat_class": "Wide",
        "reason": "switching costs hold: the installed base renews",
        "evidence": [FILING],
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
    "review_again": {"symbol": "AAPL"},
    "secondary_valuation": {
        "symbol": "AAL",  # refused: the secondary valuation is the fallback (plan 3)
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
    "foreign-filers",
    "mature-growth",
    "mature-stable",
    "growth",
    "decline",
    "start-up",
    "flags",
    "agents",
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
    """A full report's twelve sections: the first cites the price and the value, the rest are plain
    words."""
    s = f"snapshot:{snapshot_id}"
    first = [
        "The price of ",
        {"cite": "$150.00", "ref": f"{s}/price"},
        " is above the value at belief of ",
        {"cite": "$128", "ref": f"{s}/value"},
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
    # GuruFocus's series and its tool went (spec 2026-11-19 6.3): multiples_history serves the
    # series Fairband builds from FMP's data.
    assert "pe_history" not in TOOL_NAMES
    # the agent's moat verdict (spec 2026-11-19 8.6): 55 tools again; Review again (spec
    # 2026-11-23 held reviewed value, 5.6): 56
    assert len(TOOL_NAMES) == 56
    for tool in tools:  # one sentence each
        description = tool.description or ""
        assert description.endswith(".") and ". " not in description, tool.name
        assert description[0].isupper(), tool.name
    assert set(READS) | set(WRITES) | {"report", "identify"} == set(SPEC_TOOLS)
    dcf = next(t.description or "" for t in tools if t.name == "dcf")  # FMP's figure (plan 3)
    assert (
        "read only where neither the route nor the review values the company, as a cross-check on"
        " the secondary valuation"
    ) in dcf


def test_inbox_post_says_what_the_note_holds(api: FairbandClient) -> None:
    """Spec 2026-11-06 Tier 2, 8 (plan 4): the note is the request in the requester's own words."""
    server = build_server(api)

    async def listed() -> list[Any]:
        async with Client(server) as session:
            return (await session.list_tools()).tools

    tools = anyio.run(listed)
    post = next(t.description or "" for t in tools if t.name == "inbox_post")
    assert "its note the request in the requester's own words on one line" in post


def test_derive_names_the_fixed_number(api: FairbandClient) -> None:
    """Spec 2026-11-15 7.1: one operand of a derivation may be a fixed number of the server's
    list; the tool's description names the form."""

    async def listed() -> list[Any]:
        async with Client(build_server(api)) as session:
            return (await session.list_tools()).tools

    derive = next(t.description or "" for t in anyio.run(listed) if t.name == "derive")
    assert "one operand of each may be a fixed number of the server's list written number:<n>" in (
        derive
    )


def test_financial_tables_names_its_columns(api: FairbandClient) -> None:
    """Spec 2026-11-15 6.4, 6.5: the tables carry their columns past the fiscal years, and the
    quarters table stands beside the six; the tool's description says so."""
    server = build_server(api)

    async def listed() -> list[Any]:
        async with Client(server) as session:
            return (await session.list_tools()).tools

    tools = anyio.run(listed)
    tables = next(t.description or "" for t in tools if t.name == "financial_tables")
    assert tables == (
        "The six tables of a report's section 4, with their columns (the five fiscal years, the"
        " trailing twelve months and the consensus years where a table has them), and the"
        " quarters table of section 5 (the newest eight stored periods), each cell with its ref"
        " to cite."
    )


def test_company_names_the_currency_the_rate_and_the_share_basis(api: FairbandClient) -> None:
    """Spec 2026-11-10 7.4: the ``company`` read (web and MCP) carries the reporting currency, the
    ADR flag and ratio, and the rate with its date; the tool's description says so, the ratio as
    found between FMP's two share counts (spec 2026-11-19 6.2)."""
    server = build_server(api)

    async def listed() -> list[Any]:
        async with Client(server) as session:
            return (await session.list_tools()).tools

    tools = anyio.run(listed)
    company = next(t.description or "" for t in tools if t.name == "company")
    for words in (
        "the reporting currency (`currency`)",
        "the ADR flag (`isAdr`)",
        (
            "the whole number Fairband found between FMP's stored share count and the quote's"
            " (`adrRatio`, null where the counts agree)"
        ),
        "the exchange rate and its date (`fxRate`, `fxDate`)",
    ):
        assert words in company, words


def test_company_names_the_currency_of_a_row_refused_for_it(
    api: FairbandClient, db_path: Path, policy: Policy
) -> None:
    """Fix round 1 of task 6: the ``company`` tool answers what the web read does for ARSX, an ADR
    refused for ARS's expected inflation: ARS, with no rate and no rate date."""
    with closing(connect(db_path)) as conn:
        refused = value_company(ars_refused_inputs(), universe_deciles(), policy, WEB_TODAY)
        insert_snapshot(conn, refused, 1)
    [answer] = _session(build_server(api), ("company", {"symbol": "ARSX"}))
    assert (answer["currency"], answer["adrRatio"], answer["fxRate"], answer["fxDate"]) == (
        "ARS",
        2.0,
        None,
        None,
    )


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
    # the list's own fields: the report's revision (18.5, plan 4), who declined the item (spec
    # 2026-11-25 owner's inbox, 7.2), the open item's newest launch and whether launching is set
    # up (B-210)
    listed = posted | {"reportRevision": None, "declinedBy": None, "launch": None}
    assert every == client.get("/api/inbox").json() == {"launchReady": False, "items": [listed]}
    assert pending == every and done == {"launchReady": False, "items": []}


def test_every_read_tool_reads_its_route(api: FairbandClient, client: TestClient) -> None:
    server = build_server(api)
    answers = _session(server, *[(name, arguments) for name, (arguments, _) in READS.items()])
    for (name, (_, url)), answer in zip(READS.items(), answers, strict=True):
        # the header the client sends on every call, which the reads that may call a vendor need
        expected = client.get(url, headers=HEADER)
        if name == "watchlists":  # the route answers a list; a tool answers an object
            assert answer == {"watchlists": expected.json()}
        elif expected.is_success:
            assert answer == expected.json(), name
        else:
            refusal = {"refused": expected.json()["detail"], "status": expected.status_code}
            assert answer == refusal, name
    # the six pass-throughs and the three filing reads reach their routes, which have no FMP key
    # here
    vendor = answers[-9:]
    assert vendor == [{"refused": "no FMP key", "status": 503}] * 9


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
    # the guidance record's as_of sent as the API reads it, its midpoint the server's
    guided = written["guidance_add"]
    assert (guided["asOf"], guided["step"]) == ("2026-10-28", None)
    assert guided["midpoint"] == pytest.approx(6.45)
    assert guided["actor"] == "claude-opus-5-5"


def test_moat_set_and_company_say_what_the_verdict_is(api: FairbandClient) -> None:
    """Spec 2026-11-19 8.6: ``moat_set`` records the agent's verdict, also where it agrees, and
    values the company again; ``company`` names the row of the moat table it answers."""

    async def listed() -> list[Any]:
        async with Client(build_server(api)) as session:
            return (await session.list_tools()).tools

    described = {t.name: t.description or "" for t in anyio.run(listed)}
    assert described["moat_set"] == (
        "Record your verdict on the company's moat class, Wide, Narrow or None, with your reason"
        " and evidence, also when you agree with the class in force; the company is valued again"
        " at once."
    )
    assert "(`moatClass`)" in described["company"]


def test_moat_set_puts_the_verdict(api: FairbandClient, client: TestClient) -> None:
    """Spec 2026-11-19 8.6: ``moat_set`` is one ``PUT`` to the company's moat route as the agent,
    its class sent as ``class`` beside the reason and the evidence; a dotted symbol reaches its own
    route (Review Focus 1); a class outside the three is a tool error, and nothing is sent, as the
    tool list says. On the app the row becomes the agent's, the class before it kept as
    ``previous``, and the company is valued again at once: the answer's snapshot is the one
    ``company`` then reads, with the row as ``moatClass``. A blank reason is the route's 400."""
    verdict = {
        "moat_class": "Narrow",
        "reason": "rivals sell close substitutes",
        "evidence": [FILING],
    }
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    async def medium(server: MCPServer) -> Any:
        """A class outside the three, which the tool's argument does not take."""
        async with Client(server, client_info=PROBE) as session:
            await session.call_tool("identify", AGENT)
            return await session.call_tool(
                "moat_set", {"symbol": "BF.B"} | verdict | {"moat_class": "Medium"}
            )

    with httpx.Client(transport=httpx.MockTransport(answer), base_url=HOST) as http:
        server = build_server(FairbandClient(http))
        _session(server, ("identify", AGENT), ("moat_set", {"symbol": "bf.b"} | verdict))
        assert anyio.run(medium, server).is_error  # a tool error, and no call
    [put] = requests
    assert (put.method, put.url.path) == ("PUT", "/api/companies/BF.B/moat")
    assert json.loads(put.content) == {
        "class": "Narrow",
        "reason": "rivals sell close substitutes",
        "evidence": [FILING],
    }
    assert (put.headers[PRINCIPAL_HEADER], put.headers[ACTOR_HEADER]) == (
        "agent",
        "claude-opus-5-5",
    )
    before = client.get("/api/companies/AAPL").json()["snapshot"]["id"]
    _, written, read, blank = _session(
        build_server(api),
        ("identify", AGENT),
        ("moat_set", {"symbol": "aapl"} | verdict),
        ("company", {"symbol": "AAPL"}),
        ("moat_set", {"symbol": "AAPL"} | verdict | {"reason": " "}),
    )
    row = written["moatClass"]
    assert (row["class"], row["source"], row["previous"], row["actor"], row["reason"]) == (
        "Narrow",
        "agent",
        "Wide",
        "claude-opus-5-5",
        "rivals sell close substitutes",
    )
    assert written["snapshot"]["id"] == read["snapshot"]["id"] > before
    assert read["moatClass"] == row and read["moat"] == "Narrow"
    assert blank == {"refused": "a moat verdict needs a reason", "status": 400}


def test_a_finding_and_a_guidance_record_send_their_currency(api: FairbandClient) -> None:
    """Spec 2026-11-15 9.1: `finding_add` and `guidance_add` send the currency the company states
    a money figure in; with none, AAPL's answers its reporting currency, USD."""
    server = build_server(api)
    finding = WRITES["finding_add"]
    guided = WRITES["guidance_add"]
    _, *answers = _session(
        server,
        ("identify", AGENT),
        ("finding_add", finding | {"currency": "TWD"}),
        ("finding_add", finding),
        ("guidance_add", guided | {"currency": "TWD"}),
        ("guidance_add", guided | {"period": "2027"}),
    )
    assert [a["currency"] for a in answers] == ["TWD", "USD", "TWD", "USD"]


def test_a_kill_criterion_sends_its_threshold(api: FairbandClient) -> None:
    """Spec 2026-11-15 8.1: `kill_criterion_add` sends a threshold, its unit and a currency, and
    answers them; `kill_criteria` lists them; with none the criterion is words alone. With no
    currency named, AAPL's money threshold answers its reporting currency, USD."""
    server = build_server(api)
    criterion = WRITES["kill_criterion_add"]
    _, *answers, listed = _session(
        server,
        ("identify", AGENT),
        ("kill_criterion_add", criterion | {"threshold": 0.05, "unit": "percent"}),
        ("kill_criterion_add", criterion | {"threshold": 50e9, "unit": "currency"}),
        (
            "kill_criterion_add",
            criterion | {"threshold": 1.5, "unit": "per-share", "currency": "TWD"},
        ),
        ("kill_criterion_add", criterion),
        ("kill_criteria", {"symbol": "AAPL"}),
    )
    assert [(a["threshold"], a["unit"], a["currency"]) for a in answers] == [
        (0.05, "percent", None),
        (50e9, "currency", "USD"),
        (1.5, "per-share", "TWD"),
        (None, None, None),
    ]
    assert listed == {"killCriteria": answers[::-1]}


def _store_revenue(db_path: Path, revenue: float, symbol: str = "AAPL") -> None:
    """The company's fiscal 2025 revenue, its trailing revenue with no quarters on file."""
    with closing(connect(db_path)) as conn:
        response = record_response(
            conn, "fmp", "income-statement", {"symbol": symbol}, symbol, 200, "[]", None, CREATED
        )
        fact = FactRow(
            symbol=symbol,
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
    """The drivers' keys as spec 11 names them, sent as the API reads them; one form only. AAL's
    route refuses and no review values it, so it takes the fallback; AAPL's values, so the route's
    refusal comes back (plan 3), as the tool's description says."""
    _store_revenue(db_path, 22e9, "AAL")
    drivers = {
        "years": 3,
        "revenue_growth": [0.10, 0.08, 0.05],
        "operating_margin": [0.20, 0.20, 0.20],
        "tax_rate": 0.25,
        "sales_to_capital": 2.0,
        "terminal_growth": 0.02,
    }
    common = {"symbol": "AAL", "reason": "the cycle turns", "evidence": [FILING]}
    parts = WRITES["secondary_valuation"]["parts"]
    server = build_server(api)
    valued, both, neither, on_a_value = _session(
        server,
        ("identify", AGENT),
        ("secondary_valuation", common | {"drivers": drivers}),
        ("secondary_valuation", common | {"drivers": drivers, "parts": parts}),
        ("secondary_valuation", common),
        ("secondary_valuation", common | {"symbol": "AAPL", "drivers": drivers}),
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
    fallback = "the secondary valuation is the fallback where it refuses"
    assert on_a_value == {"refused": f"the route values AAPL: {fallback}", "status": 400}

    async def described() -> str:
        async with Client(server) as session:
            tools = (await session.list_tools()).tools
        return next(t.description or "" for t in tools if t.name == "secondary_valuation")

    assert anyio.run(described).startswith(
        "Value the company a second way by a standard discounted cash flow where neither the route"
        " nor the review values it; refused where either does;"
    )


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
    # Review again posts to the company's review route: the API's sentence for one that holds none
    assert _call(server, "review_again", WRITES["review_again"]) == {
        "refused": "no review for AAPL",
        "status": 404,
    }


@pytest.mark.usefixtures("secondaries", "verdicts")  # a report needs both on its snapshot
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
    submitted = _call(server, "report_submit", submission)
    report = _call(server, "report", {"symbol": "AAPL"})  # the latest, whole
    # the submit answers the report's id, symbol, time and work item, not the whole report
    assert submitted == {
        "report": {key: report[key] for key in ("id", "symbol", "createdAt", "workItemId")}
    }
    assert report["sections"] == sections
    assert (report["workItemId"], report["actor"], report["client"]) == (
        item["id"],
        "claude-opus-5-5",
        "probe/0",
    )
    assert [j["judgment"] for j in report["judgments"]] == ["phase", "moat", "belief", "roic"]
    assert _call(server, "report", {"symbol": "AAPL", "id": report["id"]}) == report
    done = _call(server, "inbox_list", {"state": "done"})["items"]
    assert [(i["id"], i["reportId"]) for i in done] == [(item["id"], report["id"])]
    news = _call(server, "news_items", {"symbol": "AAPL"})["newsItems"]
    assert [(n["headline"], n["killCriterionId"], n["reportId"]) for n in news] == [
        ("A recall", criterion["id"], report["id"])
    ]
    texts = [k["text"] for k in _call(server, "kill_criteria", {"symbol": "AAPL"})["killCriteria"]]
    assert sorted(texts) == ["A second product recall.", "The services margin falls."]


class _Canned:
    """A client whose every read answers ``answer``, for a tool that reshapes the API's answer."""

    identified = True

    def __init__(self, answer: dict[str, Any]) -> None:
        self.answer = answer

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.answer


def _daily(name: str, days: list[str]) -> dict[str, Any]:
    """A P/E series as the web read answers one, a point a day."""
    return {
        "points": [
            {"day": day, "value": 20.0 + i, "ref": f"multiple:AAPL/{name}/{day}"}
            for i, day in enumerate(days)
        ],
        "stats": {
            "avg10y": {"value": 22.0, "unit": "multiple", "ref": f"multiple:AAPL/{name}/avg_10y"}
        },
        "since": "2016-10-30",
        "responseId": 7,
        "note": None,
    }


def test_multiples_history_answers_the_last_point_of_each_month_unless_daily() -> None:
    """The web read answers every daily point, about 2,500 over ten years, which overflows the
    host's result; the tool keeps the last point of each month, the statistics and the rest of each
    series as they are; ``daily`` keeps every point; a series the read could not serve stays."""
    days = ["2026-08-31", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-30"]
    canned = {
        "symbol": "AAPL",
        "pe": _daily("pe", days),
        "peNote": None,
        "peForward": _daily("pe_forward", days[1:]),
    }
    server = build_server(_Canned(canned))  # type: ignore[arg-type]
    monthly = _call(server, "multiples_history", {"symbol": "AAPL"})
    assert [p["day"] for p in monthly["pe"]["points"]] == ["2026-08-31", "2026-09-30", "2026-10-30"]
    assert [p["day"] for p in monthly["peForward"]["points"]] == ["2026-09-30", "2026-10-30"]
    assert monthly["pe"]["points"][1] == canned["pe"]["points"][3]  # the point as the read gave it
    rest = {k: v for k, v in monthly["pe"].items() if k != "points"}
    assert rest == {k: v for k, v in canned["pe"].items() if k != "points"}
    assert monthly["symbol"] == "AAPL" and monthly["peNote"] is None
    assert _call(server, "multiples_history", {"symbol": "AAPL", "daily": True}) == canned
    unserved = canned | {"pe": None, "peNote": "no FMP key"}
    server = build_server(_Canned(unserved))  # type: ignore[arg-type]
    answered = _call(server, "multiples_history", {"symbol": "AAPL"})
    assert (answered["pe"], answered["peNote"]) == (None, "no FMP key")


@pytest.mark.usefixtures("secondaries", "verdicts")
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
    assert listed["sections"][4] == {"id": "foreign-filers", "title": "Foreign filers"}
    assert listed["sections"][5] == {"id": "mature-growth", "title": "Mature Growth"}
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
            ("filings", {"symbol": ".."}),
            ("filing_report", {"symbol": ".."}),
            ("filing_search", {"symbol": "..", "year": 2027, "period": "Q1", "text": "leases"}),
            ("identify", AGENT),
            ("note_add", {"symbol": "..", "text": "a note"}),
        )
    refused = {"refused": BAD_SYMBOL}
    assert BAD_SYMBOL == "a symbol is letters, digits, dots and dashes"
    assert answers[: len(symbols) + 6] == [refused] * (len(symbols) + 6)
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


def _sent(*calls: tuple[str, dict[str, Any]]) -> list[tuple[str, dict[str, str]]]:
    """The path and the query parameters of each request the calls send, in one session against
    a web server that answers every read with ``{}``."""
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(answer), base_url=HOST) as http:
        _session(build_server(FairbandClient(http)), *calls)
    return [(request.url.path, dict(request.url.params)) for request in requests]


def test_the_filing_tools_send_the_route_s_parameters() -> None:
    """Spec 2026-11-11, 6: each filing tool is one call to its route, its arguments sent by the
    route's names (``from_date`` as ``from``, ``to_date`` as ``to``, ``from_row`` as ``fromRow``);
    a sheet's name goes as it is, a slash and spaces in it, as the ``sheet`` parameter; an
    argument left out is not sent."""
    sheet = "Revenue by Product/Region"
    sent = _sent(
        ("filings", READS["filings"][0]),
        ("filings", {"symbol": "aapl", "to_date": "2026-11-11"}),
        ("filing_report", READS["filing_report"][0]),
        ("filing_report", {"symbol": "AAPL", "year": 2027, "period": "Q1"}),
        (
            "filing_report",
            {"symbol": "AAPL", "year": 2027, "period": "Q1", "sheet": sheet, "row": 2, "col": 0},
        ),
        ("filing_report", {"symbol": "AAPL", "year": 2027, "period": "Q1", "sheet": sheet}),
        (
            "filing_report",
            {"symbol": "AAPL", "year": 2027, "period": "FY", "sheet": sheet, "row": 1, "offset": 9},
        ),
        ("filing_search", READS["filing_search"][0]),
    )
    filings = "/api/companies/AAPL/filings"
    report = "/api/companies/AAPL/filing-report"
    assert sent == [
        (
            filings,
            {"forms": "10-K,10-Q", "from": "2026-01-01", "to": "2026-11-11", "fromRow": "50"},
        ),
        (filings, {"to": "2026-11-11"}),
        (report, {"year": "2027", "period": "Q1", "sheet": sheet, "fromRow": "100"}),
        (report, {"year": "2027", "period": "Q1"}),
        (report, {"year": "2027", "period": "Q1", "sheet": sheet, "row": "2", "col": "0"}),
        (report, {"year": "2027", "period": "Q1", "sheet": sheet}),
        (report, {"year": "2027", "period": "FY", "sheet": sheet, "row": "1", "offset": "9"}),
        (
            "/api/companies/AAPL/filing-report/search",
            {"year": "2027", "period": "Q1", "text": "not yet commenced"},
        ),
    ]


def test_insider_trades_asks_for_25_trades_unless_told() -> None:
    """FMP's page of 100 trades overflows the host's result (49.5k characters for one company):
    the tool asks the route for the newest 25, or for ``limit`` of them."""
    sent = _sent(
        ("insider_trades", {"symbol": "amd"}),
        ("insider_trades", {"symbol": "AMD", "limit": 100}),
    )
    trades = "/api/vendor/insider-trades/AMD"
    assert sent == [(trades, {"limit": "25"}), (trades, {"limit": "100"})]


def test_filing_report_with_a_symbol_alone_sends_no_parameter() -> None:
    """The reports on file (spec 2026-11-11, 5.2, view 1): neither year nor period, nor any other
    parameter, goes with the call."""
    sent = _sent(("filing_report", {"symbol": "msft"}), ("filings", {"symbol": "msft"}))
    assert sent == [
        ("/api/companies/MSFT/filing-report", {}),
        ("/api/companies/MSFT/filings", {}),
    ]


def test_the_filing_tools_say_how_a_cell_is_cited(api: FairbandClient) -> None:
    """Spec 2026-11-11, 5.5 and 6: the tools that answer a filing report's rows say how a cell of
    one is cited."""

    async def listed() -> list[Any]:
        async with Client(build_server(api)) as session:
            return (await session.list_tools()).tools

    described = {tool.name: tool.description or "" for tool in anyio.run(listed)}
    for name in ("filing_report", "filing_search"):
        # copied from the answer, never built by hand: a sheet's slash is ~1 inside the ref
        assert "cite a cell as its row's rowRef plus /<col>" in described[name], name
        assert "never built by hand" in described[name], name
        assert len(described[name]) <= 250, name


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
