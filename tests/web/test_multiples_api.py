"""The multiples history read (spec 2026-11-06 Tier 2, 13.7; spec 2026-11-19 6.3) on the database
of ``conftest.py``, with a pass-through whose FMP client answers the P/E history's three calls
from a mock transport, and AAPL's multiples log rows written by each test: the two series built
and read, their statistics and refs, the loss days, a company in another currency, an answer that
cannot be read, and the stored series served when the fetch cannot be had."""

from collections import Counter
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from support.pe_history import (
    closes_payload,
    quarter_ends,
    quarters_payload,
    rates_payload,
    report_in,
    store_pe_history,
    unit_quarters,
)
from support.web import CREATED, HEADER, HOST, NOW, _settings

from fairband.policy import Policy
from fairband.refresh.passthrough import Passthrough
from fairband.reports.refs import Resolver
from fairband.store.db import connect
from fairband.store.multiples import log_multiples
from fairband.store.vendor import record_response
from fairband.vendors import fmp as fmp_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.http import VendorHttp
from fairband.web.app import create_app

# Eleven years of AAPL's P/E on 30 October and one day before the ten years, two of them in a loss
# year: the quarters each hold a diluted EPS of 0.50, a trailing EPS of 2.00, but for the quarters
# ending 30 September 2018 and 2021, which make the year from each a loss. A day's close is twice
# its P/E, 100.00 on a loss day. The ten years to the newest day run from 30 October 2016.
PE_BY_DAY: dict[str, float | None] = {
    "2016-10-29": 30.0,  # before the ten years: in no point and no statistic, yet the first day
    "2016-10-30": 20.0,
    "2017-10-30": 22.0,
    "2018-10-30": None,
    "2019-10-30": 18.0,
    "2020-10-30": 24.0,
    "2021-10-30": None,
    "2022-10-30": 16.0,
    "2023-10-30": 35.0,
    "2024-10-30": 21.0,
    "2025-10-30": 19.0,
    "2026-10-30": 23.0,
}
LOSSES = (date(2018, 9, 30), date(2021, 9, 30))
FMP_KEY = "fake-fmp-key-0005"  # not a real key
STATS = ("avg_10y", "median_10y", "high_10y", "low_10y")
CLOSES, QUARTERS, RATES = (
    "historical-price-eod/full",
    "income-statement",
    "historical-price-eod/light",
)
UNREAD = {"Error Message": "Limit Reach . Please upgrade your plan"}  # FMP's error object
UNREADABLE = "the series could not be read"


def _closes(symbol: str = "AAPL") -> list[dict[str, Any]]:
    closes = {day: 100.0 if pe is None else 2 * pe for day, pe in PE_BY_DAY.items()}
    return closes_payload(symbol, closes)


def _quarters(symbol: str = "AAPL") -> list[dict[str, Any]]:
    return unit_quarters(symbol, LOSSES, eps=0.5)


class FmpDouble:
    """FMP on a mock transport, answering the P/E history's calls by route with ``bodies`` and
    ``status``; ``calls`` counts them by route and ``asked`` keeps each route's last symbol."""

    def __init__(self) -> None:
        self.bodies: dict[str, Any] = {CLOSES: _closes(), QUARTERS: _quarters(), RATES: []}
        self.status = 200
        self.calls: Counter[str] = Counter()
        self.asked: dict[str, str] = {}
        self.transport = httpx.MockTransport(self._answer)

    def _answer(self, request: httpx.Request) -> httpx.Response:
        route = request.url.path.removeprefix("/stable/")
        self.calls[route] += 1
        self.asked[route] = request.url.params["symbol"]
        return httpx.Response(self.status, json=self.bodies[route])


@pytest.fixture
def fmp() -> FmpDouble:
    return FmpDouble()


@pytest.fixture
def with_history(
    tmp_path: Path, db_path: Path, policy: Policy, fmp: FmpDouble
) -> Iterator[TestClient]:
    """A client of an app whose pass-through's FMP client answers from ``fmp``."""
    with VendorHttp(
        fmp_api.BASE_URL, [FMP_KEY], policy.refresh, transport=fmp.transport, sleep=lambda _: None
    ) as http:
        passthrough = Passthrough(
            Fmp(http, FMP_KEY), lambda: connect(db_path), policy, lambda: NOW, (FMP_KEY,)
        )
        app = create_app(
            _settings(tmp_path, db_path),
            policy,
            lambda: connect(db_path),
            clock=lambda: NOW,
            passthrough=passthrough,
        )
        # the read may call a vendor, so it carries the request header (D11)
        with TestClient(app, base_url=HOST, headers=HEADER) as client:
            yield client


def _get(client: TestClient, url: str) -> Any:
    r = client.get(url, headers=HEADER)
    assert r.status_code == 200, r.text
    return r.json()


def _log(db_path: Path, rows: list[tuple[str, float | None]]) -> None:
    """AAPL's multiples log: a row a day at $150 with the forward P/E given."""
    with closing(connect(db_path)) as conn:
        for day, pe_forward in rows:
            log_multiples(
                conn, "AAPL", date.fromisoformat(day), 150.0, 25.0, 24.0, pe_forward, 1, 1, CREATED
            )


def _series(
    name: str,
    points: list[tuple[str, float]],
    stats: tuple[float | None, ...],
    since: str | None,
    response_id: int | None,
    note: str | None = None,
    symbol: str = "AAPL",
) -> dict[str, Any]:
    """The series as the read answers it, the company's refs beside each point and statistic."""
    ref = f"multiple:{symbol}/{name}"
    return {
        "points": [{"day": day, "value": value, "ref": f"{ref}/{day}"} for day, value in points],
        "stats": {
            stat.replace("_", ""): {"value": value, "unit": "multiple", "ref": f"{ref}/{stat}"}
            for stat, value in zip(STATS, stats, strict=True)
        },
        "since": since,
        "responseId": response_id,
        "note": note,
    }


def _stored(db_path: Path, endpoint: str, symbol: str = "AAPL") -> list[tuple[int, str | None]]:
    """The stored responses of one of the P/E history's endpoints, by id: the id and the error."""
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT id, error FROM vendor_responses WHERE provider = 'fmp' AND endpoint = ?"
            " AND symbol = ? ORDER BY id",
            (endpoint, symbol),
        ).fetchall()
    return [tuple(row) for row in rows]


def _store(db_path: Path, observed: datetime) -> int:
    """AAPL's closes and quarters, as ``fmp`` answers them, stored ``observed``; the closes' id."""
    with closing(connect(db_path)) as conn:
        parts = {"closes": _closes(), "quarters": _quarters()}
        return store_pe_history(conn, "AAPL", parts, observed)["closes"]


TRAILING = [(day, pe) for day, pe in PE_BY_DAY.items() if day >= "2016-10-30" and pe is not None]
TRAILING_STATS = (22.0, 21.0, 35.0, 16.0)  # the average, the median, the high and the low
MONTH_AGO = datetime(2026, 10, 2, 9, 30, tzinfo=UTC)  # past the reuse window


def test_the_multiples_history_read(
    with_history: TestClient, fmp: FmpDouble, db_path: Path, policy: Policy
) -> None:
    """The trailing series built from FMP's closes and quarters over the ten years to its newest
    day, each close ÷ its trailing EPS, the loss days left out and the statistics over the points
    left; ``since`` the first day with a trailing EPS. The forward series from the log, ``since``
    its first day. Every ref resolves to its figure, and a second read reuses the stored answers."""
    _log(db_path, [("2026-10-28", 20.0), ("2026-10-29", 25.0), ("2026-10-30", 21.0)])
    body = _get(with_history, "/api/companies/aapl/multiples-history")
    [(closes_id, error)] = _stored(db_path, "pe-closes")
    [(_, quarters_error)] = _stored(db_path, "pe-quarters")
    assert error is None and quarters_error is None
    assert body == {
        "symbol": "AAPL",
        "pe": _series("pe", TRAILING, TRAILING_STATS, "2016-10-29", closes_id),
        "peNote": None,
        "peForward": _series(
            "pe_forward",
            [("2026-10-28", 20.0), ("2026-10-29", 25.0), ("2026-10-30", 21.0)],
            (22.0, 21.0, 25.0, 20.0),
            "2026-10-28",
            None,
        ),
    }
    assert _get(with_history, "/api/companies/AAPL/multiples-history") == body
    assert fmp.calls == {CLOSES: 1, QUARTERS: 1}  # reused inside reuse_hours; USD: no pair
    figures = [
        *(p for series in ("pe", "peForward") for p in body[series]["points"]),
        *(s for series in ("pe", "peForward") for s in body[series]["stats"].values()),
    ]
    with closing(connect(db_path)) as conn:
        resolver = Resolver(conn, "AAPL", policy)
        for figure in figures:
            found = resolver.resolve(figure["ref"])
            assert found is not None, figure["ref"]
            assert (found.value, found.unit) == (figure["value"], "multiple"), figure["ref"]


def test_a_company_in_another_currency_reads_its_close_at_the_pair_s_rate(
    with_history: TestClient, fmp: FmpDouble, db_path: Path
) -> None:
    """TWCO reports in TWD: the read asks the pair's closes too, and a day's close in USD comes
    into TWD at the pair's last close at or before it: 10 × 30 ÷ 15 on the 28th, 10 × 31 ÷ 15 on
    the 29th and on the 30th, at the 29th's rate; nothing before the pair's first close."""
    with closing(connect(db_path)) as conn:
        report_in(conn, "TWCO", "TWD")
    closes = {"2026-10-26": 10.0, "2026-10-28": 10.0, "2026-10-29": 10.0, "2026-10-30": 10.0}
    eps = [(end, 3.75) for end in quarter_ends(date(2025, 12, 31), 4)]
    fmp.bodies = {
        CLOSES: closes_payload("TWCO", closes),
        QUARTERS: quarters_payload("TWCO", eps, "TWD"),
        RATES: rates_payload("USDTWD", {"2026-10-28": 30.0, "2026-10-29": 31.0}),
    }
    body = _get(with_history, "/api/companies/TWCO/multiples-history")
    [(closes_id, error)] = _stored(db_path, "pe-closes", "TWCO")
    [(_, rates_error)] = _stored(db_path, "pe-rates", "USDTWD")  # stored under the pair
    assert error is None and rates_error is None
    assert fmp.calls == {CLOSES: 1, QUARTERS: 1, RATES: 1} and fmp.asked[RATES] == "USDTWD"
    at_30, at_31 = 10 * 30 / 15, 10 * 31 / 15
    days = [(point["day"], point["value"]) for point in body["pe"]["points"]]
    assert days == [("2026-10-28", at_30), ("2026-10-29", at_31), ("2026-10-30", at_31)]
    assert body["pe"]["stats"]["high10y"]["value"] == at_31
    assert (body["pe"]["since"], body["pe"]["responseId"], body["peNote"]) == (
        "2026-10-28",
        closes_id,
        None,
    )


def test_a_log_row_without_a_forward_pe_has_no_point(
    with_history: TestClient, db_path: Path
) -> None:
    """A log row with no forward P/E has no point, yet the log began on its day."""
    _log(db_path, [("2026-10-29", None), ("2026-10-30", 21.0)])
    body = _get(with_history, "/api/companies/AAPL/multiples-history")
    assert body["peForward"] == _series(
        "pe_forward", [("2026-10-30", 21.0)], (21.0, 21.0, 21.0, 21.0), "2026-10-29", None
    )


def test_without_a_pass_through_or_a_stored_series_the_trailing_series_is_null(
    client: TestClient, db_path: Path
) -> None:
    """With no series stored and no pass-through (no FMP key), the trailing series is ``null``
    with the reason in ``peNote``. The forward series still answers."""
    _log(db_path, [("2026-10-30", 21.0)])
    forward = _series(
        "pe_forward", [("2026-10-30", 21.0)], (21.0, 21.0, 21.0, 21.0), "2026-10-30", None
    )
    no_passthrough = _get(client, "/api/companies/AAPL/multiples-history")
    assert no_passthrough == {
        "symbol": "AAPL",
        "pe": None,
        "peNote": "no FMP key",
        "peForward": forward,
    }
    empty = _get(client, "/api/companies/HGCO/multiples-history")["peForward"]
    nothing_logged = _series("pe_forward", [], (None,) * 4, None, None, symbol="HGCO")
    assert empty == nothing_logged


def test_a_fetch_that_cannot_be_read_with_none_stored_has_no_points(
    with_history: TestClient, fmp: FmpDouble, db_path: Path
) -> None:
    """FMP's error object in place of the quarters: the read answers the fetched closes with no
    points and the note; the quarters are stored with the error ``unusable payload: ...`` and
    never reused, so the next read asks them again, the closes reused."""
    fmp.bodies[QUARTERS] = UNREAD
    first = _get(with_history, "/api/companies/AAPL/multiples-history")
    second = _get(with_history, "/api/companies/AAPL/multiples-history")
    [(closes_id, error)] = _stored(db_path, "pe-closes")
    assert error is None
    quarters = [stored or "" for _, stored in _stored(db_path, "pe-quarters")]
    assert [stored.startswith("unusable payload") for stored in quarters] == [True, True]
    assert fmp.calls == {CLOSES: 1, QUARTERS: 2}
    unread = _series("pe", [], (None,) * 4, None, closes_id, UNREADABLE)
    for body in (first, second):
        assert (body["pe"], body["peNote"]) == (unread, None)


@pytest.mark.parametrize(("route", "endpoint"), [(QUARTERS, "pe-quarters"), (CLOSES, "pe-closes")])
def test_a_fetch_that_cannot_be_read_serves_the_stored_series(
    with_history: TestClient,
    fmp: FmpDouble,
    db_path: Path,
    policy: Policy,
    route: str,
    endpoint: str,
) -> None:
    """Answers stored a month ago, past the reuse window, and a fetch whose quarters or closes
    cannot be read: the read serves the series of the newest usable stored answers, the fetched
    closes among them where they read, the series the refs read, with ``peNote`` "the series could
    not be read"; the unread answer is stored unusable."""
    _store(db_path, MONTH_AGO)
    fmp.bodies[route] = UNREAD
    body = _get(with_history, "/api/companies/AAPL/multiples-history")
    closes_id = max(rid for rid, error in _stored(db_path, "pe-closes") if error is None)
    pe = _series("pe", TRAILING, TRAILING_STATS, "2016-10-29", closes_id)
    assert (body["pe"], body["peNote"]) == (pe, UNREADABLE)
    assert [error is None for _, error in _stored(db_path, endpoint)] == [True, False]
    with closing(connect(db_path)) as conn:
        found = Resolver(conn, "AAPL", policy).resolve("multiple:AAPL/pe/avg_10y")
    assert found is not None and found.value == pe["stats"]["avg10y"]["value"]


def test_a_fetch_that_cannot_be_had_serves_the_stored_series(
    with_history: TestClient, client: TestClient, fmp: FmpDouble, db_path: Path, policy: Policy
) -> None:
    """Answers stored a month ago, past the reuse window: with no pass-through at all, or when
    the call fails, the read serves their series, the series the refs read, with the reason in
    ``peNote``, the key scrubbed from it."""
    closes_id = _store(db_path, MONTH_AGO)
    pe = _series("pe", TRAILING, TRAILING_STATS, "2016-10-29", closes_id)
    no_passthrough = _get(client, "/api/companies/AAPL/multiples-history")
    assert (no_passthrough["pe"], no_passthrough["peNote"]) == (pe, "no FMP key")
    fmp.status, fmp.bodies[CLOSES] = 403, {"Error Message": f"apikey {FMP_KEY} is not valid"}
    response = with_history.get("/api/companies/AAPL/multiples-history")
    assert response.status_code == 200 and FMP_KEY not in response.text
    failed = response.json()
    assert failed["pe"] == pe and fmp.calls == {CLOSES: 1}
    assert failed["peNote"].startswith(f"GET {fmp_api.BASE_URL}/{CLOSES}?")
    assert "apikey=<key> -> 403" in failed["peNote"]
    with closing(connect(db_path)) as conn:
        found = Resolver(conn, "AAPL", policy).resolve("multiple:AAPL/pe/avg_10y")
    assert found is not None and found.value == pe["stats"]["avg10y"]["value"]


def test_a_failed_fetch_with_nothing_stored_leaves_the_series_null_without_the_key(
    with_history: TestClient, fmp: FmpDouble
) -> None:
    fmp.status, fmp.bodies[CLOSES] = 403, {"Error Message": f"apikey {FMP_KEY} is not valid"}
    response = with_history.get("/api/companies/AAPL/multiples-history")
    assert response.status_code == 200 and FMP_KEY not in response.text
    body = response.json()
    assert body["pe"] is None and body["peForward"]["points"] == []
    assert body["peNote"].startswith(f"GET {fmp_api.BASE_URL}/{CLOSES}?")


def test_an_old_gurufocus_series_is_not_served(client: TestClient, db_path: Path) -> None:
    """Review Focus 5: GuruFocus's ``pettm`` answer stored before, and no answer of the P/E
    history's: with no pass-through the trailing series is ``null``, the old series unread."""
    with closing(connect(db_path)) as conn:
        old = '[["2026-10-30", 24.0, 24.0, 24.0, 24.0]]'
        record_response(conn, "gf", "pettm", {"symbol": "AAPL"}, "AAPL", 200, old, None, NOW)
    body = _get(client, "/api/companies/AAPL/multiples-history")
    assert (body["pe"], body["peNote"]) == (None, "no FMP key")


def test_a_symbol_that_is_not_one_is_400(client: TestClient) -> None:
    response = client.get("/api/companies/A$B/multiples-history", headers=HEADER)
    assert response.status_code == 400 and response.json()["detail"].startswith("'A$B'")
