import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from fairband.policy import load_policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH, SETTINGS, default_of, settings_hash
from fairband.store.settings import (
    changes,
    effective_policy,
    overlay_changed_at,
    read_overlay,
    reset_settings,
    write_settings,
)

AT = datetime(2026, 11, 4, 9, 30, tzinfo=UTC)
LATER = AT + timedelta(hours=1)


def test_write_read_and_hash(conn: sqlite3.Connection) -> None:
    p = write_settings(conn, {"required_return": 0.1, "refresh.workers": 4}, "try 10%", AT)
    assert not conn.in_transaction
    assert read_overlay(conn) == {"required_return": 0.1, "refresh.workers": 4}
    assert p.required_return == 0.1 and p.refresh.workers == 4
    assert p.settings_hash == settings_hash({"required_return": 0.1})
    assert effective_policy(conn).settings_hash == p.settings_hash
    log = changes(conn)
    assert log[0].reason == "try 10%" and log[0].changed_at == AT
    assert log[0].changes == [
        {"name": "required_return", "old": None, "new": 0.1},
        {"name": "refresh.workers", "old": None, "new": 4},
    ]


def test_write_is_all_or_none(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="required_return, terminal_growth: g_T must be below r"):
        write_settings(conn, {"refresh.workers": 4, "terminal_growth": 0.5}, None, AT)
    assert not conn.in_transaction
    assert read_overlay(conn) == {} and changes(conn) == []


def test_reset_names_or_all(conn: sqlite3.Connection) -> None:
    write_settings(conn, {"required_return": 0.1, "fade_years": 3}, None, AT)
    reset_settings(conn, ["fade_years"], AT)
    assert read_overlay(conn) == {"required_return": 0.1}
    reset_settings(conn, None, AT)
    assert read_overlay(conn) == {}
    assert changes(conn)[0].changes == [{"name": "required_return", "old": 0.1, "new": None}]
    assert [len(c.changes) for c in changes(conn)] == [1, 1, 2]  # newest first
    assert effective_policy(conn).settings_hash == EMPTY_SETTINGS_HASH


def test_an_unknown_overlay_row_names_itself(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO settings VALUES ('gone_value', '1', ?)", (AT.isoformat(),))
    conn.commit()
    with pytest.raises(
        ValueError, match="settings: gone_value: not a setting; reset it on the Settings page"
    ):
        effective_policy(conn)
    reset_settings(conn, ["gone_value"], AT)
    assert effective_policy(conn).settings_hash == EMPTY_SETTINGS_HASH


def test_an_out_of_range_overlay_row_names_itself(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO settings VALUES ('required_return', '0.5', ?)", (AT.isoformat(),))
    conn.commit()
    with pytest.raises(
        ValueError,
        match="settings: required_return: must be from 4% to 20%; reset it on the Settings page",
    ):
        effective_policy(conn)


def test_values_are_stored_in_their_converted_form(conn: sqlite3.Connection) -> None:
    write_settings(
        conn,
        {
            "inflation_addition": 3e-2,  # the default is 2e-2
            "trim_multiple": 2,
            "universe.manual_exclusions": ["brk.b"],
        },
        None,
        AT,
    )
    overlay = read_overlay(conn)
    assert overlay == {
        "inflation_addition": 0.03,
        "trim_multiple": 2.0,
        "universe.manual_exclusions": ["BRK.B"],
    }
    assert isinstance(overlay["inflation_addition"], float)
    assert isinstance(overlay["trim_multiple"], float)  # 2 and 2.0 hash alike once stored
    assert effective_policy(conn).settings_hash == settings_hash(
        {"inflation_addition": 0.03, "trim_multiple": 2.0}
    )


def test_a_save_at_the_default_stores_nothing(conn: sqlite3.Connection) -> None:
    p = write_settings(conn, {"required_return": 0.09}, None, AT)
    assert read_overlay(conn) == {} and changes(conn) == []
    assert p.settings_hash == EMPTY_SETTINGS_HASH
    base = load_policy()
    every_default = {s.name: default_of(s.name, base) for s in SETTINGS}
    assert write_settings(conn, every_default, None, AT).settings_hash == EMPTY_SETTINGS_HASH
    assert read_overlay(conn) == {} and changes(conn) == []


def test_a_save_back_to_the_default_deletes_the_row(conn: sqlite3.Connection) -> None:
    write_settings(conn, {"required_return": 0.1}, None, AT)
    p = write_settings(conn, {"required_return": 0.09}, "back", LATER)
    assert read_overlay(conn) == {} and p.settings_hash == EMPTY_SETTINGS_HASH
    assert changes(conn)[0].changes == [{"name": "required_return", "old": 0.1, "new": None}]


def test_overlay_changed_at_moves_only_with_the_value(conn: sqlite3.Connection) -> None:
    write_settings(conn, {"required_return": 0.1, "universe.cap_floor_usd": 3e9}, None, AT)
    write_settings(conn, {"required_return": 0.11, "universe.cap_floor_usd": 3e9}, None, LATER)
    assert overlay_changed_at(conn) == {"required_return": LATER, "universe.cap_floor_usd": AT}
    assert changes(conn)[0].changes == [{"name": "required_return", "old": 0.1, "new": 0.11}]


def test_effective_policy_over_a_given_base(conn: sqlite3.Connection) -> None:
    base = load_policy()
    write_settings(conn, {"fade_years": 3}, None, AT, base)
    p = effective_policy(conn, base)
    assert (p.fade_years, p.version, p.hash) == (3, base.version, base.hash)
    assert p.settings_hash == settings_hash({"fade_years": 3})
