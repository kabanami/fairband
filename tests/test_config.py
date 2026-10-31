from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import pytest

from fairband.config import Keys, MissingKey, load_keys, load_settings, require, utcnow


def _write_keys(home: Path, text: str) -> None:
    (home / ".config/fairband").mkdir(parents=True)
    (home / ".config/fairband/keys.toml").write_text(text)


def test_xdg_defaults(tmp_path: Path) -> None:
    s = load_settings(env={}, home=tmp_path)
    assert s.data_dir == tmp_path / ".local/share/fairband"
    assert s.config_dir == tmp_path / ".config/fairband"
    assert s.db_path == s.data_dir / "fairband.db" and s.port == 8470


def test_env_overrides(tmp_path: Path) -> None:
    s = load_settings(
        env={"XDG_DATA_HOME": str(tmp_path / "d"), "FAIRBAND_DATA_DIR": str(tmp_path / "x")},
        home=tmp_path,
    )
    assert s.data_dir == tmp_path / "x"


def test_xdg_homes_used_when_set(tmp_path: Path) -> None:
    s = load_settings(
        env={"XDG_DATA_HOME": str(tmp_path / "d"), "XDG_CONFIG_HOME": str(tmp_path / "c")},
        home=tmp_path,
    )
    assert s.data_dir == tmp_path / "d/fairband"
    assert s.config_dir == tmp_path / "c/fairband"
    assert s.db_path == tmp_path / "d/fairband/fairband.db"


@pytest.mark.parametrize(
    "env",
    [
        {"FAIRBAND_DATA_DIR": "", "XDG_DATA_HOME": "", "XDG_CONFIG_HOME": ""},
        {"XDG_DATA_HOME": "relative/data", "XDG_CONFIG_HOME": "relative/config"},
    ],
    ids=["empty", "relative"],
)
def test_empty_or_relative_values_fall_back_to_home(tmp_path: Path, env: dict[str, str]) -> None:
    s = load_settings(env=env, home=tmp_path)
    assert s.data_dir == tmp_path / ".local/share/fairband"
    assert s.config_dir == tmp_path / ".config/fairband"


def test_defaults_read_process_environment_and_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("FAIRBAND_FMP_KEY", raising=False)
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "x"))
    monkeypatch.setenv("FAIRBAND_GURUFOCUS_KEY", "env-gf")
    s = load_settings()
    assert s.data_dir == tmp_path / "x"
    assert s.config_dir == tmp_path / ".config/fairband"
    assert load_keys(s) == Keys(fmp=None, gurufocus="env-gf")


def test_keys_file_then_env(tmp_path: Path) -> None:
    (tmp_path / ".config/fairband").mkdir(parents=True)
    (tmp_path / ".config/fairband/keys.toml").write_text('[keys]\nfmp = "file-fmp"\n')
    s = load_settings(env={}, home=tmp_path)
    assert load_keys(s, env={}) == Keys(fmp="file-fmp", gurufocus=None)
    assert load_keys(s, env={"FAIRBAND_FMP_KEY": "env-fmp"}).fmp == "env-fmp"


def test_env_key_without_keys_file(tmp_path: Path) -> None:
    s = load_settings(env={}, home=tmp_path)
    keys = load_keys(s, env={"FAIRBAND_GURUFOCUS_KEY": "env-gf"})
    assert keys == Keys(fmp=None, gurufocus="env-gf")


def test_empty_key_is_none_and_empty_env_does_not_override(tmp_path: Path) -> None:
    _write_keys(tmp_path, '[keys]\nfmp = " "\ngurufocus = "file-gf"\n')
    s = load_settings(env={}, home=tmp_path)
    keys = load_keys(s, env={"FAIRBAND_FMP_KEY": "", "FAIRBAND_GURUFOCUS_KEY": ""})
    assert keys == Keys(fmp=None, gurufocus="file-gf")
    assert load_keys(s, env={"FAIRBAND_FMP_KEY": " env-fmp\n"}).fmp == "env-fmp"


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ('[keys]\nfmp = "file-fmp\n', ValueError),
        ("[keys]\nfmp = 4242\n", TypeError),
        ('keys = "file-fmp"\n', TypeError),
    ],
    ids=["invalid-toml", "not-a-string", "not-a-table"],
)
def test_bad_keys_file_error_names_path_never_value(
    tmp_path: Path, text: str, error: type[Exception]
) -> None:
    _write_keys(tmp_path, text)
    s = load_settings(env={}, home=tmp_path)
    with pytest.raises(error) as e:
        load_keys(s, env={})
    assert str(s.config_dir / "keys.toml") in str(e.value)
    assert "file-fmp" not in str(e.value) and "4242" not in str(e.value)


def test_keys_repr_hides_values() -> None:
    keys = Keys(fmp="k-fmp", gurufocus="k-gf")
    assert "k-fmp" not in repr(keys) and "k-gf" not in repr(keys)
    assert repr(keys) != repr(Keys(fmp=None, gurufocus=None))


def test_require_returns_the_key() -> None:
    keys = Keys(fmp="k-fmp", gurufocus="k-gf")
    assert require(keys, "fmp") == "k-fmp"
    assert require(keys, "gurufocus") == "k-gf"


def test_require_raises() -> None:
    with pytest.raises(MissingKey) as e:
        require(Keys(fmp=None, gurufocus=None), "gurufocus")
    assert e.value.vendor == "gurufocus"


@pytest.mark.parametrize(
    ("vendor", "keys", "env_var"),
    [
        ("fmp", Keys(fmp=None, gurufocus="k-other"), "FAIRBAND_FMP_KEY"),
        ("gurufocus", Keys(fmp="k-other", gurufocus=None), "FAIRBAND_GURUFOCUS_KEY"),
    ],
)
def test_missing_key_message_names_file_and_env_var_never_a_value(
    vendor: Literal["fmp", "gurufocus"], keys: Keys, env_var: str
) -> None:
    with pytest.raises(MissingKey) as e:
        require(keys, vendor)
    assert "keys.toml" in str(e.value) and env_var in str(e.value)
    assert "k-other" not in str(e.value)


def test_utcnow_is_timezone_aware_utc() -> None:
    before = datetime.now(UTC)
    now = utcnow()
    assert now.utcoffset() == timedelta(0)
    assert before <= now <= datetime.now(UTC)
