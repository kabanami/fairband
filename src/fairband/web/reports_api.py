"""The company reads and the Methodology section read (spec 2026-11-06 Tier 2, 13.5, 15.2 and 16).

Each read answers a figure as ``{value, unit, ref}``, so a cite costs the agent nothing to build;
the refs are ``fairband.reports.refs``' forms, the units ``currency``, ``per-share``, ``percent``,
``multiple``, ``count``, ``score`` and ``years`` (a currency figure is in the statements'
``currency``). Keys
are camelCase, as the agent routes send them; a ref names a field by the engine's snake_case name.

- ``GET /api/companies/{symbol}/financials``: the fiscal-year series (``FiscalYear``), the trailing
  figures (``TrailingFigures``, ``null`` without them) and the balance years (``BalanceYear``) as
  ``statements_for`` reads them, each figure with its ``fact:`` ref (``ttm`` for a trailing one);
  the EPS is per share, every other figure currency.
- ``/financial-tables``: the six tables of ``fairband.reports.tables``, each cell
  ``{period, value, unit, ref, note}``.
- ``/estimates``: the stored consensus as ``build_inputs`` reads it, the quarters and the fiscal
  years oldest first, each figure with its ``estimate:`` ref; a quarter's period is
  ``<fiscal year>-Q<n>`` and a year's the fiscal year. None without statements to place them.
- ``/price-history?years=``: the closes of the latest stored price history as ``build_inputs``
  reads them, oldest first, each with its ``close:`` ref; with ``years`` (one or more), those on
  or after the same day that many years before the newest close.
- ``/peers``: the company's mature peers with their figures and their source, as ``build_inputs``
  reads them on the latest deciles (``peer_figures``), each figure with its ``peer:`` ref; none,
  and no source, before any deciles.

The financials and the tables answer 404 "no financial statements for <symbol>" when the store
holds no annual income statement; the other reads answer what the store holds, none included. A
symbol that is not one is a 400.

``GET /api/methodology/{section}`` answers ``{id, title, text}`` for the Methodology page's
``<section id>``, read from ``methodology.html`` with ``html.parser``: the title is the section's
``h2``, the text the rest of its text content, whitespace collapsed, with a space at each element
boundary but the inline ones. The elements ``methodology.js`` fills with a policy value read as
that script fills them, from the effective policy as ``GET /api/policy`` serves it and formatted
as the script formats each unit (``data-policy``, ``data-policy-version``, and
``data-policy-changed`` when a setting differs); so do the decile edges (``data-decile``) when a
full refresh has ranked the universe. The phase counts (``data-count``) are the screen's, not the
method's, and keep the page's em dash, as does a value the policy lacks. An unknown id is a 404,
"no methodology section <id>".
"""

import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import asdict, fields
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from functools import partial
from html.parser import HTMLParser
from importlib import resources
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from pydantic.alias_generators import to_camel

from fairband.engine.anchor import AnnualEstimate, QuarterEstimate
from fairband.engine.revenue_growth import PeerFigures
from fairband.policy import Policy
from fairband.policy.settings import exchange_symbol
from fairband.policy.tax import TaxTable
from fairband.refresh.inputs import build_inputs
from fairband.refresh.inputs_statements import Statements, country_for, statements_for
from fairband.refresh.peers import peer_figures
from fairband.reports.refs import close_ref, estimate_ref, fact_ref, peer_ref
from fairband.reports.tables import financial_tables
from fairband.store.companies import latest_company
from fairband.store.refreshes import latest_deciles
from fairband.store.settings import read_overlay
from fairband.web.policy_rows import deciles_json, policy_json
from fairband.web.settings_api import effective

_METHODOLOGY = resources.files("fairband.web").joinpath("static", "methodology.html")
# A record's fields that are not figures: they place the figures.
_PLAIN = frozenset(
    {"year", "period_end", "currency", "quarters", "on_fiscal_year", "fiscal_year", "fiscal_period"}
)
# The units of the statement and consensus figures by field; every other one is currency.
_UNITS = {
    "eps_diluted": "per-share",
    "eps": "per-share",
    "analysts": "count",
    "analysts_eps": "count",
    "analysts_net_income": "count",
    "analysts_revenue": "count",
}
_PEER_UNITS = {
    "market_cap": "currency",
    "margin": "percent",
    "margin_years": "count",
    "sales_to_capital": "multiple",
    "roic": "percent",
}
_DASH = "—"
# The elements whose boundaries add no space to the text.
_INLINE = frozenset(
    {"a", "abbr", "b", "cite", "code", "em", "i", "q", "small", "span", "strong", "sub", "sup"}
)


def add_report_routes(
    app: FastAPI,
    conn_factory: Callable[[], sqlite3.Connection],
    policy: Policy,
    tax: TaxTable,
    clock: Callable[[], datetime],
) -> None:
    """Register the company reads and the Methodology section read; ``policy`` is the file's,
    which the user's settings overlay, and ``tax`` the table the statements are taxed with."""

    def statements(conn: sqlite3.Connection, symbol: str) -> Statements:
        """The company's statements; 404 without an annual income statement."""
        country, _ = country_for(conn, symbol, latest_company(conn, symbol))
        stated = statements_for(conn, symbol, country, tax, clock().date())
        if stated.refusal is not None:
            raise HTTPException(404, f"no financial statements for {symbol}")
        return stated

    @app.get("/api/companies/{symbol}/financials")
    def financials(symbol: str) -> dict[str, Any]:
        symbol = _symbol(symbol)
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

    @app.get("/api/companies/{symbol}/financial-tables")
    def tables(symbol: str) -> dict[str, Any]:
        symbol = _symbol(symbol)
        with closing(conn_factory()) as conn:
            stated = statements(conn, symbol)
            found = financial_tables(conn, symbol, effective(conn, policy), tax)
        return {
            "symbol": symbol,
            "currency": stated.currency,
            "tables": [asdict(table) for table in found],
        }

    @app.get("/api/companies/{symbol}/estimates")
    def estimates(symbol: str) -> dict[str, Any]:
        symbol = _symbol(symbol)
        with closing(conn_factory()) as conn:
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
        symbol = _symbol(symbol)
        with closing(conn_factory()) as conn:
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
        symbol = _symbol(symbol)
        with closing(conn_factory()) as conn:
            current = effective(conn, policy)
            found = peer_figures(conn, symbol, latest_deciles(conn), current, tax, clock().date())
        source = found.source
        return {
            "symbol": symbol,
            "source": None
            if source is None
            else {
                "kind": source.kind,
                "industry": source.industry,
                "fmpCounted": source.fmp_counted,
            },
            "peers": [_peer(symbol, p) for p in found.figures],
        }

    @app.get("/api/methodology/{section}")
    def methodology(section: str) -> dict[str, str]:
        with closing(conn_factory()) as conn:
            cited = policy_json(effective(conn, policy), policy, read_overlay(conn))
            deciles = latest_deciles(conn)
        live = _Live(cited, None if deciles is None else deciles_json(deciles))
        parsed = _Section(section, live.text)
        parsed.feed(_METHODOLOGY.read_text(encoding="utf-8"))
        parsed.close()
        if not parsed.found:
            raise HTTPException(404, f"no methodology section {section}")
        return {"id": section, "title": _collapsed(parsed.title), "text": _collapsed(parsed.text)}


def _symbol(text: str) -> str:
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


def _estimate(
    symbol: str, period: str, estimate: QuarterEstimate | AnnualEstimate
) -> dict[str, Any]:
    return {"period": period, **_figures(estimate, partial(estimate_ref, symbol, period))}


def _peer(symbol: str, peer: PeerFigures) -> dict[str, Any]:
    figures = {
        to_camel(name): _figure(getattr(peer, name), unit, peer_ref(symbol, peer.symbol, name))
        for name, unit in _PEER_UNITS.items()
    }
    return {"symbol": peer.symbol, **figures}


def _years_before(day: date, years: int) -> date:
    """The same day ``years`` earlier; 29 February becomes the 28th."""
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)


def _collapsed(parts: Sequence[str]) -> str:
    return " ".join("".join(parts).split())


class _Live:
    """The live values of the Methodology page, as ``methodology.js`` writes each element's text:
    ``cited`` is ``GET /api/policy``'s answer and ``deciles`` ``GET /api/deciles``' (``None``
    before a full refresh ranked the universe)."""

    def __init__(self, cited: Mapping[str, Any], deciles: Mapping[str, Any] | None) -> None:
        self.cited = cited
        self.deciles = deciles

    def text(self, attributes: Mapping[str, str | None]) -> str | None:
        """The text that replaces the element's content; ``None`` for an element the policy and
        the deciles do not fill."""
        if (name := attributes.get("data-policy")) is not None:
            return self.policy(name)
        if "data-policy-version" in attributes:
            return str(self.cited["version"])
        if "data-policy-changed" in attributes:
            changed = int(self.cited["changed"])
            if not changed:
                return ""  # the paragraph is hidden
            settings = (
                "1 setting differs" if changed == 1 else f"{_number(changed)} settings differ"
            )
            return f"{settings} from the defaults."
        if (n := attributes.get("data-decile")) is not None and self.deciles is not None:
            if n == "n":
                return _number(self.deciles["n"])
            edges = self.deciles["edges"]
            index = int(n) - 1 if n.isdigit() else -1
            return _percent(edges[index]) if 0 <= index < len(edges) else _DASH
        return None

    def policy(self, key: str) -> str:
        """A cited name's value: the name itself, or a name with a moat class or an index after
        its last dot (``runway_years.Wide``, ``fair_band.1``); an em dash for none."""
        values = self.cited["values"]
        cited = values.get(key)
        value = None if cited is None else cited["value"]
        if cited is None:
            head, _, tail = key.rpartition(".")
            cited = values.get(head) if head else None
            held = None if cited is None else cited["value"]
            if isinstance(held, dict):
                value = held.get(tail)
            elif isinstance(held, list) and tail.isdigit() and int(tail) < len(held):
                value = held[int(tail)]
        if cited is None or value is None or cited["unit"] not in _FORMATS:
            return _DASH
        return _FORMATS[cited["unit"]](value)


class _Section(HTMLParser):
    """One ``<section id>`` of the Methodology page: the text of its first ``h2`` and the rest of
    its text, each element ``fill`` names a text for replaced, content and all."""

    def __init__(self, wanted: str, fill: Callable[[Mapping[str, str | None]], str | None]) -> None:
        super().__init__(convert_charrefs=True)
        self.wanted = wanted
        self.fill = fill
        self.found = False
        self.depth = 0  # the sections open from the wanted one in
        self.title: list[str] = []
        self.text: list[str] = []
        self.heading = False  # inside the title's h2
        self.titled = False
        self.replaced = ""  # the tag of the element being replaced
        self.skip = 0  # its open elements of that tag

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if not self.depth:
            if tag == "section" and attributes.get("id") == self.wanted and not self.found:
                self.found, self.depth = True, 1
            return
        if self.skip:
            if tag == self.replaced:
                self.skip += 1
            return
        if tag == "section":
            self.depth += 1
        if tag == "h2" and not self.titled:
            self.heading = True
            return
        replacement = self.fill(attributes)
        if replacement is not None:
            self._add(replacement)
            self.replaced, self.skip = tag, 1
        elif tag not in _INLINE:
            self._add(" ")

    def handle_endtag(self, tag: str) -> None:
        if not self.depth:
            return
        if self.skip:
            if tag == self.replaced:
                self.skip -= 1
            return
        if tag == "section":
            self.depth -= 1
        elif tag == "h2" and self.heading:
            self.heading, self.titled = False, True
        elif tag not in _INLINE:
            self._add(" ")

    def handle_data(self, data: str) -> None:
        if self.depth and not self.skip:
            self._add(data)

    def _add(self, text: str) -> None:
        (self.title if self.heading else self.text).append(text)


# The page's formats by unit (methodology.js's ``FORMATS``): a fraction as a percentage to one
# decimal, points and spans of time with their word, a multiple with ×, dollars in billions or
# millions, a count or a score as a plain number, a list of exchanges or symbols in words. A
# figure and its word are joined by a no-break space, which the collapsed text makes a space.


def _fixed(x: float, places: int) -> str:
    """``Number.prototype.toFixed``: the exact value rounded half away from zero."""
    exact = Decimal(x).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return f"{exact:f}"


def _number(x: float) -> str:
    """``toLocaleString('en-US', {maximumFractionDigits: 2})``: grouped, at most two decimals."""
    text = f"{Decimal(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,f}"
    return text.rstrip("0").rstrip(".")


def _signed(text: str) -> str:
    """The design system's sign: a negative zero loses its sign, a minus becomes U+2212."""
    if re.fullmatch(r"-0?\.?0*", text):
        return text[1:]
    return "−" + text[1:] if text.startswith("-") else text


def _percent(x: float) -> str:
    return _signed(_fixed(x * 100, 1)) + "%"


def _counted(x: float, word: str) -> str:
    n = _number(x)
    return f"{n} {word}{'' if n == '1' else 's'}"


def _dollars(x: float) -> str:
    if abs(x) >= 1e9:
        return f"${_number(x / 1e9)} billion"
    if abs(x) >= 1e6:
        return f"${_number(x / 1e6)} million"
    return f"{'−$' if x < 0 else '$'}{_fixed(abs(x), 2)}"


def _listed(items: Sequence[str], word: str) -> str:
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} {word} {items[-1]}"


_FORMATS: dict[str, Callable[[Any], str]] = {
    "fraction": _percent,
    "points": lambda v: _counted(v * 100, "point"),
    "years": lambda v: _counted(v, "year"),
    "days": lambda v: _counted(v, "day"),
    "hours": lambda v: _counted(v, "hour"),
    "seconds": lambda v: _counted(v, "second"),
    "times": lambda v: f"{_number(v)}×",
    "usd": _dollars,
    "count": _number,
    "exchanges": lambda v: _listed(v, "or"),
    "symbols": lambda v: _listed(v, "and") if v else "none",
    "cap_bands": lambda v: ", ".join(f"{band[1]} from {_dollars(band[0])}" for band in v),
}
