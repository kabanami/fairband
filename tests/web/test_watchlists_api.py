"""The watchlist routes (spec 2026-11-04 9.3) and the two keys every screen row carries for them
and for the flag count (9.5), on the database of ``conftest.py``: AAPL, AAL and HGCO."""

from typing import Any

from fastapi.testclient import TestClient
from support.web import HEADER, NOW

from fairband.engine.flags import flag_count
from fairband.engine.types import ValuationResult

AT = NOW.isoformat()


def _create(client: TestClient, name: str) -> dict[str, Any]:
    r = client.post("/api/watchlists", json={"name": name}, headers=HEADER)
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


def _rows(client: TestClient) -> dict[str, dict[str, Any]]:
    return {row["ticker"]: row for row in client.get("/api/screen").json()["rows"]}


def test_create_and_list(client: TestClient) -> None:
    assert client.get("/api/watchlists").json() == []
    core = _create(client, " Core ")
    assert core == {"id": core["id"], "name": "Core", "createdAt": AT, "count": 0, "symbols": []}
    banks = _create(client, "banks")
    assert [w["name"] for w in client.get("/api/watchlists").json()] == ["banks", "Core"]
    assert client.get("/api/watchlists").json()[0] == banks


def test_create_refuses_a_name_in_use_or_out_of_bounds(client: TestClient) -> None:
    _create(client, "Core")
    r = client.post("/api/watchlists", json={"name": "CORE"}, headers=HEADER)
    assert (r.status_code, r.json()) == (409, {"detail": "a watchlist named 'Core' exists"})
    r = client.post("/api/watchlists", json={"name": "  "}, headers=HEADER)
    assert (r.status_code, r.json()) == (400, {"detail": "a name is 1 to 60 characters"})
    assert client.post("/api/watchlists", json={"name": "New"}).status_code == 403  # no header


def test_rename_and_delete(client: TestClient) -> None:
    core = _create(client, "Core")
    other = _create(client, "Other")
    r = client.patch(f"/api/watchlists/{core['id']}", json={"name": "Income"}, headers=HEADER)
    assert r.status_code == 200 and r.json()["name"] == "Income"
    r = client.patch(f"/api/watchlists/{other['id']}", json={"name": "income"}, headers=HEADER)
    assert (r.status_code, r.json()) == (409, {"detail": "a watchlist named 'Income' exists"})
    client.put(f"/api/watchlists/{core['id']}/symbols/AAPL", headers=HEADER)
    r = client.delete(f"/api/watchlists/{core['id']}", headers=HEADER)
    assert (r.status_code, r.json()) == (200, {"deleted": core["id"]})
    assert [w["id"] for w in client.get("/api/watchlists").json()] == [other["id"]]
    assert _rows(client)["AAPL"]["watchlists"] == []


def test_a_missing_list_is_a_404(client: TestClient) -> None:
    missing = {"detail": "no watchlist 99"}
    for r in (
        client.patch("/api/watchlists/99", json={"name": "Core"}, headers=HEADER),
        client.delete("/api/watchlists/99", headers=HEADER),
        client.put("/api/watchlists/99/symbols/AAPL", headers=HEADER),
        client.delete("/api/watchlists/99/symbols/AAPL", headers=HEADER),
        client.put("/api/watchlists/memberships/AAPL", json={"ids": [99]}, headers=HEADER),
    ):
        assert (r.status_code, r.json()) == (404, missing), r.request.url


def test_add_and_remove_a_symbol(client: TestClient) -> None:
    core = _create(client, "Core")
    url = f"/api/watchlists/{core['id']}/symbols"
    r = client.put(f"{url}/aapl", headers=HEADER)
    assert r.status_code == 200
    assert r.json()["symbols"] == [{"symbol": "AAPL", "addedAt": AT}] and r.json()["count"] == 1
    assert client.put(f"{url}/AAPL", headers=HEADER).json() == r.json()  # idempotent
    r = client.put(f"{url}/bad symbol", headers=HEADER)
    assert (r.status_code, r.json()) == (400, {"detail": "'bad symbol' is not a symbol"})
    r = client.delete(f"{url}/AAPL", headers=HEADER)
    assert r.status_code == 200 and r.json()["symbols"] == []


def test_a_symbol_not_in_the_universe_stays_on_the_list(client: TestClient) -> None:
    core = _create(client, "Core")
    client.put(f"/api/watchlists/{core['id']}/symbols/BRK.B", headers=HEADER)
    client.put(f"/api/watchlists/{core['id']}/symbols/AAPL", headers=HEADER)
    [listed] = client.get("/api/watchlists").json()
    assert [s["symbol"] for s in listed["symbols"]] == ["AAPL", "BRK.B"]
    assert listed["count"] == 2
    assert "BRK.B" not in _rows(client)  # no row on the screen, still on the list


def test_memberships_set_a_companys_lists_in_one_write(client: TestClient) -> None:
    core, income, watch = (_create(client, n)["id"] for n in ("Core", "Income", "Watch"))
    client.put(f"/api/watchlists/{income}/symbols/AAPL", headers=HEADER)
    r = client.put("/api/watchlists/memberships/aapl", json={"ids": [watch, core]}, headers=HEADER)
    assert (r.status_code, r.json()) == (200, {"symbol": "AAPL", "watchlists": [core, watch]})
    assert _rows(client)["AAPL"]["watchlists"] == [core, watch]
    r = client.put("/api/watchlists/memberships/AAPL", json={"ids": "all"}, headers=HEADER)
    assert r.status_code == 400
    r = client.put("/api/watchlists/memberships/AAPL", json={"ids": []}, headers=HEADER)
    assert r.json() == {"symbol": "AAPL", "watchlists": []}


def test_screen_rows_carry_the_watchlists_and_the_flag_count(
    client: TestClient, results: dict[str, ValuationResult]
) -> None:
    core = _create(client, "Core")["id"]
    client.put(f"/api/watchlists/{core}/symbols/HGCO", headers=HEADER)
    rows = _rows(client)
    assert {t: r["watchlists"] for t, r in rows.items()} == {"AAL": [], "AAPL": [], "HGCO": [core]}
    counts = {t: r["flagCount"] for t, r in rows.items()}
    assert counts == {t: flag_count(results[t].flags) for t in rows}
    assert counts == {"AAL": 0, "AAPL": 1, "HGCO": 3}  # notes do not count
