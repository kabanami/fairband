"""The universe: one FMP screener call turned into the ``companies`` rows of a refresh (spec 6.1).

``build_universe`` refuses to run inside a transaction. It reads the newest screener response
observed less than ``reuse_hours`` before ``now`` (stored as ``fetch`` stores a call: provider
``fmp``, endpoint ``screener``, params ``{}``, no symbol), else calls ``Fmp.screener`` and stores
the response, its body scrubbed of ``secrets``. Either way the rows are parsed from the scrubbed
text, so no key reaches a ``companies`` row. Then, per screener row in payload order:

1. the exchange, upper-cased, is not one of ``policy.universe.exchanges`` (an OTC listing, or no
   exchange): skipped;
2. an ETF, a fund, or not actively trading: skipped;
3. no market cap, or one below ``cap_floor_usd``: skipped;
4. the symbol is one of ``manual_exclusions``: recorded, not eligible, ``"manual exclusion"``,
   whatever the rules below say;
5. the symbol is one of ``manual_admissions``: admitted as in rule 9, whatever its industry, name
   or symbol, so the rules below are not checked;
6. the industry is excluded (below): recorded, not eligible, ``"industry: <industry>"``;
7. the name matches one of ``name_exclude_patterns`` (``re.search``, ignoring case), a note, a
   debenture or a preferred share whose symbol carries no suffix: recorded, not eligible,
   ``"name pattern"``;
8. the symbol matches one of ``symbol_exclude_patterns`` (``re.search``): recorded, not eligible,
   ``"symbol pattern"``;
9. else admitted, eligible, in the cap band of the largest floor at or below its market cap.

A skipped row stores nothing (spec 6.1 records only the listings that fail the industry or symbol
rule, and the growth routes spec 5.17 adds the name rule); ``UniverseResult.excluded`` counts it
under ``"skipped"`` so the calibration can show it. A row whose symbol an earlier row already
recorded is skipped too, so the first row recorded is kept.
Symbols are in the exchange form ``screener_rows`` returns (``BRK.B``, ``XYZ.U``), and so are the
manual exclusions and admissions, matched exactly. The symbols rule 5 admits are logged in one
INFO line in screener order, ``manual admission: V, MA``, when there are any. A recorded row
carries the screener's name, exchange, sector, industry, country and market cap; ``is_adr`` is
false and ``currency`` ``None`` because the screener does not carry them (the profile and the
statements give them, ``refresh.inputs``); only an admitted row has a cap band. The rows go in one
transaction, with ``observed_at`` the screener response's.

The industry match: the policy lists FMP's industry strings for banks, insurers, REITs and shell
companies (SPACs), and six financial industries FMP files lenders, insurers and investment banks
under, taken from FMP's published vocabulary; without a live key, the live screener's strings are
unconfirmed.
So the industry and each entry are normalized (lower-cased, each hyphen, en dash and em dash made
a space, whitespace collapsed), and an industry is excluded when it equals an entry or starts with
an entry and a space. The bare ``Banks``, ``Insurance`` and ``REIT`` entries then also cover a
string the list does not name, in any dash style: ``Banks—Regional``, ``Insurance Brokers``,
``REIT - Data Center``; ``Banking Software`` is not excluded (``banking`` is not ``banks``). The
first full refresh confirms the live vocabulary: its calibration counts the exclusions by reason,
so a leak shows.

A ``VendorError`` from the screener is stored as ``fetch`` stores one (its status, its scrubbed
message, no payload) and propagates. A payload that gives no rows is stored with the error
``"unusable payload: <the first 80 characters>"``, so it is never reused, and raises
``ValueError("screener returned no rows")``.
"""

import json
import logging
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from fairband.policy import Policy, UniversePolicy
from fairband.store.companies import CompanyRow, insert_companies
from fairband.store.vendor import latest_response, record_response, response_payload
from fairband.vendors.fmp import Fmp
from fairband.vendors.http import VendorError
from fairband.vendors.normalize_fmp import ScreenerRow, screener_rows
from fairband.vendors.scrub import scrub

logger = logging.getLogger("fairband.refresh")

PROVIDER = "fmp"
ENDPOINT = "screener"
SKIPPED = "skipped"
_PARAMS: dict[str, str] = {}
_REASONS = ("industry", "name pattern", "symbol pattern", "manual exclusion", SKIPPED)
_DETAIL_CHARS = 80  # of an unusable payload, kept as its error
_DASHES = re.compile("[-\u2013\u2014]")  # hyphen, en dash, em dash


@dataclass(frozen=True)
class UniverseResult:
    """``admitted`` holds the admitted symbols in screener order. ``excluded`` counts the rows not
    admitted by reason, every reason present: ``industry``, ``name pattern``, ``symbol pattern``
    and ``manual exclusion`` (recorded with that reason) and ``skipped`` (not recorded)."""

    refresh_id: int
    admitted: tuple[str, ...]
    excluded: dict[str, int]


def build_universe(
    conn: sqlite3.Connection,
    fmp: Fmp,
    policy: Policy,
    refresh_id: int,
    now: datetime,
    secrets: Sequence[str],
) -> UniverseResult:
    """Record ``refresh_id``'s universe from the screener and return what was admitted.

    ``now`` judges the stored response's freshness; ``secrets`` are the vendor keys, scrubbed from
    every stored text. Raises ``ValueError`` when ``conn`` is in a transaction or the screener
    gives no rows, and lets a ``VendorError`` through.
    """
    if conn.in_transaction:
        raise ValueError("build_universe must not run inside a transaction")
    rows, observed_at = _screener(conn, fmp, policy, now, secrets)
    universe = policy.universe
    exchanges = {exchange.upper() for exchange in universe.exchanges}
    names = [re.compile(pattern, re.IGNORECASE) for pattern in universe.name_exclude_patterns]
    symbols = [re.compile(pattern) for pattern in universe.symbol_exclude_patterns]
    recorded: dict[str, CompanyRow] = {}
    admitted: list[str] = []
    excluded = dict.fromkeys(_REASONS, 0)
    for row in rows:
        if row.symbol in recorded or not _listed(row, universe, exchanges):
            excluded[SKIPPED] += 1
            continue
        reason = _exclusion(row, universe, names, symbols)
        if reason is None:
            admitted.append(row.symbol)
        else:
            excluded[reason.partition(":")[0]] += 1
        recorded[row.symbol] = _company(row, refresh_id, observed_at, reason, universe)
    insert_companies(conn, list(recorded.values()))
    by_list = [symbol for symbol in admitted if symbol in universe.manual_admissions]
    if by_list:
        logger.info("manual admission: %s", ", ".join(by_list))
    return UniverseResult(refresh_id, tuple(admitted), excluded)


def _screener(
    conn: sqlite3.Connection,
    fmp: Fmp,
    policy: Policy,
    now: datetime,
    secrets: Sequence[str],
) -> tuple[list[ScreenerRow], datetime]:
    """The screener rows and when they were observed: from the newest fresh stored response, else
    from a new call, which is stored first."""
    latest = latest_response(conn, PROVIDER, ENDPOINT, None, _PARAMS)
    if latest is not None and now - latest.observed_at < timedelta(
        hours=policy.refresh.reuse_hours
    ):
        stored = response_payload(conn, latest.id)
        rows = _rows(stored) if stored is not None else []
        if rows:
            return rows, latest.observed_at
    try:
        response = fmp.screener()
    except VendorError as exc:
        message = scrub(str(exc), secrets)
        record_response(conn, PROVIDER, ENDPOINT, _PARAMS, None, exc.status, None, message, now)
        raise
    payload = scrub(response.text, secrets)
    rows = _rows(payload)
    # The payload was scrubbed before it is cut, so no part of a key is left.
    error = None if rows else f"unusable payload: {' '.join(payload.split())[:_DETAIL_CHARS]}"
    record_response(
        conn,
        PROVIDER,
        ENDPOINT,
        _PARAMS,
        None,
        response.status,
        payload,
        error,
        response.observed_at,
    )
    if not rows:
        raise ValueError("screener returned no rows")
    return rows, response.observed_at


def _rows(payload: str) -> list[ScreenerRow]:
    """The screener rows of a scrubbed payload; none when it is not JSON."""
    try:
        return screener_rows(json.loads(payload))
    except json.JSONDecodeError:
        return []


def _listed(row: ScreenerRow, universe: UniversePolicy, exchanges: set[str]) -> bool:
    """Whether the row passes the silent filters: the exchange, the kind of listing, the floor."""
    return (
        row.exchange is not None
        and row.exchange.upper() in exchanges
        and not (row.is_etf or row.is_fund)
        and row.is_actively_trading
        and row.market_cap is not None
        and row.market_cap >= universe.cap_floor_usd
    )


def _exclusion(
    row: ScreenerRow,
    universe: UniversePolicy,
    names: Sequence[re.Pattern[str]],
    symbols: Sequence[re.Pattern[str]],
) -> str | None:
    """The reason a listing that passes the silent filters is not admitted, if any. The manual
    exclusions come first, then the manual admissions, which pass whatever the other rules say."""
    if row.symbol in universe.manual_exclusions:
        return "manual exclusion"
    if row.symbol in universe.manual_admissions:
        return None
    if row.industry is not None and _excluded_industry(row.industry, universe.excluded_industries):
        return f"industry: {row.industry}"
    if row.name is not None and any(pattern.search(row.name) for pattern in names):
        return "name pattern"
    if any(pattern.search(row.symbol) for pattern in symbols):
        return "symbol pattern"
    return None


def _excluded_industry(industry: str, excluded: Sequence[str]) -> bool:
    """Whether ``industry``, normalized, equals a normalized entry or starts with one and a space."""
    name = _normalized(industry)
    entries = (_normalized(entry) for entry in excluded)
    return any(name == entry or name.startswith(f"{entry} ") for entry in entries)


def _normalized(industry: str) -> str:
    """Lower-cased, each hyphen, en dash and em dash a space, whitespace collapsed."""
    return " ".join(_DASHES.sub(" ", industry.lower()).split())


def _company(
    row: ScreenerRow,
    refresh_id: int,
    observed_at: datetime,
    reason: str | None,
    universe: UniversePolicy,
) -> CompanyRow:
    band = None
    if reason is None and row.market_cap is not None:
        band = _cap_band(row.market_cap, universe.cap_bands)
    return CompanyRow(
        symbol=row.symbol,
        refresh_id=refresh_id,
        name=row.name,
        exchange=row.exchange,
        sector=row.sector,
        industry=row.industry,
        country=row.country,
        currency=None,
        is_adr=False,
        cap_band=band,
        market_cap=row.market_cap,
        eligible=reason is None,
        exclusion_reason=reason,
        observed_at=observed_at,
    )


def _cap_band(market_cap: Decimal, bands: Sequence[tuple[float, str]]) -> str | None:
    """The label of the largest floor at or below ``market_cap``."""
    return next(
        (label for floor, label in sorted(bands, reverse=True) if market_cap >= floor), None
    )
