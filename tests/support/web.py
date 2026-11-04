"""The web tests' shared names: the dates of the test database, the clock its apps read, the host
the app trusts, the header every write carries, a universe row, the app's settings, and the page's
static files as text.

``tests/web/conftest.py`` builds its fixtures from them. A test module imports them from here, not
from a conftest: the conftest modules of two test directories share one module name, so which one
``from conftest import`` reads depends on the paths a run collects."""

from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import resources
from pathlib import Path

from fairband.config import DEFAULT_PORT, Settings
from fairband.store.companies import CompanyRow

TODAY = date(2026, 10, 31)  # the day the engine's test companies are valued
STARTED = datetime(2026, 10, 31, 22, 0, tzinfo=UTC)
CREATED = datetime(2026, 10, 31, 22, 15, tzinfo=UTC)
FINISHED = datetime(2026, 10, 31, 22, 20, tzinfo=UTC)
NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
CALIBRATION = {"refused": 1, "valued": 2}
HOST = "http://127.0.0.1:8470"  # a host the app trusts (D11)
HEADER = {"X-Fairband-Request": "1"}  # the header a write must carry (D11)


def _company(symbol: str, refresh_id: int, name: str, market_cap: Decimal) -> CompanyRow:
    return CompanyRow(
        symbol=symbol,
        refresh_id=refresh_id,
        name=name,
        exchange="NASDAQ",
        sector="Technology",
        industry="Software - Application",
        country="US",
        currency="USD",
        is_adr=False,
        cap_band="mega" if market_cap >= 100_000_000_000 else "mid",
        market_cap=market_cap,
        eligible=True,
        exclusion_reason=None,
        observed_at=STARTED,
    )


def _settings(tmp_path: Path, db_path: Path) -> Settings:
    return Settings(
        data_dir=db_path.parent, config_dir=tmp_path / "config", db_path=db_path, port=DEFAULT_PORT
    )


def _component_file(name: str) -> str:
    """A file of the repository's design-system copy, as text."""
    components = resources.files("fairband.web").joinpath("static", "design-system", "components")
    return components.joinpath(name).read_text(encoding="utf-8")


def _static_file(name: str) -> str:
    """A file of the page's own static directory, as text."""
    return resources.files("fairband.web").joinpath("static", name).read_text(encoding="utf-8")
