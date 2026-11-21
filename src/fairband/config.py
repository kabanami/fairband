"""Settings and vendor keys: where the data and the config live, and the keys to load.

``load_settings`` and ``load_keys`` take the environment (and the home directory) as arguments so
that tests never read the real ones; the defaults are ``os.environ`` and ``Path.home()``. The one
key is FMP's (spec 2026-11-19 8.10): the keys file's other lines, and the environment's other
variables, are not read, so a file that still names a vendor Fairband no longer calls loads as
before, with no error and no warning.
"""

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

type Vendor = Literal["fmp"]

DEFAULT_PORT = 8470

_KEYS_FILE = "keys.toml"
_KEYS_FILE_HINT = "~/.config/fairband/keys.toml ($XDG_CONFIG_HOME/fairband/keys.toml when set)"
_KEY_ENV_VARS: dict[Vendor, str] = {"fmp": "FAIRBAND_FMP_KEY"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    config_dir: Path
    db_path: Path
    port: int


def load_settings(env: Mapping[str, str] | None = None, home: Path | None = None) -> Settings:
    """Resolve the directories: ``FAIRBAND_DATA_DIR``, then XDG, then the home defaults."""
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    data_override = env.get("FAIRBAND_DATA_DIR")
    if data_override:
        data_dir = Path(data_override)
    else:
        data_dir = _xdg_home(env, "XDG_DATA_HOME", home / ".local/share") / "fairband"
    config_dir = _xdg_home(env, "XDG_CONFIG_HOME", home / ".config") / "fairband"
    return Settings(
        data_dir=data_dir,
        config_dir=config_dir,
        db_path=data_dir / "fairband.db",
        port=DEFAULT_PORT,
    )


def _xdg_home(env: Mapping[str, str], name: str, fallback: Path) -> Path:
    """The XDG base directory in ``name``; unset, empty or relative values are ignored."""
    path = Path(env.get(name, ""))
    return path if path.is_absolute() else fallback


@dataclass(frozen=True)
class Keys:
    """The vendor API key, FMP's; ``None`` when absent, never ``""``. The repr hides it."""

    fmp: str | None

    def __repr__(self) -> str:
        return f"Keys(fmp={'None' if self.fmp is None else '<set>'})"


class MissingKey(Exception):
    """A vendor key is in neither the keys file nor the environment."""

    def __init__(self, vendor: Vendor) -> None:
        super().__init__(
            f"no {vendor} key: set {vendor} under [keys] in {_KEYS_FILE_HINT}, "
            f"or set {_KEY_ENV_VARS[vendor]}"
        )
        self.vendor: str = vendor


def keys_path(settings: Settings) -> Path:
    """The keys file: ``keys.toml`` in the config directory."""
    return settings.config_dir / _KEYS_FILE


def load_keys(settings: Settings, env: Mapping[str, str] | None = None) -> Keys:
    """Read ``keys.toml`` in the config directory if present; the environment overrides it."""
    env = os.environ if env is None else env
    file_keys = _read_keys_file(keys_path(settings))

    def pick(vendor: Vendor) -> str | None:
        return env.get(_KEY_ENV_VARS[vendor], "").strip() or file_keys.get(vendor)

    return Keys(fmp=pick("fmp"))


def _read_keys_file(path: Path) -> dict[Vendor, str]:
    """The non-empty keys of ``Vendor`` under ``[keys]`` in ``path``; any other line under it is
    not read. Errors name the file, never its text."""
    try:
        with path.open("rb") as f:
            document = tomllib.load(f)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError:
        raise ValueError(f"{path} is not valid TOML") from None
    table = document.get("keys", {})
    if not isinstance(table, dict):
        raise TypeError(f"{path}: [keys] must be a table")
    keys: dict[Vendor, str] = {}
    for vendor in _KEY_ENV_VARS:
        value = table.get(vendor)
        if value is None:
            continue
        if not isinstance(value, str):
            raise TypeError(f"{path}: keys.{vendor} must be a string")
        if key := value.strip():
            keys[vendor] = key
    return keys


def require(keys: Keys, vendor: Vendor) -> str:
    """The key for ``vendor``; raises ``MissingKey`` when it is absent."""
    key = keys.fmp
    if not key:
        raise MissingKey(vendor)
    return key


def utcnow() -> datetime:
    """Timezone-aware UTC now; the default ``clock`` of every module that reads the time."""
    return datetime.now(UTC)
