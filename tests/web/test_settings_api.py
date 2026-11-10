"""The settings, policy and deciles routes (spec 2026-11-04 7.4 and 8.7), on the database of
``conftest.py``: three snapshots valued under the packaged policy at its defaults, listed in the
universe of one finished full refresh started at ``STARTED``."""

import json
from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from support.engine_companies import universe_deciles
from support.web import HEADER, HOST, NOW, STARTED, _company, _settings

from fairband.engine import METHOD_VERSION
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH, SETTINGS, settings_hash
from fairband.store.companies import insert_companies
from fairband.store.db import connect, migrate
from fairband.store.refreshes import create_refresh, finish_refresh, save_deciles
from fairband.store.snapshots import insert_snapshot
from fairband.web.app import create_app

R_SOURCE = "design.md 6.2 (stocks method v1.7 section 3): required return r = 9%"
STALE = "settings: gone_value: not a setting; reset it on the Settings page"


def _setting(body: dict[str, Any], name: str) -> dict[str, Any]:
    found: dict[str, Any] = next(
        s for g in body["groups"] for s in g["settings"] if s["name"] == name
    )
    return found


def test_get_settings_shape(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    assert set(body) == {"groups", "current", "valuedUnder"}
    assert [g["name"] for g in body["groups"]] == [
        "valuation",
        "flags",
        "validity",
        "universe",
        "refresh",
    ]
    assert [s["name"] for g in body["groups"] for s in g["settings"]] == [s.name for s in SETTINGS]
    r = next(s for s in body["groups"][0]["settings"] if s["name"] == "required_return")
    assert r == {
        "name": "required_return",
        "label": "Hurdle rate r",
        "description": r["description"],
        "unit": "fraction",
        "default": 0.09,
        "value": 0.09,
        "range": "4% to 20%, above g_T",
        "effect": "revalue",
        "source": R_SOURCE,
        "changed": False,
        "changedAt": None,
    }
    assert r["description"].startswith("The yearly return you require")
    assert body["current"] == {
        "policyVersion": "fairband-policy-v11",
        "settingsHash": EMPTY_SETTINGS_HASH,
    }
    assert body["valuedUnder"] == {
        "policyVersion": "fairband-policy-v11",
        "settingsHash": EMPTY_SETTINGS_HASH,
        "fullRefreshAt": STARTED.isoformat(),
        "universeChanged": False,
    }


def test_the_table_settings_serve_their_json_form(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    runway = _setting(body, "runway_years")
    assert runway["default"] == runway["value"] == {"None": 5, "Narrow": 10, "Wide": 20}
    assert _setting(body, "fair_band")["value"] == [0.85, 1.15]
    assert _setting(body, "universe.cap_bands")["value"] == [
        [200e9, "Mega"],
        [10e9, "Large"],
        [2e9, "Mid"],
    ]
    workers = _setting(body, "refresh.workers")
    assert (workers["value"], workers["unit"], workers["effect"]) == (16, "count", "run")
    assert workers["source"].startswith("research.md D13")  # the refresh table's source line


def test_put_settings_all_or_none_and_the_notice(client: TestClient) -> None:
    r = client.put(
        "/api/settings",
        json={"changes": {"required_return": 0.1, "terminal_growth": 0.5}},
        headers=HEADER,
    )
    assert (
        r.status_code == 400
        and r.json()["detail"] == "required_return, terminal_growth: g_T must be below r"
    )
    assert client.get("/api/settings").json()["current"]["settingsHash"] == EMPTY_SETTINGS_HASH
    r = client.put(
        "/api/settings", json={"changes": {"required_return": 0.1}, "reason": "try"}, headers=HEADER
    )
    assert r.status_code == 200 and r.json()["current"]["settingsHash"] != EMPTY_SETTINGS_HASH
    assert r.json()["valuedUnder"]["settingsHash"] == EMPTY_SETTINGS_HASH  # the snapshots are older
    assert r.json() == client.get("/api/settings").json()  # the GET body
    assert r.json()["current"]["settingsHash"] == settings_hash({"required_return": 0.1})
    rr = _setting(r.json(), "required_return")
    assert (rr["value"], rr["default"], rr["changed"]) == (0.1, 0.09, True)
    assert rr["changedAt"] == NOW.isoformat()


def test_put_refuses_a_name_that_is_not_a_setting(client: TestClient) -> None:
    r = client.put("/api/settings", json={"changes": {"gone_value": 1}}, headers=HEADER)
    assert (r.status_code, r.json()) == (400, {"detail": "gone_value: not a setting"})
    r = client.put("/api/settings", json={"changes": {"fade_years": "five"}}, headers=HEADER)
    assert (r.status_code, r.json()) == (
        400,
        {"detail": "fade_years: 'five' is not a whole number"},
    )
    r = client.put("/api/settings", json={"reason": "none"}, headers=HEADER)
    assert (r.status_code, r.json()) == (400, {"detail": "changes: Field required"})


def test_reset(client: TestClient) -> None:
    changes = {"required_return": 0.1, "fade_years": 3, "refresh.workers": 4}
    assert client.put("/api/settings", json={"changes": changes}, headers=HEADER).status_code == 200
    r = client.post("/api/settings/reset", json={"names": ["fade_years"]}, headers=HEADER)
    assert r.status_code == 200 and r.json() == client.get("/api/settings").json()
    assert [_setting(r.json(), n)["changed"] for n in changes] == [True, False, True]
    assert _setting(r.json(), "fade_years")["value"] == 5
    r = client.post("/api/settings/reset", json={}, headers=HEADER)  # no names: every setting
    assert r.status_code == 200
    assert not any(s["changed"] for g in r.json()["groups"] for s in g["settings"])
    assert r.json()["current"]["settingsHash"] == EMPTY_SETTINGS_HASH
    client.put("/api/settings", json={"changes": {"fade_years": 3}}, headers=HEADER)
    r = client.post("/api/settings/reset", headers=HEADER)  # no body at all: every setting too
    assert r.status_code == 200 and not _setting(r.json(), "fade_years")["changed"]


def test_put_needs_the_request_header(client: TestClient) -> None:
    r = client.put("/api/settings", json={"changes": {"required_return": 0.1}})
    assert (r.status_code, r.json()) == (403, {"detail": "missing X-Fairband-Request header"})
    assert client.post("/api/settings/reset", json={}).status_code == 403
    assert client.get("/api/settings").json()["current"]["settingsHash"] == EMPTY_SETTINGS_HASH


def test_a_universe_setting_changed_after_the_full_refresh(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    r = client.put(
        "/api/settings", json={"changes": {"universe.cap_floor_usd": 3e9}}, headers=HEADER
    )
    body = r.json()
    assert body["valuedUnder"]["universeChanged"] is True  # changed at NOW, after STARTED
    assert body["current"]["settingsHash"] == EMPTY_SETTINGS_HASH  # the universe is not hashed
    # The floor carries the Mid band's floor: the value is the effective policy's, and only the
    # floor, which the user changed, reads changed.
    bands = _setting(body, "universe.cap_bands")
    assert bands["value"] == [[200e9, "Mega"], [10e9, "Large"], [3e9, "Mid"]]
    assert bands["default"] == [[200e9, "Mega"], [10e9, "Large"], [2e9, "Mid"]]
    assert bands["changed"] is False
    assert _setting(body, "universe.cap_floor_usd")["changed"] is True

    later = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
    with closing(connect(db_path)) as conn:
        refresh_id = create_refresh(
            conn, "full", None, policy.version, METHOD_VERSION, later, EMPTY_SETTINGS_HASH
        )
        finish_refresh(conn, refresh_id, "done", later)
    under = client.get("/api/settings").json()["valuedUnder"]
    assert (under["fullRefreshAt"], under["universeChanged"]) == (later.isoformat(), False)


def test_a_universe_setting_reset_after_the_full_refresh(
    client_with_clock: Callable[[datetime], TestClient], db_path: Path, policy: Policy
) -> None:
    """The universe was built under the floor the reset removes; a reset deletes the row, so the
    change log, not the overlay, tells; a save back to the default does the same."""
    t1 = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    floor = {"changes": {"universe.cap_floor_usd": 3e9}}
    assert client_with_clock(t1).put("/api/settings", json=floor, headers=HEADER).status_code == 200
    _full_refresh(db_path, policy, t1 + timedelta(hours=1))
    client = client_with_clock(t1 + timedelta(hours=2))
    assert client.get("/api/settings").json()["valuedUnder"]["universeChanged"] is False
    r = client.post(
        "/api/settings/reset", json={"names": ["universe.cap_floor_usd"]}, headers=HEADER
    )
    assert r.json()["valuedUnder"]["universeChanged"] is True
    assert not _setting(r.json(), "universe.cap_floor_usd")["changed"]  # no row left

    client.put("/api/settings", json=floor, headers=HEADER)
    _full_refresh(db_path, policy, t1 + timedelta(hours=3))
    client = client_with_clock(t1 + timedelta(hours=4))
    back = {"changes": {"universe.cap_floor_usd": 2e9}}  # the default: the row goes
    r = client.put("/api/settings", json=back, headers=HEADER)
    assert r.json()["valuedUnder"]["universeChanged"] is True
    other = client.put("/api/settings", json={"changes": {"fade_years": 3}}, headers=HEADER)
    assert other.json()["valuedUnder"]["universeChanged"] is True  # still, until a full refresh


def test_valued_under_counts_the_screens_snapshots_only(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """A full refresh under a higher floor admits AAPL alone; AAL and HGCO keep their snapshots
    under the old hash, two to one. A revalue under r = 10% values AAPL, the screen's one row,
    and the notice clears: the companies the universe dropped do not vote."""
    r = client.put("/api/settings", json={"changes": {"required_return": 0.1}}, headers=HEADER)
    current = r.json()["current"]["settingsHash"]
    later = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
    with closing(connect(db_path)) as conn:
        full = _full_refresh(db_path, policy, later)
        insert_companies(
            conn, [_company("AAPL", full, "Mature Growth Co", Decimal(150_000_000_000))]
        )
        revalue = create_refresh(
            conn, "revalue", None, policy.version, METHOD_VERSION, later, current
        )
        insert_snapshot(conn, replace(results["AAPL"], settings_hash=current), revalue)
        finish_refresh(conn, revalue, "done", later)
    assert [row["ticker"] for row in client.get("/api/screen").json()["rows"]] == ["AAPL"]
    under = client.get("/api/settings").json()["valuedUnder"]
    assert (under["policyVersion"], under["settingsHash"]) == (policy.version, current)


def _full_refresh(db_path: Path, policy: Policy, at: datetime) -> int:
    """A full refresh started and finished ``at``; its id."""
    with closing(connect(db_path)) as conn:
        refresh_id = create_refresh(
            conn, "full", None, policy.version, METHOD_VERSION, at, EMPTY_SETTINGS_HASH
        )
        finish_refresh(conn, refresh_id, "done", at)
    return refresh_id


def test_valued_under_before_any_snapshot_or_full_refresh(tmp_path: Path, policy: Policy) -> None:
    """Nothing valued yet: no versions to cite; and with no full refresh, any universe setting
    changed is a change the universe has not seen."""
    path = tmp_path / "empty.db"
    with closing(connect(path)) as conn:
        migrate(conn)
    app = create_app(_settings(tmp_path, path), policy, lambda: connect(path), clock=lambda: NOW)
    with TestClient(app, base_url=HOST) as c:
        assert c.get("/api/settings").json()["valuedUnder"] == {
            "policyVersion": None,
            "settingsHash": None,
            "fullRefreshAt": None,
            "universeChanged": False,
        }
        changes = {"universe.manual_exclusions": ["xyz"]}
        r = c.put("/api/settings", json={"changes": changes}, headers=HEADER)
        assert _setting(r.json(), "universe.manual_exclusions")["value"] == ["XYZ"]
        assert r.json()["valuedUnder"]["universeChanged"] is True


def test_a_stored_row_the_policy_refuses_is_a_409_until_reset(
    client: TestClient, db_path: Path
) -> None:
    client.put("/api/settings", json={"changes": {"fade_years": 3}}, headers=HEADER)
    with closing(connect(db_path)) as conn, conn:
        conn.execute("INSERT INTO settings VALUES ('gone_value', '1', ?)", (NOW.isoformat(),))
    for path in ("/api/settings", "/api/policy", "/api/screen", "/api/groups?by=phase"):
        r = client.get(path)
        assert (r.status_code, r.json()) == (409, {"detail": STALE}), path
    assert client.get("/api/companies/AAPL").status_code == 409
    r = client.post("/api/settings/reset", json={"names": ["gone_value"]}, headers=HEADER)
    assert r.status_code == 200
    assert _setting(r.json(), "fade_years")["changed"] is True  # the other row is kept
    assert client.get("/api/screen").status_code == 200


def test_policy_route_has_the_cited_values_and_no_table(client: TestClient) -> None:
    body = client.get("/api/policy").json()
    assert (body["version"], body["settingsHash"], body["changed"]) == (
        "fairband-policy-v11",
        EMPTY_SETTINGS_HASH,
        0,
    )
    assert body["values"]["required_return"] == {
        "value": 0.09,
        "unit": "fraction",
        "source": R_SOURCE,
        "setting": True,
        "changed": False,
    }
    edges = body["values"]["designation_edges"]
    assert edges["value"] == [0.65, 0.85, 1.15, 1.5] and edges["setting"] is False
    assert body["values"]["wide_terminal_roic_cap"]["value"] == 0.13
    read_only = {
        "moat_wide_min": 8,
        "moat_narrow_min": 4,
        "peer_margin_min_years": 5,
        "z_distress": 1.1,
        "z_safe": 2.6,
        "f_score_low": 1,
        "implied_margin_bounds": [-0.5, 1.0],
    }
    for name, value in read_only.items():
        entry = body["values"][name]
        assert (entry["value"], entry["setting"], entry["changed"]) == (value, False, False), name
        assert entry["source"], name
    assert set(body["values"]) == {s.name for s in SETTINGS} | set(read_only) | {
        "designation_edges",
        "wide_terminal_roic_cap",
    }
    assert "base_rates" not in body["values"] and "synthetic_rating" not in body["values"]
    assert "key" not in json.dumps(body).lower()
    for table in ("excluded_industries", "symbol_exclude_patterns", "default_probability"):
        assert table not in json.dumps(body), table


def test_policy_route_follows_the_settings(client: TestClient) -> None:
    client.put("/api/settings", json={"changes": {"required_return": 0.1}}, headers=HEADER)
    body = client.get("/api/policy").json()
    assert body["changed"] == 1 and body["settingsHash"] == settings_hash({"required_return": 0.1})
    assert body["values"]["required_return"]["value"] == 0.1
    assert body["values"]["required_return"]["changed"] is True
    cap = body["values"]["wide_terminal_roic_cap"]  # r + the spread
    assert cap["value"] == 0.1 + 0.04 and cap["changed"] is True
    assert body["values"]["designation_edges"]["changed"] is False


def test_deciles_route(client: TestClient, db_path: Path) -> None:
    r = client.get("/api/deciles")
    assert (r.status_code, r.json()) == (404, {"detail": "no deciles yet"})
    deciles = universe_deciles()
    with closing(connect(db_path)) as conn:
        save_deciles(conn, 1, deciles, NOW)
    r = client.get("/api/deciles")
    assert r.status_code == 200
    assert r.json() == {
        "edges": list(deciles.growth_edges),
        "words": {
            "Very High": [9, 10],
            "High": [7, 8],
            "Moderate": [5, 6],
            "Low": [3, 4],
            "Close to zero or negative": [1, 2],
        },
        "n": deciles.n_growth,
    }
    assert len(r.json()["edges"]) == 9
