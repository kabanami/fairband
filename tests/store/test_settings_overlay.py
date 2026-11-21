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


def test_a_stored_row_of_a_removed_setting_is_skipped_then_deleted(
    conn: sqlite3.Connection,
) -> None:
    """Spec 2026-11-19 5 point 4 and 7.4: skipped at every read, deleted at the next save."""
    conn.execute("INSERT INTO settings VALUES ('gone_value', '1', ?)", (AT.isoformat(),))
    conn.commit()
    assert effective_policy(conn).settings_hash == EMPTY_SETTINGS_HASH
    write_settings(conn, {"fade_years": 3}, None, AT)
    assert read_overlay(conn) == {"fade_years": 3}
    assert changes(conn)[0].changes == [
        {"name": "fade_years", "old": None, "new": 3},
        {"name": "gone_value", "old": 1, "new": None},
    ]


def test_a_stored_gf_reuse_days_is_ignored_and_deleted(conn: sqlite3.Connection) -> None:
    """Spec 2026-11-19 8.9 by 7.4's path: policy v18 drops the setting ``refresh.gf_reuse_days``,
    so a value a user saved under v17 is skipped at every read, the effective policy the file's,
    and deleted at the next save, logged after the save's own change."""
    conn.execute("INSERT INTO settings VALUES ('refresh.gf_reuse_days', '3', ?)", (AT.isoformat(),))
    conn.commit()
    policy = effective_policy(conn)
    assert policy == load_policy() and policy.settings_hash == EMPTY_SETTINGS_HASH
    assert not hasattr(policy.refresh, "gf_reuse_days")
    write_settings(conn, {"refresh.workers": 4}, None, LATER)
    assert read_overlay(conn) == {"refresh.workers": 4}
    assert changes(conn)[0].changes == [
        {"name": "refresh.workers", "old": None, "new": 4},
        {"name": "refresh.gf_reuse_days", "old": 3, "new": None},
    ]


def test_a_save_that_names_no_setting_writes_nothing(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="gone_value: not a setting"):
        write_settings(conn, {"gone_value": 1, "fade_years": 3}, None, AT)
    assert read_overlay(conn) == {}
    # nor does it delete a stored row of a removed setting: the refusal comes before the sweep
    conn.execute("INSERT INTO settings VALUES ('gone_value', '1', ?)", (AT.isoformat(),))
    conn.commit()
    with pytest.raises(ValueError, match="gone_value: not a setting"):
        write_settings(conn, {"fade_years": 3, "gone_value": 1}, None, AT)
    assert not conn.in_transaction
    assert read_overlay(conn) == {"gone_value": 1} and changes(conn) == []


def test_a_reset_deletes_a_stored_row_of_a_removed_setting(conn: sqlite3.Connection) -> None:
    write_settings(conn, {"required_return": 0.1, "fade_years": 3}, None, AT)
    conn.execute("INSERT INTO settings VALUES ('gone_value', '1', ?)", (AT.isoformat(),))
    conn.commit()
    reset_settings(conn, ["fade_years"], LATER)
    assert read_overlay(conn) == {"required_return": 0.1}
    assert changes(conn)[0].changes == [
        {"name": "fade_years", "old": 3, "new": None},
        {"name": "gone_value", "old": 1, "new": None},
    ]
    conn.execute("INSERT INTO settings VALUES ('gone_value', '1', ?)", (AT.isoformat(),))
    conn.commit()
    reset_settings(conn, [], LATER)  # no setting named: the removed one goes all the same
    assert read_overlay(conn) == {"required_return": 0.1}
    assert changes(conn)[0].changes == [{"name": "gone_value", "old": 1, "new": None}]
    conn.execute("INSERT INTO settings VALUES ('gone_value', '1', ?)", (AT.isoformat(),))
    conn.commit()
    reset_settings(conn, None, LATER)  # every row: the removed one is logged once
    assert read_overlay(conn) == {}
    assert changes(conn)[0].changes == [
        {"name": "gone_value", "old": 1, "new": None},
        {"name": "required_return", "old": 0.1, "new": None},
    ]


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
