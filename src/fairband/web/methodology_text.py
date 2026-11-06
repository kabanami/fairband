"""The Methodology page's sections as text (spec 2026-11-06 Tier 2, 15.2), for
``GET /api/methodology/{section}`` and the MCP ``methodology`` tool.

``section_text`` reads ``methodology.html`` with ``html.parser``: the title is the section's
``h2``, the text the rest of its text content, whitespace collapsed, with a space at each element
boundary but the inline ones. The elements ``methodology.js`` fills with a policy value read as
that script fills them, from the effective policy as ``GET /api/policy`` serves it and formatted
as the script formats each unit (``data-policy``, ``data-policy-version``, and
``data-policy-changed`` when a setting differs); so do the decile edges (``data-decile``) when a
full refresh has ranked the universe. The phase counts (``data-count``) are the screen's, not the
method's, and keep the page's em dash, as does a value the policy lacks.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from html.parser import HTMLParser
from importlib import resources
from typing import Any

_METHODOLOGY = resources.files("fairband.web").joinpath("static", "methodology.html")
_DASH = "—"
# The elements whose boundaries add no space to the text.
_INLINE = frozenset(
    {"a", "abbr", "b", "cite", "code", "em", "i", "q", "small", "span", "strong", "sub", "sup"}
)


def section_text(
    section: str, cited: Mapping[str, Any], deciles: Mapping[str, Any] | None
) -> tuple[str, str] | None:
    """The title and the text of the page's ``<section id>``; ``None`` for an unknown id.
    ``cited`` is ``GET /api/policy``'s answer and ``deciles`` ``GET /api/deciles``' (``None``
    before a full refresh ranked the universe)."""
    parsed = _Section(section, _Live(cited, deciles).text)
    parsed.feed(_METHODOLOGY.read_text(encoding="utf-8"))
    parsed.close()
    if not parsed.found:
        return None
    return _collapsed(parsed.title), _collapsed(parsed.text)


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
