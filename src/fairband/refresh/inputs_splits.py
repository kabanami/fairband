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
date. Each trailing period (``periods``: the four quarters, or the two half-years of a half-yearly
reporter, or the fiscal year on the fallback, oldest first) is read by its own period end: its ρ
is the product of the ratios of the splits dated after its end and at or before the price date. A
split is pending (``pending_splits``) when it falls after the oldest trailing period's end and at
or before the price date, so for about a year after a split, until every trailing period
postdates it. The vendor check of 2026-11-10 found that
FMP restates its statements, street actuals, consensus and closes to the post-split basis, but on
no known day. The quote's market cap ÷ its price gives the share count of the quote date, Q, so the
rule scales only what the data shows pre-split, ``within(a, b)`` reading ``|a − b| ≤ tolerance ×
b`` (false for a ``b`` of zero):

- the diluted count D (the newest quarter's, else the newest fiscal year's): against Q with the
  newest period's ρ, pre-split when D × ρ lies within the tolerance of Q and D does not, and then it
  reads D × ρ. It is read as stored when D lies within Q and D × ρ does not (post-split), and with
  the statements when both or neither do, or without Q, the sentence saying which. With every
  pending split before the newest period's end, ρ is 1: D is on the quote's basis by construction
  and needs no Q. S, the count on the quote's basis, is D × ρ when scaled, else D;
- each trailing period with a split after its end, on its own count: the newest against Q by the
  test D takes, the older ones against S, pre-split when the count × the period's ρ lies within the
  tolerance and the count does not. A pre-split period's EPS and its street actual (the one at its
  end) read ÷ its ρ; a period without a count, or whose count fits both bases or neither, is read
  as stored and named with its reason. The trailing EPS is then
  the sum of the periods' EPS when each has one, and the street trailing EPS the sum of the
  actuals, one a period (``SplitFigures.street_ttm_eps``). So on the fiscal-year fallback the year
  is judged by its own count, and a trailing sum of periods on two bases is read on one;
- the consensus, by the splits after the newest statement period end (none when the newest
  period's ρ is 1): each annual and quarterly row ending after that end (the rows the engine can
  read: the NTM window, the base year and the path years) with an EPS and a net-income mean: its
  implied count I, the net income ÷ the EPS, within the tolerance of the pre-split count P and not
  of the post-split count S reads its EPS ÷ ρ, with P = S ÷ ρ. A row without a net-income mean,
  with an EPS of zero, or with an implied count within both counts or neither is read as stored
  and named with its reason; every row without a count D is read as stored, the statement side's
  sentence saying so. A row ending at or before the newest statement period end is already
  reported: read as stored and never named;
- the closes and the quote never: they are FMP's, already on the post-split basis.

A reverse split prints its inverse: ``÷10`` on the count and ``×10`` on the per-share figures for a
1-for-10.

The count, the trailing EPS, the street trailing EPS and the NTM EPS, when scaled, are estimates
under the method ``split-scaled`` and carry a note naming the split, keyed by the engine's DATA
input names: ``shares_diluted``, ``eps_ttm``, ``street_ttm_eps``, and ``ntm_eps`` when a scaled
quarterly row is in the NTM window the engine reads (``ntm_window`` on the trailing figures'
cadence: the four quarters, or the two half-years). The notes of the two trailing EPS figures say
"on 3 of 4 quarters" when not every period scaled; a half-yearly reporter's notes name its periods
half-years ("on 1 of 2 half-years"), and the quarterly consensus rows are named by the NTM window's
cadence, else the trailing figures'. No DATA input holds the annual consensus EPS (the path steps
are rates, unmoved when both years scale), so the ``split-pending`` sentence alone names it. A
pending split puts the note ``split-pending`` on the row, its sentence naming the splits and the
newest trailing period they follow, the figures read on the new basis and the periods they were
scaled on, and those read as stored with the reason: the statement side's when it scaled nothing
(FMP's figures already post-split only when the count and every period tested read post-split),
each period left and each consensus row left; without one every figure is read as stored and
nothing is noted.

``apply_splits`` first reads an ADR's statements on the quote's share basis (spec 2026-11-10
section 6.1, spec 2026-11-19 6.2) when FMP flags the row as an ADR (``is_adr``), the quote gives
its count Q and a diluted count D is on file; a row without the flag reads as the split rule alone
reads it, whatever its counts. FMP's statements hold the listed-share (ADS) count, but on some
periods one off by a whole number or its inverse, the depositary's ratio. No vendor on file states
the ratio, so ``found_ratio`` finds it from the counts:

- a count c *differs* from the count A it is judged against when neither c nor c × the ratio of
  the pending splits after its period's end lies within the tolerance of A. For such a count the
  multiple m is A ÷ c, then A ÷ (c × the splits' ratio). At m of 1.5 or more the candidate is the
  whole number n nearest m, the factor n; at 1 ÷ 1.5 or less the whole number n nearest 1 ÷ m, the
  factor 1 ÷ n; between the two there is none. A candidate fits when c × the factor, × the splits'
  ratio on the second multiple, lies within the tolerance of A;
- ρ is the n of the first count that differs and fits: D against Q; then, when D does not differ,
  each trailing period oldest first, the newest against Q and each older one against D as stored.
  A period that differs and fits no whole number is passed over, and so is a period without a
  count; D so is the refusal "share basis unclear: the newest period's count <D> against the
  quote's <Q>", every figure as given. With no ratio found the row reads as the split rule alone
  reads it. The counts cannot say which way the depositary's ratio runs, so ρ is always the whole
  number, and no whole number is too large to be one.

With ρ found, ``_basis_side`` reads the counts by it:

- a count c fits a factor f in 1, ρ and 1 ÷ ρ, tried in that order, when c × f, or c × f × the
  ratio of the splits after its period's end, lies within the tolerance of the count it is judged
  against. D is judged against Q, then each trailing period on its own count, the newest against
  Q and the older ones against S, D on the quote's basis;
- one factor fitting, or two that read c at one multiple (a depositary's ratio change that FMP
  lists as a split), is the factor: the count reads × f and the period's EPS ÷ f, the trailing
  EPS the sum of the periods' when each has one, and the split rule then judges the figures so
  read as it judges any;
- a period whose count fits no factor, or two at different multiples, is read as stored and
  named with its reason, and so, when the rule notes anything, is a period without a count; D so
  is the refusal "share basis unclear: the newest period's count <D> against the quote's <Q>",
  every figure as given;
- the street actuals, the consensus and the closes are on the quote's basis already and take
  no factor.

The count and the trailing EPS so scaled are estimates under the method ``basis-scaled``, which
takes the place of ``split-scaled`` on a figure both rules scaled, the note naming the split, then
the factor. The row's note ``basis-scaled`` names the factor, the periods scaled and the two
counts, and each period read as stored with its reason; with every factor 1 and no period so
named there is none. ρ itself is the DATA input ``adr_ratio`` (``SplitOutcome.adr_ratio``), an
estimate under the method ``counts-ratio`` whose note names the count it was found on and the
count that count was judged against.
"""

import math
import sqlite3
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal

from fairband.engine.anchor import (
    AnnualEstimate,
    Cadence,
    QuarterEstimate,
    TrailingFigures,
    ntm_window,
)
from fairband.engine.types import Flag
from fairband.refresh.inputs_statements import PERIOD_NOUNS, TrailingPeriod
from fairband.store.observations import observations_for
from fairband.store.vendor import latest_response

SPLIT_SCALED = "split-scaled"
BASIS_SCALED = "basis-scaled"
COUNTS_RATIO = "counts-ratio"
# A multiple at or above this, or at or below its inverse, has a whole number for a candidate.
_PLAIN = 1.5
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
_NOTHING_TO_SCALE = "No trailing EPS or street actuals are on file to scale."
# Why a consensus row ending after the newest statement is read as stored.
_NO_MEAN = "no net-income mean"
_ZERO_EPS = "an EPS of zero"
_BOTH_COUNTS = "a count fitting both bases"
_NEITHER_COUNT = "a count fitting neither basis"
# The per-share DATA inputs the statement side may scale, in words.
_PER_SHARE = {"eps_ttm": "the trailing EPS", "street_ttm_eps": "the street actuals"}
_TAIL = "The closes and the quote are FMP's, already on the post-split basis."

# Where a count stands against another: pre-split, post-split, or on both bases or neither.
type _Basis = Literal["pre", "post", "both", "neither"]
# A trailing period's verdict: its count's basis, ``None`` without a count.
type _Verdict = _Basis | None
# Why a judged period is read as stored, said of one period and of several; ``{}`` is the count it
# was judged against.
_PERIOD_LEFT: dict[_Verdict, tuple[str, str]] = {
    "both": ("fits both bases of {}", "fit both bases of {}"),
    "neither": ("fits neither basis of {}", "fit neither basis of {}"),
    None: ("has no share count", "have no share count"),
}
# Where a count stands on the listed-share basis when no one factor reads it: no factor fits, or
# two at different multiples.
type _Unclear = Literal["none", "two"]
# Why a period is read as stored on the listed-share basis, as ``_PERIOD_LEFT`` says it.
_BASIS_LEFT: dict[_Unclear | None, tuple[str, str]] = {
    "none": ("fits no share basis of {}", "fit no share basis of {}"),
    "two": ("fits two share bases of {}", "fit two share bases of {}"),
    None: ("has no share count", "have no share count"),
}
# The stored count's share of the quote's, by the multiple it is read at, and a few numbers in
# words; any other prints as a figure.
_PART_OF = {
    "2": "half of",
    "3": "a third of",
    "4": "a quarter of",
    "5": "a fifth of",
    "6": "a sixth of",
    "7": "a seventh of",
    "8": "an eighth of",
    "9": "a ninth of",
    "10": "a tenth of",
    "20": "a twentieth of",
}
_MILLION = 1_000_000


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
    """The figures the rule may scale, as assembly read them: ``periods`` are the trailing periods
    behind ``trailing``, oldest first, and ``street_actuals`` the street actual at each trailing
    period end (four quarters or two half-years), empty on the fiscal-year fallback or when one is
    missing."""

    shares_diluted: float | None
    trailing: TrailingFigures | None
    periods: tuple[TrailingPeriod, ...]
    street_actuals: tuple[tuple[date, float], ...]
    quarter_estimates: tuple[QuarterEstimate, ...]
    annual_estimates: tuple[AnnualEstimate, ...]

    @property
    def street_ttm_eps(self) -> float | None:
        """The street's trailing EPS: the sum of the street actuals, one at each trailing period
        end (four quarters or two half-years); ``None`` without them."""
        if not self.street_actuals or len(self.street_actuals) != len(self.periods):
            return None
        return sum(eps for _, eps in self.street_actuals)


@dataclass(frozen=True)
class SplitOutcome:
    """The figures, each one the rule scaled on the new basis; the ``split-pending`` note, ``None``
    without a pending split; the note and the method of each scaled DATA input, by the
    engine's input name (``shares_diluted``, ``eps_ttm``, ``street_ttm_eps``, ``ntm_eps``); the
    ``basis-scaled`` note, ``None`` when the listed-share basis read nothing to note; the refusal
    "share basis unclear: ...", with the figures as given; and ``adr_ratio``, the ratio the counts
    of a flagged ADR gave, ``None`` without one, its note and its method ``counts-ratio`` under
    ``adr_ratio`` beside the others'."""

    figures: SplitFigures
    flag: Flag | None
    notes: dict[str, str]
    estimate_methods: dict[str, str]
    basis_flag: Flag | None = None
    refusal: str | None = None
    adr_ratio: float | None = None


@dataclass(frozen=True)
class _Words:
    """How the notes name the trailing periods: the fiscal year on the fallback, else each period
    a quarter or a half-year, ``one`` and ``many``, by the trailing figures' cadence."""

    fiscal_year: bool
    one: str
    many: str

    @classmethod
    def of(cls, figures: SplitFigures) -> "_Words":
        trailing = figures.trailing
        one, many = PERIOD_NOUNS["quarterly" if trailing is None else trailing.cadence]
        return cls(trailing is not None and trailing.on_fiscal_year, one, many)


# One side of the rule: the figures as it leaves them, its notes by DATA input name, its sentences.
type _Side = tuple[SplitFigures, dict[str, str], list[str]]
# The trailing periods scaled, by their place in ``periods``, with the splits after each one's end.
type _Scaled = dict[int, tuple[SplitRow, ...]]


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
    splits: Sequence[SplitRow], oldest_end: date | None, price_date: date | None
) -> tuple[SplitRow, ...]:
    """The splits dated after ``oldest_end``, the oldest trailing period's end, and at or before
    ``price_date``, oldest first; none when either date is unknown."""
    if oldest_end is None or price_date is None:
        return ()
    found = (s for s in splits if oldest_end < s.date <= price_date)
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
    is_adr: bool = False,
) -> SplitOutcome:
    """``figures`` on the share basis of the quote date (the module docstring states the rule);
    ``statement_end`` is the newest trailing period's end and ``is_adr`` FMP's ADR flag, on which
    the ratio is found from the counts and the listed-share basis read before the split rule."""
    oldest = figures.periods[0].end if figures.periods else statement_end
    pending = pending_splits(splits, oldest, price_date)
    quote_count = (
        None if quote_market_cap is None or not quote_price else quote_market_cap / quote_price
    )
    count = figures.shares_diluted
    if not is_adr or not quote_count or not count:
        return _split_rule(figures, pending, statement_end, quote_count, tolerance)
    found = _find_ratio(figures, pending, statement_end, quote_count, tolerance)
    if found is None:
        return _split_rule(figures, pending, statement_end, quote_count, tolerance)
    if isinstance(found, str):
        return SplitOutcome(figures, None, {}, {}, refusal=_unclear(count, quote_count))
    adr_ratio, found_at = found
    newest = () if statement_end is None else _after(pending, statement_end)
    basis = _basis_side(figures, count, _ratio(newest), pending, quote_count, adr_ratio, tolerance)
    if basis.refusal is not None:
        return basis
    split = _split_rule(basis.figures, pending, statement_end, quote_count, tolerance)
    notes = split.notes | {
        name: f"{split.notes[name]} and {note}" if name in split.notes else note
        for name, note in basis.notes.items()
    }
    notes["adr_ratio"] = _ratio_note(figures, found_at, quote_count)
    methods = split.estimate_methods | basis.estimate_methods | {"adr_ratio": COUNTS_RATIO}
    return replace(
        split,
        notes=notes,
        estimate_methods=methods,
        basis_flag=basis.basis_flag,
        adr_ratio=adr_ratio,
    )


def found_ratio(
    figures: SplitFigures,
    pending: Sequence[SplitRow],
    statement_end: date | None,
    quote_count: float,
    tolerance: float,
) -> float | Literal["none"] | None:
    """ρ, the ratio the counts of a flagged ADR give (the module docstring): a whole number, 2.0
    or more; ``"none"`` when the diluted count differs from ``quote_count`` and fits no whole
    number; ``None`` when no count that differs fits one, or without a diluted count."""
    found = _find_ratio(figures, pending, statement_end, quote_count, tolerance)
    return found if found is None or isinstance(found, str) else found[0]


def _find_ratio(
    figures: SplitFigures,
    pending: Sequence[SplitRow],
    statement_end: date | None,
    quote_count: float,
    tolerance: float,
) -> tuple[float, int | None] | Literal["none"] | None:
    """``found_ratio``'s ρ with where it was found: ``None`` for the diluted count, else the
    trailing period's place in ``periods``. The diluted count first, against the quote's count;
    then, when it does not differ, each period with a count, oldest first, the newest against the
    quote's count and each older one against the diluted count as stored. A count or a quote's
    count at or below zero gives none."""
    count = figures.shares_diluted
    if count is None or count <= 0 or quote_count <= 0:
        return None
    first = _whole_number(count, quote_count, pending, statement_end, tolerance)
    if first is not None:
        return first if isinstance(first, str) else (first, None)
    newest = len(figures.periods) - 1
    for k, period in enumerate(figures.periods):
        own = period.shares_diluted
        if own is None or own <= 0:
            continue
        against = quote_count if k == newest else count
        found = _whole_number(own, against, pending, period.end, tolerance)
        if isinstance(found, float):
            return found, k
    return None


def _whole_number(
    count: float,
    against: float,
    pending: Sequence[SplitRow],
    end: date | None,
    tolerance: float,
) -> float | Literal["none"] | None:
    """The whole number n that brings ``count`` within ``against``, as a float: ``None`` when the
    count does not differ from it, as it is or × the ratio of the pending splits after ``end``;
    else the first candidate that fits, the multiple ``against`` ÷ ``count`` tried first, then
    that with the splits' ratio; ``"none"`` when neither fits."""
    split = 1.0 if end is None else _ratio(_after(pending, end))
    if _within(count, against, tolerance) or _within(count * split, against, tolerance):
        return None
    for multiple, scaled in ((against / count, 1.0), (against / (count * split), split)):
        if multiple >= _PLAIN:
            n = round(multiple)
            factor = float(n)
        elif multiple <= 1 / _PLAIN:
            n = round(1 / multiple)
            factor = 1 / n
        else:
            continue
        if _within(count * factor * scaled, against, tolerance):
            return float(n)
    return "none"


def _ratio_note(figures: SplitFigures, found_at: int | None, quote_count: float) -> str:
    """The ``adr_ratio`` input's note: the count ρ was found on and the count it was judged
    against, the stored diluted count against the quote's, or a trailing period's count against
    the quote's (the newest) or the newest count (an older one)."""
    count = figures.shares_diluted
    assert count is not None  # ρ is found only with a diluted count
    quote = f"the quote's, {_millions(quote_count)}"
    if found_at is None:
        return f"the whole number that brings the stored count, {_millions(count)}, to {quote}"
    period = figures.periods[found_at]
    own = period.shares_diluted
    assert own is not None  # ρ is found only on a period with a count
    words = _Words.of(figures)
    named = "the fiscal year" if words.fiscal_year else f"the {words.one} ending {_day(period.end)}"
    against = (
        quote if found_at == len(figures.periods) - 1 else f"the newest count, {_millions(count)}"
    )
    return f"the whole number that brings the count of {named}, {_millions(own)}, to {against}"


def _unclear(count: float, quote_count: float) -> str:
    """The listed-share basis's refusal, the two counts in millions as stored."""
    return (
        f"share basis unclear: the newest period's count {_millions(count)} against the quote's "
        f"{_millions(quote_count)}"
    )


def _split_rule(
    figures: SplitFigures,
    pending: Sequence[SplitRow],
    statement_end: date | None,
    quote_count: float | None,
    tolerance: float,
) -> SplitOutcome:
    """The split rule on ``figures``: the statements and the consensus on the basis of the quote
    date, with the ``split-pending`` note; as given without a pending split."""
    if not pending or statement_end is None:
        return SplitOutcome(figures, None, {}, {})
    stated, statement_notes, statement = _statement_side(
        figures, pending, statement_end, quote_count, tolerance
    )
    estimated, consensus_notes, consensus = _consensus_side(
        stated, _after(pending, statement_end), statement_end, tolerance
    )
    head = _head(pending, figures.periods, statement_end, _Words.of(figures))
    sentence = " ".join([head, *statement, *consensus, _TAIL])
    notes = statement_notes | consensus_notes
    flag = Flag("split-pending", "Split pending", sentence)
    return SplitOutcome(estimated, flag, notes, dict.fromkeys(notes, SPLIT_SCALED))


def _statement_side(
    figures: SplitFigures,
    pending: Sequence[SplitRow],
    statement_end: date,
    quote_count: float | None,
    tolerance: float,
) -> _Side:
    """The diluted count × the newest period's ρ when the quote's count shows it pre-split, then
    each trailing period's EPS and street actual ÷ its own ρ when its own count shows it pre-split;
    else as stored, the sentence saying why."""
    count = figures.shares_diluted
    if count is None:
        return figures, {}, [_NO_COUNT]
    newest = _after(pending, statement_end)
    ratio = _ratio(newest)
    scale_count = False
    if newest:
        if quote_count is None:
            return figures, {}, [_NO_QUOTE_COUNT]
        basis = _basis(count, ratio, quote_count, tolerance)
        if basis == "both":
            return figures, {}, [_BOTH_BASES]
        if basis == "neither":
            return figures, {}, [_NEITHER_BASIS]
        scale_count = basis == "pre"
    post_split = count * ratio if scale_count else count
    # The newest period has a split after its end only when ``newest`` has one, and Q is then known.
    by_quote = post_split if quote_count is None else quote_count
    verdicts = _judge_periods(figures.periods, pending, by_quote, post_split, tolerance)
    scaled = {k: after for k, (verdict, after) in verdicts.items() if verdict == "pre"}
    tested = [verdict for verdict, _ in verdicts.values() if verdict is not None]
    out, moved = _scale_periods(replace(figures, shares_diluted=post_split), scaled)
    groups = _groups(scaled)
    notes: dict[str, str] = {}
    if scale_count:
        notes["shares_diluted"] = f"{_times(ratio)} for {named_splits(newest)}"
    words = _Words.of(figures)
    notes |= {name: _per_share_note(groups, len(figures.periods), words) for name in moved}
    sentences: list[str] = []
    if scale_count or moved:
        spans = _spans(groups, figures.periods, words)
        per_share = [_PER_SHARE[name] for name in moved]
        sentences.append(_scaled_sentence(ratio if scale_count else None, per_share, spans))
    elif scaled:
        sentences.append(_NOTHING_TO_SCALE)
    elif (newest or tested) and all(verdict == "post" for verdict in tested):
        sentences.append(_POST_SPLIT)
    sentences += _periods_left(verdicts, figures.periods, words)
    return out, notes, sentences


def _judge_periods(
    periods: Sequence[TrailingPeriod],
    pending: Sequence[SplitRow],
    quote_count: float,
    post_split: float,
    tolerance: float,
) -> dict[int, tuple[_Verdict, tuple[SplitRow, ...]]]:
    """Each period with a pending split after its end, on its own count: the newest against the
    quote's count, as the diluted count is judged, the older ones against ``post_split``, S. Its
    verdict, ``None`` without a count, with the splits after its end, by its place in ``periods``.
    """
    verdicts: dict[int, tuple[_Verdict, tuple[SplitRow, ...]]] = {}
    for k, period in enumerate(periods):
        after = _after(pending, period.end)
        if not after:
            continue  # it postdates every pending split: on the quote's basis by construction
        if period.shares_diluted is None:
            verdicts[k] = (None, after)
            continue
        against = quote_count if k == len(periods) - 1 else post_split
        verdicts[k] = (_basis(period.shares_diluted, _ratio(after), against, tolerance), after)
    return verdicts


def _scale_periods(figures: SplitFigures, scaled: _Scaled) -> tuple[SplitFigures, list[str]]:
    """Each scaled period's EPS and street actual ÷ its ρ; the trailing EPS then the sum of the
    periods' when it was on file and each has one, the street's the sum of the actuals, one a
    period. The figures, and the DATA inputs whose figure moved (``eps_ttm``,
    ``street_ttm_eps``)."""
    if not scaled:
        return figures, []
    ratios = {figures.periods[k].end: _ratio(after) for k, after in scaled.items()}
    periods = tuple(
        replace(p, eps_diluted=p.eps_diluted / ratios[p.end])
        if p.end in ratios and p.eps_diluted is not None
        else p
        for p in figures.periods
    )
    moved: list[str] = []
    trailing, actuals = figures.trailing, figures.street_actuals
    each = [p.eps_diluted for p in periods if p.eps_diluted is not None]
    if trailing is not None and trailing.eps_diluted is not None and len(each) == len(periods):
        trailing = replace(trailing, eps_diluted=sum(each))
        moved.append("eps_ttm")
    if figures.street_ttm_eps is not None:
        actuals = tuple((end, eps / ratios.get(end, 1)) for end, eps in actuals)
        moved.append("street_ttm_eps")
    scaled_figures = replace(figures, trailing=trailing, periods=periods, street_actuals=actuals)
    return scaled_figures, moved


def _groups(scaled: _Scaled) -> list[tuple[tuple[SplitRow, ...], list[int]]]:
    """The scaled periods grouped by the splits after their ends, the oldest period's group first:
    its splits are every split that scaled a period."""
    groups: dict[tuple[SplitRow, ...], list[int]] = {}
    for k in sorted(scaled):
        groups.setdefault(scaled[k], []).append(k)
    return list(groups.items())


def _per_share_note(
    groups: Sequence[tuple[tuple[SplitRow, ...], list[int]]], n: int, words: _Words
) -> str:
    """``÷2 for the 2-for-1 split of 15 Oct 2026`` when every period scaled by one ratio, else
    ``÷2 on 3 of 4 quarters for ...`` (``on 1 of 2 half-years``), a part for each ratio."""
    named = named_splits(groups[0][0])
    if len(groups) == 1 and len(groups[0][1]) == n:
        return f"{_divided(_ratio(groups[0][0]))} for {named}"
    parts = [f"{_divided(_ratio(after))} on {len(ks)} of {n} {words.many}" for after, ks in groups]
    return f"{' and '.join(parts)} for {named}"


def _spans(
    groups: Sequence[tuple[tuple[SplitRow, ...], list[int]]],
    periods: Sequence[TrailingPeriod],
    words: _Words,
) -> str:
    """``÷2 on the quarters to 30 Sep 2026``, a part for each ratio."""
    return " and ".join(
        f"{_divided(_ratio(after))} on {_span(ks, periods, words)}" for after, ks in groups
    )


def _span(ks: Sequence[int], periods: Sequence[TrailingPeriod], words: _Words) -> str:
    """``the fiscal year``, ``the quarters to 30 Sep 2026`` when every quarter is among ``ks``,
    else ``the quarter ending ...``, ``the quarters ending 31 Dec 2025 to 30 Jun 2026`` or, when
    they do not follow one another, ``the quarters ending A, B and C``; half-years so named."""
    if words.fiscal_year:
        return "the fiscal year"
    ends = [_day(periods[k].end) for k in ks]
    if len(ks) == len(periods):
        return f"the {words.many} to {ends[-1]}"
    if len(ks) == 1:
        return f"the {words.one} ending {ends[0]}"
    if ks[-1] - ks[0] == len(ks) - 1:
        return f"the {words.many} ending {ends[0]} to {ends[-1]}"
    return f"the {words.many} ending {_and(ends)}"


def _scaled_sentence(count_ratio: float | None, per_share: Sequence[str], spans: str) -> str:
    """The figures read on the post-split basis: the count with its factor when it scaled, the
    per-share figures with the periods they scaled on."""
    if count_ratio is not None:
        counted = f"The diluted count ({_times(count_ratio)})"
        if not per_share:
            return f"{counted} is read on the post-split basis."
        joint = ", " if len(per_share) == 2 else " and "
        return (
            f"{counted}{joint}{' and '.join(per_share)} ({spans}) are read on the post-split basis."
        )
    listed = " and ".join(per_share)
    verb = "are" if len(per_share) == 2 else "is"
    return f"{listed[0].upper()}{listed[1:]} ({spans}) {verb} read on the post-split basis."


def _periods_left(
    verdicts: dict[int, tuple[_Verdict, tuple[SplitRow, ...]]],
    periods: Sequence[TrailingPeriod],
    words: _Words,
) -> list[str]:
    """A sentence for each reason judged periods are read as stored: a count fitting both bases or
    neither of the count it was judged against (the quote's for the newest period, the newest
    count for the others), or no share count."""
    reasons = {k: verdict for k, (verdict, _) in verdicts.items()}
    return _named_left(reasons, _PERIOD_LEFT, periods, words)


def _left(
    ks: Sequence[int], periods: Sequence[TrailingPeriod], words: _Words, said: tuple[str, str]
) -> str:
    """``The quarter ending 31 Mar 2026 has no share count and is read as stored.``, a half-year
    so named."""
    one, many = said
    if words.fiscal_year:
        return f"The fiscal year {one} and is read as stored."
    ends = _and([_day(periods[k].end) for k in ks])
    if len(ks) == 1:
        return f"The {words.one} ending {ends} {one} and is read as stored."
    return f"The {words.many} ending {ends} {many} and are read as stored."


def _consensus_side(
    figures: SplitFigures, pending: Sequence[SplitRow], statement_end: date, tolerance: float
) -> _Side:
    """Each consensus EPS ending after ``statement_end`` ÷ ρ whose implied count shows it
    pre-split, against S, the count as the statement side left it, and P = S ÷ ρ; every row as
    stored without a count, and without a split after ``statement_end``. The NTM EPS carries the
    note when a scaled row is in the NTM window the engine reads on the trailing figures' cadence
    (``ntm_window``: the four quarters, or the two half-years), its span theirs. The quarterly
    consensus rows are named by the window's cadence, else the trailing figures': quarters, or
    half-years."""
    if figures.shares_diluted is None or not pending:
        return figures, {}, []
    ratio = _ratio(pending)
    r, counts = _divided(ratio), (figures.shares_diluted / ratio, figures.shares_diluted)
    annual, annual_scaled, annual_left = _consensus(
        figures.annual_estimates, ratio, counts, statement_end, tolerance
    )
    quarters, quarters_scaled, quarters_left = _consensus(
        figures.quarter_estimates, ratio, counts, statement_end, tolerance
    )
    cadence: Cadence = "quarterly" if figures.trailing is None else figures.trailing.cadence
    window = ntm_window(figures.quarter_estimates, statement_end, cadence)
    ntm, rows_cadence = ((), cadence) if window is None else window
    nouns = PERIOD_NOUNS[rows_cadence]
    spans = [_years_span(annual_scaled)] if annual_scaled else []
    if quarters_scaled:
        spans.append(f"the {_quarters_span(quarters_scaled, nouns)}")
    scaled_ends = {q.period_end for q in quarters_scaled}
    ntm_scaled = [q for q in ntm if q.period_end in scaled_ends]
    notes: dict[str, str] = {}
    if ntm_scaled:
        span = _quarters_span(ntm_scaled, nouns)
        notes["ntm_eps"] = f"the consensus {span} {r} for {named_splits(pending)}"
    sentences = [f"The consensus EPS for {' and for '.join(spans)} is read {r}."] if spans else []
    left = [
        *(f"{_years_list(rows)} ({reason})" for reason, rows in _by_reason(annual_left)),
        *(
            f"{_quarters_list(rows, nouns)} ({reason})"
            for reason, rows in _by_reason(quarters_left)
        ),
    ]
    if left:
        sentences.append(f"The consensus EPS for {_and(left)} is read as stored.")
    scaled = replace(figures, annual_estimates=annual, quarter_estimates=quarters)
    return scaled, notes, sentences


def _consensus[E: (QuarterEstimate, AnnualEstimate)](
    rows: Sequence[E],
    ratio: float,
    counts: tuple[float, float],
    statement_end: date,
    tolerance: float,
) -> tuple[tuple[E, ...], tuple[E, ...], tuple[tuple[str, E], ...]]:
    """The rows with each pre-split EPS ÷ ``ratio``, the rows scaled, and the rows with an EPS left
    as stored, each with its reason; ``counts`` are the pre-split and the post-split counts. A row
    whose implied count fits the post-split count alone is already on it, neither scaled nor left;
    a row ending at or before ``statement_end`` is already reported, kept as stored, unnamed."""
    before, after = counts
    out: list[E] = []
    scaled: list[E] = []
    left: list[tuple[str, E]] = []
    for row in rows:
        if row.period_end > statement_end and row.eps is not None:
            if row.net_income is None:
                left.append((_NO_MEAN, row))
            elif not row.eps:
                left.append((_ZERO_EPS, row))
            else:
                implied = row.net_income / row.eps
                pre, post = _within(implied, before, tolerance), _within(implied, after, tolerance)
                if pre and post:
                    left.append((_BOTH_COUNTS, row))
                elif not pre and not post:
                    left.append((_NEITHER_COUNT, row))
                elif pre:
                    scaled.append(row)
                    row = replace(row, eps=row.eps / ratio)
        out.append(row)
    return tuple(out), tuple(scaled), tuple(left)


def _by_reason[E: (QuarterEstimate, AnnualEstimate)](
    left: Sequence[tuple[str, E]],
) -> list[tuple[str, list[E]]]:
    """The rows left as stored, grouped by reason in the order the reasons first appear."""
    groups: dict[str, list[E]] = {}
    for reason, row in left:
        groups.setdefault(reason, []).append(row)
    return list(groups.items())


def _basis_side(
    figures: SplitFigures,
    count: float,
    split_ratio: float,
    pending: Sequence[SplitRow],
    quote_count: float,
    adr_ratio: float,
    tolerance: float,
) -> SplitOutcome:
    """The statements on the quote's share basis: the diluted count ``count`` × its factor
    against the quote's count, by ``split_ratio``, the ratio of the splits after the newest
    period's end, then each trailing period's count × its own factor and its EPS ÷ it; the
    refusal when the count fits no factor or two. The split rule reads the figures it leaves."""
    found = _factor(count, adr_ratio, split_ratio, quote_count, tolerance)
    if isinstance(found, str):
        return SplitOutcome(figures, None, {}, {}, refusal=_unclear(count, quote_count))
    factor, read = found
    readings = _read_periods(
        figures.periods, pending, adr_ratio, quote_count, count * read, tolerance
    )
    left = {k: r for k, r in readings.items() if r is None or isinstance(r, str)}
    scaled = {
        k: f for k, f in readings.items() if f is not None and not isinstance(f, str) and f != 1
    }
    out, moved = _factor_periods(replace(figures, shares_diluted=count * factor), scaled)
    if factor == 1 and not moved and not any(left.values()):
        return SplitOutcome(out, None, {}, {})
    relation = (
        f"the stored count, {_millions(count)}, {_relation(read)} the quote's, "
        f"{_millions(quote_count)}{_adr(adr_ratio)}"
    )
    groups: dict[float, list[int]] = {}
    for k in sorted(scaled):
        groups.setdefault(scaled[k], []).append(k)
    notes: dict[str, str] = {}
    if factor != 1:
        notes["shares_diluted"] = f"{_times(factor)} to the quote's share basis: {relation}"
    words = _Words.of(figures)
    if moved:
        notes["eps_ttm"] = _basis_note(list(groups.items()), len(figures.periods), adr_ratio, words)
    if factor != 1 or moved:
        spans = _basis_spans(list(groups.items()), figures.periods, words) if moved else None
        lead = _basis_scaled(None if factor == 1 else factor, spans, relation)
    else:
        lead = f"{relation[0].upper()}{relation[1:]}."
    named = _named_left(left, _BASIS_LEFT, figures.periods, words)
    flag = Flag(BASIS_SCALED, "Share basis scaled", " ".join([lead, *named]))
    return SplitOutcome(out, None, notes, dict.fromkeys(notes, BASIS_SCALED), flag)


def _factor(
    count: float, adr_ratio: float, split_ratio: float, against: float, tolerance: float
) -> tuple[float, float] | _Unclear:
    """The factor in 1, ρ and 1 ÷ ρ, tried in that order, that brings ``count`` within
    ``against`` as it is or × ``split_ratio``, with the multiple it reads ``count`` at: the factor,
    × the split ratio when only the split brings it there. ``"none"`` when no factor fits;
    ``"two"`` when two fit at different multiples (two at one multiple read alike, a ratio change
    FMP lists as a split, and the first stands)."""
    fits = [
        (f, f * s)
        for f in (1.0, adr_ratio, 1 / adr_ratio)
        for s in dict.fromkeys((1.0, split_ratio))
        if _within(count * f * s, against, tolerance)
    ]
    if not fits:
        return "none"
    first, read = fits[0]
    if any(f != first and not math.isclose(m, read) for f, m in fits):
        return "two"
    return first, read


def _read_periods(
    periods: Sequence[TrailingPeriod],
    pending: Sequence[SplitRow],
    adr_ratio: float,
    quote_count: float,
    on_quote: float,
    tolerance: float,
) -> dict[int, float | _Unclear | None]:
    """Each period's factor on its own count, by the splits after its own end: the newest against
    the quote's count, the older ones against ``on_quote``, the diluted count on the quote's basis
    (S); ``"none"`` or ``"two"`` when it is unclear, ``None`` without a count."""
    readings: dict[int, float | _Unclear | None] = {}
    for k, period in enumerate(periods):
        if period.shares_diluted is None:
            readings[k] = None
            continue
        against = quote_count if k == len(periods) - 1 else on_quote
        split_ratio = _ratio(_after(pending, period.end))
        found = _factor(period.shares_diluted, adr_ratio, split_ratio, against, tolerance)
        readings[k] = found if isinstance(found, str) else found[0]
    return readings


def _factor_periods(figures: SplitFigures, scaled: dict[int, float]) -> tuple[SplitFigures, bool]:
    """Each scaled period's count × its factor and its EPS ÷ it; the trailing EPS then the sum of
    the periods' when it was on file and each has one. The figures, and whether the trailing EPS
    moved."""
    if not scaled:
        return figures, False
    periods = tuple(
        _on_basis(p, scaled[k]) if k in scaled else p for k, p in enumerate(figures.periods)
    )
    trailing = figures.trailing
    each = [p.eps_diluted for p in periods if p.eps_diluted is not None]
    if trailing is None or trailing.eps_diluted is None or len(each) != len(periods):
        return replace(figures, periods=periods), False
    return replace(
        figures, trailing=replace(trailing, eps_diluted=sum(each)), periods=periods
    ), True


def _on_basis(period: TrailingPeriod, factor: float) -> TrailingPeriod:
    """``period`` with its count × ``factor`` and its EPS ÷ it."""
    eps, count = period.eps_diluted, period.shares_diluted
    return replace(
        period,
        eps_diluted=None if eps is None else eps / factor,
        shares_diluted=None if count is None else count * factor,
    )


def _basis_note(
    groups: Sequence[tuple[float, list[int]]], n: int, adr_ratio: float, words: _Words
) -> str:
    """``÷10 to the quote's share basis (the ratio 10)`` when every period scaled by one
    factor, else ``... on 1 of 4 quarters`` (``on 1 of 2 half-years``), a part for each factor."""
    basis = f"to the quote's share basis{_adr(adr_ratio)}"
    if len(groups) == 1:
        factor, ks = groups[0]
        share = "" if len(ks) == n else f" on {len(ks)} of {n} {words.many}"
        return f"{_divided(factor)} {basis}{share}"
    parts = [f"{_divided(factor)} on {len(ks)} of {n} {words.many}" for factor, ks in groups]
    return f"{' and '.join(parts)} {basis}"


def _basis_spans(
    groups: Sequence[tuple[float, list[int]]],
    periods: Sequence[TrailingPeriod],
    words: _Words,
) -> str:
    """``÷10 on every trailing quarter``, ``÷5 on the quarter ending 30 Sep 2026``, a part for
    each factor; half-years so named."""

    def span(ks: Sequence[int]) -> str:
        every = len(ks) == len(periods) and not words.fiscal_year
        return f"every trailing {words.one}" if every else _span(ks, periods, words)

    return " and ".join(f"{_divided(factor)} on {span(ks)}" for factor, ks in groups)


def _basis_scaled(count_factor: float | None, spans: str | None, relation: str) -> str:
    """The figures read on the quote's share basis: the count with its factor when it scaled,
    the trailing EPS with the periods it scaled on, and why."""
    if count_factor is None:
        return f"The trailing EPS ({spans}) is read on the quote's share basis: {relation}."
    counted = f"The diluted count ({_times(count_factor)})"
    if spans is None:
        return f"{counted} is read on the quote's share basis: {relation}."
    return (
        f"{counted} and the trailing EPS ({spans}) are read on the quote's share basis: {relation}."
    )


def _relation(read: float) -> str:
    """How the stored count stands to the quote's, by the multiple it is read at: ``is a tenth
    of`` at ×10, ``is twice`` at ÷2, ``lies within the tolerance of`` as stored."""
    if read == 1:
        return "lies within the tolerance of"
    if read > 1:
        n = _count(read)
        return f"is {_PART_OF.get(n, f'1/{n} of')}"
    n = _count(1 / read)
    return "is twice" if n == "2" else f"is {n} times"


def _adr(ratio: float) -> str:
    """The ratio after a count: `` (the ratio 10)``."""
    return f" (the ratio {_count(ratio)})"


def _millions(count: float) -> str:
    """``1,450.8 m``."""
    return f"{count / _MILLION:,.1f} m"


def _named_left[R](
    reasons: Mapping[int, R],
    said: Mapping[R, tuple[str, str]],
    periods: Sequence[TrailingPeriod],
    words: _Words,
) -> list[str]:
    """A sentence for each reason in ``said`` that periods are read as stored, in its order, the
    periods by their place in ``periods``; ``{}`` in the reason is the count each was judged
    against (the quote's for the newest period, the newest count for the others)."""
    groups: dict[tuple[str, str], list[int]] = {}
    for reason, (one, many) in said.items():
        for k in sorted(k for k, found in reasons.items() if found == reason):
            against = "the quote's count" if k == len(periods) - 1 else "the newest count"
            groups.setdefault((one.format(against), many.format(against)), []).append(k)
    return [_left(ks, periods, words, reason) for reason, ks in groups.items()]


def _after(splits: Sequence[SplitRow], day: date) -> tuple[SplitRow, ...]:
    """The splits dated after ``day``, in their order."""
    return tuple(s for s in splits if s.date > day)


def _ratio(splits: Sequence[SplitRow]) -> float:
    """ρ, the splits' ratios compounded."""
    return math.prod(s.ratio for s in splits)


def _basis(count: float, ratio: float, against: float, tolerance: float) -> _Basis:
    """Where ``count`` stands against ``against``: pre-split when ``count × ratio`` lies within
    the tolerance and ``count`` does not, post-split the other way round, else both or neither."""
    stored = _within(count, against, tolerance)
    scaled = _within(count * ratio, against, tolerance)
    if stored == scaled:
        return "both" if stored else "neither"
    return "post" if stored else "pre"


def _times(ratio: float) -> str:
    """A share count's factor: ``×2`` for a 2-for-1 split, its inverse ``÷10`` for a 1-for-10
    reverse split."""
    return f"×{_count(ratio)}" if ratio >= 1 else f"÷{_count(1 / ratio)}"


def _divided(ratio: float) -> str:
    """A per-share figure's factor: ``÷2`` for a 2-for-1 split, its inverse ``×10`` for a
    1-for-10 reverse split."""
    return f"÷{_count(ratio)}" if ratio >= 1 else f"×{_count(1 / ratio)}"


def _within(a: float, b: float, tolerance: float) -> bool:
    """``a`` lies within ``tolerance`` of ``b``, as a share of ``b``; never for a ``b`` of zero."""
    return b != 0 and abs(a - b) <= tolerance * b


def _head(
    pending: Sequence[SplitRow],
    periods: Sequence[TrailingPeriod],
    statement_end: date,
    words: _Words,
) -> str:
    """``A 2-for-1 split of 28 Jan 2027 falls after the newest statement (30 Sep 2026).``, or,
    when the oldest pending split falls within the trailing periods, ``... falls after the quarter
    ending 31 Mar 2026.`` (``the half-year ending``), the newest period it follows."""
    splits = _and([f"{_article(s)} {s.word} of {_day(s.date)}" for s in pending])
    verb = "falls" if len(pending) == 1 else "fall"
    first = pending[0].date
    before = [p.end for p in periods if p.end < first]
    if first > statement_end or not before:
        where = f"the newest statement ({_day(statement_end)})"
    else:
        where = f"the {words.one} ending {_day(before[-1])}"
    return f"{splits[0].upper()}{splits[1:]} {verb} after {where}."


def _years_span(rows: Sequence[AnnualEstimate]) -> str:
    first, last = rows[0].fiscal_year, rows[-1].fiscal_year
    return f"fiscal {first}" if first == last else f"fiscal {first} to {last}"


def _quarters_span(rows: Sequence[QuarterEstimate], nouns: tuple[str, str]) -> str:
    """``quarters to 30 Sep 2027``, or ``half-years to ...`` by ``nouns``."""
    one, many = nouns
    return f"{one if len(rows) == 1 else many} to {_day(rows[-1].period_end)}"


def _years_list(rows: Sequence[AnnualEstimate]) -> str:
    return f"fiscal {_and([str(a.fiscal_year) for a in rows])}" if rows else ""


def _quarters_list(rows: Sequence[QuarterEstimate], nouns: tuple[str, str]) -> str:
    """``the quarters ending A and B``, or ``the half-years ending ...`` by ``nouns``."""
    if not rows:
        return ""
    one, many = nouns
    named = one if len(rows) == 1 else many
    return f"the {named} ending {_and([_day(q.period_end) for q in rows])}"


def named_splits(splits: Sequence[SplitRow]) -> str:
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
