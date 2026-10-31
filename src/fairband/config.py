"""Settings and vendor keys: where the data and the config live, and the keys to load.

``load_settings`` and ``load_keys`` take the environment (and the home directory) as arguments so
that tests never read the real ones; the defaults are ``os.environ`` and ``Path.home()``.
"""

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

type Vendor = Literal["fmp", "gurufocus"]

DEFAULT_PORT = 8470

_KEYS_FILE = "keys.toml"
_KEYS_FILE_HINT = "~/.config/fairband/keys.toml ($XDG_CONFIG_HOME/fairband/keys.toml when set)"
_KEY_ENV_VARS: dict[Vendor, str] = {
    "fmp": "FAIRBAND_FMP_KEY",
    "gurufocus": "FAIRBAND_GURUFOCUS_KEY",
}


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
    """Vendor API keys; a key is ``None`` when absent, never ``""``. The repr hides them."""

    fmp: str | None
    gurufocus: str | None

    def __repr__(self) -> str:
        def shown(key: str | None) -> str:
            return "None" if key is None else "<set>"

        return f"Keys(fmp={shown(self.fmp)}, gurufocus={shown(self.gurufocus)})"


class MissingKey(Exception):
    """A vendor key is in neither the keys file nor the environment."""

    def __init__(self, vendor: Vendor) -> None:
        super().__init__(
            f"no {vendor} key: set {vendor} under [keys] in {_KEYS_FILE_HINT}, "
            f"or set {_KEY_ENV_VARS[vendor]}"
        )
        self.vendor: str = vendor


def load_keys(settings: Settings, env: Mapping[str, str] | None = None) -> Keys:
    """Read ``keys.toml`` in the config directory if present; the environment overrides it."""
    env = os.environ if env is None else env
    file_keys = _read_keys_file(settings.config_dir / _KEYS_FILE)

    def pick(vendor: Vendor) -> str | None:
        return env.get(_KEY_ENV_VARS[vendor], "").strip() or file_keys.get(vendor)

    return Keys(fmp=pick("fmp"), gurufocus=pick("gurufocus"))


def _read_keys_file(path: Path) -> dict[Vendor, str]:
    """The non-empty keys under ``[keys]`` in ``path``. Errors name the file, never its text."""
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
    key = keys.fmp if vendor == "fmp" else keys.gurufocus
    if not key:
        raise MissingKey(vendor)
    return key


def utcnow() -> datetime:
    """Timezone-aware UTC now; the default ``clock`` of every module that reads the time."""
    return datetime.now(UTC)
