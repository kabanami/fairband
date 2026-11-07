"""GuruFocus payloads to observations, the summary's scores and the key ratios' EPS, and the
trailing P/E series to its rows (``pe_ttm_rows``), which the multiples history reads.

- ``gf-score`` (``summary_observations``): ``moat_score`` (unit ``score``), ``z2score`` (Altman
  Z″) and ``depositary_receipt_ratio`` (unit ``ratio`` both) from the legacy summary's
  ``summary.company_data`` (gurufocus-dependencies; source-evidence P21).
- ``gf-ratio`` (``keyratios_observations``): ``eps_ttm`` from ``"EPS (TTM)"`` and
  ``eps_without_nri`` from ``"EPS without NRI"``, unit ``per-share`` (source-evidence P22). The
  key-ratios response is an object of category objects (``{"Basic": {...}, "Fundamental": {...},
  "Valuation Ratio": {...}, ...}``) and the category that holds a key is not part of its name, so
  every category is searched in response order and the first one that holds the key wins.

Every row has ``period`` ``None`` and ``as_of`` the observed date: these are current values, and
GuruFocus gives no publication timestamp for them (P21). A key the response lacks, or a value that
does not parse, gives a row with no value. A payload without the expected shape gives no rows: a
summary without a ``summary.company_data`` object, or key ratios without a category object (an
``{"error": ...}`` body arrives with HTTP 200); the caller records the failed shape. Nothing here
raises on vendor data.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fairband.store.observations import ObservationRow
from fairband.vendors._fmp_parse import PER_SHARE, Source, number

SCORE, RATIO = "score", "ratio"

type _Fields = tuple[tuple[str, str, str], ...]  # (field, GuruFocus key, unit)

_SUMMARY: _Fields = (
    ("moat_score", "moat_score", SCORE),
    ("z2score", "z2score", RATIO),
    ("depositary_receipt_ratio", "depositary_receipt_ratio", RATIO),
)
_KEYRATIOS: _Fields = (
    ("eps_ttm", "EPS (TTM)", PER_SHARE),
    ("eps_without_nri", "EPS without NRI", PER_SHARE),
)


def num(value: Any) -> Decimal | None:
    """A finite ``Decimal`` from a JSON number or a numeric string, else ``None``.

    GuruFocus sends most numbers as strings (``"4.37"``) and marks a missing value with ``"-"``,
    ``"N/A"``, an empty string or null; each of those is ``None``, as are a boolean, NaN, an
    infinity and any other word (``"At Loss"``). Surrounding whitespace is ignored; nothing else is
    stripped, so a percentage string (``"12.5%"``) or a thousands separator does not parse.
    """
    return number(value)


def summary_observations(
    payload: Any, symbol: str, response_id: int, observed_at: datetime, entered_at: datetime
) -> list[ObservationRow]:
    """The three ``gf-score`` rows from ``summary.company_data``; none without it."""
    summary = payload.get("summary") if isinstance(payload, dict) else None
    company = summary.get("company_data") if isinstance(summary, dict) else None
    if not isinstance(company, dict):
        return []
    source = Source(symbol, response_id, observed_at, entered_at)
    as_of = observed_at.date()
    return [
        source.observation("gf-score", None, name, num(company.get(key)), unit, as_of)
        for name, key, unit in _SUMMARY
    ]


def keyratios_observations(
    payload: Any, symbol: str, response_id: int, observed_at: datetime, entered_at: datetime
) -> list[ObservationRow]:
    """The two ``gf-ratio`` rows, each read from the first category that holds its key; none when
    the payload holds no category object."""
    values = payload.values() if isinstance(payload, dict) else ()
    categories = [category for category in values if isinstance(category, dict)]
    if not categories:
        return []
    source = Source(symbol, response_id, observed_at, entered_at)
    as_of = observed_at.date()
    out: list[ObservationRow] = []
    for name, key, unit in _KEYRATIOS:
        raw = next((category[key] for category in categories if key in category), None)
        out.append(source.observation("gf-ratio", None, name, num(raw), unit, as_of))
    return out


def pe_ttm_rows(payload: Any) -> list[tuple[date, float | None]] | None:
    """The ``pettm`` series' rows in payload order, each day with its trailing P/E, ``None`` for a
    loss; ``None`` for a payload that is not a list holding a dated row, or whose dated rows hold
    no point above zero: GuruFocus answers some failures with HTTP 200 and a JSON body, and its
    catch-all with every value zero.

    An indicator row is ``[date, open, high, low, close]``, the close the day's value, or
    ``[date, value]`` (the stocks repository's notes, section 22). A value that is not a positive
    number is a loss: GuruFocus writes a loss day as ``"At Loss"`` and three zeros, and some series
    as a negative multiple. A row whose first element is not an ISO date is left out.
    """
    if not isinstance(payload, list):
        return None
    rows: list[tuple[date, float | None]] = []
    for row in payload:
        if not isinstance(row, list) or len(row) < 2 or not isinstance(row[0], str):
            continue
        try:
            day = date.fromisoformat(row[0])
        except ValueError:
            continue
        value = num(row[-1] if len(row) >= 5 else row[1])
        rows.append((day, float(value) if value is not None and value > 0 else None))
    return rows if any(value is not None for _, value in rows) else None
