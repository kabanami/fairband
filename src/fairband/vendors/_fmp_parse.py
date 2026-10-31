"""The parsing primitives the FMP normalizers share: rows, dates, numbers and provenance.

Nothing here raises on vendor data. A payload that is not a list gives no rows, a row that is not
an object is dropped, and a value that does not parse is ``None``.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fairband.store.facts import FactRow
from fairband.store.observations import ObservationRow

MONEY, SHARES, PER_SHARE, COUNT = "currency", "shares", "per-share", "count"


@dataclass(frozen=True)
class Source:
    """The provenance every row of one response shares; builds its fact and observation rows."""

    symbol: str
    response_id: int
    observed_at: datetime
    entered_at: datetime

    def fact(
        self,
        row: Mapping[str, Any],
        dataset: str,
        period_end: date,
        field: str,
        value: Decimal | None,
        unit: str,
        reason: str | None,
    ) -> FactRow:
        """An observed fact as of ``period_end``, labelled from the row's ``fiscalYear``,
        ``period`` and ``reportedCurrency``."""
        return FactRow(
            symbol=self.symbol,
            dataset=dataset,
            period_end=period_end,
            fiscal_year=whole(row.get("fiscalYear")),
            fiscal_period=text(row.get("period")),
            field=field,
            value=value,
            unit=unit,
            currency=text(row.get("reportedCurrency")),
            kind="observed",
            estimate_method=None,
            missing_reason=reason,
            as_of=period_end,
            observed_at=self.observed_at,
            entered_at=self.entered_at,
            response_id=self.response_id,
        )

    def observation(
        self,
        dataset: str,
        period: date | None,
        field: str,
        value: Decimal | None,
        unit: str | None,
        as_of: date,
    ) -> ObservationRow:
        return ObservationRow(
            symbol=self.symbol,
            dataset=dataset,
            period=period,
            field=field,
            value=value,
            unit=unit,
            as_of=as_of,
            observed_at=self.observed_at,
            entered_at=self.entered_at,
            response_id=self.response_id,
        )


def objects(payload: Any) -> Iterator[dict[str, Any]]:
    """The object rows of a list payload."""
    if isinstance(payload, list):
        yield from (row for row in payload if isinstance(row, dict))


def dated(payload: Any) -> Iterator[tuple[dict[str, Any], date]]:
    """Each object row with a parseable ``date``, and that date; the others are skipped."""
    for row in objects(payload):
        when = parse_date(row.get("date"))
        if when is not None:
            yield row, when


def number(raw: Any) -> Decimal | None:
    """A finite ``Decimal`` from a JSON number or a numeric string, else ``None``."""
    if isinstance(raw, bool) or not isinstance(raw, int | float | str):
        return None
    try:
        value = Decimal(str(raw).strip())
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def whole(raw: Any) -> int | None:
    """An integer from a whole number or a numeric string such as ``"2025"``."""
    value = number(raw)
    return int(value) if value is not None and value == value.to_integral_value() else None


def parse_date(raw: Any) -> date | None:
    """The date of an ISO date or date-time string."""
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.strip()).date()
    except ValueError:
        return None


def text(raw: Any) -> str | None:
    """A non-empty stripped string, else ``None``."""
    return raw.strip() or None if isinstance(raw, str) else None
