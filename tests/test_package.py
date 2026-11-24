import subprocess
import sys

import fairband
from fairband.__main__ import parse_args


def test_version() -> None:
    assert fairband.__version__ == "0.1.0"


def test_cli_version() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "fairband", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert out.returncode == 0 and "0.1.0" in out.stdout


def test_serve_port_defaults_to_8470() -> None:
    assert parse_args(["serve"]).port == 8470
    assert parse_args(["serve", "--port", "9000"]).port == 9000


def test_refresh_with_symbols_defaults_to_scoped() -> None:
    args = parse_args(["refresh", "AAPL,MSFT"])
    assert args.symbols == ["AAPL", "MSFT"] and args.kind == "scoped"


def test_refresh_without_symbols_defaults_to_full() -> None:
    args = parse_args(["refresh"])
    assert args.symbols is None and args.kind == "full"


def test_refresh_kind_given_wins() -> None:
    assert parse_args(["refresh", "--kind", "price"]).kind == "price"


def test_migrate_registered() -> None:
    assert parse_args(["migrate"]).command == "migrate"
