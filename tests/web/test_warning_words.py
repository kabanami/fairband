"""The plain words of a row's quality warnings and the mark's rule (spec 2026-11-19 7.5): each
quality warning reads by its code, ``margin-flag`` by its word, in the order of the result's
flags; a note has none, nor a code that left the method with 1.7. A mechanical value is marked
when no reviewed value stands over it and it carries ``warning_mark_min`` warnings or more."""

from fairband.engine.flags import QUALITY_WARNINGS
from fairband.engine.types import Flag
from fairband.web.warning_words import MARGIN_WORDS, WARNING_WORDS, is_marked, warning_words

# The hover's three warnings of the Words table, each flag's word the engine's.
THREE = (
    Flag("heavy-capex", "Heavy capex", ""),
    Flag("negative-fcf", "Negative free cash flow", ""),
    Flag("equity-raise", "Equity raise", ""),
)
THREE_WORDS = ["heavy capital spending", "negative free cash flow", "new shares issued"]


def test_every_quality_warning_has_its_words() -> None:
    assert set(WARNING_WORDS) | {"margin-flag"} == QUALITY_WARNINGS
    assert "margin-flag" not in WARNING_WORDS
    # the Words table's, copied
    assert WARNING_WORDS == {
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
    assert MARGIN_WORDS == {
        "Margin above history": "margin above its history",
        "Newly profitable": "newly profitable",
        "Possible cycle peak": "possible cycle peak",
    }


def test_the_words_follow_the_flags_and_leave_the_notes_out() -> None:
    notes = (
        Flag("fcf-sign", "Free cash flow disagrees", ""),
        Flag("roic-on-n-years", "ROIC on 7 years", ""),
        Flag("sbc-basis-uncertain", "Stock-pay basis uncertain", ""),
    )
    mixed = (notes[0], THREE[0], notes[1], THREE[1], THREE[2], notes[2])
    assert warning_words(mixed) == THREE_WORDS
    assert warning_words(mixed[::-1]) == THREE_WORDS[::-1]
    assert warning_words(notes) == [] and warning_words(()) == []
    one = Flag("one-time-items", "One-time items", "")
    assert warning_words((*notes, one)) == ["one-time items"]


def test_margin_flag_reads_by_its_word() -> None:
    for word, words in MARGIN_WORDS.items():
        assert warning_words((Flag("margin-flag", word, ""),)) == [words], word
    # a word the engine does not write reads as the flag's first meaning
    assert warning_words((Flag("margin-flag", "Margin far above", ""),)) == [
        "margin above its history"
    ]
    margin = Flag("margin-flag", "Possible cycle peak", "")
    assert warning_words((THREE[0], margin, THREE[1])) == [
        "heavy capital spending",
        "possible cycle peak",
        "negative free cash flow",
    ]


def test_a_result_valued_before_1_7_counts_neither_old_code() -> None:
    old = (Flag("large-nri", "", ""), Flag("consensus-basis-unknown", "", ""))
    assert warning_words(old) == []
    # as a stored result holds them: their words, among two warnings, which alone count
    stored = (
        Flag("large-nri", "Large NRI", "The non-recurring gap is large."),
        THREE[1],
        Flag("consensus-basis-unknown", "Consensus basis unknown", ""),
        THREE[2],
    )
    words = warning_words(stored)
    assert words == ["negative free cash flow", "new shares issued"]
    assert not is_marked(12.40, None, words, 3)


def test_is_marked() -> None:
    three = ["a", "b", "c"]
    assert is_marked(12.40, None, three, 3) and not is_marked(12.40, None, three[:2], 3)
    assert not is_marked(12.40, 13.0, three, 3) and not is_marked(None, None, three, 3)
    # the cut-off is the policy's: more than it marks, and it may be any count from one
    assert is_marked(12.40, None, [*three, "d"], 3)
    assert is_marked(12.40, None, three[:1], 1) and not is_marked(12.40, None, [], 1)
    assert not is_marked(12.40, None, three, 4)
