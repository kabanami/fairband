"""The company page's Investor relations tab from FMP's stored answers (the Investor relations tab's
design, 5, 7.4, 7.5 and 8.2): pure readers, a parsed payload in and plain data out, with no store,
network or clock, beside the page's others (``page_fmp``, ``page_financials``). The refresh and
the tab's reads hand them the stored ``transcript``, ``transcript-dates``, ``earnings`` and
``sec-filings`` answers.

- A transcript is FMP's one row ``{symbol, period, year, date, content}``, its content plain text.
  Its turns are cut at the speaker's lines (``speaker_turns``), each turn's words broken into
  paragraphs at the ends of sentences (``paragraphs``), and the questions' start found by 7.4's
  rule (``questions_at``). Every word of the content stands in the turns, in its order: only a
  blank line is dropped, and the spaces at either end of a line or at a paragraph's break. A
  vendor's words stay text: nothing here reads or writes markup.
- A call is a row of the list of calls ``{quarter, fiscalYear, date}``, with the four figures of
  its quarter from the ``earnings`` row of its label dated near it (``calls``); nothing is
  computed, no gap to an estimate among them. Every figure is in US dollars, as the Estimates
  tab's (``page_fmp.money``).
- A filing is a row of the filing list, its two links kept only where they start ``https://``,
  so a vendor's row can put no other kind of address behind a press (``filing_rows``).
- An answer of the wrong shape (FMP's ``{"Error Message": ...}``, ``null``, a text, a list of
  anything but objects) reads as no answer: no words, no call, no filing. None of the readers
  raises on any JSON value.
"""

import re
from collections.abc import Iterator, Sequence
from datetime import date
from typing import Any

from fairband.vendors._fmp_parse import dated, objects, parse_date, text, whole
from fairband.vendors.page_fmp import money

type Turn = tuple[str | None, str]  # (the speaker's name, or None for no name; the turn's words)

PARAGRAPH_CHARS = 520  # the longest paragraph but a single longer sentence
JOIN_DAYS = 45  # the most days between a call and the earnings row of its label
SPEAKER_WORDS = 6  # the most words in a speaker's name

_NAME_CHARS = range(2, 61)  # a speaker's name is 2 to 60 characters
_OPERATOR, _QUESTION = "operator", "question"
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")  # a `.`, `!` or `?` and the space after it
_USD = "USD"
_HTTPS = "https://"

# (the tab's name, the ``earnings`` row's field)
_FIGURES = (
    ("epsReported", "epsActual"),
    ("epsEstimate", "epsEstimated"),
    ("revenueReported", "revenueActual"),
    ("revenueEstimate", "revenueEstimated"),
)


def speaker_turns(content: str) -> list[Turn]:
    """The turns of a transcript's text, line by line (7.4). A speaker's line, ``Name: words``,
    starts a turn: the name is the text before the line's first ``": "``, of 2 to 60 characters,
    with no colon in it and of ``SPEAKER_WORDS`` words at most. Any other line that is not blank
    joins the turn before it after one space; before any speaker's line it starts a turn with no
    name. A line's spaces at either end are dropped; its words are kept as given."""
    turns: list[tuple[str | None, list[str]]] = []  # a turn's lines, joined at the end
    for line in (raw.strip() for raw in content.splitlines()):
        if not line:
            continue
        spoken = _speaker_line(line)
        if spoken is not None:
            turns.append((spoken[0], [spoken[1]]))
        elif turns:
            turns[-1][1].append(line)
        else:
            turns.append((None, [line]))
    return [(speaker, " ".join(lines)) for speaker, lines in turns]


def paragraphs(words: str) -> list[str]:
    """A turn's words in paragraphs (7.4): broken after a ``.``, ``!`` or ``?`` and the space after
    it, and the sentences packed in order, each paragraph taking the next while it stays at
    ``PARAGRAPH_CHARS`` characters or under, so that no paragraph passes it but a single longer
    sentence, which stands alone. Joined by one space, the paragraphs are the words as given, but
    for the spaces around them and the spaces at a break, which are one."""
    out: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(words.strip()):
        if not sentence:
            continue
        if current and len(current) + 1 + len(sentence) > PARAGRAPH_CHARS:
            out.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current:
        out.append(current)
    return out


def questions_at(turns: Sequence[Turn]) -> int | None:
    """The index of the questions' first turn (7.4): the first turn whose speaker is ``Operator``,
    whatever the case, that has a turn by another named speaker somewhere before it and whose
    words hold ``question``, whatever the case. A turn with no name is no other speaker, so a
    call's opening before any name is no start. ``None`` where no turn fits."""
    spoken = False  # a turn by a named speaker other than the operator has come
    for index, (speaker, words) in enumerate(turns):
        if speaker is None:
            continue
        if speaker.casefold() != _OPERATOR:
            spoken = True
        elif spoken and _QUESTION in words.casefold():
            return index
    return None


def has_words(payload: Any) -> bool:
    """Whether a ``transcript`` answer holds words (8.2): a list whose first row is an object with
    a ``content`` that is a text and not blank. A call the vendor has no words for answers no
    row, or a row with no text (7.4)."""
    return text(_content(payload)) is not None


def transcript(payload: Any) -> dict[str, Any]:
    """A call's transcript from a ``transcript`` answer's first row (7.4, 8.2): ``date``, the ISO
    date of its ``date``, ``None`` without one; ``turns``, each ``{"speaker", "paragraphs"}`` by
    ``speaker_turns`` and ``paragraphs``, empty where the answer has no words (``has_words``);
    and ``questionsAt``, the index of the questions' first turn by ``questions_at``, else
    ``None``. A row without words keeps its date."""
    turns = speaker_turns(_content(payload))  # none for a blank content
    return {
        "date": _iso(parse_date(_first_row(payload).get("date"))),
        "turns": [{"speaker": who, "paragraphs": paragraphs(words)} for who, words in turns],
        "questionsAt": questions_at(turns),
    }


def newest_call(dates: Any) -> tuple[int, int] | None:
    """The fiscal year and quarter of the newest call of a ``transcript-dates`` answer: the usable
    row (``calls``) with the latest ``date``, the first on a tie; ``None`` without one."""
    newest = max(_calls(dates), key=lambda call: call[0], default=None)
    return None if newest is None else (newest[1], newest[2])


def calls(dates: Any, earnings: Any) -> list[dict[str, Any]]:
    """Every call of a ``transcript-dates`` answer, newest first by ``date`` (rows of one date in
    the answer's order), each ``{"fiscalYear", "quarter", "date", "epsReported", "epsEstimate",
    "revenueReported", "revenueEstimate"}`` (7.4, 8.2).

    A usable row holds a whole ``fiscalYear`` and a ``quarter`` of 1 to 4, each a JSON number
    (``2026``, ``2026.0``) and never a text (``"2026"``), and an ISO ``date``; any other row is
    dropped. The four figures are the ``earnings`` row's of the call's label, its ``fiscalYear``
    the call's (read by ``whole``, a text of digits among them) and its ``fiscalPeriod``
    ``Q<quarter>``, dated within ``JOIN_DAYS`` of the call, before or after: the design's section
    5 found a quarter's row within four weeks of its call, and another period under the same
    label months or a year off. Of several such rows the nearest in days is the call's, the
    first on a tie. Each figure is ``page_fmp.money`` of its field in US dollars, ``None`` where
    the row lacks it or where no row is the call's."""
    rows = list(dated(earnings))
    found = sorted(_calls(dates), key=lambda call: call[0], reverse=True)
    return [
        {"fiscalYear": year, "quarter": quarter, "date": when.isoformat()}
        | _figures(_earnings_row(rows, year, quarter, when))
        for when, year, quarter in found
    ]


def filing_rows(payload: Any) -> list[dict[str, Any]]:
    """The rows of a ``sec-filings`` answer, in its order, put in no other: each object row with a
    ``formType`` that is a text and not blank, as ``{"form", "filed", "document",
    "files"}`` (7.5, 8.2). ``form`` is the form as given; ``filed`` the ISO date of the
    ``filingDate``, ``None`` without one; ``document`` the ``finalLink``, the filing's main
    document, and ``files`` the ``link``, its index page, each ``None`` unless a text that starts
    ``https://``. Any other row is dropped."""
    out: list[dict[str, Any]] = []
    for row in objects(payload):
        form = text(row.get("formType"))
        if form is None:
            continue
        out.append(
            {
                "form": form,
                "filed": _iso(parse_date(row.get("filingDate"))),
                "document": _https(row.get("finalLink")),
                "files": _https(row.get("link")),
            }
        )
    return out


def _speaker_line(line: str) -> Turn | None:
    """``(name, words)`` of a stripped line that is a speaker's line, else ``None``."""
    name, colon, words = line.partition(": ")
    name = name.strip()
    if (
        not colon
        or ":" in name
        or len(name) not in _NAME_CHARS
        or len(name.split()) > SPEAKER_WORDS
    ):
        return None
    return name, words.strip()


def _first_row(payload: Any) -> dict[str, Any]:
    """A list answer's first row where it is an object, else an empty row."""
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    return {}


def _content(payload: Any) -> str:
    """The first row's ``content`` where it is a text, else an empty text."""
    content = _first_row(payload).get("content")
    return content if isinstance(content, str) else ""


def _calls(dates: Any) -> Iterator[tuple[date, int, int]]:
    """``(date, fiscal year, quarter)`` of each usable row of a ``transcript-dates`` answer, in
    the answer's order."""
    for row in objects(dates):
        year, quarter = _count(row.get("fiscalYear")), _count(row.get("quarter"))
        when = parse_date(row.get("date"))
        if year is not None and quarter is not None and 1 <= quarter <= 4 and when is not None:
            yield when, year, quarter


def _count(raw: Any) -> int | None:
    """A whole JSON number (``2026``, ``2026.0``); ``None`` for a text, a boolean or any other."""
    return None if isinstance(raw, str) else whole(raw)


def _earnings_row(
    rows: Sequence[tuple[dict[str, Any], date]], year: int, quarter: int, call: date
) -> dict[str, Any]:
    """The ``earnings`` row of a call (``calls``), else an empty row."""
    labelled = (
        (abs((when - call).days), row)
        for row, when in rows
        if whole(row.get("fiscalYear")) == year and text(row.get("fiscalPeriod")) == f"Q{quarter}"
    )
    near = [(days, row) for days, row in labelled if days <= JOIN_DAYS]
    return min(near, key=lambda pair: pair[0], default=(0, {}))[1]


def _figures(row: dict[str, Any]) -> dict[str, Any]:
    """The four figures of an ``earnings`` row under the tab's names, in US dollars."""
    return {name: money(row.get(field), _USD) for name, field in _FIGURES}


def _https(raw: Any) -> str | None:
    """A link that is a text and starts ``https://``, stripped; ``None`` for any other."""
    link = text(raw)
    return link if link is not None and link.startswith(_HTTPS) else None


def _iso(when: date | None) -> str | None:
    return None if when is None else when.isoformat()
