"""The multiples history read (spec 2026-11-06 Tier 2, 13.7) on the database of ``conftest.py``,
with a pass-through whose GuruFocus client answers a synthetic P/E series from a mock transport,
and AAPL's multiples log rows written by each test: the two series, their statistics and refs,
the loss rows, the payload that cannot be read, and the stored series served when the fetch
cannot be had."""

import json
from collections.abc import Callable, Iterator
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from support.web import CREATED, HOST, NOW, _settings

from fairband.policy import Policy
from fairband.refresh.passthrough import Passthrough
from fairband.reports.refs import Resolver
from fairband.store.db import connect
from fairband.store.multiples import log_multiples
from fairband.store.vendor import record_response
from fairband.vendors import fmp as fmp_api
from fairband.vendors import gurufocus as gurufocus_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.gurufocus import GuruFocus
from fairband.vendors.http import VendorHttp
from fairband.web.app import create_app

# Fourteen years of GuruFocus's pettm series, a row on 30 October each year, three of them loss
# rows. The ten years to the newest day run from 30 October 2016, so 2013 and 2015 fall outside.
PETTM_YEARS: dict[int, float | None] = {
    2013: 30.0,
    2014: None,
    2015: 25.0,
    2016: 20.0,
    2017: 22.0,
    2018: None,
    2019: 18.0,
    2020: 24.0,
    2021: None,
    2022: 16.0,
    2023: 35.0,
    2024: 21.0,
    2025: 19.0,
    2026: 23.0,
}
FMP_KEY = "fake-fmp-key-0005"  # not a real key
GF_TOKEN = "fakegfhalf5:fakegfhalf6"  # not a real token
NO_GF_KEY = "no GuruFocus key: the pe-history pass-through is off"
STATS = ("avg_10y", "median_10y", "high_10y", "low_10y")
UNREAD = {"error": "Stock not found"}  # GuruFocus answers some failures with HTTP 200


def _pettm(years: dict[int, float | None]) -> list[list[Any]]:
    """A row a year, ``[date, open, high, low, close]``; a loss row as GuruFocus writes one."""
    return [
        [f"{year}-10-30", "At Loss", 0, 0, 0]
        if close is None
        else [f"{year}-10-30", close - 0.5, close + 0.5, close - 1.0, close]
        for year, close in years.items()
    ]


class GuruFocusDouble:
    """GuruFocus on a mock transport: every request answers ``body`` with ``status``; ``calls``
    counts them."""

    def __init__(self) -> None:
        self.body: Any = _pettm(PETTM_YEARS)
        self.status = 200
        self.calls = 0
        self.transport = httpx.MockTransport(self._answer)

    def _answer(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        assert request.url.path == f"/public/user/{GF_TOKEN}/stock/AAPL/pettm"
        return httpx.Response(self.status, json=self.body)


@pytest.fixture
def gf() -> GuruFocusDouble:
    return GuruFocusDouble()


@pytest.fixture
def with_history(
    tmp_path: Path, db_path: Path, policy: Policy, gf: GuruFocusDouble
) -> Iterator[Callable[[bool], TestClient]]:
    """Makes a client of an app whose pass-through has a GuruFocus client over ``gf``, or none."""
    opened: list[Any] = []

    def make(with_gurufocus: bool) -> TestClient:
        def http(base_url: str, secret: str, transport: httpx.BaseTransport) -> VendorHttp:
            made = VendorHttp(
                base_url, [secret], policy.refresh, transport=transport, sleep=lambda _: None
            )
            opened.append(made)
            return made

        nowhere = httpx.MockTransport(lambda request: httpx.Response(404))
        fmp = Fmp(http(fmp_api.BASE_URL, FMP_KEY, nowhere), FMP_KEY)
        gurufocus = GuruFocus(http(gurufocus_api.BASE_URL, GF_TOKEN, gf.transport), GF_TOKEN)
        passthrough = Passthrough(
            fmp,
            lambda: connect(db_path),
            policy,
            lambda: NOW,
            (FMP_KEY, GF_TOKEN),
            gurufocus if with_gurufocus else None,
        )
        app = create_app(
            _settings(tmp_path, db_path),
            policy,
            lambda: connect(db_path),
            clock=lambda: NOW,
            passthrough=passthrough,
        )
        opened.append(TestClient(app, base_url=HOST))
        client: TestClient = opened[-1]
        return client

    yield make
    for made in opened:
        made.close()


def _get(client: TestClient, url: str) -> Any:
    r = client.get(url)
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


def _pettm_rows(db_path: Path) -> list[tuple[int, str, str | None]]:
    """AAPL's stored ``pettm`` responses by id: the id, the provider and the error."""
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT id, provider, error FROM vendor_responses"
            " WHERE endpoint = 'pettm' AND symbol = 'AAPL' ORDER BY id"
        ).fetchall()
    return [tuple(row) for row in rows]


TRAILING = [  # PETTM_YEARS' points of the ten years: 20, 22, 18, 24, 16, 35, 21, 19 and 23
    (f"{year}-10-30", close)
    for year, close in PETTM_YEARS.items()
    if year >= 2016 and close is not None
]
TRAILING_STATS = (22.0, 21.0, 35.0, 16.0)  # the average, the median, the high and the low


def test_the_multiples_history_read(
    with_history: Callable[[bool], TestClient], gf: GuruFocusDouble, db_path: Path, policy: Policy
) -> None:
    """The trailing series over the ten years to its newest day, the loss rows dropped and the
    statistics over the points left; the forward series from the log, ``since`` its first day.
    Every ref resolves to its figure, and a second read reuses the stored series."""
    _log(db_path, [("2026-10-28", 20.0), ("2026-10-29", 25.0), ("2026-10-30", 21.0)])
    client = with_history(True)
    body = _get(client, "/api/companies/aapl/multiples-history")
    [(response_id, provider, error)] = _pettm_rows(db_path)
    assert (provider, error) == ("gf", None)
    assert body == {
        "symbol": "AAPL",
        "pe": _series("pe", TRAILING, TRAILING_STATS, "2013-10-30", response_id),
        "peNote": None,
        "peForward": _series(
            "pe_forward",
            [("2026-10-28", 20.0), ("2026-10-29", 25.0), ("2026-10-30", 21.0)],
            (22.0, 21.0, 25.0, 20.0),
            "2026-10-28",
            None,
        ),
    }
    assert _get(client, "/api/companies/AAPL/multiples-history") == body
    assert gf.calls == 1  # stored inside its seven days: no second call
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


def test_loss_rows_are_dropped_from_the_series(
    with_history: Callable[[bool], TestClient], gf: GuruFocusDouble, db_path: Path
) -> None:
    """A loss leaves a gap: an "At Loss" row, a negative or a zero multiple has no point and
    nothing fills its days; a log row with no forward P/E has none either, yet the log began on
    its day."""
    gf.body = [
        ["2026-10-26", 18.0, 18.0, 18.0, 18.0],
        ["2026-10-27", "At Loss", 0, 0, 0],
        ["2026-10-28", -3.0],
        ["2026-10-29", 0],
        ["2026-10-30", 20.0, 20.0, 20.0, 20.0],
    ]
    _log(db_path, [("2026-10-29", None), ("2026-10-30", 21.0)])
    body = _get(with_history(True), "/api/companies/AAPL/multiples-history")
    [(response_id, _, _)] = _pettm_rows(db_path)
    assert body["pe"] == _series(
        "pe",
        [("2026-10-26", 18.0), ("2026-10-30", 20.0)],
        (19.0, 19.0, 20.0, 18.0),
        "2026-10-26",
        response_id,
    )
    assert body["peForward"] == _series(
        "pe_forward", [("2026-10-30", 21.0)], (21.0, 21.0, 21.0, 21.0), "2026-10-29", None
    )


def test_without_a_gurufocus_client_the_trailing_series_is_null(
    with_history: Callable[[bool], TestClient],
    client: TestClient,
    gf: GuruFocusDouble,
    db_path: Path,
) -> None:
    """With no series stored, the trailing series is ``null`` with the reason in ``peNote``: no
    GuruFocus key, or, on a server with no pass-through at all, no FMP key. The forward series
    still answers."""
    _log(db_path, [("2026-10-30", 21.0)])
    forward = _series(
        "pe_forward", [("2026-10-30", 21.0)], (21.0, 21.0, 21.0, 21.0), "2026-10-30", None
    )
    without = _get(with_history(False), "/api/companies/AAPL/multiples-history")
    assert without == {"symbol": "AAPL", "pe": None, "peNote": NO_GF_KEY, "peForward": forward}
    no_passthrough = _get(client, "/api/companies/AAPL/multiples-history")
    assert no_passthrough == {**without, "peNote": "no FMP key"}
    assert gf.calls == 0
    empty = _get(client, "/api/companies/HGCO/multiples-history")["peForward"]
    nothing_logged = _series("pe_forward", [], (None,) * 4, None, None, symbol="HGCO")
    assert empty == nothing_logged


def test_a_series_that_cannot_be_read_has_no_points(
    with_history: Callable[[bool], TestClient], gf: GuruFocusDouble, db_path: Path
) -> None:
    """A payload with no dated row answers no points and the note; it is stored with the error
    ``unusable payload: ...`` and never reused, so the next read fetches again."""
    gf.body = UNREAD
    client = with_history(True)
    first = _get(client, "/api/companies/AAPL/multiples-history")
    second = _get(client, "/api/companies/AAPL/multiples-history")
    error = 'unusable payload: {"error":"Stock not found"}'  # the body as the double sent it
    rows = _pettm_rows(db_path)
    assert [(provider, stored) for _, provider, stored in rows] == [("gf", error)] * 2
    assert gf.calls == 2
    for body, (response_id, _, _) in zip((first, second), rows, strict=True):
        unread = _series("pe", [], (None,) * 4, None, response_id, "the series could not be read")
        assert (body["pe"], body["peNote"]) == (unread, None)


def test_a_fetch_that_cannot_be_had_serves_the_stored_series(
    with_history: Callable[[bool], TestClient],
    client: TestClient,
    gf: GuruFocusDouble,
    db_path: Path,
    policy: Policy,
) -> None:
    """A series stored a month ago, past its seven days: with no GuruFocus key, with no
    pass-through at all, or when the call fails, the read serves it, the series the refs read,
    with the reason in ``peNote``."""
    stored = _pettm(PETTM_YEARS)
    observed = datetime(2026, 10, 2, 9, 30, tzinfo=UTC)
    with closing(connect(db_path)) as conn:
        response_id = record_response(
            conn, "gf", "pettm", {"symbol": "AAPL"}, "AAPL", 200, json.dumps(stored), None, observed
        )
    pe = _series("pe", TRAILING, TRAILING_STATS, "2013-10-30", response_id)
    no_key = _get(with_history(False), "/api/companies/AAPL/multiples-history")
    assert (no_key["pe"], no_key["peNote"]) == (pe, NO_GF_KEY)
    no_passthrough = _get(client, "/api/companies/AAPL/multiples-history")
    assert (no_passthrough["pe"], no_passthrough["peNote"]) == (pe, "no FMP key")
    gf.status, gf.body = 403, {"error": f"token {GF_TOKEN} is not valid"}
    response = with_history(True).get("/api/companies/AAPL/multiples-history")
    assert response.status_code == 200 and GF_TOKEN not in response.text
    failed = response.json()
    assert failed["pe"] == pe and gf.calls == 1
    assert failed["peNote"].startswith(
        "GET https://api.gurufocus.com/public/user/<key>/stock/AAPL/pettm -> 403"
    )
    with closing(connect(db_path)) as conn:
        found = Resolver(conn, "AAPL", policy).resolve("multiple:AAPL/pe/avg_10y")
    assert found is not None and found.value == pe["stats"]["avg10y"]["value"]


def test_a_failed_fetch_with_nothing_stored_leaves_the_series_null_without_the_token(
    with_history: Callable[[bool], TestClient], gf: GuruFocusDouble
) -> None:
    gf.status, gf.body = 403, {"error": f"token {GF_TOKEN} is not valid"}
    response = with_history(True).get("/api/companies/AAPL/multiples-history")
    assert response.status_code == 200 and GF_TOKEN not in response.text
    body = response.json()
    assert body["pe"] is None and body["peForward"]["points"] == []
    assert body["peNote"].startswith(
        "GET https://api.gurufocus.com/public/user/<key>/stock/AAPL/pettm -> 403"
    )


def test_a_symbol_that_is_not_one_is_400(client: TestClient) -> None:
    response = client.get("/api/companies/A$B/multiples-history")
    assert response.status_code == 400 and response.json()["detail"].startswith("'A$B'")
