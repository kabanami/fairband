"""The number check of a report (spec 2026-11-06 Tier 2, 13.1 and 13.3; ``method.md`` 16).

A report is published whole or rejected whole. Before the number check run the structural checks
(``structure_refusal``), each refused with one sentence: the mode's section count, ten for a full
report and eight for a valuation review, which leaves out "The business" and "Industry and
competition"; the stance, one of the policy's ``stance_words``; the required judgments, ``phase``,
``moat`` and ``belief`` on every report, ``roic`` where the route is Mature Growth or Mature
Stable and ``target_margin`` where it is the revenue-growth route (High Growth, Young Growth) or
Start-up; and the headings, design.md 9.3's in its order (``HEADINGS``).

The number check (``check_sections``) walks every part of every section and answers a finding for
each failure, ``where`` the section and the part counted from 1 and the text at fault,
``section 1, part 3: $12.345``. The six failures, in the server's words:

- ``a number with no reference``: a quantity in a plain part (``quantities``);
- ``unresolved reference``: a cite whose ref names nothing, or a figure the record does not hold;
- ``wrong unit``: a cite whose suffix does not fit the ref's unit, or whose number is not the
  ref's value at the report's rounding (``rounded_equal``), the value in the detail as the cite
  should read; a word cited against a number, or a word that is not the ref's;
- ``wrong period``: a cite naming a period that is not the ref's (``FY2025`` reads ``2025``); a
  cite naming none passes;
- ``wrong snapshot``: a cite whose ref rests on a snapshot other than the company's latest, or one
  the latest does not reprice (``refs.same_snapshot``), the latest's id in the detail;
- ``a derived figure the engine has not emitted``: a ``derived:`` cite with no stored derivation
  of the company or one with no value, and a multiple (``12.3x``) in a plain part, a ratio
  written out rather than derived.

One finding for each cite, the first failure in the order wrong snapshot, not emitted,
unresolved, wrong period, wrong unit; one for each quantity of a plain part.

A quantity (13.3's token rule) is a money amount (``$1,234.50``), a percentage (``11.2%``,
``11.2 percent``), a multiple (``12.3x``, ``12.3×``), a decimal, or an integer of two or more
digits; a sign (``-``, the minus ``−``) or parentheses may stand around it. Not a quantity: a
year from 1990 to 2099, an ISO date, a day of the month beside a month's name (``27 Oct``), a
number joined to letters (``FY2025``, ``Q3``, ``COVID-19``, ``5G``, ``21st``), a filing form
(``10-K``, ``8-K``, ``20-F``), a section's or an item's number (``section 13.3``, ``Item 10``),
anything inside a URL or after a slash (``fairband-review/1``), and an integer of one digit.

A cite's text is read by ``parse_cite``: an optional sign or parentheses (a negative), ``$``, the
number with its thousands separators, and a suffix, ``%`` (or ``percent``), ``x`` (or ``×``),
``years`` (or ``year``) or none. ``rounded_equal`` takes design.md 9.2's rounding by the ref's
unit: ``currency`` to whole dollars; ``per-share`` to cents, or to whole dollars as a value and
its levels are written; ``percent`` to one decimal of the fraction × 100; ``multiple`` to two
decimals; ``years`` to one; ``score`` to two; ``count`` to a whole number. The cite must be
written at that rounding or coarser on its grid (``$12.345`` is not cents) and lie within half a
step of the value. A suffix fits a unit: ``$`` a currency or per-share figure, ``%`` a percent,
``x`` a multiple, ``years`` a span in years; none fits any unit but a percent. A ref with no unit
(an intermediate, a vendor field) takes any suffix, at the cite's own precision.
"""

import re
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from fairband.engine.types import Route
from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.reports.refs import Resolved, Resolver, rests_on, same_snapshot

UNRESOLVED = "unresolved reference"
WRONG_UNIT = "wrong unit"
WRONG_PERIOD = "wrong period"
WRONG_SNAPSHOT = "wrong snapshot"
NO_REFERENCE = "a number with no reference"
NOT_EMITTED = "a derived figure the engine has not emitted"
FAILURES = (UNRESOLVED, WRONG_UNIT, WRONG_PERIOD, WRONG_SNAPSHOT, NO_REFERENCE, NOT_EMITTED)

HEADINGS = (
    "Summary",
    "The business",
    "Industry and competition",
    "Financial performance and health",
    "Life-cycle phase",
    "Valuation",
    "Price facts and multiples",
    "Key judgments",
    "Recent news",
    "Risks and kill criteria",
)
# The two sections a valuation review leaves out (design.md 7.5).
FULL_ONLY = ("The business", "Industry and competition")
ALWAYS_JUDGED = ("phase", "moat", "belief")
_JUDGED_BY_ROUTE: dict[str, str] = {
    "mature-growth": "roic",
    "mature-stable": "roic",
    "revenue-growth": "target_margin",
    "start-up": "target_margin",
}
# The structural checks, in the order they run, then the six failures: the checks Appendix A
# lists as run.
STRUCTURE = (
    "the mode's section count",
    "the stance word",
    "the required judgments",
    "the headings in design.md 9.3's order",
)
CHECKS = STRUCTURE + FAILURES

_NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_QUANTITY = re.compile(
    r"(?<![\w.,/])(?<![A-Za-z]-)"  # not inside a word, a number or a path
    rf"\(?[−-]?\$?[−-]?(?:{_NUMBER})"
    r"(?:\s?%|\s?percent\b|[x×](?![A-Za-z0-9]))?\)?"
    r"(?!\w)(?![.,]\d)(?!-[A-Z]\b)"  # not a filing form, 10-K
)
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
    r"|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?![a-z])"
)
# Text that holds no quantity: a URL, an ISO date, a day beside a month's name.
_NOT_QUANTITIES = re.compile(
    rf"https?://\S+|\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}\s+{_MONTH}|{_MONTH}\.?\s+\d{{1,2}}\b"
)
_SECTION_NUMBER = re.compile(r"(?:\bsections?|§|\bitems?)\s*$", re.IGNORECASE)
_CITE = re.compile(
    r"\s*(?P<open>\()?\s*(?P<sign>[−-])?\s*(?P<dollar>\$)?\s*(?P<sign2>[−-])?"
    rf"(?P<number>{_NUMBER})"
    r"\s*(?P<suffix>%|percent|[x×]|years?)?\s*(?P<close>\))?\s*"
)
_SUFFIXES = {"%": "%", "percent": "%", "x": "x", "×": "x", "year": "years", "years": "years"}
_FITS: dict[str, frozenset[str]] = {
    "$": frozenset({"currency", "per-share"}),
    "%": frozenset({"percent"}),
    "x": frozenset({"multiple"}),
    "years": frozenset({"years"}),
    "": frozenset({"currency", "per-share", "multiple", "years", "count", "score"}),
}
# The decimals each unit is written to (design.md 9.2); a per-share figure also to whole dollars.
_PLACES: dict[str, tuple[int, ...]] = {
    "currency": (0,),
    "per-share": (2, 0),
    "percent": (1,),
    "multiple": (2,),
    "years": (1,),
    "score": (2,),
    "count": (0,),
}


@dataclass(frozen=True)
class Finding:
    """One failure: where it is (``section <i>, part <j>: <text>``), its word and a detail."""

    where: str
    what: str
    detail: str


def headings(mode: str) -> tuple[str, ...]:
    """The headings of a report in ``mode``, in order."""
    return HEADINGS if mode == "full report" else tuple(h for h in HEADINGS if h not in FULL_ONLY)


def required_judgments(route: Route | None) -> tuple[str, ...]:
    """The judgments a report on ``route`` carries; ``None`` for an unclassified row."""
    extra = None if route is None else _JUDGED_BY_ROUTE.get(route)
    return ALWAYS_JUDGED if extra is None else (*ALWAYS_JUDGED, extra)


def structure_refusal(
    mode: str,
    stance: str,
    section_headings: Sequence[str],
    judgments: Sequence[str],
    route: Route | None,
    policy: Policy,
) -> str | None:
    """The sentence of the first structural check the submission fails (module docstring), in
    ``STRUCTURE``'s order; ``None`` when it passes them all."""
    expected = headings(mode)
    if len(section_headings) != len(expected):
        count = len(section_headings)
        return f"a {mode} has {len(expected)} sections, not {count}"
    if stance not in policy.stance_words:
        return f"a stance is one of {_listed(policy.stance_words, 'or')}, not {stance!r}"
    missing = [k for k in required_judgments(route) if k not in judgments]
    if missing:
        return f"the report lacks the judgment{'s' if len(missing) > 1 else ''} " + _listed(
            missing, "and"
        )
    twice = next((k for k in judgments if judgments.count(k) > 1), None)
    if twice is not None:
        return f"one judgment of each kind: {twice} is given twice"
    for i, (got, want) in enumerate(zip(section_headings, expected, strict=True), 1):
        if got.strip() != want:
            return f"section {i} is headed {want!r}, not {got!r}"
    return None


def check_sections(
    conn: sqlite3.Connection,
    symbol: str,
    snapshot_id: int,
    sections: Sequence[Mapping[str, object]],
    policy: Policy,
    tax: TaxTable | None = None,
) -> list[Finding]:
    """Every failure of the sections' parts, in order, against the company's latest snapshot
    ``snapshot_id``; ``policy`` is the effective one and ``tax`` the statements' table."""
    resolver = Resolver(conn, symbol, policy, tax)
    found = []
    for where, part in parts(sections):
        if isinstance(part, str):
            for q in quantities(part):
                what = NOT_EMITTED if _multiple(q) else NO_REFERENCE
                found.append(Finding(f"{where}: {q}", what, _plain_detail(what)))
        elif isinstance(part, Mapping):
            failure = _cite_failure(conn, resolver, snapshot_id, part)
            if failure is not None:
                found.append(Finding(f"{where}: {part.get('cite', '')}", *failure))
    return found


def parts(sections: Sequence[Mapping[str, object]]) -> Iterator[tuple[str, object]]:
    """Each part of each section with its place, ``section <i>, part <j>``, counted from 1."""
    for i, section in enumerate(sections, 1):
        found = section.get("parts")
        for j, part in enumerate(found if isinstance(found, list | tuple) else (), 1):
            yield f"section {i}, part {j}", part


def cited_records(
    conn: sqlite3.Connection, sections: Sequence[Mapping[str, object]]
) -> tuple[int | None, int | None, int | None]:
    """The snapshot the cites rest on (the earliest of those they name), and the newest review and
    secondary valuation they cite; ``None`` for each they do not."""
    snapshots: list[int] = []
    reviews: list[int] = []
    secondaries: list[int] = []
    for _, part in parts(sections):
        ref = str(part.get("ref", "")).strip() if isinstance(part, Mapping) else ""
        rested = rests_on(conn, ref)
        if rested is not None:
            snapshots.append(rested)
        form, _, path = ref.partition(":")
        head = path.partition("/")[0]
        if head.isdigit() and form in ("review", "secondary"):
            (reviews if form == "review" else secondaries).append(int(head))
    return (
        min(snapshots, default=None),
        max(reviews, default=None),
        max(secondaries, default=None),
    )


def quantities(text: str) -> list[str]:
    """The quantities of a plain part, as written (module docstring)."""
    blanked = _NOT_QUANTITIES.sub(lambda m: " " * len(m.group(0)), text)
    found = []
    for match in _QUANTITY.finditer(blanked):
        token = match.group(0)
        if "$" in token or "%" in token or "percent" in token or _multiple(token):
            found.append(token)
            continue
        if _SECTION_NUMBER.search(blanked[: match.start()]):
            continue
        core = token.strip("()")
        digits = core.lstrip("−-").replace(",", "")
        if "." in core or (len(digits) >= 2 and not _year(core)):
            found.append(token)
    return found


def parse_cite(text: str) -> tuple[float, str] | None:
    """A cite's number and its suffix, ``$``, ``%``, ``x``, ``years`` or ``""``; ``None`` for a
    text that is not one number (module docstring)."""
    match = _CITE.fullmatch(text)
    if match is None or bool(match["open"]) != bool(match["close"]):
        return None
    if match["sign"] and match["sign2"]:
        return None
    suffix = _SUFFIXES.get(match["suffix"] or "", "")
    if match["dollar"]:
        if suffix:
            return None
        suffix = "$"
    number = float(match["number"].replace(",", ""))
    negative = bool(match["open"] or match["sign"] or match["sign2"])
    return (-number if negative else number), suffix


def fits(suffix: str, unit: str | None) -> bool:
    """Whether a cite with ``suffix`` may cite a figure in ``unit``."""
    return unit is None or unit in _FITS.get(suffix, frozenset())


def rounded_equal(cite: float, suffix: str, value: float, unit: str | None) -> bool:
    """Whether ``cite``, written with ``suffix``, is ``value`` in ``unit`` at the report's
    rounding (module docstring)."""
    if not fits(suffix, unit):
        return False
    scaled = value * 100 if unit == "percent" or (unit is None and suffix == "%") else value
    places = _PLACES[unit] if unit is not None else (_decimals(cite),)
    return any(_on_grid(cite, p) and _within(cite, scaled, p) for p in places)


def shown(value: float, unit: str | None) -> str:
    """The value as a cite of it reads at the report's rounding."""
    sign = "−" if value < 0 else ""
    size = abs(value)
    match unit:
        case "currency":
            return f"{sign}${size:,.0f}"
        case "per-share":
            return f"{sign}${size:,.2f}"
        case "percent":
            return f"{sign}{size * 100:,.1f}%"
        case "multiple":
            return f"{sign}{size:,.2f}x"
        case "years":
            return f"{sign}{size:,.1f} years"
        case "score":
            return f"{sign}{size:,.2f}"
        case "count":
            return f"{sign}{size:,.0f}"
    return f"{value:g}"


def _cite_failure(
    conn: sqlite3.Connection, resolver: Resolver, latest: int, part: Mapping[str, object]
) -> tuple[str, str] | None:
    """The first failure of the cite, its word and its detail; ``None`` when it passes."""
    cite, ref = str(part.get("cite", "")), str(part.get("ref", ""))
    period = part.get("period")
    rested = rests_on(conn, ref)
    if rested is not None and not same_snapshot(conn, rested, latest):
        why = f"{ref} rests on snapshot {rested}; the company's latest is snapshot {latest}"
        return WRONG_SNAPSHOT, f"{why}: read it again"
    resolved = resolver.resolve(ref)
    if ref.strip().startswith("derived:") and (resolved is None or resolved.value is None):
        why = "has no value" if resolved else f"is no derivation of {resolver.symbol}"
        return NOT_EMITTED, f"{ref} {why}: derive the figure and cite its id"
    if resolved is None:
        return UNRESOLVED, f"{ref} names no stored value"
    if resolved.value is None:
        return UNRESOLVED, f"{ref} holds no value"
    if period is not None and _period(str(period)) != _period(resolved.period):
        found = "has no period" if resolved.period is None else f"is for {resolved.period}"
        return WRONG_PERIOD, f"{ref} {found}, not {period}"
    return _unit_failure(cite, ref, resolved)


def _unit_failure(cite: str, ref: str, resolved: Resolved) -> tuple[str, str] | None:
    value, unit = resolved.value, resolved.unit
    if isinstance(value, str):
        if cite.strip().casefold() == value.strip().casefold():
            return None
        return WRONG_UNIT, f"{ref} reads {value!r}"
    assert value is not None  # the caller answered a figure with none
    parsed = parse_cite(cite)
    expected = shown(value, unit)
    if parsed is None:
        return WRONG_UNIT, f"{cite!r} is not one number: {ref} reads {expected}"
    number, suffix = parsed
    if not fits(suffix, unit):
        return WRONG_UNIT, f"{cite!r} does not fit a {unit} figure: {ref} reads {expected}"
    if not rounded_equal(number, suffix, value, unit):
        return WRONG_UNIT, f"{ref} reads {expected}"
    return None


def _plain_detail(what: str) -> str:
    if what == NOT_EMITTED:
        return "a ratio in plain text: derive it and cite the derivation"
    return "cite it with its reference, or write a small count in words"


def _multiple(token: str) -> bool:
    return token.rstrip(")").endswith(("x", "×"))


def _period(text: str | None) -> str | None:
    """A period as compared: upper case, a fiscal year's ``FY`` dropped."""
    if text is None:
        return None
    upper = text.strip().upper()
    return upper[2:] if upper.startswith("FY") and upper[2:].isdigit() else upper


def _decimals(x: float) -> int:
    """The decimals ``x`` is written with."""
    exponent = Decimal(repr(x)).normalize().as_tuple().exponent
    return max(0, -exponent) if isinstance(exponent, int) else 0


def _year(core: str) -> bool:
    """Whether the unsigned whole number ``core`` is a year from 1990 to 2099."""
    return core.isdigit() and 1990 <= int(core) <= 2099


def _on_grid(x: float, places: int) -> bool:
    """Whether ``x`` is written with at most ``places`` decimals."""
    scaled = x * 10.0**places
    return abs(scaled - round(scaled)) <= 1e-9 * max(1.0, abs(scaled))


def _within(cite: float, value: float, places: int) -> bool:
    return abs(cite - value) <= 0.5 * 10.0**-places + 1e-9 * max(1.0, abs(value))


def _listed(items: Sequence[str], word: str) -> str:
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} {word} {items[-1]}"
