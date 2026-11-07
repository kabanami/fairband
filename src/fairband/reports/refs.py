"""The references a report cites (spec 2026-11-06 Tier 2, 13.2; ``method.md`` 16.1): one builder
per form, so the reads that hand a ref beside each figure and the resolver that reads it back
agree on its text, and one resolver that reads every form back.

A ref is ``<form>:<path>``. The forms, each read for one company, the symbol ``resolve`` is given:

- ``snapshot:<id>/value``, ``/price``, ``/price_to_value``, ``/levels/<name>`` (``buy``,
  ``fair_low``, ``fair_high``, ``trim``), ``/inputs/<name>`` (a tagged input: its number, or for a
  word input, a moat class say, the word that leads its note), ``/intermediates/<path>`` (an
  intermediate by its path of keys and list indexes, ``belief/rate``, ``growth_rates/0``) and
  ``/phase/<field>`` (a field of the classifier's evidence, ``phase``, ``growth_3y``);
- ``review:<id>/value``, ``/price_to_value``, ``/levels/<name>`` and ``/bridge/<n>/delta``,
  ``/old`` or ``/new``, the bridge's line ``n`` counted from 1;
- ``secondary:<id>/value`` (the value a share), ``/firm_value``, ``/equity``, ``/debt``, ``/cash``,
  ``/shares``, ``/price_to_value``, ``/levels/<name>`` and ``/grid/<i>/<j>`` (the grid's row ``i``
  at its column ``j``, a value a share); on the parts form ``/parts/<n>/pv/<t>``,
  ``/parts/<n>/fcff/<t>``, ``/parts/<n>/value``, ``/parts/<n>/terminal``,
  ``/parts/<n>/terminal_pv`` and ``/parts/<n>/terminal_growth``; on the drivers form
  ``/years/<t>/<line>`` (``revenue``, ``ebit``, ``nopat``, ``reinvestment``, ``fcff``, ``pv``),
  ``/terminal_fcff``, ``/terminal``, ``/terminal_pv``, ``/drivers/<name>`` (``years``, ``tax_rate``,
  ``sales_to_capital``, ``terminal_growth``) and ``/drivers/<name>/<t>`` (``revenue_growth``,
  ``operating_margin``); every index (the part ``n``, the year ``t``, the row ``i`` and the column
  ``j``) counted from 1, and a form's paths naming nothing on the other form;
- ``sensitivity:<id>/<i>/<j>``: a stored sensitivity reading's value a share at its row ``i`` and
  its column ``j``, each counted from 1; a refused cell holds no value;
- ``fact:<symbol>/<line>/<period>``: a stored statement line as the engine reads it, ``<line>``
  the engine's field name (``fairband.reports.tables.LINES`` for a fiscal year, read through
  ``year_lines``; the trailing figures' fields for ``ttm``) and ``<period>`` the fiscal year as
  text or ``ttm``;
- ``table:<symbol>/<table>/<row>/<period>``: a cell of the financial tables (13.5);
- ``estimate:<symbol>/<period>/<field>``: a stored consensus figure, ``<period>`` the fiscal year
  (``2026``) or the quarter (``2026-Q4``) and ``<field>`` the engine's name (``eps``,
  ``net_income``, ``analysts_eps``);
- ``close:<symbol>/<date>``: a stored daily close;
- ``multiple:<symbol>/<series>/<date>`` and ``/<stat>``: a point of the trailing (``pe``) or the
  forward (``pe_forward``) P/E history by its ISO date, or one of its statistics over the ten years
  to its newest day, ``avg_10y``, ``median_10y``, ``high_10y``, ``low_10y``
  (``fairband.reports.multiples``): the trailing series is the newest stored ``pe-history``
  response's, the forward one the multiples log's; a statistic of a series with no point holds no
  figure;
- ``peer:<symbol>/<peer>/<field>``: a figure of one of the company's mature peers as assembly
  reads it (``market_cap``, ``margin``, ``margin_years``, ``sales_to_capital``, ``roic``);
- ``finding:<id>``: a finding's value, its unit and its period;
- ``guidance:<id>/low``, ``/high``, ``/midpoint`` and ``/step``: a guidance record's figures in
  its metric's unit (``store.guidance.UNITS``), its step a percent, each of the record's period;
  a step the record does not take holds no figure;
- ``derived:<id>``: a derivation's value and unit (13.4);
- ``response:<id>/<json pointer>``: a field of a stored vendor response (RFC 6901, ``/0/revenue``);
- ``policy:<name>``: a value the Methodology page cites from the policy, by its name or by its
  name and a moat class or an index (``runway_years.Wide``, ``fair_band.0``); the page's
  ``count`` reads as a ``score`` (the Z″ edges have decimals), its ``fraction`` and ``points`` as
  a percent.

Each resolves to a ``Resolved``: the value (a number, a word, or ``None`` where the record holds no
figure), its unit, its period and the snapshot it rests on, and two marks the check reads: a share
price (``snapshot:<id>/price``, ``/inputs/price``, ``close:``), which is written to cents, and a
line the store signs as an outflow (``capex``, ``dividends`` and ``buybacks`` as ``fact:`` lines
and table rows, and the snapshot's ``capex_ttm``, ``dividends_ttm`` and ``buybacks_ttm``), which a
cite may give by its size. The units are the reads': ``currency``
(a total, in the statements' currency), ``per-share``, ``percent`` (a fraction), ``multiple``,
``count``, ``score``, ``years``; ``None`` for a word and wherever the record names no unit, an
intermediate or a vendor field. An engine input's unit maps onto them: a currency code is
``currency``, ``<code> a share`` ``per-share``, ``ratio`` ``percent``, ``shares`` and the other
counted things ``count``. The period is the fiscal year (``2025``), the quarter (``2026-Q4``),
``ttm``, or the close's or the multiple's date for the forms that have one, a finding's and a
guidance record's as recorded; ``None`` for the others. The snapshot is the record's own for
``snapshot:``, ``review:``, ``secondary:`` and ``sensitivity:``, and for ``derived:`` the
snapshot its operands rest on; ``None`` for the others, a finding and a guidance record being
facts of the company.

A ref resolves to ``None`` when it names nothing: a malformed ref, a record or a field that does
not exist, a figure that is a table rather than a number or a word, or a record of another
company. A ``Resolver`` reads one company's refs with its statements, tables, consensus and peers
read once; ``resolve`` reads one ref.

``Resolver.describe`` gives the references list a ref's source in words, one sentence a form: a
date or a name where one serves, a record's id where nothing else names it. ``snapshot:`` "snapshot
412, the clean P/E, priced 3 Nov 2026" (the path in words, an input, an intermediate or a
classifier field by its name in words, ``field_words``, where no fixed words name it; the
snapshot's price date); ``review:``
"review 88, bridge line 1 (belief), the change in the value a share"; ``secondary:`` "secondary
valuation 9, year 3 FCFF"; ``sensitivity:`` "sensitivity 7, row 1 column 2"; ``fact:`` "the
revenue line of fiscal 2025 on file"; ``table:`` "the growth table, revenue growth, fiscal 2025";
``estimate:`` "the consensus for Q4 of fiscal 2026, EPS"; ``close:`` "the close of 3 Nov 2026";
``multiple:`` "the trailing P/E, 30 Oct 2026" or "the forward P/E, the ten-year average";
``peer:`` "ACME, margin"; ``finding:`` "finding 88: 10-K 2025, p. 41", the finding's source;
``guidance:`` "guidance record 5: EPS for fiscal 2027, the midpoint"; ``derived:`` "derivation 7:
the ratio of <a> and <b>", the operands' refs; ``response:`` "FMP segments, observed 1 Nov 2026";
``policy:`` "policy required_return, <the policy's version>". A ref whose form or record names
nothing, a record of another company among them, is its own description; a ``secondary:`` or
``sensitivity:`` ref is read as ``resolve`` reads it, so a path its record lacks names nothing.

``same_snapshot`` is the reprice rule (13.2): a later snapshot that reprices the cited one, with
the same data date, method, policy, settings hash and value, counts as the cited one.
"""

import json
import math
import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import date
from typing import Any

from fairband.engine.anchor import TrailingFigures
from fairband.engine.overrides import LABELS, TAGS
from fairband.engine.route import CompanyInputs
from fairband.engine.types import PhaseEvidence
from fairband.policy import Policy
from fairband.policy.settings import exchange_symbol
from fairband.policy.tax import TaxTable, load_tax_table
from fairband.refresh.inputs import build_inputs
from fairband.refresh.inputs_statements import Statements, country_for, statements_for
from fairband.refresh.peers import peer_figures
from fairband.reports.multiples import SERIES, STATS, Series, stored_series
from fairband.store.companies import latest_company
from fairband.store.guidance import UNITS as GUIDANCE_UNITS
from fairband.store.guidance import guidance_row
from fairband.store.refreshes import latest_deciles
from fairband.store.research import finding_row
from fairband.store.reviews import review_row
from fairband.store.secondary import derivation_row, secondary_row
from fairband.store.sensitivities import sensitivity_row
from fairband.store.snapshots import SnapshotRow, snapshot_row
from fairband.store.vendor import response_payload, response_row
from fairband.web.policy_rows import policy_json

__all__ = [
    "ESTIMATE_UNITS",
    "PEER_UNITS",
    "Resolved",
    "Resolver",
    "close_ref",
    "day_words",
    "estimate_ref",
    "fact_ref",
    "field_words",
    "guidance_cited",
    "multiple_ref",
    "peer_ref",
    "resolve",
    "rests_on",
    "same_snapshot",
    "table_ref",
    "unit_of",
]

# The units of the consensus figures by field; every other figure is currency.
ESTIMATE_UNITS: dict[str, str] = {
    "eps": "per-share",
    "analysts": "count",
    "analysts_eps": "count",
    "analysts_net_income": "count",
    "analysts_revenue": "count",
}
PEER_UNITS: dict[str, str] = {
    "market_cap": "currency",
    "margin": "percent",
    "margin_years": "count",
    "sales_to_capital": "multiple",
    "roic": "percent",
}
_LEVELS = frozenset({"buy", "fair_low", "fair_high", "trim"})
# A level's column on a review or a secondary valuation, by its name in a ref.
_LEVEL_COLUMNS = {
    "buy": "buy_level",
    "fair_low": "fair_low",
    "fair_high": "fair_high",
    "trim": "trim_level",
}
_PHASE_UNITS = {
    "growth_3y": "percent",
    "margin": "percent",
    "margin_slope": "percent",
    "revenue_slope": "currency",
    "growth_decile": "count",
    "years_used": "count",
    "positive_years_last_five": "count",
    "positive_years_on_file": "count",
}
_SECONDARY_FIELDS = {
    "value": ("value_per_share", "per-share"),
    "firm_value": ("firm_value", "currency"),
    "equity": ("equity", "currency"),
    "debt": ("debt", "currency"),
    "cash": ("cash", "currency"),
    "shares": ("shares", "count"),
    "price_to_value": ("price_to_value", "multiple"),
}
_PART_FIELDS = {
    "value": "currency",
    "terminal": "currency",
    "terminal_pv": "currency",
    "terminal_growth": "percent",
}
# The drivers form's projection: a year's lines, and the terminal's three figures, all currency.
_YEAR_LINES = frozenset({"revenue", "ebit", "nopat", "reinvestment", "fcff", "pv"})
_TERMINAL_FIGURES = frozenset({"terminal_fcff", "terminal", "terminal_pv"})
# The drivers by name with their units: one figure each, or a list, a rate for each year.
_DRIVER_UNITS = {
    "years": "count",
    "tax_rate": "percent",
    "sales_to_capital": "multiple",
    "terminal_growth": "percent",
}
_DRIVER_LISTS = frozenset({"revenue_growth", "operating_margin"})
# A guidance record's figures a ref names, and the record as an evidence item names it.
_GUIDANCE_FIGURES = frozenset({"low", "high", "midpoint", "step"})
_GUIDANCE_RECORD = re.compile(r"guidance:(\d+)")
# The inputs whose engine unit names the currency of a figure that is a share's: the price.
_INPUT_UNITS = {"price": "per-share"}
# A step of a path that is not there, told apart from a figure stored as null.
_ABSENT = object()
# The lines the store signs as outflows (``cfi`` and ``cff`` are net flows, not these): the
# statement lines, the tables' rows of them and the snapshot's trailing inputs.
_OUTFLOW_LINES = frozenset({"capex", "dividends", "buybacks"})
_OUTFLOW_ROWS = frozenset({"capital_spending", "dividends", "buybacks"})
_OUTFLOW_INPUTS = frozenset({"capex_ttm", "dividends_ttm", "buybacks_ttm"})
# The engine's unit words for counted things.
_COUNTED = frozenset({"shares", "fiscal years", "daily closes", "peers", "year"})
# The Methodology page's units (``policy_rows``) as the resolver's.
_POLICY_UNITS = {
    "fraction": "percent",
    "points": "percent",
    "times": "multiple",
    "years": "years",
    "usd": "currency",
    "count": "score",  # the page shows a score as a count: Z'' edges have decimals
    "days": "count",
    "hours": "count",
    "seconds": "count",
}
# The fields of a statement or consensus record that place its figures.
_PLAIN = frozenset(
    {"year", "period_end", "currency", "quarters", "on_fiscal_year", "fiscal_year", "fiscal_period"}
)
_TRAILING_FIGURES = frozenset(f.name for f in fields(TrailingFigures)) - _PLAIN
_PHASE_FIELDS = frozenset(f.name for f in fields(PhaseEvidence)) - {"checks"}
# ``statements_for`` and the peers read their day only as the data date of a store without
# statements, which no ref reads.
_NO_DAY = date.min

# The references list's words (``Resolver.describe``): a record's figures and levels, a part's,
# a projection year's lines, the drivers, a bridge line's three figures, the two P/E series and
# their statistics, the vendors by name.
_FIGURE_WORDS = {
    "value": "the value a share",
    "price": "the price",
    "price_to_value": "price ÷ value",
    "firm_value": "the firm value",
    "equity": "the equity",
    "debt": "the debt",
    "cash": "the cash",
    "shares": "the diluted shares",
    "terminal_fcff": "the terminal FCFF",
    "terminal": "the terminal value",
    "terminal_pv": "the terminal's present value",
}
_LEVEL_WORDS = {
    "buy": "the buy level",
    "fair_low": "the fair band's low",
    "fair_high": "the fair band's high",
    "trim": "the trim level",
}
_PART_WORDS = {
    "value": "its value",
    "terminal": "the terminal value",
    "terminal_pv": "the terminal's present value",
    "terminal_growth": "the terminal growth",
}
_YEAR_WORDS = {
    "revenue": "revenue",
    "ebit": "EBIT",
    "nopat": "NOPAT",
    "reinvestment": "reinvestment",
    "fcff": "FCFF",
    "pv": "present value",
}
_DRIVER_WORDS = {
    "years": "the years projected",
    "tax_rate": "the tax rate",
    "sales_to_capital": "the sales-to-capital",
    "terminal_growth": "the terminal growth",
}
_BRIDGE_WORDS = {
    "delta": "the change in the value a share",
    "old": "the old figure",
    "new": "the new figure",
}
_SERIES_WORDS = {"pe": "the trailing P/E", "pe_forward": "the forward P/E"}
_STAT_WORDS = {
    "avg_10y": "the ten-year average",
    "median_10y": "the ten-year median",
    "high_10y": "the ten-year high",
    "low_10y": "the ten-year low",
}
_PROVIDER_WORDS = {"fmp": "FMP", "gf": "GuruFocus"}
# An engine name's words: an abbreviation in capitals, a statement line's short name spelled out.
# A whole name is read before its words, so a score or a ratio reads as the spec writes it.
_NAME_WORDS = {
    "altman_z": "Altman's Z″",
    "piotroski_f": "Piotroski's F",
    "beneish_m": "Beneish's M",
    "aggregate_roic": "ten-year aggregate ROIC",
    "aggregate_roic_ten_year": "ten-year aggregate ROIC",
    "eps_diluted": "diluted EPS",
    "shares_diluted": "diluted shares",
    "eps": "EPS",
    "fcf": "FCF",
    "roic": "ROIC",
    "roe": "ROE",
    "ebit": "EBIT",
    "ebitda": "EBITDA",
    "ttm": "TTM",
    "ntm": "NTM",
    "fy": "FY",
    "pe": "P/E",
    "nri": "NRI",
    "cfo": "operating cash flow",
    "cfi": "investing cash flow",
    "cff": "financing cash flow",
    "capex": "capital spending",
    "sbc": "stock compensation",
}
# A snapshot's paths a report cites most, in words; any other reads through ``field_words``.
_SNAPSHOT_PATH_WORDS = {
    "intermediates/belief/rate": "the belief",
    "intermediates/implied_growth": "the growth the price needs",
    "intermediates/multiples/pe_clean": "the clean P/E",
    "intermediates/multiples/pe_reported": "the reported P/E",
    "intermediates/multiples/pe_forward": "the forward P/E",
    "intermediates/roic/aggregate": "the ten-year aggregate ROIC",
    "intermediates/price_facts/high_52w": "the 52-week high",
    "intermediates/price_facts/low_52w": "the 52-week low",
    "intermediates/price_facts/change_1y": "the price change over one year",
    "intermediates/price_facts/change_3y": "the price change over three years",
    "intermediates/price_facts/change_5y": "the price change over five years",
    "intermediates/price_facts/drawdown_from_peak": "the drop from the last peak",
    "phase/phase": "the phase",
    "phase/growth_3y": "the three-year revenue growth",
    "phase/dickinson": "the Dickinson stage",
}
# Each input's bridge label by its tag as a stored bridge line names it.
_LABELS: dict[str, str] = {tag: label for tag, label in LABELS.items()}
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_QUARTER = re.compile(r"(\d{4})-?(Q[1-4])")


@dataclass(frozen=True)
class Resolved:
    """A ref's value, its unit, its period and the snapshot it rests on (module docstring);
    ``price`` marks a share price, which is written to cents, and ``outflow`` a cash flow line the
    store signs as an outflow, which a cite may give by its size."""

    value: float | str | None
    unit: str | None
    period: str | None
    snapshot_id: int | None
    price: bool = False
    outflow: bool = False


def fact_ref(symbol: str, line: str, period: str) -> str:
    return f"fact:{symbol}/{line}/{period}"


def table_ref(symbol: str, table: str, row: str, period: str) -> str:
    return f"table:{symbol}/{table}/{row}/{period}"


def estimate_ref(symbol: str, period: str, field: str) -> str:
    return f"estimate:{symbol}/{period}/{field}"


def close_ref(symbol: str, day: str) -> str:
    return f"close:{symbol}/{day}"


def peer_ref(symbol: str, peer: str, field: str) -> str:
    return f"peer:{symbol}/{peer}/{field}"


def multiple_ref(symbol: str, series: str, key: str) -> str:
    """A point of a P/E series by its ISO date, or a statistic by its name."""
    return f"multiple:{symbol}/{series}/{key}"


def guidance_cited(ref: str) -> int | None:
    """The id of the guidance record an evidence item's ref names, ``guidance:<id>``; ``None``
    for a ref of any other form."""
    found = _GUIDANCE_RECORD.fullmatch(ref.strip())
    return None if found is None else int(found[1])


def resolve(
    conn: sqlite3.Connection, symbol: str, ref: str, policy: Policy, tax: TaxTable | None = None
) -> Resolved | None:
    """What ``ref`` names for the company ``symbol``, ``None`` where it names nothing; ``policy``
    is the effective one, which ``policy:`` and the tables read, and ``tax`` the table the
    statements are taxed with, the packaged one when ``None``."""
    return Resolver(conn, symbol, policy, tax).resolve(ref)


def same_snapshot(conn: sqlite3.Connection, cited: int, latest: int) -> bool:
    """Whether ``latest`` is the snapshot ``cited``, or a later one of the same company that
    reprices it: the same data date, method version, policy version, settings hash and value."""
    if cited == latest:
        return True
    a, b = snapshot_row(conn, cited), snapshot_row(conn, latest)
    if a is None or b is None or a.symbol != b.symbol or b.id < a.id:
        return False
    keys = ("data_date", "method_version", "policy_version", "settings_hash", "value")
    return all(getattr(a, key) == getattr(b, key) for key in keys)


def rests_on(conn: sqlite3.Connection, ref: str) -> int | None:
    """The snapshot the record a ``snapshot:``, ``review:``, ``secondary:``, ``sensitivity:`` or
    ``derived:`` ref names rests on, whichever company's it is (a derivation's, its operands');
    ``None`` for the other forms and for a record that does not exist."""
    form, path = _split(ref)
    head = path.partition("/")[0]
    if not head.isdigit():
        return None
    record_id = int(head)
    if form == "snapshot":
        return None if snapshot_row(conn, record_id) is None else record_id
    if form == "review":
        review = review_row(conn, record_id)
        return None if review is None else review.snapshot_id
    if form == "secondary":
        secondary = secondary_row(conn, record_id)
        return None if secondary is None else secondary.snapshot_id
    if form == "sensitivity":
        reading = sensitivity_row(conn, record_id)
        return None if reading is None else reading.snapshot_id
    if form == "derived":
        derivation = derivation_row(conn, record_id)
        if derivation is None:
            return None
        for operand in (derivation.a, derivation.b):  # each an earlier record: no cycle
            found = rests_on(conn, operand)
            if found is not None:
                return found
    return None


def unit_of(engine_unit: str | None) -> str | None:
    """An engine input's unit as the resolver's (module docstring); ``None`` for a word, a date
    or a unit the resolver has no name for."""
    if engine_unit is None:
        return None
    if engine_unit in ("ratio", "multiple", "years", "score"):
        return "percent" if engine_unit == "ratio" else engine_unit
    if engine_unit in _COUNTED:
        return "count"
    if engine_unit.endswith(" a share"):
        return "per-share"
    if re.fullmatch(r"[A-Z]{3}", engine_unit):
        return "currency"
    return None


class Resolver:
    """One company's refs, the store's statements, tables, consensus and peers read at most once
    for all of them."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        symbol: str,
        policy: Policy,
        tax: TaxTable | None = None,
    ) -> None:
        self.conn = conn
        self.symbol = symbol
        self.policy = policy
        self.tax = load_tax_table() if tax is None else tax
        self._cache: dict[str, Any] = {}
        self._readers: dict[str, Callable[[str], Resolved | None]] = {
            "snapshot": self._snapshot,
            "review": self._review,
            "secondary": self._secondary,
            "sensitivity": self._sensitivity,
            "fact": self._fact,
            "table": self._table,
            "estimate": self._estimate,
            "close": self._close,
            "multiple": self._multiple,
            "peer": self._peer,
            "finding": self._finding,
            "guidance": self._guidance,
            "derived": self._derived,
            "response": self._response,
            "policy": self._policy,
        }

    def resolve(self, ref: str) -> Resolved | None:
        """What ``ref`` names, ``None`` where it names nothing."""
        form, path = _split(ref)
        reader = self._readers.get(form)
        return None if reader is None else reader(path)

    def describe(self, ref: str) -> str:
        """The source of what ``ref`` names in words, one sentence for the references list
        (module docstring); the ref itself where its form or its record names nothing."""
        form, path = _split(ref)
        pieces = path.split("/")
        head, rest = pieces[0], pieces[1:]
        found: str | None = None
        match form, pieces:
            case "snapshot", _:
                found = self._snapshot_source(head, rest)
            case "review", _:
                found = self._review_source(head, rest)
            case "secondary", _ if self.resolve(ref) is not None:  # the record read, its path
                words = _secondary_words(rest)
                found = None if words is None else f"secondary valuation {head}, {words}"
            case "sensitivity", [_, i, j] if self.resolve(ref) is not None:
                found = f"sensitivity {head}, row {i} column {j}"
            case "fact", [_, line, period]:
                found = f"the {field_words(line)} line of {_period_words(period)} on file"
            case "table", [_, table, row, period]:
                cell = f"{field_words(row)}, {_period_words(period)}"
                found = f"the {field_words(table)} table, {cell}"
            case "estimate", [_, period, name]:
                found = f"the consensus for {_period_words(period)}, {field_words(name)}"
            case "close", [_, day]:
                found = f"the close of {_iso_words(day)}"
            case "multiple", [_, series, key] if series in _SERIES_WORDS:
                found = f"{_SERIES_WORDS[series]}, {_STAT_WORDS.get(key) or _iso_words(key)}"
            case "peer", [_, peer, name]:
                found = f"{peer}, {field_words(name)}"
            case "finding", [_]:
                found = self._finding_source(head)
            case "guidance", [_, name] if name in _GUIDANCE_FIGURES:
                found = self._guidance_source(head, name)
            case "derived", [_]:
                found = self._derived_source(head)
            case "response", _:
                found = self._response_source(head)
            case "policy", _ if path:
                found = f"policy {path}, {self.policy.version}"
        return ref.strip() if found is None else found

    def _once(self, key: str, read: Callable[[], Any]) -> Any:
        if key not in self._cache:
            self._cache[key] = read()
        return self._cache[key]

    def _own(self, text: str) -> bool:
        """Whether ``text`` names the company."""
        try:
            return exchange_symbol(text) == self.symbol
        except ValueError:
            return False

    def _snapshot(self, path: str) -> Resolved | None:
        head, _, rest = path.partition("/")
        row = snapshot_row(self.conn, int(head)) if head.isdigit() else None
        if row is None or row.symbol != self.symbol:
            return None
        result = row.result
        kind, _, name = rest.partition("/")
        found: tuple[Any, str | None] | None = None
        if kind in ("value", "price") and not name:
            found = getattr(result, kind), "per-share"
        elif kind == "price_to_value" and not name:
            found = result.price_to_value, "multiple"
        elif kind == "levels" and name in _LEVELS:
            found = None if result.levels is None else getattr(result.levels, name), "per-share"
        elif kind == "inputs":
            cited = next((x for x in result.inputs if x.name == name), None)
            if cited is not None:
                unit = _INPUT_UNITS.get(name) or unit_of(cited.unit)
                found = _input_value(cited.value, cited.unit, cited.note), unit
        elif kind == "intermediates" and name:
            found = _at_path(result.intermediates, name.split("/")), None
        elif kind == "phase" and name in _PHASE_FIELDS:
            found = getattr(result.phase, name), _PHASE_UNITS.get(name)
        if found is None:
            return None
        price = (kind == "price" and not name) or (kind == "inputs" and name == "price")
        outflow = kind == "inputs" and name in _OUTFLOW_INPUTS
        return _figure(*found, None, row.id, price=price, outflow=outflow)

    def _review(self, path: str) -> Resolved | None:
        head, _, rest = path.partition("/")
        row = review_row(self.conn, int(head)) if head.isdigit() else None
        if row is None or row.symbol != self.symbol:
            return None
        pieces = rest.split("/")
        found: tuple[Any, str | None] | None = None
        match pieces:
            case ["value"]:
                found = row.value, "per-share"
            case ["price_to_value"]:
                found = row.price_to_value, "multiple"
            case ["levels", name] if name in _LEVEL_COLUMNS:
                found = getattr(row, _LEVEL_COLUMNS[name]), "per-share"
            case ["bridge", n, ("delta" | "old" | "new") as field]:
                line = _nth(row.bridge, n)
                if line is not None:
                    found = line[field], "per-share" if field == "delta" else _tag_unit(line["tag"])
        return None if found is None else _figure(*found, None, row.snapshot_id)

    def _secondary(self, path: str) -> Resolved | None:
        head, _, rest = path.partition("/")
        row = secondary_row(self.conn, int(head)) if head.isdigit() else None
        if row is None or row.symbol != self.symbol:
            return None
        pieces = rest.split("/")
        projection, drivers, grid = row.projection, row.drivers, row.grid
        found: tuple[Any, str | None] | None = None
        match pieces:
            case [name] if name in _SECONDARY_FIELDS:
                column, unit = _SECONDARY_FIELDS[name]
                found = getattr(row, column), unit
            case ["levels", name] if name in _LEVEL_COLUMNS:
                found = getattr(row, _LEVEL_COLUMNS[name]), "per-share"
            case ["grid", i, j] if grid is not None:
                cells = _nth(grid["cells"], i)
                cell = None if cells is None else _nth(cells, j)
                if cell is not None:
                    found = cell, "per-share"
            case ["parts", n, ("pv" | "fcff") as field, t]:
                part = _nth(row.parts, n)
                year = None if part is None else _nth(part[field], t)
                if year is not None:
                    found = year, "currency"
            case ["parts", n, name] if name in _PART_FIELDS:
                part = _nth(row.parts, n)
                if part is not None:
                    found = part[name], _PART_FIELDS[name]
            case ["years", t, line] if projection is not None and line in _YEAR_LINES:
                year = _nth(projection["years"], t)
                if year is not None:
                    found = year[line], "currency"
            case [name] if projection is not None and name in _TERMINAL_FIGURES:
                found = projection[name], "currency"
            case ["drivers", name] if drivers is not None and name in _DRIVER_UNITS:
                found = drivers[name], _DRIVER_UNITS[name]
            case ["drivers", name, t] if drivers is not None and name in _DRIVER_LISTS:
                rate = _nth(drivers[name], t)
                if rate is not None:
                    found = rate, "percent"
        return None if found is None else _figure(*found, None, row.snapshot_id)

    def _sensitivity(self, path: str) -> Resolved | None:
        """A cell by its row and its column; a refused cell resolves with no value."""
        pieces = path.split("/")
        row = sensitivity_row(self.conn, int(pieces[0])) if pieces[0].isdigit() else None
        if row is None or row.symbol != self.symbol or len(pieces) != 3:
            return None
        i = _index(row.cells, pieces[1])
        j = None if i is None else _index(row.cells[i], pieces[2])
        if i is None or j is None:
            return None
        return _figure(row.cells[i][j], "per-share", None, row.snapshot_id)

    def _fact(self, path: str) -> Resolved | None:
        pieces = path.split("/")
        if len(pieces) != 3 or not self._own(pieces[0]):
            return None
        _, line, period = pieces
        if period == "ttm":
            trailing = self._statements().trailing
            if trailing is None or line not in _TRAILING_FIGURES:
                return None
            value = getattr(trailing, line)
            return _figure(value, _line_unit(line), period, outflow=line in _OUTFLOW_LINES)
        from fairband.reports.tables import LINES, year_lines  # tables builds its refs here

        lines = self._once("lines", lambda: year_lines(self.conn, self.symbol))
        year = lines.get(int(period)) if period.isdigit() else None
        if year is None or line not in LINES:
            return None
        return _figure(year[line], _line_unit(line), period, outflow=line in _OUTFLOW_LINES)

    def _table(self, path: str) -> Resolved | None:
        pieces = path.split("/")
        if len(pieces) != 4 or not self._own(pieces[0]):
            return None
        _, table, row, period = pieces
        from fairband.reports.tables import Table, financial_tables  # tables builds its refs here

        tables: tuple[Table, ...] = self._once(
            "tables", lambda: financial_tables(self.conn, self.symbol, self.policy, self.tax)
        )
        for found in tables:
            for r in found.rows if found.name == table else ():
                for cell in r.cells if r.name == row else ():
                    if cell.period == period:
                        outflow = row in _OUTFLOW_ROWS
                        return _figure(cell.value, cell.unit, cell.period, outflow=outflow)
        return None

    def _estimate(self, path: str) -> Resolved | None:
        pieces = path.split("/")
        if len(pieces) != 3 or not self._own(pieces[0]):
            return None
        _, period, field = pieces
        inputs = self._inputs()
        quarters = {f"{q.fiscal_year}-{q.fiscal_period}": q for q in inputs.quarter_estimates}
        years = {str(a.fiscal_year): a for a in inputs.annual_estimates}
        record = quarters.get(period) or years.get(period)
        if record is None or field in _PLAIN or field not in _field_names(record):
            return None
        return _figure(getattr(record, field), ESTIMATE_UNITS.get(field, "currency"), period, None)

    def _close(self, path: str) -> Resolved | None:
        pieces = path.split("/")
        if len(pieces) != 2 or not self._own(pieces[0]):
            return None
        day = pieces[1]
        close = next((c for d, c in self._inputs().closes if d.isoformat() == day), None)
        return None if close is None else _figure(close, "per-share", day, price=True)

    def _multiple(self, path: str) -> Resolved | None:
        pieces = path.split("/")
        if len(pieces) != 3 or not self._own(pieces[0]) or pieces[1] not in SERIES:
            return None
        _, name, key = pieces
        series: Series | None = self._once(
            f"multiple:{name}", lambda: stored_series(self.conn, self.symbol, name)
        )
        if series is None:
            return None
        if key in STATS:
            return _figure(series.stats[key], "multiple")
        value = next((v for day, v in series.points if day.isoformat() == key), None)
        return None if value is None else _figure(value, "multiple", key)

    def _peer(self, path: str) -> Resolved | None:
        pieces = path.split("/")
        if len(pieces) != 3 or not self._own(pieces[0]) or pieces[2] not in PEER_UNITS:
            return None
        _, peer, field = pieces
        found = self._once(
            "peers",
            lambda: peer_figures(
                self.conn,
                self.symbol,
                latest_deciles(self.conn),
                self.policy,
                self.tax,
                _NO_DAY,
            ),
        )
        figures = next((p for p in found.figures if p.symbol == peer), None)
        return None if figures is None else _figure(getattr(figures, field), PEER_UNITS[field])

    def _finding(self, path: str) -> Resolved | None:
        row = finding_row(self.conn, int(path)) if path.isdigit() else None
        if row is None or row.symbol != self.symbol:
            return None
        return _figure(row.value, row.unit, row.period, None)

    def _guidance(self, path: str) -> Resolved | None:
        head, _, field = path.partition("/")
        row = guidance_row(self.conn, int(head)) if head.isdigit() else None
        if row is None or row.symbol != self.symbol or field not in _GUIDANCE_FIGURES:
            return None
        unit = "percent" if field == "step" else GUIDANCE_UNITS[row.metric]
        return _figure(getattr(row, field), unit, row.period)

    def _derived(self, path: str) -> Resolved | None:
        row = derivation_row(self.conn, int(path)) if path.isdigit() else None
        if row is None or row.symbol != self.symbol:
            return None
        return _figure(row.value, row.unit, None, rests_on(self.conn, f"derived:{path}"))

    def _response(self, path: str) -> Resolved | None:
        head, slash, pointer = path.partition("/")
        row = response_row(self.conn, int(head)) if head.isdigit() else None
        text = None if row is None else response_payload(self.conn, row.id)
        if row is None or row.symbol != self.symbol or text is None:
            return None
        try:
            payload = json.loads(text)
        except ValueError:
            return None
        keys = [_unescaped(k) for k in pointer.split("/")] if slash else []
        return _figure(_at_path(payload, keys), None)

    def _policy(self, name: str) -> Resolved | None:
        values = self._once("policy", lambda: policy_json(self.policy, self.policy, {})["values"])
        cited = values.get(name)
        if cited is not None:
            value = cited["value"]
        else:
            head, _, tail = name.rpartition(".")
            cited = values.get(head) if head else None
            value = _ABSENT if cited is None else _at_path(cited["value"], [tail])
        if cited is None:
            return None
        return _figure(value, _POLICY_UNITS.get(cited["unit"]))

    def _statements(self) -> Statements:
        def read() -> Statements:
            country, _ = country_for(self.conn, self.symbol, latest_company(self.conn, self.symbol))
            return statements_for(self.conn, self.symbol, country, self.tax, _NO_DAY)

        found: Statements = self._once("statements", read)
        return found

    def _inputs(self) -> CompanyInputs:
        found: CompanyInputs = self._once(
            "inputs", lambda: build_inputs(self.conn, self.symbol, self.policy, self.tax, _NO_DAY)
        )
        return found

    def _snapshot_source(self, head: str, rest: Sequence[str]) -> str | None:
        """The snapshot, the path in words and the snapshot's price date."""
        words = _snapshot_words(rest)
        if words is None or not head.isdigit():
            return None
        row: SnapshotRow | None = self._once(
            f"snapshot {head}", lambda: snapshot_row(self.conn, int(head))
        )
        if row is None or row.symbol != self.symbol:
            return None
        priced = "" if row.price_date is None else f", priced {day_words(row.price_date)}"
        return f"snapshot {row.id}, {words}{priced}"

    def _review_source(self, head: str, rest: Sequence[str]) -> str | None:
        """The review and the path in words, a bridge line with its input's label."""
        row = review_row(self.conn, int(head)) if head.isdigit() else None
        if row is None or row.symbol != self.symbol:
            return None
        match rest:
            case ["bridge", n, field] if field in _BRIDGE_WORDS:
                line = _nth(row.bridge, n)
                label = "" if line is None else f" ({_LABELS.get(line['tag'], line['tag'])})"
                words: str | None = f"bridge line {n}{label}, {_BRIDGE_WORDS[field]}"
            case _:
                words = _figure_words(rest)
        return None if words is None else f"review {row.id}, {words}"

    def _finding_source(self, head: str) -> str | None:
        """The finding and its source as recorded."""
        row = finding_row(self.conn, int(head)) if head.isdigit() else None
        if row is None or row.symbol != self.symbol:
            return None
        return f"finding {row.id}: {row.source_ref}"

    def _guidance_source(self, head: str, name: str) -> str | None:
        """The guidance record, its metric and period, and the figure named."""
        row = guidance_row(self.conn, int(head)) if head.isdigit() else None
        if row is None or row.symbol != self.symbol:
            return None
        guided = f"{field_words(row.metric)} for {_period_words(row.period)}"
        return f"guidance record {row.id}: {guided}, the {name}"

    def _derived_source(self, head: str) -> str | None:
        """The derivation, its operation and its operands' refs."""
        row = derivation_row(self.conn, int(head)) if head.isdigit() else None
        if row is None or row.symbol != self.symbol:
            return None
        over = "" if row.years is None else f" over {row.years} years"
        return f"derivation {row.id}: the {row.operation} of {row.a} and {row.b}{over}"

    def _response_source(self, head: str) -> str | None:
        """The vendor, the endpoint and the day the response was observed."""
        row = response_row(self.conn, int(head)) if head.isdigit() else None
        if row is None or row.symbol != self.symbol:
            return None
        vendor = _PROVIDER_WORDS.get(row.provider, row.provider)
        return f"{vendor} {row.endpoint}, observed {day_words(row.observed_at.date())}"


def field_words(name: str) -> str:
    """An engine name in a reader's words: the whole name as the spec writes it (``altman_z``
    reads "Altman's Z″"), else its underscores as spaces, an abbreviation in capitals and a
    statement line's short name spelled out (``capex`` reads "capital spending")."""
    whole = _NAME_WORDS.get(name)
    return whole or " ".join(_NAME_WORDS.get(word, word) for word in name.split("_"))


def day_words(day: date) -> str:
    """A day as the report writes it, ``3 Nov 2026``."""
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def _figure_words(rest: Sequence[str]) -> str | None:
    """A snapshot's, a review's or a secondary valuation's figure or level in words."""
    match rest:
        case [name] if name in _FIGURE_WORDS:
            return _FIGURE_WORDS[name]
        case ["levels", name] if name in _LEVEL_WORDS:
            return _LEVEL_WORDS[name]
    return None


def _snapshot_words(rest: Sequence[str]) -> str | None:
    """A snapshot's path in words: a path a report cites most by its words, else an input, an
    intermediate or a classifier field by its name in words."""
    known = _SNAPSHOT_PATH_WORDS.get("/".join(rest))
    if known is not None:
        return known
    match rest:
        case ["inputs", name]:
            return f"the {field_words(name)}"
        case ["intermediates", *path] if path:
            return f"the {' '.join(field_words(key) for key in path)}"
        case ["phase", name]:
            return f"the classifier's {field_words(name)}"
    return _figure_words(rest)


def _secondary_words(rest: Sequence[str]) -> str | None:
    """A secondary valuation's path in words: its grid, its parts, its projection, its drivers."""
    match rest:
        case ["grid", i, j]:
            return f"the grid, row {i} column {j}"
        case ["parts", n, ("pv" | "fcff") as line, t]:
            return f"part {n}, year {t} {_YEAR_WORDS[line]}"
        case ["parts", n, name] if name in _PART_WORDS:
            return f"part {n}, {_PART_WORDS[name]}"
        case ["years", t, line] if line in _YEAR_WORDS:
            return f"year {t} {_YEAR_WORDS[line]}"
        case ["drivers", name] if name in _DRIVER_WORDS:
            return _DRIVER_WORDS[name]
        case ["drivers", name, t]:
            return f"the {field_words(name)} of year {t}"
    return _figure_words(rest)


def _period_words(period: str) -> str:
    """A fiscal year, a quarter or the trailing twelve months in words."""
    if period == "ttm":
        return "the trailing twelve months"
    if len(period) == 4 and period.isdecimal():
        return f"fiscal {period}"
    quarter = _QUARTER.fullmatch(period)
    return period if quarter is None else f"{quarter[2]} of fiscal {quarter[1]}"


def _iso_words(text: str) -> str:
    """An ISO date as the report writes it; any other text as it is."""
    try:
        return day_words(date.fromisoformat(text))
    except ValueError:
        return text


def _split(ref: str) -> tuple[str, str]:
    form, colon, path = ref.strip().partition(":")
    return (form, path) if colon else ("", "")


def _figure(
    value: Any,
    unit: str | None,
    period: str | None = None,
    snapshot_id: int | None = None,
    *,
    price: bool = False,
    outflow: bool = False,
) -> Resolved | None:
    """The resolved figure: a finite number, a word or ``None``; ``None`` for anything else, a
    table, a list or a step that is not there, which names no figure."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        number = float(value)
        value = number if math.isfinite(number) else None
    elif value is not None and not isinstance(value, str):
        return None
    return Resolved(value, unit, period, snapshot_id, price, outflow)


def _input_value(value: float | None, unit: str, note: str | None) -> float | str | None:
    """A tagged input's figure: its number, or a word input's word, which leads its note."""
    if value is None and unit in ("class", "phase") and note:
        return note.split(":", 1)[0].strip()
    return value


def _tag_unit(tag: str) -> str | None:
    spec = next((s for s in TAGS.values() if s.tag == tag), None)
    return None if spec is None else unit_of(spec.unit)


def _line_unit(line: str) -> str:
    if line == "eps_diluted":
        return "per-share"
    return "count" if line == "shares_diluted" else "currency"


def _nth(items: Sequence[Any], n: str) -> Any:
    """The item numbered ``n`` from 1; ``None`` where there is none."""
    k = _index(items, n)
    return None if k is None else items[k]


def _index(items: Sequence[Any], n: str) -> int | None:
    """The index of the item numbered ``n`` from 1; ``None`` where there is none."""
    return int(n) - 1 if n.isdigit() and 1 <= int(n) <= len(items) else None


def _at_path(x: Any, keys: Sequence[str]) -> Any:
    """The value at ``keys`` through dicts and lists; ``_ABSENT`` where a step is absent."""
    for key in keys:
        if isinstance(x, Mapping):
            x = x.get(key, _ABSENT)
        elif isinstance(x, list | tuple) and key.isdigit() and int(key) < len(x):
            x = x[int(key)]
        else:
            return _ABSENT
    return x


def _unescaped(key: str) -> str:
    """A JSON pointer's reference token, RFC 6901's escapes read."""
    return key.replace("~1", "/").replace("~0", "~")


def _field_names(record: Any) -> frozenset[str]:
    return frozenset(f.name for f in fields(record))
