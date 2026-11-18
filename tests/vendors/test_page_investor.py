"""The Investor relations tab's payload readers against synthetic answers, an invented company's
invented call among them: a transcript's turns by the speaker's line with every word kept in
order, its paragraphs at sentence ends under the limit, where the questions start, the calls
joined to the earnings rows by label and date, a filing list's rows and links, and an answer of
the wrong shape read as no answer."""

from typing import Any

import pytest

from fairband.vendors.page_fmp import money
from fairband.vendors.page_investor import (
    JOIN_DAYS,
    PARAGRAPH_CHARS,
    SPEAKER_WORDS,
    calls,
    filing_rows,
    has_words,
    newest_call,
    paragraphs,
    questions_at,
    speaker_turns,
    transcript,
)

CEO = "Mira Osei -- Chief Executive Officer"
ANALYST = "Tomas Reyes -- Analyst"

# Pellbrook Kettles, an invented company, and its invented third-quarter call: a line before the
# first speaker's line, an operator who opens the call and names the questions to come, a blank
# line, a line that reads as a speaker's ("Note: ..."), a line with no name, then the operator in
# capitals opening the questions.
CALL = (
    "Pellbrook Kettles third quarter 2026 earnings call\n"
    "Operator: Good morning, and welcome. A question session follows the remarks.\n"
    f"{CEO}: Thank you. We sold more kettles than in any quarter before.\n"
    "\n"
    "Note: see the slides for the regional split.\n"
    "Revenue rose in every region.\n"
    "OPERATOR: We will now begin the Question-and-answer session.\n"
    f"{ANALYST}: How did prices move in the quarter?\n"
    f"{CEO}: Up two points, on the new range.\n"
)
TURNS = [
    (None, "Pellbrook Kettles third quarter 2026 earnings call"),
    ("Operator", "Good morning, and welcome. A question session follows the remarks."),
    (CEO, "Thank you. We sold more kettles than in any quarter before."),
    ("Note", "see the slides for the regional split. Revenue rose in every region."),
    ("OPERATOR", "We will now begin the Question-and-answer session."),
    (ANALYST, "How did prices move in the quarter?"),
    (CEO, "Up two points, on the new range."),
]
ROW = {"symbol": "PLBK", "period": "Q3", "year": 2026, "date": "2026-10-28 17:00:00"}

WRONG_SHAPES: list[Any] = [
    [],
    {"Error Message": "x"},
    None,
    "Operator: hello",
    17,
    ["Operator: hello"],
    [{"content": "  "}],
    [{"content": ""}],
    [{"content": 5}],
    [{"date": "2026-10-28"}],
    [{"content": "  "}, {"content": "Operator: hello"}],
]


def said(turns: list[tuple[str | None, str]]) -> list[str]:
    """Every word of the turns in order, a speaker's name as its line gave it."""
    return " ".join(words if who is None else f"{who}: {words}" for who, words in turns).split()


def test_the_limits() -> None:
    assert (PARAGRAPH_CHARS, JOIN_DAYS, SPEAKER_WORDS) == (520, 45, 6)


# The turns


def test_a_speaker_s_line_starts_a_turn_and_another_line_joins_it() -> None:
    content = "Opening music\nAda Park: Good day.\nMore words.\nOperator: First question.\n"
    assert speaker_turns(content) == [
        (None, "Opening music"),
        ("Ada Park", "Good day. More words."),
        ("Operator", "First question."),
    ]


def test_seven_words_or_a_colon_in_the_name_is_no_speaker_s_line() -> None:
    assert speaker_turns("one two three four five six seven: words") == [
        (None, "one two three four five six seven: words")
    ]
    assert speaker_turns("https://example.com/a: b") == [(None, "https://example.com/a: b")]


def test_six_words_make_a_speaker_s_name() -> None:
    assert speaker_turns("one two three four five six: words") == [
        ("one two three four five six", "words")
    ]
    assert speaker_turns(f"{CEO}: Thanks.") == [(CEO, "Thanks.")]


def test_a_name_is_two_to_sixty_characters() -> None:
    assert speaker_turns("Q: What moved?") == [(None, "Q: What moved?")]
    assert speaker_turns("Bo: Fine.") == [("Bo", "Fine.")]
    assert speaker_turns("A" * 60 + ": Fine.") == [("A" * 60, "Fine.")]
    assert speaker_turns("A" * 61 + ": Fine.") == [(None, "A" * 61 + ": Fine.")]


def test_a_colon_with_no_space_after_it_is_no_speaker_s_line() -> None:
    assert speaker_turns("Ada: Hello.\n10:30 the call began late.") == [
        ("Ada", "Hello. 10:30 the call began late.")
    ]


def test_the_invented_call_s_turns_keep_every_word_in_order() -> None:
    turns = speaker_turns(CALL)
    assert turns == TURNS
    assert said(turns) == CALL.split()


def test_a_content_with_no_speaker_s_line_is_one_turn_with_no_name() -> None:
    content = "Good morning, all of you\nwith no name on any line.\n\n\nThe end.  \n"
    assert speaker_turns(content) == [
        (None, "Good morning, all of you with no name on any line. The end.")
    ]
    assert said(speaker_turns(content)) == content.split()


def test_blank_lines_and_windows_line_ends_split_no_word() -> None:
    assert speaker_turns("Ada: One.\r\n\r\n  Two.  \r\nBo: Three.\r\n") == [
        ("Ada", "One. Two."),
        ("Bo", "Three."),
    ]


def test_a_content_of_no_words_has_no_turn() -> None:
    assert speaker_turns("") == []
    assert speaker_turns(" \n\t\n ") == []


def test_a_turn_of_many_lines_keeps_them_all_in_order() -> None:
    lines = [f"Kettle line {n} sold well." for n in range(5_000)]
    turns = speaker_turns("Ada Park: Hello.\n" + "\n".join(lines))
    assert turns == [("Ada Park", " ".join(["Hello.", *lines]))]


# The paragraphs


def test_paragraphs_end_at_sentences_and_stay_under_the_limit() -> None:
    sentence = "Word " * 59 + "end. "  # 300 characters
    parts = paragraphs((sentence * 4).strip())
    assert [len(p) <= PARAGRAPH_CHARS for p in parts] == [True] * 4
    assert " ".join(parts) == (sentence * 4).strip()
    long = "x" * 600 + "."
    assert paragraphs(long + " Short one.") == [long, "Short one."]


def test_paragraphs_pack_sentences_greedily() -> None:
    sentence = "k" * 99 + "."  # 100 characters: five and their spaces make 504
    parts = paragraphs(" ".join([sentence] * 12))
    assert parts == [" ".join([sentence] * 5)] * 2 + [" ".join([sentence] * 2)]
    assert [len(p) for p in parts] == [504, 504, 201]


def test_a_question_mark_and_an_exclamation_mark_end_a_sentence() -> None:
    asked, cried = "y" * 299 + "?", "z" * 299 + "!"
    assert paragraphs(f"{asked} {cried} Done.") == [asked, f"{cried} Done."]


def test_a_point_with_no_space_after_it_ends_no_sentence() -> None:
    words = "Revenue was $1.5" + " billion" * 80 + "."
    assert len(words) > PARAGRAPH_CHARS
    assert paragraphs(words) == [words]


def test_a_turn_of_sixty_thousand_characters_is_kept_whole_in_paragraphs() -> None:
    marks = ".!?"
    words = " ".join(
        f"Line {n} of kettles sold {'well' * (n % 7 + 1)}{marks[n % 3]}" for n in range(2_000)
    )
    assert len(words) > 60_000
    parts = paragraphs(words)
    assert " ".join(parts) == words
    assert all(len(part) <= PARAGRAPH_CHARS for part in parts)
    assert all(part[-1] in marks for part in parts)


def test_words_of_no_sentence_have_no_paragraph() -> None:
    assert paragraphs("") == []
    assert paragraphs("   ") == []


# The questions' start


def test_the_questions_start_at_the_operator_s_turn_that_says_question() -> None:
    opened = [
        ("Operator", "Welcome."),
        ("Ada Park", "Thanks."),
        ("OPERATOR", "Our first Question."),
    ]
    assert questions_at(opened) == 2
    assert questions_at([("Operator", "Welcome to the question session."), ("Ada", "Hi.")]) is None
    assert questions_at([("Ada", "Hi."), ("Operator", "Please go ahead.")]) is None
    assert questions_at([("Ada", "Any question?"), ("Bo", "No.")]) is None


def test_an_operator_s_turn_without_question_is_passed_over() -> None:
    turns = [
        ("Ada", "Remarks."),
        ("Operator", "Please go ahead."),
        ("Bo", "More remarks."),
        ("operator", "We take questions now."),
    ]
    assert questions_at(turns) == 3


def test_a_turn_with_no_name_is_no_other_speaker() -> None:
    assert questions_at([(None, "Music."), ("Operator", "A question session follows.")]) is None


def test_the_invented_call_s_questions_start_where_the_operator_opens_them() -> None:
    assert questions_at(TURNS) == 4
    assert questions_at([]) is None


# The transcript


def test_has_words() -> None:
    assert has_words([{**ROW, "content": CALL}]) is True
    assert has_words([{"content": "No name at all."}]) is True


@pytest.mark.parametrize("payload", WRONG_SHAPES)
def test_an_answer_with_no_words_has_none(payload: Any) -> None:
    assert has_words(payload) is False
    assert transcript(payload)["turns"] == []
    assert transcript(payload)["questionsAt"] is None


def test_the_transcript() -> None:
    answer = transcript([{**ROW, "content": CALL}])
    assert answer == {
        "date": "2026-10-28",
        "turns": [{"speaker": who, "paragraphs": [words]} for who, words in TURNS],
        "questionsAt": 4,
    }


def test_a_transcript_with_no_words_keeps_its_date() -> None:
    assert transcript([{**ROW, "content": "  "}]) == {
        "date": "2026-10-28",
        "turns": [],
        "questionsAt": None,
    }
    assert transcript([{"content": CALL, "date": "late October"}])["date"] is None
    assert transcript({"Error Message": "x"}) == {"date": None, "turns": [], "questionsAt": None}


def test_a_transcript_with_no_speaker_s_line_keeps_every_word_in_one_turn() -> None:
    content = " ".join(f"Sentence {n} of a call with no names." for n in range(200))
    answer = transcript([{"date": "2026-10-28", "content": content}])
    assert [turn["speaker"] for turn in answer["turns"]] == [None]
    assert " ".join(answer["turns"][0]["paragraphs"]).split() == content.split()
    assert answer["questionsAt"] is None


# The calls

DATES = [
    {"quarter": 3, "fiscalYear": 2026, "date": "2026-10-28"},
    {"quarter": 1, "fiscalYear": 2026, "date": "2026-04-29"},
    {"quarter": 2, "fiscalYear": 2026, "date": "2026-07-29"},
]
EARNED = {"epsActual": 2.0, "epsEstimated": 1.9, "revenueActual": 5e9, "revenueEstimated": 4.9e9}
NO_FIGURES = {
    "epsReported": None,
    "epsEstimate": None,
    "revenueReported": None,
    "revenueEstimate": None,
}


def earned(year: int, period: str, day: str | None, **figures: Any) -> dict[str, Any]:
    return {"fiscalYear": year, "fiscalPeriod": period, "date": day, **EARNED, **figures}


@pytest.mark.parametrize(
    "dropped",
    [
        {"quarter": 5, "fiscalYear": 2027, "date": "2027-02-03"},
        {"quarter": 0, "fiscalYear": 2027, "date": "2027-02-03"},
        {"quarter": "4", "fiscalYear": 2026, "date": "2027-02-03"},
        {"quarter": 4, "fiscalYear": "2026", "date": "2027-02-03"},
        {"quarter": 4, "fiscalYear": 2026.5, "date": "2027-02-03"},
        {"quarter": 4, "fiscalYear": True, "date": "2027-02-03"},
        {"quarter": 4, "fiscalYear": 2026},
        {"quarter": 4, "fiscalYear": 2026, "date": "early February"},
        "2026Q4",
    ],
)
def test_a_row_that_is_not_a_call_is_dropped(dropped: Any) -> None:
    assert newest_call([*DATES, dropped]) == (2026, 3)
    assert [(c["fiscalYear"], c["quarter"]) for c in calls([*DATES, dropped], [])] == [
        (2026, 3),
        (2026, 2),
        (2026, 1),
    ]


def test_the_newest_call_is_found_by_its_date_not_its_place() -> None:
    assert newest_call(DATES) == (2026, 3)
    assert newest_call([*DATES, {"quarter": 4, "fiscalYear": 2026, "date": "2027-02-03"}]) == (
        2026,
        4,
    )
    assert newest_call([{"quarter": 4, "fiscalYear": 2026.0, "date": "2027-02-03"}]) == (2026, 4)


@pytest.mark.parametrize("payload", [[], {"Error Message": "x"}, None, [{"quarter": 1}]])
def test_a_list_with_no_call_has_no_newest_and_no_calls(payload: Any) -> None:
    assert newest_call(payload) is None
    assert calls(payload, [earned(2026, "Q1", "2026-04-29")]) == []


def test_the_calls_stand_newest_first() -> None:
    assert [c["date"] for c in calls(DATES, [])] == ["2026-10-28", "2026-07-29", "2026-04-29"]


def test_a_call_takes_the_earnings_row_of_its_label_within_45_days() -> None:
    dates = [{"quarter": 1, "fiscalYear": 2025, "date": "2025-04-17"}]
    row = {
        "fiscalYear": 2025,
        "fiscalPeriod": "Q1",
        "epsActual": 2.0,
        "epsEstimated": 1.9,
        "revenueActual": 5e9,
        "revenueEstimated": 4.9e9,
    }
    near = calls(dates, [{**row, "date": "2025-05-15"}])[0]
    assert near["epsReported"] == money(2.0, "USD")
    assert near["revenueEstimate"] == money(4.9e9, "USD")
    far = calls(dates, [{**row, "date": "2026-04-17"}])[0]
    assert far["epsReported"] is None and far["date"] == "2025-04-17"


def test_a_call() -> None:
    joined = calls(DATES[:1], [earned(2026, "Q3", "2026-10-28 16:30:00")])
    assert joined == [
        {
            "fiscalYear": 2026,
            "quarter": 3,
            "date": "2026-10-28",
            "epsReported": {"value": 2.0, "currency": "USD"},
            "epsEstimate": {"value": 1.9, "currency": "USD"},
            "revenueReported": {"value": 5e9, "currency": "USD"},
            "revenueEstimate": {"value": 4.9e9, "currency": "USD"},
        }
    ]


@pytest.mark.parametrize(
    ("day", "joined"),
    [
        ("2026-10-28", True),
        ("2026-11-25", True),  # 28 days after, as TSM's
        ("2026-09-30", True),  # 28 days before
        ("2026-12-12", True),  # 45 days after
        ("2026-09-13", True),  # 45 days before
        ("2026-12-13", False),  # 46 days after
        ("2026-09-12", False),  # 46 days before
        ("2026-03-28", False),  # five months before, as RELX's
        ("2027-10-28", False),  # a year after, as GOOG's
        (None, False),
    ],
)
def test_the_earnings_row_must_be_dated_within_45_days(day: str | None, joined: bool) -> None:
    call = calls(DATES[:1], [earned(2026, "Q3", day)])[0]
    assert (call["epsReported"] == money(2.0, "USD")) is joined


@pytest.mark.parametrize(
    "row",
    [
        earned(2026, "Q2", "2026-10-28"),
        earned(2025, "Q3", "2026-10-28"),
        earned(2026, "q3", "2026-10-28"),
        earned(2026, "Q3 2026", "2026-10-28"),
        {**earned(2026, "Q3", "2026-10-28"), "fiscalPeriod": None},
        {**earned(2026, "Q3", "2026-10-28"), "fiscalYear": None},
    ],
)
def test_the_earnings_row_must_bear_the_call_s_label(row: dict[str, Any]) -> None:
    assert calls(DATES[:1], [row]) == [
        {"fiscalYear": 2026, "quarter": 3, "date": "2026-10-28", **NO_FIGURES}
    ]


def test_the_earnings_row_s_fiscal_year_may_be_a_text_of_digits() -> None:
    row = {**earned(2026, "Q3", "2026-10-28"), "fiscalYear": "2026"}
    assert calls(DATES[:1], [row])[0]["epsReported"] == money(2.0, "USD")


def test_of_the_rows_of_the_label_the_nearest_is_the_call_s_the_first_on_a_tie() -> None:
    rows = [
        earned(2026, "Q3", "2026-11-20", epsActual=1.0),
        earned(2026, "Q3", "2026-10-29", epsActual=3.0),
        earned(2026, "Q3", "2026-10-27", epsActual=4.0),
    ]
    assert calls(DATES[:1], rows)[0]["epsReported"] == money(3.0, "USD")


def test_a_figure_the_row_lacks_is_none() -> None:
    row = earned(2026, "Q3", "2026-10-28", epsActual=None, revenueActual="5e9")
    del row["epsEstimated"]
    call = calls(DATES[:1], [row])[0]
    assert (call["epsReported"], call["epsEstimate"], call["revenueReported"]) == (None,) * 3
    assert call["revenueEstimate"] == money(4.9e9, "USD")


@pytest.mark.parametrize("earnings", [[], {"Error Message": "x"}, None, ["Q3"]])
def test_earnings_of_the_wrong_shape_give_no_figures(earnings: Any) -> None:
    assert calls(DATES[:1], earnings)[0] == {
        "fiscalYear": 2026,
        "quarter": 3,
        "date": "2026-10-28",
        **NO_FIGURES,
    }


# The filings

SEC = "https://www.sec.gov/Archives/edgar/data/1/000000000126000008"


def filed(form: Any = "8-K", day: Any = "2026-10-30 00:00:00", **links: Any) -> dict[str, Any]:
    row = {"symbol": "PLBK", "formType": form, "filingDate": day, "acceptedDate": day}
    return row | {"link": f"{SEC}/index.htm", "finalLink": f"{SEC}/plbk-8k.htm"} | links


def test_filing_rows() -> None:
    assert filing_rows([filed(), filed("4", "2026-10-29 00:00:00")]) == [
        {
            "form": "8-K",
            "filed": "2026-10-30",
            "document": f"{SEC}/plbk-8k.htm",
            "files": f"{SEC}/index.htm",
        },
        {
            "form": "4",
            "filed": "2026-10-29",
            "document": f"{SEC}/plbk-8k.htm",
            "files": f"{SEC}/index.htm",
        },
    ]


def test_the_filings_keep_the_answer_s_order() -> None:
    rows = [filed("10-Q", "2026-07-30"), filed("10-K", "2026-11-01"), filed("8-K", "2026-08-01")]
    assert [row["filed"] for row in filing_rows(rows)] == ["2026-07-30", "2026-11-01", "2026-08-01"]


@pytest.mark.parametrize(
    "link", [None, "", "  ", "javascript:alert(1)", "http://www.sec.gov/x.htm", "sec.gov/x", 5]
)
def test_a_link_that_is_not_https_is_none(link: Any) -> None:
    files = filing_rows([filed(link=link)])[0]
    assert (files["files"], files["document"]) == (None, f"{SEC}/plbk-8k.htm")
    document = filing_rows([filed(finalLink=link)])[0]
    assert (document["files"], document["document"]) == (f"{SEC}/index.htm", None)


def test_a_missing_link_is_none() -> None:
    row = filed()
    del row["link"], row["finalLink"]
    assert filing_rows([row]) == [
        {"form": "8-K", "filed": "2026-10-30", "document": None, "files": None}
    ]


def test_a_filing_with_no_day_keeps_its_row() -> None:
    assert filing_rows([filed(day=None)])[0]["filed"] is None
    assert filing_rows([filed(day="last week")])[0]["filed"] is None


@pytest.mark.parametrize("form", [None, "", "  ", 4, ["8-K"]])
def test_a_row_with_no_form_is_dropped(form: Any) -> None:
    assert [row["form"] for row in filing_rows([filed(form), filed("10-K")])] == ["10-K"]


def test_a_row_that_is_no_object_is_dropped() -> None:
    assert [row["form"] for row in filing_rows(["8-K", None, filed("SC 13G/A")])] == ["SC 13G/A"]


@pytest.mark.parametrize("payload", [[], {"Error Message": "x"}, None, "8-K", {"formType": "8-K"}])
def test_a_filing_list_of_the_wrong_shape_has_no_rows(payload: Any) -> None:
    assert filing_rows(payload) == []
