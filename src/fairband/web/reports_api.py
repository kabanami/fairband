"""The company reads, the Methodology section read and the report routes (spec 2026-11-06 Tier 2,
12, 13, 15.2 and 16; ``method.md`` 16).

Each read answers a figure as ``{value, unit, ref}``, so a cite costs the agent nothing to build;
the refs are ``fairband.reports.refs``' forms, the units ``currency``, ``per-share``, ``percent``,
``multiple``, ``count``, ``score`` and ``years`` (a currency figure is in the statements'
``currency``). Keys are camelCase, as the agent routes send them; a ref names a field by the
engine's snake_case name.

- ``GET /api/companies/{symbol}/financials``: the fiscal-year series (``FiscalYear``), the trailing
  figures (``TrailingFigures``, ``null`` without them) and the balance years (``BalanceYear``) as
  ``statements_for`` reads them, each figure with its ``fact:`` ref (``ttm`` for a trailing one);
  the EPS is per share, every other figure currency.
- ``/quarters``: the newest ``QUARTERS_SERVED`` stored quarterly periods in the reporting currency,
  oldest first, as ``stored_quarters`` reads them (spec 2026-11-11 7.1), each ``{period,
  periodEnd, fiscalYear, fiscalPeriod}`` with a figure a line of the trailing figures, its ref
  ``fact:<symbol>/<line>/<period>`` by the stored fiscal label (``2027-Q1``); ``otherCurrency``
  counts the stored periods left out for another currency. ``financials`` does not serve them.
- ``/financial-tables``: the six tables of ``fairband.reports.tables`` under ``tables``, each with
  its columns ``{period, kind, label}`` and each cell ``{period, value, unit, ref, note}``, and
  the quarters table of section 5 beside them under ``quarters``, in the same form (spec
  2026-11-15 6.4, 6.5).
- ``/estimates``: the stored consensus as ``build_inputs`` reads it, the quarters and the fiscal
  years oldest first, each figure with its ``estimate:`` ref; a quarter's period is
  ``<fiscal year>-Q<n>`` and a year's the fiscal year. None without statements to place them.
- ``/price-history?years=``: the closes of the latest stored price history as ``build_inputs``
  reads them, oldest first, each with its ``close:`` ref; with ``years`` (one or more), those on
  or after the same day that many years before the newest close.
- ``/peers``: the company's mature peers with their figures and their source, its kind and its
  industry, as ``build_inputs`` reads them on the latest deciles (``peer_figures``), each figure
  with its ``peer:`` ref; none, and no source, before any deciles.

The financials, the quarters and the tables answer 404 "no financial statements for <symbol>" when
the store holds no annual income statement; the estimates, the closes and the peers 404 "no
snapshot for <symbol>", as the company read (``GET /api/companies/{symbol}``) does, for a company
with no snapshot, and what the store holds, none included, for one with a snapshot. A symbol that
is not one is a 400.

``GET /api/methodology/{section}`` answers ``{id, title, text}`` for the Methodology page's
``<section id>`` (``methodology_text``), its live values from the effective policy and the latest
deciles; an unknown id is a 404, "no methodology section <id>". ``GET /api/methodology`` lists the
sections in the page's order, ``{sections: [{id, title}]}``.

``POST /api/companies/{symbol}/reports`` takes ``{mode, stance, sections: [{heading, parts}],
judgments: [{judgment, decision, overrideId?}], killCriteria?: [{text}], newsItems?: [{date,
headline, source, text, killCriterionId?}], workItemId?}``, a part a plain string or ``{cite,
ref, period?}``, from any writer. A judgment is a record and takes no other key: one with a
``bull`` or a ``bear`` is refused 400 by the body's validation, naming the field. On the
company's latest snapshot (404 "no snapshot for <symbol>" without one): the structural checks
(``check.structure_refusal``), each a 400 with its sentence, the required judgments by the route
of the company's current review when it rests on that snapshot, else the snapshot's (its phase's
for a refused row), and, on a refused latest snapshot, the company's newest secondary valuation
resting on that snapshot or one it reprices, else "the report needs a secondary valuation on
snapshot <id>", unless the company can have none there (``store.secondary.no_secondary``): its
current review rests on that snapshot or one it reprices and has a value, "the review values the
company" (an override routed it: the secondary valuation is the fallback where neither the route
nor the review values the company, plan 3), or the snapshot refused for a reason an agent cannot
fix (``store.secondary.cannot_fix``: no diluted share count, the reporting currency's or the share
basis's, spec 2026-11-10 7.6), the reason the refusal's own sentence; a valued latest snapshot
needs none, the secondary route refusing one there (``no_secondary``'s first reason, "the route
values the company"); a work item it names must be the company's (404 "no work
item <id>", "... for <symbol>") and open (409 "work item <id> is <state>"). Then the number check
(``check.check_sections`` over the sections, and ``check.check_judgments`` over the judgments'
decisions, which hold no figure): with findings, the answer is 422
``{findings: [{where, what, detail}]}`` and nothing is stored but a ``report`` ledger row that
points at no record, "rejected: <n> findings", resting on the latest snapshot. Without, the report
is published, 201 ``{report}``: stored as the company's next revision on the snapshot its cites
rest on (the earliest they name, else the latest), with the review and the secondary valuation
they cite, else the company's current review when it rests on the latest snapshot or one it
reprices and, on a refused latest snapshot, its newest secondary valuation when that one does;
where ``no_secondary`` gives a reason a secondary valuation on file (one made before plan 3, or
before an override routed the company) is the report's only when a cite names it, else Appendix A
names the reason in its own sentence (``render.appendix_a``); a valuation review reuses the
company's newest full report, ``None`` without one. Its judgments, kill criteria and news items are
stored with it, under its id (an override a judgment names, or a kill criterion a news item names,
must be the company's: 404; a blank text 400), and the work item named is completed. Each record is
a ledger row (``report``, ``judgment``, ``kill-criterion``, ``news-item``, ``complete``) resting on
the report's snapshot, the report's and the completion's naming the work item, all in one
transaction.

``GET /api/companies/{symbol}/reports`` lists the company's revisions newest first, each record
without its sections: its id, date (``createdAt``), writer, revision, mode, stance and the full
report it reuses (spec 18.4), the list the Research tab's read carries as its reports on file
(``report_list``; the Research tab's design, 7.3 and 8.1);
``GET /api/reports/{id}`` answers one whole, with its judgments, its appendixes and its
references, ``[{n, ref, source}]``, generated at read time (``render.appendix_a``, ``appendix_b``,
``references``), as the publish answers it; ``GET /api/reports/{id}/markdown`` its Markdown
(``render.markdown``), ``text/markdown``, each cite with its footnote mark, the references last,
after Appendix B, and the chart tables (``charts.chart_tables``) under their sections, which the
JSON does not carry; a valuation review's names the full report it reuses by that report's date
(spec 2026-11-15 7), or, where that report's record is not on file, an earlier full report, so a
stored report always renders. A missing report is a 404, "no report <id>".
"""

import sqlite3
from collections.abc import Callable, Iterable, Iterator
from contextlib import closing, contextmanager
from dataclasses import asdict, fields
from datetime import date, datetime
from functools import partial
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from fairband.engine.anchor import AnnualEstimate, QuarterEstimate
from fairband.engine.overrides import route_of
from fairband.engine.revenue_growth import PeerFigures
from fairband.engine.types import Route, ValuationResult
from fairband.policy import Policy
from fairband.policy.settings import exchange_symbol
from fairband.policy.tax import TaxTable
from fairband.refresh.inputs import build_inputs
from fairband.refresh.inputs_statements import (
    QuarterFigures,
    Statements,
    country_for,
    statements_for,
    stored_quarters,
)
from fairband.refresh.peers import peer_figures
from fairband.reports.charts import chart_tables
from fairband.reports.check import (
    check_judgments,
    check_sections,
    cited_records,
    structure_refusal,
)
from fairband.reports.refs import (
    ESTIMATE_UNITS,
    PEER_UNITS,
    close_ref,
    estimate_ref,
    fact_ref,
    peer_ref,
    same_snapshot,
)
from fairband.reports.render import appendix_a, appendix_b, markdown, references
from fairband.reports.tables import financial_tables, quarters_table
from fairband.store.companies import latest_company
from fairband.store.db import transaction
from fairband.store.inbox import Mode, WorkItem, complete_item, work_item
from fairband.store.ledger import Writer, record
from fairband.store.refreshes import latest_deciles
from fairband.store.reports import (
    JudgmentKind,
    ReportRow,
    insert_judgments,
    insert_report,
    judgments_for,
    report_row,
    reports_for,
)
from fairband.store.research import add_kill_criterion, add_news_item
from fairband.store.reviews import latest_review
from fairband.store.secondary import latest_secondary, no_secondary
from fairband.store.settings import read_overlay
from fairband.store.snapshots import latest_snapshot
from fairband.web.agents_api import KillCriterionText, NewsItemPost, WriterOf, gist, record_json
from fairband.web.methodology_text import section_index, section_text
from fairband.web.policy_rows import deciles_json, policy_json
from fairband.web.settings_api import effective

# A record's fields that are not figures: they place the figures.
_PLAIN = frozenset(
    {
        "year",
        "period_end",
        "currency",
        "quarters",
        "on_fiscal_year",
        "cadence",
        "fiscal_year",
        "fiscal_period",
    }
)
# The units of the statement figures by field; every other one is currency.
_UNITS = {"eps_diluted": "per-share"} | ESTIMATE_UNITS
# The stored quarters the quarters read serves, the newest (spec 2026-11-11 7.1): the refresh
# fetches eight a run and the store keeps every one it stored, so the answer stays this long.
QUARTERS_SERVED = 8


class _Body(BaseModel):
    """A request body, its keys camelCase."""

    model_config = ConfigDict(alias_generator=to_camel)


class Cite(_Body):
    cite: str
    ref: str
    period: str | None = None


class Section(_Body):
    heading: str
    parts: list[str | Cite]


class JudgmentPost(_Body):
    """A judgment as a record: the decision and the override it produced. An unknown key, a
    ``bull`` or a ``bear`` among them, is refused rather than dropped."""

    model_config = ConfigDict(alias_generator=to_camel, extra="forbid")

    judgment: JudgmentKind
    decision: str
    override_id: int | None = None


class ReportPost(_Body):
    mode: Mode
    stance: str
    sections: list[Section]
    judgments: list[JudgmentPost]
    kill_criteria: list[KillCriterionText] = []  # text alone; a threshold is the tool's (8.1)
    news_items: list[NewsItemPost] = []
    work_item_id: int | None = None


def add_report_routes(
    app: FastAPI,
    conn_factory: Callable[[], sqlite3.Connection],
    policy: Policy,
    tax: TaxTable,
    clock: Callable[[], datetime],
) -> None:
    """Register the company reads, the Methodology section read and the report routes;
    ``policy`` is the file's, which the user's settings overlay, and ``tax`` the table the
    statements are taxed with."""

    def statements(conn: sqlite3.Connection, symbol: str) -> Statements:
        """The company's statements; 404 without an annual income statement."""
        country, _ = country_for(conn, symbol, latest_company(conn, symbol))
        stated = statements_for(conn, symbol, country, tax, clock().date())
        if stated.refusal is not None:
            raise HTTPException(404, f"no financial statements for {symbol}")
        return stated

    def known(conn: sqlite3.Connection, symbol: str) -> None:
        """404 for a company with no snapshot, in the company read's words."""
        if latest_snapshot(conn, symbol) is None:
            raise HTTPException(404, f"no snapshot for {symbol}")

    @app.get("/api/companies/{symbol}/financials")
    def financials(symbol: str) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        with closing(conn_factory()) as conn:
            stated = statements(conn, symbol)
        trailing = stated.trailing
        return {
            "symbol": symbol,
            "currency": stated.currency,
            "series": [_figures(fy, _facts(symbol, str(fy.year))) for fy in stated.series],
            "trailing": None if trailing is None else _figures(trailing, _facts(symbol, "ttm")),
            "balanceYears": [
                _figures(by, _facts(symbol, str(by.year))) for by in stated.balance_years
            ],
        }

    @app.get("/api/companies/{symbol}/quarters")
    def quarters(symbol: str) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        with closing(conn_factory()) as conn:
            stated = statements(conn, symbol)
            stored = stored_quarters(conn, symbol)
        return {
            "symbol": symbol,
            "currency": stated.currency,
            "quarters": [_quarter(symbol, q) for q in stored.periods[-QUARTERS_SERVED:]],
            "otherCurrency": stored.other_currency,
        }

    @app.get("/api/companies/{symbol}/financial-tables")
    def tables(symbol: str) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        with closing(conn_factory()) as conn:
            stated = statements(conn, symbol)  # once, for the answer and the six
            stored = stored_quarters(conn, symbol).periods  # once, for the six and the quarters
            current = effective(conn, policy)
            found = financial_tables(conn, symbol, current, tax, stored=stored, stated=stated)
            quarters = quarters_table(conn, symbol, stored=stored)
        return {
            "symbol": symbol,
            "currency": stated.currency,
            "tables": [asdict(table) for table in found],
            "quarters": asdict(quarters),
        }

    @app.get("/api/companies/{symbol}/estimates")
    def estimates(symbol: str) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        with closing(conn_factory()) as conn:
            known(conn, symbol)
            inputs = build_inputs(conn, symbol, effective(conn, policy), tax, clock().date())
        quarters = [
            _estimate(symbol, f"{q.fiscal_year}-{q.fiscal_period}", q)
            for q in inputs.quarter_estimates
        ]
        annual = [_estimate(symbol, str(a.fiscal_year), a) for a in inputs.annual_estimates]
        return {"symbol": symbol, "quarters": quarters, "annual": annual}

    @app.get("/api/companies/{symbol}/price-history")
    def price_history(
        symbol: str, years: Annotated[int | None, Query(ge=1)] = None
    ) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        with closing(conn_factory()) as conn:
            known(conn, symbol)
            closes = build_inputs(conn, symbol, effective(conn, policy), tax, clock().date()).closes
        if years is not None and closes:
            since = _years_before(closes[-1][0], years)
            closes = tuple(c for c in closes if c[0] >= since)
        return {
            "symbol": symbol,
            "closes": [
                {
                    "date": day.isoformat(),
                    "close": _figure(close, "per-share", close_ref(symbol, day.isoformat())),
                }
                for day, close in closes
            ],
        }

    @app.get("/api/companies/{symbol}/peers")
    def peers(symbol: str) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        with closing(conn_factory()) as conn:
            known(conn, symbol)
            current = effective(conn, policy)
            found = peer_figures(conn, symbol, latest_deciles(conn), current, tax, clock().date())
        source = found.source
        return {
            "symbol": symbol,
            "source": None
            if source is None
            else {"kind": source.kind, "industry": source.industry},
            "peers": [_peer(symbol, p) for p in found.figures],
        }

    @app.get("/api/methodology")
    def methodology_sections() -> dict[str, list[dict[str, str]]]:
        return {"sections": [{"id": s, "title": title} for s, title in section_index()]}

    @app.get("/api/methodology/{section}")
    def methodology(section: str) -> dict[str, str]:
        with closing(conn_factory()) as conn:
            cited = policy_json(effective(conn, policy), policy, read_overlay(conn))
            deciles = latest_deciles(conn)
        found = section_text(section, cited, None if deciles is None else deciles_json(deciles))
        if found is None:
            raise HTTPException(404, f"no methodology section {section}")
        title, text = found
        return {"id": section, "title": title, "text": text}

    @app.post("/api/companies/{symbol}/reports", status_code=201, response_model=None)
    def submit(symbol: str, body: ReportPost, writer: WriterOf) -> dict[str, Any] | JSONResponse:
        """Check the report and publish it whole, or reject it whole (module docstring)."""
        symbol = checked_symbol(symbol)
        sections = [s.model_dump(exclude_none=True) for s in body.sections]
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            latest = latest_snapshot(conn, symbol)
            if latest is None:
                raise HTTPException(404, f"no snapshot for {symbol}")
            current = effective(conn, policy)
            review = latest_review(conn, symbol)
            if review is not None and not same_snapshot(conn, review.snapshot_id, latest.id):
                review = None
            secondary = latest_secondary(conn, symbol)
            if secondary is not None and not same_snapshot(conn, secondary.snapshot_id, latest.id):
                secondary = None
            why = no_secondary(latest, review)
            exempt = secondary is None and why is not None
            # where the route or the review values the company the report talks about that value
            # alone: a secondary on file (one made before plan 3, or before an override routed
            # the company) is the report's only when a cite names it
            uncited = None if secondary is None or why is not None else secondary.id
            refusal = structure_refusal(
                body.mode,
                body.stance,
                [s.heading for s in body.sections],
                [j.judgment for j in body.judgments],
                _route(latest.result if review is None else review.result),
                current,
                secondary is not None or exempt,
                latest.id,
            )
            if refusal is not None:
                raise HTTPException(400, refusal)
            item = _open_item(conn, body.work_item_id, symbol)
            judgments = [j.model_dump() for j in body.judgments]
            findings = check_sections(conn, symbol, latest.id, sections, current, tax)
            findings += check_judgments(judgments)
            if findings:
                n = len(findings)
                summary = f"rejected: {n} finding{'' if n == 1 else 's'}"
                record(
                    conn,
                    writer,
                    at,
                    "report",
                    symbol,
                    None,
                    None,
                    snapshot_id=latest.id,
                    work_item_id=body.work_item_id,
                    summary=summary,
                )
                return JSONResponse({"findings": [asdict(f) for f in findings]}, status_code=422)
            cited, cited_review, cited_secondary = cited_records(conn, sections)
            reused = None
            if body.mode == "valuation review":
                full = (r.id for r in reports_for(conn, symbol) if r.mode == "full report")
                reused = next(full, None)
            report_id = insert_report(
                conn,
                symbol,
                body.mode,
                body.stance,
                sections,
                reused,
                latest.id if cited is None else cited,
                cited_review or (None if review is None else review.id),
                cited_secondary or uncited,
                body.work_item_id,
                writer,
                at,
            )
            report = report_row(conn, report_id)
            assert report is not None  # written in this transaction
            rows = _Rows(conn, writer, at, symbol, report.snapshot_id)
            published = f"{body.mode} revision {report.revision}: {body.stance}"
            rows.add("report", "reports", report_id, published, body.work_item_id)
            with _missing("override", symbol):
                ids = insert_judgments(conn, report_id, symbol, judgments)
            for judgment_id, j in zip(ids, body.judgments, strict=True):
                rows.add("judgment", "judgments", judgment_id, f"{j.judgment}: {gist(j.decision)}")
            for criterion in body.kill_criteria:
                with _missing("kill criterion", symbol):
                    criterion_id = add_kill_criterion(
                        conn, symbol, criterion.text, writer, at, report_id
                    )
                rows.add("kill-criterion", "kill_criteria", criterion_id, gist(criterion.text))
            for news in body.news_items:
                with _missing("kill criterion", symbol):
                    news_id = add_news_item(
                        conn,
                        symbol,
                        news.day,
                        news.headline,
                        news.source,
                        news.text,
                        writer,
                        at,
                        news.kill_criterion_id,
                        report_id,
                    )
                rows.add("news-item", "news_items", news_id, gist(news.headline))
            if item is not None:
                complete_item(conn, item.id, report_id, at)
                summary = f"completed with report {report_id}"
                rows.add("complete", "work_items", item.id, summary, item.id)
            return {"report": report_json(conn, report, current, tax)}

    @app.get("/api/companies/{symbol}/reports")
    def reports(symbol: str) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        with closing(conn_factory()) as conn:
            found = reports_for(conn, symbol)
        return {"reports": report_list(found)}

    @app.get("/api/reports/{report_id}")
    def report(report_id: int) -> dict[str, Any]:
        with closing(conn_factory()) as conn:
            found = _report(conn, report_id)
            return report_json(conn, found, effective(conn, policy), tax)

    @app.get("/api/reports/{report_id}/markdown")
    def report_markdown(report_id: int) -> Response:
        with closing(conn_factory()) as conn:
            found = _report(conn, report_id)
            current = effective(conn, policy)
            a = appendix_a(conn, found, current)
            refs = references(conn, found, current, tax)
            tables = chart_tables(conn, found, current, tax)
            # the reused full report's day; none where its row is not on file, so the report
            # still renders
            reused_of = found.reuses_full_report_of
            reused = None if reused_of is None else report_row(conn, reused_of)
        day = None if reused is None else reused.created_at.date()
        text = markdown(found, a, appendix_b(found.sections), refs, tables, reused=day)
        return Response(text, media_type="text/markdown; charset=utf-8")


class _Rows:
    """The ledger rows of one publish, each resting on the report's snapshot."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        writer: Writer,
        at: datetime,
        symbol: str,
        snapshot_id: int,
    ) -> None:
        self.conn, self.writer, self.at = conn, writer, at
        self.symbol, self.snapshot_id = symbol, snapshot_id

    def add(
        self,
        kind: str,
        table: str,
        record_id: int,
        summary: str,
        work_item_id: int | None = None,
    ) -> None:
        record(
            self.conn,
            self.writer,
            self.at,
            kind,
            self.symbol,
            table,
            record_id,
            snapshot_id=self.snapshot_id,
            work_item_id=work_item_id,
            summary=summary,
        )


@contextmanager
def _missing(what: str, symbol: str) -> Iterator[None]:
    """A store's refusals as answers: a cited ``what`` that is not the company's 404, a bad value
    400."""
    try:
        yield
    except KeyError as exc:
        raise HTTPException(404, f"no {what} {exc.args[0]} for {symbol}") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


def _open_item(conn: sqlite3.Connection, item_id: int | None, symbol: str) -> WorkItem | None:
    """The open work item of the company a submission names; ``None`` when it names none."""
    if item_id is None:
        return None
    try:
        item = work_item(conn, item_id)
    except KeyError:
        raise HTTPException(404, f"no work item {item_id}") from None
    if item.symbol != symbol:
        raise HTTPException(404, f"no work item {item_id} for {symbol}")
    if item.state not in ("pending", "claimed"):
        raise HTTPException(409, f"work item {item_id} is {item.state}")
    return item


def _route(result: ValuationResult) -> Route | None:
    """The route the result's row takes: its own, else its phase's (a refused row's)."""
    phase = result.phase.phase
    return result.route or (None if phase is None else route_of(phase))


def _report(conn: sqlite3.Connection, report_id: int) -> ReportRow:
    found = report_row(conn, report_id)
    if found is None:
        raise HTTPException(404, f"no report {report_id}")
    return found


def report_json(
    conn: sqlite3.Connection, report: ReportRow, policy: Policy, tax: TaxTable
) -> dict[str, Any]:
    """A report whole, as the report read answers it: its record, its judgments, its two
    appendixes and its references; ``policy`` is the effective one and ``tax`` the statements'
    table. The Research tab's read answers the report it shows by it."""
    return {
        **record_json(report),
        "judgments": [record_json(j) for j in judgments_for(conn, report.id)],
        "appendixA": appendix_a(conn, report, policy),
        "appendixB": appendix_b(report.sections),
        "references": references(conn, report, policy, tax),
    }


def report_list(reports: Iterable[ReportRow]) -> list[dict[str, Any]]:
    """The revisions ``reports`` as the list read answers them, each record without its sections.
    The Research tab's read answers the company's revisions by it."""
    return [{k: v for k, v in record_json(r).items() if k != "sections"} for r in reports]


def checked_symbol(text: str) -> str:
    """The symbol ``text`` names in the store's form (``exchange_symbol``); a 400 with its
    sentence for one that is not a symbol. The company page's reads share it."""
    try:
        return exchange_symbol(text)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


def _figure(value: float | None, unit: str, ref: str) -> dict[str, Any]:
    return {"value": value, "unit": unit, "ref": ref}


def _figures(record: Any, ref: Callable[[str], str]) -> dict[str, Any]:
    """A statement or consensus record's fields by camelCase name: a placing field as it is (a
    date as ISO text), a figure as ``{value, unit, ref}`` with ``ref`` of its field's name."""
    out: dict[str, Any] = {}
    for field in fields(record):
        value = getattr(record, field.name)
        if field.name in _PLAIN:
            out[to_camel(field.name)] = value.isoformat() if isinstance(value, date) else value
        else:
            unit = _UNITS.get(field.name, "currency")
            out[to_camel(field.name)] = _figure(value, unit, ref(field.name))
    return out


def _facts(symbol: str, period: str) -> Callable[[str], str]:
    """The ``fact:`` ref of a line of ``period``."""
    return lambda line: fact_ref(symbol, line, period)


def _quarter(symbol: str, quarter: QuarterFigures) -> dict[str, Any]:
    """A stored quarter by its fiscal label, its placing fields and its lines' figures."""
    return {"period": quarter.period, **_figures(quarter, _facts(symbol, quarter.period))}


def _estimate(
    symbol: str, period: str, estimate: QuarterEstimate | AnnualEstimate
) -> dict[str, Any]:
    return {"period": period, **_figures(estimate, partial(estimate_ref, symbol, period))}


def _peer(symbol: str, peer: PeerFigures) -> dict[str, Any]:
    figures = {
        to_camel(name): _figure(getattr(peer, name), unit, peer_ref(symbol, peer.symbol, name))
        for name, unit in PEER_UNITS.items()
    }
    return {"symbol": peer.symbol, **figures}


def _years_before(day: date, years: int) -> date:
    """The same day ``years`` earlier; 29 February becomes the 28th."""
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)
