"""The MCP server (spec 2026-11-06 Tier 2, 6, 7 and 15): ``fairband mcp``, a stdio process the
agent host starts. It holds no database connection and no key: every tool is one or two calls to
the web API (``FairbandClient``), tools only, no resources or prompts. The tools are spec 15's,
in its order (``TOOL_NAMES``), each with a one-sentence description and the arguments the spec
names.

A tool answers the API's JSON, an object; ``watchlists``, whose route answers a list, answers it as
``{"watchlists": [...]}``. A refusal is ``{"refused": <the API's sentence>, "status":
<code>}`` with the rest of the API's answer beside it: a refused override's record, a rejected
report's findings. A server that does not answer is ``{"refused": <the client's sentence>}``,
``NOT_RUNNING``, or ``NO_ANSWER`` when the call reached it and timed out.

``identify(agent)`` keeps the model identifier the agent runs as for the MCP process, with the
client's name and version from the handshake (``clientInfo``), and every later call carries them
(``fairband.web.identity``); a write tool called before it answers ``{"refused": IDENTIFY_FIRST}``
and calls nothing. An identifier that is not printable ASCII answers ``{"refused": NOT_ASCII}``
and leaves the identity as it was; a client name or version that is not leaves the client out.
The reads and the vendor pass-throughs need no identity.

Spec 15 names the arguments; a record inside one (a part, an evidence item, a section's cite, a
judgment, a news item) may name its keys as the spec does (``terminal_growth``,
``kill_criterion_id``) or as the API does (``terminalGrowth``): each key is sent camelCase, as the
API reads them. A symbol in a path is upper-cased and must be letters, digits, dots and dashes
with a letter or a digit among them, else the tool answers ``{"refused": BAD_SYMBOL}`` and calls
nothing: a slash or a dot segment (``..``) would reach another route. A section is sent escaped,
as one path segment. ``report`` without an id reads the company's latest report: its revisions
newest first, then the first whole; with none, ``{"refused": "no report for <symbol>", "status":
404}``. ``methodology`` without a section lists the page's sections (``GET /api/methodology``).

The command's ``httpx.Client`` (``loopback``) reads no proxy or other setting from the
environment, so a proxy variable never takes a call meant for the loopback.
"""

import re
from collections.abc import Callable
from typing import Any, Literal
from urllib.parse import quote

import httpx
from mcp.server.mcpserver import Context, MCPServer
from pydantic.alias_generators import to_camel

from fairband import __version__
from fairband.engine.overrides import Lifetime
from fairband.mcp.client import TIMEOUT_S, FairbandClient, Refused, ServerDown
from fairband.refresh.run import Kind
from fairband.store.inbox import Mode, State
from fairband.store.research import CriterionState, Unit
from fairband.web.identity import IDENTIFY_FIRST

BAD_SYMBOL = "a symbol is letters, digits, dots and dashes"
# A letter or a digit among them, so no symbol is a dot segment ("." or "..").
_SYMBOL = re.compile(r"[A-Z0-9.\-]*[A-Z0-9][A-Z0-9.\-]*")
INSTRUCTIONS = (
    "Call identify with the model identifier you run as before any write; every write is recorded"
    " under it."
)
TOOL_NAMES: tuple[str, ...] = (
    # 15.2, the reads
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
    # 15.3, the vendor pass-throughs
    "transcript",
    "news",
    "segments",
    "insider_trades",
    # 15.4, the writes
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


def main(port: int) -> None:
    """Serve the tools over stdio against the web server on 127.0.0.1:``port`` until the host
    closes the pipe."""
    with loopback(port) as http:
        build_server(FairbandClient(http)).run("stdio")


def loopback(port: int) -> httpx.Client:
    """The client of the web server on 127.0.0.1:``port``: no proxy or other setting from the
    environment, and ``TIMEOUT_S``."""
    return httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=TIMEOUT_S, trust_env=False)


class _Unsent(Exception):
    """A call refused before it is sent: its sentence."""


def build_server(client: FairbandClient) -> MCPServer:
    """The server with spec 15's tools, each a call through ``client``."""
    server = MCPServer("fairband", version=__version__, instructions=INSTRUCTIONS)

    def answer(call: Callable[[], Any]) -> dict[str, Any]:
        """The call's JSON, or its refusal (module docstring)."""
        try:
            answered: dict[str, Any] = call()
        except Refused as exc:
            return {"refused": exc.detail, "status": exc.status, **exc.extra}
        except (ServerDown, _Unsent) as exc:
            return {"refused": str(exc)}
        return answered

    def write(call: Callable[[], Any]) -> dict[str, Any]:
        """The write's answer; refused, with no call, before ``identify``."""
        if not client.identified:
            return {"refused": IDENTIFY_FIRST}
        return answer(call)

    # 15.2, the reads

    @server.tool(description="The screen's rows, one a company, sorted by a column key.")
    def screen(
        sort: str | None = None, direction: Literal["asc", "desc"] | None = None
    ) -> dict[str, Any]:
        return answer(lambda: client.get("/api/screen", {"sort": sort, "dir": direction}))

    @server.tool(
        description="The company's latest snapshot in full: value, levels, inputs, intermediates,"
        " phase and flags."
    )
    def company(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol)))

    @server.tool(
        description="The company's fiscal years, trailing figures and balance years from the"
        " stored statements, each figure with its ref."
    )
    def financials(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "financials")))

    @server.tool(
        description="The six five-year tables of a report's section 4, each cell with its ref to"
        " cite."
    )
    def financial_tables(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "financial-tables")))

    @server.tool(
        description="The stored analyst consensus by quarter and fiscal year, each figure with its"
        " ref."
    )
    def estimates(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "estimates")))

    @server.tool(
        description="The stored closing prices, oldest first, each with its ref; years keeps the"
        " latest years only."
    )
    def price_history(symbol: str, years: int | None = None) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "price-history"), {"years": years}))

    @server.tool(
        description="The company's mature peers with their figures and their source, each figure"
        " with its ref."
    )
    def peers(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "peers")))

    @server.tool(description="The watchlists with their companies.")
    def watchlists() -> dict[str, Any]:
        return answer(lambda: {"watchlists": client.get("/api/watchlists")})

    @server.tool(
        description="The work items, newest first, or those in one state: pending, claimed, done,"
        " declined or dropped."
    )
    def inbox_list(state: State | None = None) -> dict[str, Any]:
        return answer(lambda: client.get("/api/inbox", {"state": state}))

    @server.tool(description="The company's published reports, newest first, without their text.")
    def reports(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "reports")))

    @server.tool(description="One published report whole, by id, or the company's latest.")
    def report(symbol: str, id: int | None = None) -> dict[str, Any]:
        def read() -> Any:
            if id is not None:
                return client.get(f"/api/reports/{id}")
            listed = client.get(_company(symbol, "reports"))["reports"]
            if not listed:
                raise Refused(404, f"no report for {_symbol(symbol)}")
            return client.get(f"/api/reports/{listed[0]['id']}")

        return answer(read)

    @server.tool(description="The company's notes, newest first.")
    def notes(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "notes")))

    @server.tool(description="The company's findings with their sources.")
    def findings(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "findings")))

    @server.tool(description="The company's overrides, newest first, each with its state.")
    def overrides(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "overrides")))

    @server.tool(description="The company's reviews, newest first, each with its bridge.")
    def reviews(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "reviews")))

    @server.tool(description="The company's secondary valuations, newest first.")
    def secondary(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "secondary")))

    @server.tool(description="The company's kill criteria, each with its state.")
    def kill_criteria(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "kill-criteria")))

    @server.tool(description="The company's news items.")
    def news_items(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_company(symbol, "news-items")))

    @server.tool(
        description="The ledger's newest rows, for one company or all: every write, who made it"
        " and what it rests on."
    )
    def ledger(symbol: str | None = None, limit: int | None = None) -> dict[str, Any]:
        return answer(lambda: client.get("/api/ledger", {"symbol": symbol, "limit": limit}))

    @server.tool(description="The review log, newest first, for one company or all.")
    def review_log(symbol: str | None = None) -> dict[str, Any]:
        return answer(lambda: client.get("/api/review-log", {"symbol": symbol}))

    @server.tool(
        description="The policy values in force, the user's settings over the file's, each with"
        " its source."
    )
    def policy() -> dict[str, Any]:
        return answer(lambda: client.get("/api/policy"))

    @server.tool(
        description="A section of the Methodology page in plain words with the live values, or"
        " the list of sections."
    )
    def methodology(section: str | None = None) -> dict[str, Any]:
        path = "/api/methodology" if section is None else f"/api/methodology/{_segment(section)}"
        return answer(lambda: client.get(path))

    @server.tool(
        description="The running refresh's progress, or the last refresh's record when none runs."
    )
    def refresh_status() -> dict[str, Any]:
        return answer(lambda: client.get("/api/refresh/current"))

    # 15.3, the vendor pass-throughs: fetched by the server, stored so a report can cite them

    @server.tool(
        description="The earnings call transcript of a fiscal quarter from FMP, stored so a report"
        " can cite it."
    )
    def transcript(symbol: str, year: int, quarter: int) -> dict[str, Any]:
        params = {"year": year, "quarter": quarter}
        return answer(lambda: client.get(_vendor("transcript", symbol), params))

    @server.tool(
        description="Recent stock news from FMP, 20 items or limit up to 100, stored so a report"
        " can cite it."
    )
    def news(symbol: str, limit: int | None = None) -> dict[str, Any]:
        return answer(lambda: client.get(_vendor("news", symbol), {"limit": limit}))

    @server.tool(
        description="Revenue by product and by region from FMP, stored so a report can cite it."
    )
    def segments(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_vendor("segments", symbol)))

    @server.tool(description="Insider trades from FMP, stored so a report can cite them.")
    def insider_trades(symbol: str) -> dict[str, Any]:
        return answer(lambda: client.get(_vendor("insider-trades", symbol)))

    # 15.4, the writes

    @server.tool(
        description="Name the model identifier you run as, such as claude-opus-5-5; every write"
        " after it is recorded under it."
    )
    def identify(agent: str, ctx: Context) -> dict[str, Any]:
        name, version = _client_info(ctx)
        try:
            client.identify(agent, name, version)
        except ValueError as exc:
            return {"refused": str(exc)}
        return {"agent": agent, "client": client.client}

    @server.tool(
        description="Post a work item for a company, its mode valuation review or full report."
    )
    def inbox_post(symbol: str, mode: Mode, note: str = "") -> dict[str, Any]:
        body = {"symbol": symbol, "mode": mode, "note": note}
        return write(lambda: client.post("/api/inbox", body))

    @server.tool(description="Claim the work item named, or the oldest pending one.")
    def inbox_claim(item_id: int | None = None) -> dict[str, Any]:
        return write(lambda: client.post("/api/inbox/claim", {"itemId": item_id}))

    @server.tool(description="Complete a work item with the published report that answers it.")
    def inbox_complete(item_id: int, report_id: int) -> dict[str, Any]:
        body = {"action": "complete", "reportId": report_id}
        return write(lambda: client.patch(f"/api/inbox/{item_id}", body))

    @server.tool(description="Decline a work item, with the reason.")
    def inbox_decline(item_id: int, reason: str) -> dict[str, Any]:
        body = {"action": "decline", "reason": reason}
        return write(lambda: client.patch(f"/api/inbox/{item_id}", body))

    @server.tool(description="Add a note to the company, tied to an override when one is named.")
    def note_add(symbol: str, text: str, override_id: int | None = None) -> dict[str, Any]:
        body = {"text": text, "overrideId": override_id}
        return write(lambda: client.post(_company(symbol, "notes"), body))

    @server.tool(
        description="Record a figure or a fact from outside Fairband with its source {kind, ref,"
        " note}, so a report can cite it."
    )
    def finding_add(
        symbol: str,
        as_of: str,
        text: str,
        source: dict[str, Any],
        value: float | None = None,
        unit: Unit | None = None,
        period: str | None = None,
    ) -> dict[str, Any]:
        body = {
            "asOf": as_of,
            "text": text,
            "source": _camel(source),
            "value": value,
            "unit": unit,
            "period": period,
        }
        return write(lambda: client.post(_company(symbol, "findings"), body))

    @server.tool(
        description="Override one input with a reason and evidence [{kind, ref, note}]; answers"
        " its state and, when applied, the review with its bridge."
    )
    def override_add(
        symbol: str,
        tag: str,
        new: float | str,
        reason: str,
        evidence: list[dict[str, Any]],
        lifetime: Lifetime,
        period: str | None = None,
    ) -> dict[str, Any]:
        body = {
            "tag": tag,
            "new": new,
            "reason": reason,
            "evidence": _camel(evidence),
            "lifetime": lifetime,
            "period": period,
        }
        return write(lambda: client.post(_company(symbol, "overrides"), body))

    @server.tool(
        description="Drop an applied override, with the reason; the review is recomputed over the"
        " rest."
    )
    def override_drop(override_id: int, reason: str) -> dict[str, Any]:
        return write(lambda: client.delete(f"/api/overrides/{override_id}", {"reason": reason}))

    @server.tool(
        description="Value the company a second way from your cash-flow path, parts [{name, fcff,"
        " terminal_growth, note}], with a reason and evidence."
    )
    def secondary_valuation(
        symbol: str,
        parts: list[dict[str, Any]],
        reason: str,
        evidence: list[dict[str, Any]],
        debt: float | None = None,
        cash: float | None = None,
    ) -> dict[str, Any]:
        body = {
            "parts": _camel(parts),
            "reason": reason,
            "evidence": _camel(evidence),
            "debt": debt,
            "cash": cash,
        }
        return write(lambda: client.post(_company(symbol, "secondary"), body))

    @server.tool(
        description="Compute figures from refs, [{operation, a, b, years}], each stored to cite as"
        " derived:<id>."
    )
    def derive(symbol: str, derivations: list[dict[str, Any]]) -> dict[str, Any]:
        body = {"derivations": _camel(derivations)}
        return write(lambda: client.post(_company(symbol, "derivations"), body))

    @server.tool(
        description="Submit a report with every quantity cited: published whole, or rejected whole"
        " with each finding to fix."
    )
    def report_submit(
        symbol: str,
        mode: Mode,
        stance: str,
        sections: list[dict[str, Any]],
        judgments: list[dict[str, Any]],
        kill_criteria: list[dict[str, Any]] | None = None,
        news_items: list[dict[str, Any]] | None = None,
        work_item_id: int | None = None,
    ) -> dict[str, Any]:
        body = {
            "mode": mode,
            "stance": stance,
            "sections": _camel(sections),
            "judgments": _camel(judgments),
            "killCriteria": _camel(kill_criteria or []),
            "newsItems": _camel(news_items or []),
            "workItemId": work_item_id,
        }
        return write(lambda: client.post(_company(symbol, "reports"), body))

    @server.tool(description="Add a kill criterion to the company.")
    def kill_criterion_add(symbol: str, text: str) -> dict[str, Any]:
        return write(lambda: client.post(_company(symbol, "kill-criteria"), {"text": text}))

    @server.tool(
        description="Move a kill criterion to open, triggered or retired, with the reason."
    )
    def kill_criterion_set(id: int, state: CriterionState, reason: str) -> dict[str, Any]:
        body = {"state": state, "reason": reason}
        return write(lambda: client.patch(f"/api/kill-criteria/{id}", body))

    @server.tool(
        description="Record a news item for the company, tied to a kill criterion when one is"
        " named."
    )
    def news_item_add(
        symbol: str,
        date: str,
        headline: str,
        source: str,
        text: str,
        kill_criterion_id: int | None = None,
    ) -> dict[str, Any]:
        body = {
            "date": date,
            "headline": headline,
            "source": source,
            "text": text,
            "killCriterionId": kill_criterion_id,
        }
        return write(lambda: client.post(_company(symbol, "news-items"), body))

    @server.tool(
        description="Start a refresh on the server: full, price, scoped with symbols, or revalue."
    )
    def refresh_start(kind: Kind, symbols: list[str] | None = None) -> dict[str, Any]:
        body = {"kind": kind, "symbols": symbols}
        return write(lambda: client.post("/api/refresh", body))

    @server.tool(description="Ask the running refresh to stop after the companies in flight.")
    def refresh_cancel() -> dict[str, Any]:
        return write(lambda: client.post("/api/refresh/cancel", {}))

    return server


def _client_info(ctx: Context) -> tuple[str | None, str | None]:
    """The client's name and version from the handshake; ``None`` each without them."""
    try:
        params = ctx.request_context.session.client_params
    except ValueError:  # a call made in process, outside a request
        return None, None
    if params is None:
        return None, None
    return params.client_info.name, params.client_info.version


def _segment(text: str) -> str:
    """``text`` as one path segment: a slash, a query or a fragment in it is sent escaped."""
    return quote(text, safe="")


def _symbol(text: str) -> str:
    """``text`` upper-cased as a symbol; ``_Unsent(BAD_SYMBOL)`` outside the symbol characters
    (module docstring)."""
    symbol = text.upper()
    if not _SYMBOL.fullmatch(symbol):
        raise _Unsent(BAD_SYMBOL)
    return symbol


def _company(symbol: str, read: str = "") -> str:
    """The company's route, or the route of one of its records."""
    return f"/api/companies/{_symbol(symbol)}" + (f"/{read}" if read else "")


def _vendor(kind: str, symbol: str) -> str:
    return f"/api/vendor/{kind}/{_symbol(symbol)}"


def _camel(value: Any) -> Any:
    """``value`` with every key of every record in it camelCase (module docstring)."""
    if isinstance(value, dict):
        return {to_camel(key): _camel(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_camel(item) for item in value]
    return value
