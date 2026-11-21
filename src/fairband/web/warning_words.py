"""The plain words of a row's quality warnings and the rule of the mark beside a mechanical value
(spec 2026-11-19 7.5).

A quality warning (``engine.flags.QUALITY_WARNINGS``) reads by its code (``WARNING_WORDS``), and
``margin-flag`` by its word (``MARGIN_WORDS``), since its one code holds three meanings; a word
the engine does not write reads as the flag's first meaning. The words live here, in the web
layer, by flag code: ``Flag.word`` stays the engine's, as every stored result holds it. A note has
no words, nor a code that left the method: a result valued before method 1.7 may hold
``large-nri`` and ``consensus-basis-unknown``, which are no quality warning and count for nothing.

A mechanical value is marked when no reviewed value stands over it and it carries the policy's
``warning_mark_min`` warnings or more (``is_marked``).
"""

from collections.abc import Mapping, Sequence

from fairband.engine.flags import QUALITY_WARNINGS
from fairband.engine.types import Flag

# The plain words of each quality warning but margin-flag, by its code (spec 7.5's table).
WARNING_WORDS: Mapping[str, str] = {
    "one-time-items": "one-time items",
    "value-spread": "value sensitive to its inputs",
    "z-distress": "distress signal",
    "f-score-low": "weak financial health",
    "reinvesting-in-decline": "investing while revenue falls",
    "equity-raise": "new shares issued",
    "negative-fcf": "negative free cash flow",
    "heavy-capex": "heavy capital spending",
    "burn-cover-short": "cash covers under two years",
    "consensus-recovery": "analysts expect a recovery",
    "share-count-gap": "share count unclear",
}
# The plain words of margin-flag, by the flag's word (``engine.flags.margin_flag``).
MARGIN_WORDS: Mapping[str, str] = {
    "Margin above history": "margin above its history",
    "Newly profitable": "newly profitable",
    "Possible cycle peak": "possible cycle peak",
}
_MARGIN = "margin-flag"
_MARGIN_UNKNOWN = MARGIN_WORDS["Margin above history"]


def warning_words(flags: Sequence[Flag]) -> list[str]:
    """The plain words of each of ``flags`` that is a quality warning, in their order."""
    return [_words(f) for f in flags if f.code in QUALITY_WARNINGS]


def _words(flag: Flag) -> str:
    if flag.code == _MARGIN:
        return MARGIN_WORDS.get(flag.word, _MARGIN_UNKNOWN)
    return WARNING_WORDS[flag.code]


def is_marked(
    value: float | None, reviewed: float | None, warnings: Sequence[str], mark_min: int
) -> bool:
    """Whether the mechanical ``value`` is marked: it is a value, no ``reviewed`` value stands
    over it, and it has ``mark_min`` ``warnings`` or more."""
    return value is not None and reviewed is None and len(warnings) >= mark_min
