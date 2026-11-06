"""The MCP server's tools (spec 2026-11-06 Tier 2, 6, 7 and 15) on the web tests' app, called the
way a host calls them: through the SDK's in-process client (``mcp.Client`` on the server), which
runs the handshake with the client's name and version. Every tool of spec 15 is registered with a
one-sentence description; each reads or writes its route; a write before ``identify`` is refused
without a call; a refusal is the API's sentence and a server that does not answer is one
sentence."""

from typing import Any

import anyio
import httpx
from fastapi.testclient import TestClient
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import Implementation
from support.web import HEADER, HOST

from fairband.mcp.client import NOT_RUNNING, FairbandClient
from fairband.mcp.server import TOOL_NAMES, build_server
from fairband.reports.check import headings
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
JUDGMENTS = [
    {"judgment": kind, "bull": f"bull on {kind}", "bear": f"bear on {kind}", "decision": "keep"}
    for kind in ("phase", "moat", "belief", "roic")
]
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


def test_a_symbol_reaches_no_other_route(api: FairbandClient) -> None:
    server = build_server(api)
    answer = _call(server, "company", {"symbol": "AAPL/../../policy"})
    assert "values" not in answer and answer["status"] == 404


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
