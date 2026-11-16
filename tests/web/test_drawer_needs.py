"""What the price needs (method 4.11) is on no page (spec 2026-11-16 company page, 4, 11 and 13):
the drawer and the report page draw no sentence of it and the page has no style for one. The
company's detail still carries ``priceNeeds`` for an agent's research
(``tests/web/test_price_needs_api.py``)."""

from importlib import resources
from pathlib import Path

STATIC = Path(str(resources.files("fairband.web").joinpath("static")))
APP = STATIC / "app.js"
REPORT = STATIC / "report.js"
INDEX = STATIC / "index.html"


def test_the_drawer_does_not_draw_it() -> None:
    assert "priceNeeds" not in APP.read_text(encoding="utf-8")


def test_the_report_page_does_not_draw_it() -> None:
    assert "priceNeeds" not in REPORT.read_text(encoding="utf-8")


def test_the_page_has_no_style_for_it() -> None:
    assert ".app-needs" not in INDEX.read_text(encoding="utf-8")


def test_no_page_script_names_it() -> None:
    """No script of the page draws it (the design's 13), the company page's among them."""
    scripts = sorted(STATIC.glob("*.js"))
    assert APP in scripts and REPORT in scripts
    for script in scripts:
        assert "priceNeeds" not in script.read_text(encoding="utf-8"), script.name
