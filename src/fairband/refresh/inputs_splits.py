"""The stock splits on file and the share basis they set (spec 2026-11-09 section 10).

``splits_for`` reads the ``split`` observations back as one ``SplitRow`` a split, oldest first. The
normalizer stores two observations a split, the numerator and the denominator, on the split date
(``split_observations``). Only the rows of the latest usable ``splits`` response are read: FMP's
list at the newest fetch is the whole truth, so a split it no longer lists, withdrawn or re-dated,
is not read though its observations stay on file; without a usable response there is no split. A
date that lacks one of the two, or whose denominator is zero, is skipped. The ratio, numerator ÷
denominator, is the new shares to one old share: 2 for a 2-for-1 split, 0.1 for a 1-for-10 reverse
split.

``apply_splits`` reads every share count and per-share figure on the share basis of the quote
date. A split dated after the newest statement period end (the trailing figures' ``period_end``)
and at or before the price date is pending (``pending_splits``); several compound, their ratios
multiplied into ρ. The vendor check of 2026-11-10 found that FMP restates its statements, street
actuals, consensus and closes to the post-split basis, but on no known day. The quote's market cap
÷ its price gives the share count of the quote date, Q, so the rule scales only what the data shows
pre-split, ``within(a, b)`` reading ``|a − b| ≤ tolerance × b`` (false for a ``b`` of zero):

- the statement side, the diluted count D, the trailing diluted EPS (the sum as a whole) and the
  street trailing EPS: pre-split when D × ρ lies within the tolerance of Q and D does not; then the
  count reads D × ρ and the two EPS figures ÷ ρ. Otherwise they are read as stored: post-split when
  D lies within the tolerance of Q and D × ρ does not, undecided when both or neither do, and
  untested without D or Q, the sentence saying which;
- the consensus, each annual and quarterly row with an EPS and a net-income mean: its implied
  count I, the net income ÷ the EPS, within the tolerance of the pre-split count P and not of the
  post-split count S reads its EPS ÷ ρ; S is D × ρ when the statements were scaled, else D, and P
  is S ÷ ρ. A row without a net-income mean, or within both counts or neither, is read as stored,
  and so is every row without a count D;
- GuruFocus's trailing EPS and EPS without non-recurring items, each observed before a pending
  split: ÷ the ratios of the pending splits dated after its observation;
- the closes and the quote never: they are FMP's, already on the new basis.

The count, the trailing EPS and the NTM EPS, when scaled, are estimates under the method
``split-scaled`` and carry a note naming the split, keyed by the engine's DATA input names:
``shares_diluted``, ``eps_ttm``, and ``ntm_eps`` when a quarterly consensus row was scaled. No DATA
input holds the annual consensus (the path steps are rates, unmoved when both years scale), the
street actuals or the GuruFocus figures, so the ``split-pending`` sentence alone names them. A
pending split puts the note ``split-pending`` on the row, its sentence naming the splits, the
figures read on the new basis and those read as stored; without one every figure is read as stored
and nothing is noted.
"""

import math
import sqlite3
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date

from fairband.engine.anchor import AnnualEstimate, QuarterEstimate, TrailingFigures
from fairband.engine.types import Flag
from fairband.store.observations import observations_for
from fairband.store.vendor import latest_response

SPLIT_SCALED = "split-scaled"
_NO_COUNT = "No diluted count is on file, so the statements and the consensus are read as stored."
_NO_QUOTE_COUNT = "The quote gives no share count, so the statements are read as stored."
_POST_SPLIT = "FMP's statements and street actuals already read on the post-split basis."
_BOTH_BASES = (
    "The diluted count lies within the tolerance of the quote's count on both bases, so the "
    "statements are read as stored."
)
_NEITHER_BASIS = (
    "The diluted count matches neither basis of the quote's count, so the statements are read as "
    "stored."
)
_TAIL = "The closes and the quote are FMP's, already on it."


@dataclass(frozen=True)
class SplitRow:
    """One split: from ``date`` on, ``numerator`` shares stand where ``denominator`` stood."""

    date: date
    numerator: float
    denominator: float

    @property
    def ratio(self) -> float:
        """The new shares to one old share, numerator ÷ denominator."""
        return self.numerator / self.denominator

    @property
    def word(self) -> str:
        """The split in words: ``2-for-1 split``, ``3-for-2 split``, ``1-for-10 reverse split``."""
        kind = "reverse split" if self.ratio < 1 else "split"
        return f"{_count(self.numerator)}-for-{_count(self.denominator)} {kind}"


@dataclass(frozen=True)
class SplitFigures:
    """The figures the rule may scale, as assembly read them."""

    shares_diluted: float | None
    trailing: TrailingFigures | None
    street_ttm_eps: float | None
    gf_eps_ttm: float | None
    gf_eps_ttm_as_of: date | None
    gf_eps_without_nri: float | None
    gf_eps_without_nri_as_of: date | None
    quarter_estimates: tuple[QuarterEstimate, ...]
    annual_estimates: tuple[AnnualEstimate, ...]


@dataclass(frozen=True)
class SplitOutcome:
    """The figures, each one the rule scaled on the new basis; the ``split-pending`` note, ``None``
    without a pending split; and the note and the method of each scaled DATA input, by the
    engine's input name (``shares_diluted``, ``eps_ttm``, ``ntm_eps``)."""

    figures: SplitFigures
    flag: Flag | None
    notes: dict[str, str]
    estimate_methods: dict[str, str]


# One side of the rule: the figures as it leaves them, its notes by DATA input name, its sentences.
type _Side = tuple[SplitFigures, dict[str, str], list[str]]


def splits_for(conn: sqlite3.Connection, symbol: str) -> tuple[SplitRow, ...]:
    """The splits of the latest usable ``splits`` response for ``symbol``, oldest first."""
    response = latest_response(conn, "fmp", "splits", symbol, {"symbol": symbol})
    if response is None:
        return ()
    fields: dict[date, dict[str, float]] = defaultdict(dict)
    for row in observations_for(conn, symbol, "split"):
        if row.response_id == response.id and row.period is not None and row.value is not None:
            fields[row.period][row.field] = float(row.value)
    out: list[SplitRow] = []
    for when in sorted(fields):
        numerator, denominator = fields[when].get("numerator"), fields[when].get("denominator")
        if numerator is None or denominator is None or denominator == 0:
            continue
        out.append(SplitRow(when, numerator, denominator))
    return tuple(out)


def pending_splits(
    splits: Sequence[SplitRow], statement_end: date | None, price_date: date | None
) -> tuple[SplitRow, ...]:
    """The splits dated after ``statement_end`` and at or before ``price_date``, oldest first;
    none when either date is unknown."""
    if statement_end is None or price_date is None:
        return ()
    found = (s for s in splits if statement_end < s.date <= price_date)
    return tuple(sorted(found, key=lambda s: s.date))


def apply_splits(
    figures: SplitFigures,
    splits: Sequence[SplitRow],
    *,
    statement_end: date | None,
    price_date: date | None,
    quote_market_cap: float | None,
    quote_price: float | None,
    tolerance: float,
) -> SplitOutcome:
    """``figures`` on the share basis of the quote date (the module docstring states the rule)."""
    pending = pending_splits(splits, statement_end, price_date)
    if not pending or statement_end is None:
        return SplitOutcome(figures, None, {}, {})
    quote_count = (
        None if quote_market_cap is None or not quote_price else quote_market_cap / quote_price
    )
    stated, statement_notes, statement = _statement_side(figures, pending, quote_count, tolerance)
    estimated, consensus_notes, consensus = _consensus_side(stated, pending, tolerance)
    out, gurufocus = _gurufocus_side(estimated, pending)
    sentence = " ".join([_head(pending, statement_end), *statement, *consensus, *gurufocus, _TAIL])
    notes = statement_notes | consensus_notes
    flag = Flag("split-pending", "Split pending", sentence)
    return SplitOutcome(out, flag, notes, dict.fromkeys(notes, SPLIT_SCALED))


def _statement_side(
    figures: SplitFigures, pending: Sequence[SplitRow], quote_count: float | None, tolerance: float
) -> _Side:
    """The diluted count × ρ and the trailing and street EPS ÷ ρ when the quote's count shows the
    count pre-split; else as stored, the sentence saying why."""
    count, ratio = figures.shares_diluted, _ratio(pending)
    if count is None:
        return figures, {}, [_NO_COUNT]
    if quote_count is None:
        return figures, {}, [_NO_QUOTE_COUNT]
    as_stored = _within(count, quote_count, tolerance)
    as_scaled = _within(count * ratio, quote_count, tolerance)
    if as_stored:
        return figures, {}, [_BOTH_BASES if as_scaled else _POST_SPLIT]
    if not as_scaled:
        return figures, {}, [_NEITHER_BASIS]
    r, named = _count(ratio), _named(pending)
    notes = {"shares_diluted": f"×{r} for {named}"}
    per_share: list[str] = []
    trailing, street = figures.trailing, figures.street_ttm_eps
    if trailing is not None and trailing.eps_diluted is not None:
        trailing = replace(trailing, eps_diluted=trailing.eps_diluted / ratio)
        notes["eps_ttm"] = f"÷{r} for {named}"
        per_share.append("the trailing EPS")
    if street is not None:
        street = street / ratio
        per_share.append("the street actuals")
    scaled = replace(
        figures, shares_diluted=count * ratio, trailing=trailing, street_ttm_eps=street
    )
    if not per_share:
        return scaled, notes, [f"The diluted count (×{r}) is read on the post-split basis."]
    joint = ", " if len(per_share) == 2 else " and "
    figures_read = f"The diluted count (×{r}){joint}{' and '.join(per_share)} (÷{r})"
    return scaled, notes, [f"{figures_read} are read on the post-split basis."]


def _consensus_side(figures: SplitFigures, pending: Sequence[SplitRow], tolerance: float) -> _Side:
    """Each consensus EPS ÷ ρ whose implied count shows it pre-split, against S, the count as the
    statement side left it, and P = S ÷ ρ; every row as stored without a count. The NTM EPS, which
    the quarterly rows make, carries the note when one of them was scaled."""
    if figures.shares_diluted is None:
        return figures, {}, []
    ratio = _ratio(pending)
    r, counts = _count(ratio), (figures.shares_diluted / ratio, figures.shares_diluted)
    annual, annual_scaled, annual_left = _consensus(
        figures.annual_estimates, ratio, counts, tolerance
    )
    quarters, quarters_scaled, quarters_left = _consensus(
        figures.quarter_estimates, ratio, counts, tolerance
    )
    notes: dict[str, str] = {}
    spans = [_years_span(annual_scaled)] if annual_scaled else []
    if quarters_scaled:
        span = _quarters_span(quarters_scaled)
        spans.append(f"the {span}")
        notes["ntm_eps"] = f"the consensus {span} ÷{r} for {_named(pending)}"
    sentences = [f"The consensus EPS for {' and for '.join(spans)} is read ÷{r}."] if spans else []
    left = [rows for rows in (_years_list(annual_left), _quarters_list(quarters_left)) if rows]
    if left:
        unmeaned = " and for ".join(left)
        sentences.append(
            f"The consensus EPS for {unmeaned} has no net-income mean and is read as stored."
        )
    scaled = replace(figures, annual_estimates=annual, quarter_estimates=quarters)
    return scaled, notes, sentences


def _consensus[E: (QuarterEstimate, AnnualEstimate)](
    rows: Sequence[E], ratio: float, counts: tuple[float, float], tolerance: float
) -> tuple[tuple[E, ...], tuple[E, ...], tuple[E, ...]]:
    """The rows with each pre-split EPS ÷ ``ratio``, the rows scaled, and the rows with an EPS and
    no net-income mean; ``counts`` are the pre-split and the post-split counts."""
    before, after = counts
    out: list[E] = []
    scaled: list[E] = []
    left: list[E] = []
    for row in rows:
        if row.eps is not None and row.net_income is None:
            left.append(row)
        elif row.eps and row.net_income is not None:
            implied = row.net_income / row.eps
            if _within(implied, before, tolerance) and not _within(implied, after, tolerance):
                scaled.append(row)
                row = replace(row, eps=row.eps / ratio)
        out.append(row)
    return tuple(out), tuple(scaled), tuple(left)


def _gurufocus_side(
    figures: SplitFigures, pending: Sequence[SplitRow]
) -> tuple[SplitFigures, list[str]]:
    """Both GuruFocus EPS figures read by ``_observed``; one sentence for each observation date
    and ratio. No DATA input holds them by name, so they carry no note."""
    ttm, ttm_read = _observed(figures.gf_eps_ttm, figures.gf_eps_ttm_as_of, pending)
    clean, clean_read = _observed(
        figures.gf_eps_without_nri, figures.gf_eps_without_nri_as_of, pending
    )
    sentences = list(dict.fromkeys(s for s in (ttm_read, clean_read) if s is not None))
    return replace(figures, gf_eps_ttm=ttm, gf_eps_without_nri=clean), sentences


def _observed(
    value: float | None, as_of: date | None, pending: Sequence[SplitRow]
) -> tuple[float | None, str | None]:
    """A GuruFocus figure ÷ the ratios of the pending splits dated after its observation, and the
    sentence that says so; as stored, with none, when no pending split followed it."""
    after = () if as_of is None else tuple(s for s in pending if s.date > as_of)
    if value is None or as_of is None or not after:
        return value, None
    ratio = _ratio(after)
    return value / ratio, f"GuruFocus's EPS observed {_day(as_of)} is read ÷{_count(ratio)}."


def _ratio(splits: Sequence[SplitRow]) -> float:
    """ρ, the splits' ratios compounded."""
    return math.prod(s.ratio for s in splits)


def _within(a: float, b: float, tolerance: float) -> bool:
    """``a`` lies within ``tolerance`` of ``b``, as a share of ``b``; never for a ``b`` of zero."""
    return b != 0 and abs(a - b) <= tolerance * b


def _head(pending: Sequence[SplitRow], statement_end: date) -> str:
    """``A 2-for-1 split of 28 Jan 2027 falls after the newest statement (30 Sep 2026).``"""
    splits = _and([f"{_article(s)} {s.word} of {_day(s.date)}" for s in pending])
    verb = "falls" if len(pending) == 1 else "fall"
    newest = _day(statement_end)
    return f"{splits[0].upper()}{splits[1:]} {verb} after the newest statement ({newest})."


def _years_span(rows: Sequence[AnnualEstimate]) -> str:
    first, last = rows[0].fiscal_year, rows[-1].fiscal_year
    return f"fiscal {first}" if first == last else f"fiscal {first} to {last}"


def _quarters_span(rows: Sequence[QuarterEstimate]) -> str:
    quarters = "quarter" if len(rows) == 1 else "quarters"
    return f"{quarters} to {_day(rows[-1].period_end)}"


def _years_list(rows: Sequence[AnnualEstimate]) -> str:
    return f"fiscal {_and([str(a.fiscal_year) for a in rows])}" if rows else ""


def _quarters_list(rows: Sequence[QuarterEstimate]) -> str:
    if not rows:
        return ""
    quarters = "quarter" if len(rows) == 1 else "quarters"
    return f"the {quarters} ending {_and([_day(q.period_end) for q in rows])}"


def _named(splits: Sequence[SplitRow]) -> str:
    """``the 2-for-1 split of 15 Oct 2026``, each further split after ``and``."""
    return _and([f"the {s.word} of {_day(s.date)}" for s in splits])


def _article(split: SplitRow) -> str:
    """``an`` before a numerator read with a vowel (8, 11, 18, 80), else ``a``."""
    spoken = _count(split.numerator)
    return "an" if spoken.startswith("8") or spoken.split(".")[0] in ("11", "18") else "a"


def _and(items: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``."""
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _day(day: date) -> str:
    """``15 Oct 2026``."""
    return f"{day.day} {day:%b %Y}"


def _count(n: float) -> str:
    """A whole number as an integer (``2``), any other to two decimals with trailing zeros dropped
    (``1.5``, ``1.05``)."""
    return str(int(n)) if n.is_integer() else f"{n:.2f}".rstrip("0").rstrip(".")
