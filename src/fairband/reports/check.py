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

``check_judgments`` reads the judgments' bull, bear and decision text, which carries no cite: a
quantity there is ``a number with no reference``, located ``judgment <kind>, <field>: <text>``.
A ``review:`` cite must also be the company's current review, the newest on its snapshot with the
current review that one or its reprice; else it is ``wrong snapshot``, the current id named.

A quantity (13.3's token rule) is any number a currency sign leads (``$``, ``€``, ``£``,
``¥``, a letter prefix before it or not), whatever letters follow it (``$5``, ``$ 5``, ``US$5``,
``$5mm``, ``$3.2T``, ``€1.5B``, ``£126m``); a decimal joined to a one-letter scale (``m``, ``b``,
``k``, ``t``, any case: ``1.5B``, ``2.3M``, ``4.5k``); a number followed, with or without a space
and in any case, by a scale of two letters or more or a unit word, whatever its digits
(``12 billion``, ``11.2pp``, ``50bps``, ``5 basis points``, ``5 percentage points``,
``2 Years``); a percentage (``11.2%``, ``11.2 percent``, ``5 per cent``); a multiple (``12.3x``,
``5 x``, ``12.3×``, and ``X`` joined to the number, ``15X``, never after a space); a decimal; or
an integer of two or more digits; a sign (``-``, the minus ``−``) or parentheses may stand around
it. Not a quantity: a year from 1990 to 2099, an ISO date, a day of the month beside a month's
name (``27 Oct``) unless a decimal, ``%`` or a scale follows it (``March 12%``) or a currency sign
leads it, an integer joined to letters with no currency sign (``FY2025``, ``Q3``, ``COVID-19``,
``5G``, ``3M``, ``401k``, ``150M``, ``21st``), a filing form (``10-K``, ``8-K``, ``20-F``), a
section's or an item's number (``section 13.3``, ``Item 10``), anything inside a URL or after a
slash (``fairband-review/1``), and an integer of one digit with no unit word.

A cite's text is read by ``parse_cite``: an optional sign, ``+``, or ``-``, ``−`` or parentheses
for a negative, ``$``, the number with its thousands separators, a scale word (``thousand``,
``million``, ``billion``, ``trillion``, ``k``, ``m``, ``mn``, ``b``, ``bn``, ``tn``), and a suffix,
``%`` (or ``percent``, or ``pp`` or ``percentage points``, a difference of two percents read as a
percent), ``x`` (or ``×``, or ``X`` joined to the number), ``years`` (or ``year``) or none.
``rounded_equal`` takes design.md 9.2's rounding by the ref's unit: ``currency`` to whole
dollars; ``price`` (a share price: ``snapshot:<id>/price``, its ``inputs/price``, a ``close:``) to
cents; ``per-share`` (a value, a level, an EPS) to cents or to whole dollars, as a value and its
levels are written; ``percent`` to one decimal of the fraction × 100; ``multiple`` to two
decimals; ``years`` to one; ``score`` to two; ``count`` to a whole number. The cite must be
written at that rounding or coarser on its grid (``$12.345`` is not cents) and lie within half a
step of the value. A suffix fits a unit: ``$`` a currency, price or per-share figure, ``%`` a
percent, ``x`` a multiple, ``years`` a span in years; none fits any unit but a percent. A ref with
no unit (an intermediate, a vendor field) takes any suffix, at the cite's own precision, the
decimals it was written with. Three more rules (``method.md`` 16.3): a cite with a scale word fits
a total (with ``$`` or none) or a count (with none) and is compared at the decimals it was written
with in its scale, with two significant figures at least; a cite with no sign of a line the store
signs as an outflow (``Resolved.outflow``) matches its size, and one with a sign, ``+`` included,
its signed value; and a ``%`` cite of a ``derived:`` or ``table:`` multiple, a ratio of two
figures in one unit, is compared as a percentage.
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
from fairband.store.reviews import latest_review, latest_review_on, review_row

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
# The words after a number, with or without a space and in any case, that make it a quantity
# whatever its digits: a scale of two letters or more (``bn``, ``mm``, ``million``), points
# (``pp``, ``bps``, ``percentage points``), a percentage (``%``, ``percent``, ``per cent``), a
# multiple (``x``, ``×``, or ``X`` joined to the number) and a span of years. A one-letter scale
# (``m``, ``b``, ``k``, ``t``) counts after a currency sign or on a decimal: an integer joined to
# a letter with no sign is a name (``3M``, ``401k``).
_UNIT_WORDS = (
    r"thousand|million|billion|trillion|percentage\s+points?|basis\s+points?|percent|per\s+cent"
    r"|years?|bps|bp|bn|mn|mm|pp|tn"
)
_UNIT_AFTER = rf"(?:\s?%|\s?[x×](?![A-Za-z0-9])|X(?![A-Za-z0-9])|\s?(?i:{_UNIT_WORDS})\b)"
_SIGNS = "$€£¥"  # the currency signs that make the number after them a money amount
_DECIMAL = r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d+"
_QUANTITY = re.compile(
    rf"(?<![\w.,/{_SIGNS}])(?<![A-Za-z]-)"  # not inside a word, a number or a path
    r"\(?[−-]?(?:"
    # led by a currency sign, a currency's letters before it or not: any letters after
    rf"(?:[A-Z]{{1,3}})?[{_SIGNS}]\s?[−-]?(?:{_NUMBER})(?:[A-Za-z]+|{_UNIT_AFTER})?"
    rf"|{_DECIMAL}[mbktMBKT](?![A-Za-z0-9])"  # a decimal in a one-letter scale
    rf"|(?:{_NUMBER}){_UNIT_AFTER}?"
    r")\)?"
    r"(?!\w)(?![.,]\d)(?!-[A-Z]\b)"  # not a filing form, 10-K
)
_CARRIES_A_UNIT = re.compile(rf"\d{_UNIT_AFTER}\)?$")
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
    r"|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?![a-z])"
)
# Text that holds no quantity: a URL, an ISO date, a day beside a month's name; not a day followed
# by a decimal, a percent sign, a multiple's or a scale's word, which is a quantity after a month.
_NOT_QUANTITIES = re.compile(
    rf"https?://\S+|\b\d{{4}}-\d{{2}}-\d{{2}}\b"
    rf"|(?<![\d.,{_SIGNS}])(?<![{_SIGNS}]\s)\b\d{{1,2}}\s+{_MONTH}"
    rf"|{_MONTH}\.?\s+\d{{1,2}}\b(?![.,]\d|{_UNIT_AFTER})"
)
_SECTION_NUMBER = re.compile(r"(?:\bsections?|§|\bitems?)\s*$", re.IGNORECASE)
_CITE = re.compile(
    r"\s*(?P<open>\()?\s*(?P<sign>[−+-])?\s*(?P<dollar>\$)?\s*(?P<sign2>[−+-])?"
    rf"(?P<number>{_NUMBER})"
    r"(?:(?P<upper>X)"  # a multiple's X, joined to the number
    r"|\s*(?:(?P<scale>(?i:thousand|million|billion|trillion|mn|bn|tn|k|m|b))(?![A-Za-z]))?"
    r"\s*(?P<suffix>%|percentage\s+points?|percent|pp|[x×]|years?)?)\s*(?P<close>\))?\s*"
)
_NEGATIVE = ("−", "-")  # the signs of a negative; ``+`` is a sign too, of a positive
_SCALES = {
    "k": 10**3,
    "thousand": 10**3,
    "m": 10**6,
    "mn": 10**6,
    "million": 10**6,
    "b": 10**9,
    "bn": 10**9,
    "billion": 10**9,
    "tn": 10**12,
    "trillion": 10**12,
}
_SUFFIXES = {
    "%": "%",
    "percent": "%",
    # points: a difference of two percents, compared as a percent is
    "pp": "%",
    "percentage point": "%",
    "percentage points": "%",
    "x": "x",
    "×": "x",
    "year": "years",
    "years": "years",
}
_FITS: dict[str, frozenset[str]] = {
    "$": frozenset({"currency", "per-share", "price"}),
    "%": frozenset({"percent"}),
    "x": frozenset({"multiple"}),
    "years": frozenset({"years"}),
    "": frozenset({"currency", "per-share", "price", "multiple", "years", "count", "score"}),
}
# The units a cite with a scale word fits: a total with ``$`` or none, a count with none.
_SCALED = {"$": frozenset({"currency"}), "": frozenset({"currency", "count"})}
# The decimals each unit is written to (design.md 9.2): a price to cents, a value a share or a
# level to cents or to whole dollars.
_PLACES: dict[str, tuple[int, ...]] = {
    "currency": (0,),
    "price": (2,),
    "per-share": (2, 0),
    "percent": (1,),
    "multiple": (2,),
    "years": (1,),
    "score": (2,),
    "count": (0,),
}
# The engine's ratios of two figures in one unit, a ``%`` cite may write as a percentage.
_RATIO_FORMS = ("derived:", "table:")


@dataclass(frozen=True)
class Finding:
    """One failure: where it is (``section <i>, part <j>: <text>``), its word and a detail."""

    where: str
    what: str
    detail: str


@dataclass(frozen=True)
class _Cite:
    """A cite's text read: its number in units, its suffix, its scale, the decimals and the
    significant figures written, and whether it carries a sign."""

    number: float
    suffix: str
    scale: int
    decimals: int
    significant: int
    signed: bool


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


def check_judgments(judgments: Sequence[Mapping[str, object]]) -> list[Finding]:
    """A finding for each quantity in a judgment's bull, bear or decision text, which carries no
    cite, located ``judgment <kind>, <field>: <text>``."""
    found = []
    for j in judgments:
        for field in ("bull", "bear", "decision"):
            for q in quantities(str(j.get(field, ""))):
                where = f"judgment {j.get('judgment')}, {field}: {q}"
                detail = "a judgment's text holds no figure: cite it in a section"
                found.append(Finding(where, NO_REFERENCE, detail))
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
        if any(sign in token for sign in _SIGNS) or _CARRIES_A_UNIT.search(token):
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
    text that is not one number (module docstring). A scale word multiplies the number:
    ``$2.1 billion`` reads 2,100,000,000 and ``$``."""
    parsed = _parsed(text)
    return None if parsed is None else (parsed.number, parsed.suffix)


def fits(suffix: str, unit: str | None, scale: int = 1) -> bool:
    """Whether a cite with ``suffix``, and a scale word when ``scale`` is not 1, may cite a figure
    in ``unit``."""
    if scale != 1:
        return suffix in _SCALED and (unit is None or unit in _SCALED[suffix])
    return unit is None or unit in _FITS.get(suffix, frozenset())


def rounded_equal(
    cite: float,
    suffix: str,
    value: float,
    unit: str | None,
    scale: int = 1,
    decimals: int | None = None,
) -> bool:
    """Whether ``cite``, written with ``suffix`` (and a scale word when ``scale`` is not 1), is
    ``value`` in ``unit`` at the report's rounding (module docstring). A cite with a scale word, or
    of a figure with no unit, is compared at its own precision: the ``decimals`` it was written
    with, else those its number shows."""
    if not fits(suffix, unit, scale):
        return False
    scaled = value * 100 if unit == "percent" or (unit is None and suffix == "%") else value
    if scale != 1:  # at the cite's own precision in its scale
        written = round(cite / scale, 9)
        places = _decimals(written) if decimals is None else decimals
        return _within(written, scaled / scale, places)
    own = _decimals(cite) if decimals is None else decimals
    places_by_unit = _PLACES[unit] if unit is not None else (own,)
    return any(_on_grid(cite, p) and _within(cite, scaled, p) for p in places_by_unit)


def shown(value: float, unit: str | None) -> str:
    """The value as a cite of it reads at the report's rounding."""
    sign = "−" if value < 0 else ""
    size = abs(value)
    match unit:
        case "currency":
            return f"{sign}${size:,.0f}"
        case "per-share" | "price":
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
    stale = _stale_review(conn, resolver.symbol, ref)
    if stale is not None:
        return WRONG_SNAPSHOT, stale
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


def _stale_review(conn: sqlite3.Connection, symbol: str, ref: str) -> str | None:
    """Why a ``review:`` cite of the company is not of its current review, the newest on its
    snapshot that the current one is or reprices; ``None`` when it is, or for another ref."""
    form, _, path = ref.strip().partition(":")
    head = path.partition("/")[0]
    cited = review_row(conn, int(head)) if form == "review" and head.isdigit() else None
    if cited is None or cited.symbol != symbol:
        return None
    current = latest_review(conn, symbol)
    newest = latest_review_on(conn, cited.snapshot_id)
    if (
        current is not None
        and newest is not None
        and newest.id == cited.id
        and same_snapshot(conn, cited.snapshot_id, current.snapshot_id)
    ):
        return None
    now = "the company has none" if current is None else f"cite review:{current.id}"
    return f"{ref} is not the company's current review: {now}"


def _unit_failure(cite: str, ref: str, resolved: Resolved) -> tuple[str, str] | None:
    value, unit = resolved.value, resolved.unit
    if isinstance(value, str):
        if cite.strip().casefold() == value.strip().casefold():
            return None
        return WRONG_UNIT, f"{ref} reads {value!r}"
    assert value is not None  # the caller answered a figure with none
    if resolved.price and unit == "per-share":
        unit = "price"
    parsed = _parsed(cite)
    if parsed is None:
        return WRONG_UNIT, f"{cite!r} is not one number: {ref} reads {shown(value, unit)}"
    if parsed.suffix == "%" and unit == "multiple" and ref.strip().startswith(_RATIO_FORMS):
        unit = "percent"  # a ratio of two figures in one unit, written as a percentage
    target = abs(value) if resolved.outflow and not parsed.signed else value
    expected = shown(target, unit)
    if parsed.scale != 1 and parsed.significant < 2:
        rule = "a cite with a scale word gives two significant figures or more"
        return WRONG_UNIT, f"{rule}: {ref} reads {expected}"
    if not fits(parsed.suffix, unit, parsed.scale):
        return WRONG_UNIT, f"{cite!r} does not fit a {unit} figure: {ref} reads {expected}"
    if unit == "price" and parsed.decimals != 2:
        return WRONG_UNIT, f"a price is cited to cents: {ref} reads {expected}"
    found = (parsed.number, parsed.suffix, target, unit, parsed.scale, parsed.decimals)
    if not rounded_equal(*found):
        return WRONG_UNIT, f"{ref} reads {expected}"
    return None


def _parsed(text: str) -> _Cite | None:
    match = _CITE.fullmatch(text)
    if match is None or bool(match["open"]) != bool(match["close"]):
        return None
    if match["sign"] and match["sign2"]:
        return None
    sign = match["sign"] or match["sign2"] or ""
    if match["open"] and sign == "+":  # parentheses are a negative
        return None
    written = " ".join((match["suffix"] or "").split())
    suffix = "x" if match["upper"] else _SUFFIXES.get(written, "")
    scale = _SCALES[match["scale"].lower()] if match["scale"] else 1
    if suffix and (match["dollar"] or scale != 1):  # a %, x or years with $ or a scale
        return None
    if match["dollar"]:
        suffix = "$"
    digits = match["number"].replace(",", "")
    signed = bool(match["open"] or sign)
    negative = bool(match["open"]) or sign in _NEGATIVE
    decimals = len(digits.partition(".")[2])
    significant = len(digits.replace(".", "").lstrip("0"))
    number = float(Decimal(digits) * scale) * (-1 if negative else 1)
    return _Cite(number, suffix, scale, decimals, significant, signed)


def _plain_detail(what: str) -> str:
    if what == NOT_EMITTED:
        return "a ratio in plain text: derive it and cite the derivation"
    return "cite it with its reference, or write a small count in words"


def _multiple(token: str) -> bool:
    return token.rstrip(")").endswith(("x", "X", "×"))


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
