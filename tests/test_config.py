import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from support.system import needs_linux_file_modes

from fairband import __main__ as cli
from fairband.config import Keys, MissingKey, load_keys, load_settings, require, utcnow
from fairband.plans import PREMIUM, ULTIMATE


def _write_keys(home: Path, text: str, again: bool = False) -> None:
    (home / ".config/fairband").mkdir(parents=True, exist_ok=again)
    (home / ".config/fairband/keys.toml").write_text(text, encoding="utf-8")


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
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # where Windows reads the home
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("FAIRBAND_FMP_KEY", "env-fmp")
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "x"))
    s = load_settings()
    assert s.data_dir == tmp_path / "x"
    assert s.config_dir == tmp_path / ".config/fairband"
    assert load_keys(s) == Keys(fmp="env-fmp")


def test_keys_file_then_env(tmp_path: Path) -> None:
    (tmp_path / ".config/fairband").mkdir(parents=True)
    (tmp_path / ".config/fairband/keys.toml").write_text(
        '[keys]\nfmp = "file-fmp"\n', encoding="utf-8"
    )
    s = load_settings(env={}, home=tmp_path)
    assert load_keys(s, env={}) == Keys(fmp="file-fmp")
    assert load_keys(s, env={"FAIRBAND_FMP_KEY": "env-fmp"}).fmp == "env-fmp"


def test_env_key_without_keys_file(tmp_path: Path) -> None:
    s = load_settings(env={}, home=tmp_path)
    keys = load_keys(s, env={"FAIRBAND_FMP_KEY": "env-fmp"})
    assert keys == Keys(fmp="env-fmp")
    assert load_keys(s, env={}) == Keys(fmp=None)


def test_empty_key_is_none_and_empty_env_does_not_override(tmp_path: Path) -> None:
    _write_keys(tmp_path, '[keys]\nfmp = " "\n')
    s = load_settings(env={}, home=tmp_path)
    assert load_keys(s, env={"FAIRBAND_FMP_KEY": ""}) == Keys(fmp=None)
    _write_keys(tmp_path, '[keys]\nfmp = "file-fmp"\n', again=True)
    assert load_keys(s, env={"FAIRBAND_FMP_KEY": ""}) == Keys(fmp="file-fmp")
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


@needs_linux_file_modes
@pytest.mark.parametrize(
    "line",
    ['gurufocus = "file-gf"', "gurufocus = 4242", 'gurufocus = " "'],
    ids=["a-key", "not-a-string", "blank"],
)
@pytest.mark.parametrize("gurufocus_env", [None, "env-gf"], ids=["no-env", "env"])
def test_a_keys_file_with_a_gurufocus_line_loads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    line: str,
    gurufocus_env: str | None,
) -> None:
    """Spec 2026-11-19 8.10: Fairband reads the FMP key alone. A keys file kept from before, its
    ``gurufocus`` line of any kind, loads as the command reads it, without an error and without a
    log record, and ``FAIRBAND_GURUFOCUS_KEY``, set or not, changes nothing."""
    _write_keys(tmp_path, f'[keys]\nfmp = "file-fmp"\n{line}\n')
    (tmp_path / ".config/fairband/keys.toml").chmod(0o600)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # where Windows reads the home
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("FAIRBAND_FMP_KEY", raising=False)
    if gurufocus_env is None:
        monkeypatch.delenv("FAIRBAND_GURUFOCUS_KEY", raising=False)
    else:
        monkeypatch.setenv("FAIRBAND_GURUFOCUS_KEY", gurufocus_env)
    with caplog.at_level(logging.DEBUG):
        keys = cli._keys(load_settings())
    assert keys == Keys(fmp="file-fmp")
    assert keys.fmp == "file-fmp"
    assert caplog.records == []


def test_keys_repr_hides_values() -> None:
    keys = Keys(fmp="k-fmp")
    assert "k-fmp" not in repr(keys)
    assert repr(keys) == "Keys(fmp=<set>, plan=ultimate)"
    assert repr(Keys(fmp=None, plan=PREMIUM)) == "Keys(fmp=None, plan=premium)"


# --- the FMP plan, stated beside the key ---------------------------------------------------------


def test_a_keys_file_with_no_plan_is_on_ultimate(tmp_path: Path) -> None:
    """The plan a key is on is stated under ``[fmp]`` in the keys file; a file that states none,
    every file written before the plans, is on Ultimate, the plan Fairband was built on."""
    _write_keys(tmp_path, '[keys]\nfmp = "file-fmp"\n')
    keys = load_keys(load_settings(env={}, home=tmp_path), env={})
    assert keys.plan is ULTIMATE and keys == Keys(fmp="file-fmp", plan=ULTIMATE)
    assert load_keys(load_settings(env={}, home=tmp_path / "none"), env={}).plan is ULTIMATE


@pytest.mark.parametrize("word", ["premium", " Premium ", "PREMIUM"])
def test_the_plan_is_read_from_the_keys_file(tmp_path: Path, word: str) -> None:
    _write_keys(tmp_path, f'[keys]\nfmp = "file-fmp"\n\n[fmp]\nplan = "{word}"\n')
    keys = load_keys(load_settings(env={}, home=tmp_path), env={})
    assert keys == Keys(fmp="file-fmp", plan=PREMIUM)
    assert keys != Keys(fmp="file-fmp")


def test_the_environment_overrides_the_files_plan(tmp_path: Path) -> None:
    _write_keys(tmp_path, '[keys]\nfmp = "file-fmp"\n\n[fmp]\nplan = "premium"\n')
    s = load_settings(env={}, home=tmp_path)
    assert load_keys(s, env={"FAIRBAND_FMP_PLAN": "ultimate"}).plan is ULTIMATE
    assert load_keys(s, env={"FAIRBAND_FMP_PLAN": " "}).plan is PREMIUM  # blank: the file's
    bare = load_settings(env={}, home=tmp_path / "none")
    assert load_keys(bare, env={"FAIRBAND_FMP_PLAN": "Premium"}).plan is PREMIUM


def test_a_blank_plan_in_the_file_is_no_plan(tmp_path: Path) -> None:
    _write_keys(tmp_path, '[keys]\nfmp = "file-fmp"\n\n[fmp]\nplan = " "\n')
    assert load_keys(load_settings(env={}, home=tmp_path), env={}).plan is ULTIMATE


@pytest.mark.parametrize(
    ("text", "error", "rule"),
    [
        ('[fmp]\nplan = "starter"\n', ValueError, "fmp.plan must be ultimate or premium"),
        ("[fmp]\nplan = 4242\n", TypeError, "fmp.plan must be a string"),
    ],
    ids=["another-plan", "not-a-string"],
)
def test_a_bad_plan_in_the_file_names_the_path_and_the_plans_never_the_value(
    tmp_path: Path, text: str, error: type[Exception], rule: str
) -> None:
    _write_keys(tmp_path, '[keys]\nfmp = "file-fmp"\n\n' + text)
    s = load_settings(env={}, home=tmp_path)
    with pytest.raises(error) as e:
        load_keys(s, env={})
    assert str(e.value) == f"{s.config_dir / 'keys.toml'}: {rule}"
    assert "starter" not in str(e.value) and "4242" not in str(e.value)
    # The environment's plan stands in for the file's, bad or not.
    assert load_keys(s, env={"FAIRBAND_FMP_PLAN": "premium"}).plan is PREMIUM


def test_a_bad_plan_in_the_environment_names_the_variable_never_the_value(tmp_path: Path) -> None:
    s = load_settings(env={}, home=tmp_path)
    with pytest.raises(ValueError) as e:
        load_keys(s, env={"FAIRBAND_FMP_PLAN": "starter"})
    assert str(e.value) == "FAIRBAND_FMP_PLAN must be ultimate or premium"


def test_an_fmp_line_that_is_no_table_states_no_plan(tmp_path: Path) -> None:
    """A top-level ``fmp`` line, a key put outside ``[keys]`` say, was not read before the plans
    and is not read now: no plan, no error, and so nothing of its value in any message."""
    _write_keys(tmp_path, 'fmp = "misplaced-key"\n\n[keys]\nfmp = "file-fmp"\n')
    assert load_keys(load_settings(env={}, home=tmp_path), env={}) == Keys(fmp="file-fmp")


def test_require_returns_the_key() -> None:
    assert require(Keys(fmp="k-fmp"), "fmp") == "k-fmp"


def test_require_raises() -> None:
    with pytest.raises(MissingKey) as e:
        require(Keys(fmp=None), "fmp")
    assert e.value.vendor == "fmp"


def test_missing_key_message_names_file_and_env_var_never_a_value(tmp_path: Path) -> None:
    _write_keys(tmp_path, '[keys]\ngurufocus = "k-other"\n')
    keys = load_keys(load_settings(env={}, home=tmp_path), env={"FAIRBAND_GURUFOCUS_KEY": "k-env"})
    with pytest.raises(MissingKey) as e:
        require(keys, "fmp")
    assert "keys.toml" in str(e.value) and "FAIRBAND_FMP_KEY" in str(e.value)
    assert "k-other" not in str(e.value) and "k-env" not in str(e.value)


def test_utcnow_is_timezone_aware_utc() -> None:
    before = datetime.now(UTC)
    now = utcnow()
    assert now.utcoffset() == timedelta(0)
    assert before <= now <= datetime.now(UTC)
