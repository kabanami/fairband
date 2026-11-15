"""The drawer's and the report page's words for a company in another currency, or an ADR (spec
2026-11-10 6.2, 7.4 and 10): a USD figure with `$` as before, any other with its code before the
number, a total to whole units and a figure a share to two decimals; the rate, the differential and
the ADR ratio among the inputs, each in its own form; and the line under the head that says what
the figures are in. A finding's and a guidance record's money in the record's own currency (spec
2026-11-15 9.5). The page's own script runs in node after the bundle (``page.mjs``), and the
tests read what its helpers return."""

import json
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("page.mjs")
STATIC = Path(str(resources.files("fairband.web").joinpath("static")))
BUNDLE = STATIC / "design-system" / "components" / "bundle.js"
APP = STATIC / "app.js"
GOLDEN = Path(__file__).parent.parent / "fixtures" / "golden"

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# The brief's line: TSM reports in TWD, one ADS is five ordinary shares, at 32.96 TWD a dollar.
TSM = {"currency": "TWD", "isAdr": True, "adrRatio": 5.0, "fxRate": 32.96, "fxDate": "2026-11-10"}
DOMESTIC = {"currency": "USD", "isAdr": False, "adrRatio": None, "fxRate": None, "fxDate": None}


def _call(helper: str, *args: Any) -> Any:
    """What app.js's ``helper`` returns on ``args``, through JSON."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, str(HARNESS), str(BUNDLE), str(APP), helper],
        input=json.dumps(list(args)),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(done.stdout)


def _texts(node: Any) -> list[str]:
    """The text of an element tree, in order: its strings and its children's."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [text for child in node for text in _texts(child)]
    if isinstance(node, dict):
        return _texts(node.get("props", {}).get("children", []))
    return []


def _after(texts: list[str], label: str) -> str:
    """The text that follows ``label``: a figure after its name."""
    return texts[texts.index(label) + 1]


@pytest.mark.parametrize(
    ("given", "shown"),
    [
        # in another currency: the code before the number, a share to cents, a total whole
        ({"name": "eps_ttm", "value": 12807.36, "unit": "TWD a share"}, "TWD 12,807.36"),
        (
            {"name": "market_cap", "value": 3_809_054_300_000, "unit": "TWD"},
            "TWD 3,809,054,300,000",
        ),
        ({"name": "dividends_ttm", "value": -800e6, "unit": "SEK"}, "−SEK 800,000,000"),
        ({"name": "ntm_eps", "value": 47.2, "unit": "SEK a share"}, "SEK 47.20"),
        # in USD, as before: a price to cents, a total in whole dollars
        ({"name": "price", "value": 50.0, "unit": "USD"}, "$50.00"),
        ({"name": "eps_ttm", "value": 6.42, "unit": "USD a share"}, "$6.42"),
        ({"name": "market_cap", "value": 5.9e9, "unit": "USD"}, "$5,900,000,000"),
        # the rate in units of the currency a dollar, four decimals below one
        ({"name": "fx_rate", "value": 32.96, "unit": "TWD per USD"}, "32.96"),
        ({"name": "fx_rate", "value": 0.86124, "unit": "EUR per USD"}, "0.8612"),
        # the differential a percentage; the ADR ratio a number of shares, never a percentage
        ({"name": "inflation_differential", "value": -0.00509, "unit": "ratio"}, "−0.5%"),
        ({"name": "adr_ratio", "value": 5.0, "unit": "ratio"}, "5"),
        ({"name": "adr_ratio", "value": 0.3333, "unit": "ratio"}, "0.3333"),
        ({"name": "adr_ratio", "value": None, "unit": "ratio"}, "—"),
        ({"name": "required_return", "value": 0.0845, "unit": "ratio"}, "8.5%"),
    ],
)
def test_an_input_reads_in_its_unit(given: dict[str, Any], shown: str) -> None:
    assert _call("inputValue", given) == shown


def test_an_override_or_a_bridge_line_reads_in_its_unit() -> None:
    """An override made on a row in another currency carries the code in its unit (7.3), so its
    old and new values, and its bridge line's, print with the code."""
    assert _call("inputFigure", 40.0, "SEK a share") == "SEK 40.00"
    assert _call("inputFigure", 40.0, "USD a share") == "$40.00"
    assert _call("inputFigure", 2.5, "multiple") == "2.50x"


@pytest.mark.parametrize(
    ("body", "line"),
    [
        (TSM, "Reports in TWD; one ADS is five ordinary shares; valued at TWD 32.96 per USD"),
        (DOMESTIC, ""),  # a domestic row says nothing new
        (
            DOMESTIC | {"currency": "SEK", "fxRate": 8.0},
            "Reports in SEK; valued at SEK 8.00 per USD",
        ),
        (
            DOMESTIC | {"isAdr": True, "adrRatio": 2.0},
            "Reports in USD; one ADS is two ordinary shares",
        ),
        (DOMESTIC | {"adrRatio": 1.0}, "Reports in USD; one ADS is one ordinary share"),
        (
            DOMESTIC | {"isAdr": True, "adrRatio": 20.0},
            "Reports in USD; one ADS is 20 ordinary shares",
        ),
        (
            DOMESTIC | {"isAdr": True, "adrRatio": 1.5},
            "Reports in USD; one ADS is 1.5 ordinary shares",
        ),
        (
            TSM | {"currency": "CNY", "adrRatio": 0.3333, "fxRate": 7.1234},
            "Reports in CNY; three ADSs are one ordinary share; valued at CNY 7.12 per USD",
        ),
        (
            TSM | {"currency": "EUR", "adrRatio": None, "fxRate": 0.86124},
            "Reports in EUR; the ADR ratio is not on file; valued at EUR 0.8612 per USD",
        ),
        # refused for its currency (fix round 1): the code, but no rate, so no "valued at"
        (
            TSM | {"currency": "ARS", "adrRatio": 2.0, "fxRate": None, "fxDate": None},
            "Reports in ARS; one ADS is two ordinary shares",
        ),
    ],
)
def test_the_head_says_what_the_figures_are_in(body: dict[str, Any], line: str) -> None:
    assert _call("currencyLine", body) == line


def test_the_report_page_says_every_figure_a_share_is_per_ads() -> None:
    """Spec 6.2: the report's words, "one ADS is five ordinary shares; every per-share figure here
    is per ADS"; a company that is no ADR says nothing of it."""
    assert _call("currencyLine", TSM, True) == (
        "Reports in TWD; one ADS is five ordinary shares; every per-share figure here is per ADS;"
        " valued at TWD 32.96 per USD"
    )
    assert _call("currencyLine", DOMESTIC | {"currency": "SEK", "fxRate": 8.0}, True) == (
        "Reports in SEK; valued at SEK 8.00 per USD"
    )


def test_a_figure_in_the_currency_takes_its_code() -> None:
    """The drawer's tables print a total and a figure a share in the row's currency: the code
    before the number, or `$` for USD and for none named."""
    assert _call("whole", 3_809_054_300_000, "TWD") == "TWD 3,809,054,300,000"
    assert _call("whole", -5e9) == "−$5,000,000,000"
    assert _call("whole", -5e9, "USD") == "−$5,000,000,000"
    assert _call("whole", None, "SEK") == "—"
    assert _call("money", 837.1415, "SEK") == "SEK 837.14"
    assert _call("money", -1.5, "SEK") == "−SEK 1.50"
    assert _call("money", 104.6427) == "$104.64"
    assert _call("money", None, "SEK") == "—"


def test_the_intermediates_of_a_row_in_another_currency_name_its_code() -> None:
    """FXCO's golden, valued in SEK: the route's figures are in SEK (the value a share before
    translation, the earnings a share, the total value), the price facts in USD, as the closes
    are; the rate in units of the currency a dollar and the differential a percentage."""
    im = json.loads((GOLDEN / "FXCO.json").read_text())["intermediates"]
    texts = _texts(_call("intermediates", im))
    assert _after(texts, "value_per_share") == "SEK 837.14"
    assert _after(texts, "value_in_currency") == "SEK 837.14"
    assert _after(texts, "value_total") == "SEK 83,714,149,943"
    assert _after(texts, "clean") == "SEK 42.00"  # the eps group
    assert _after(texts, "high_52w") == "$50.00"
    assert _after(texts, "fx_rate") == "8.00"
    assert _after(texts, "inflation_differential") == "2.0%"
    assert _after(texts, "currency") == "SEK"
    mgco = json.loads((GOLDEN / "MGCO.json").read_text())["intermediates"]
    usd = _texts(_call("intermediates", mgco))
    assert _after(usd, "value_per_share").startswith("$")


def test_the_secondary_path_and_the_guidance_read_in_the_currency() -> None:
    """A secondary valuation's parts and a guidance record's figures are in the reporting currency
    (7.3, 7.6): the code before them; in USD, `$` as before."""
    parts = {"form": "parts", "parts": [{"name": "the business", "value": 1_234e6, "note": None}]}
    assert "SEK 1,234,000,000" in _texts(_call("secondaryPath", parts, "SEK"))
    assert "$1,234,000,000" in _texts(_call("secondaryPath", parts))
    guidance = [
        {
            "id": 1,
            "metric": "eps",
            "period": "2027",
            "basis": "gaap",
            "asOf": "2026-10-30",
            "state": "current",
            "citedBy": [],
            "low": 4.2,
            "high": 4.4,
            "midpoint": 4.3,
        },
        {
            "id": 2,
            "metric": "revenue",
            "period": "2027",
            "basis": "gaap",
            "asOf": "2026-10-30",
            "state": "current",
            "citedBy": [],
            "low": 2.1e9,
            "high": 2.1e9,
            "midpoint": 2.1e9,
        },
    ]
    texts = _texts(_call("guidanceTable", guidance, "SEK"))
    for figure in ("SEK 4.20 – SEK 4.40", "midpoint SEK 4.30", "SEK 2,100,000,000"):
        assert figure in texts, figure
    assert "$4.20 – $4.40" in _texts(_call("guidanceTable", guidance))


def _guided(record_id: int, metric: str, low: float, high: float, currency: str | None) -> Any:
    """A guidance record as the research read sends it, its ``currency`` that of its money (spec
    2026-11-15 9.1), with the state and the citing overrides Details gives it."""
    return {
        "id": record_id,
        "metric": metric,
        "period": "2027",
        "basis": "gaap",
        "asOf": "2026-10-30",
        "state": "current",
        "citedBy": [],
        "low": low,
        "high": high,
        "midpoint": (low + high) / 2,
        "currency": currency,
    }


def test_the_guidance_table_writes_each_record_in_its_own_currency() -> None:
    """Spec 2026-11-15 9.5: each record's money in the record's currency, `$` for USD and the code
    before the number otherwise, the company's code only where the record names none; a percent
    as before. A US company's records read with `$` as before, and one in EUR with EUR."""
    guidance = [
        _guided(1, "eps", 4.2, 4.4, "USD"),
        _guided(2, "revenue", 2.1e9, 2.1e9, "SEK"),
        _guided(3, "net_income", 3e8, 3e8, None),
        _guided(4, "operating_margin", 0.3, 0.32, None),
    ]
    texts = _texts(_call("guidanceTable", guidance, "SEK"))
    for figure in (
        "$4.20 – $4.40",
        "midpoint $4.30",
        "SEK 2,100,000,000",
        "SEK 300,000,000",  # none named: the company's code
        "30.0% – 32.0%",
        "midpoint 31.0%",
    ):
        assert figure in texts, figure
    assert "SEK 4.20 – SEK 4.40" not in texts and "$2,100,000,000" not in texts
    us = [_guided(1, "eps", 4.2, 4.4, "USD"), _guided(2, "revenue", 2.1e9, 2.1e9, "EUR")]
    texts = _texts(_call("guidanceTable", us, "USD"))
    assert "$4.20 – $4.40" in texts and "EUR 2,100,000,000" in texts


def _finding(finding_id: int, value: float, unit: str, currency: str | None) -> Any:
    """A finding as the research read sends it (``agents_api.finding_json``)."""
    return {
        "id": finding_id,
        "symbol": "FXCO",
        "asOf": "2026-10-30",
        "text": "Segment revenue.",
        "value": value,
        "unit": unit,
        "period": "2026",
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
        "at": "2026-11-01T09:30:00+00:00",
        "currency": currency,
        "source": {"kind": "filing", "ref": "10-K 2026, p. 41", "note": None},
    }


def test_the_findings_block_writes_each_finding_in_its_own_currency() -> None:
    """Spec 2026-11-15 9.5: Details' Findings block writes a finding's money in its currency, a
    USD finding with `$` and one with no currency named in the company's code; a percent as
    before. A US company's findings read as before, and one in EUR with EUR."""
    findings = [
        _finding(1, 1.5e9, "currency", "USD"),
        _finding(2, 4.2, "per-share", None),
        _finding(3, 0.12, "percent", None),
    ]
    texts = _texts(_call("findingsList", findings, "SEK"))
    for figure in (" $1,500,000,000", " SEK 4.20", " 12.0%"):
        assert figure in texts, figure
    us = [_finding(1, 1.5e9, "currency", "USD"), _finding(2, 2e9, "currency", "EUR")]
    texts = _texts(_call("findingsList", us, "USD"))
    assert " $1,500,000,000" in texts and " EUR 2,000,000,000" in texts
