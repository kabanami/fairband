"""The page's own script and the bundle run in node (``tests/web/page.mjs``), for the tests that
read what a helper returns or what a component draws: ``node`` calls a helper as
``window.FairbandPage`` names it ("reportCharts.roicPoints"), or a bundle component as ``window``
names it ("Fairband.ReportReader"), on its arguments and answers its result through JSON, a
component's the tree it draws; ``elements``, ``classed`` and ``text`` read such a tree.
``tests/web/test_report_charts.py`` and ``tests/web/test_report_reader.py`` use them."""

import json
import shutil
import subprocess
from collections.abc import Iterator
from importlib import resources
from pathlib import Path
from typing import Any

NODE = shutil.which("node")
HARNESS = Path(__file__).parent.parent / "web" / "page.mjs"
STATIC = Path(str(resources.files("fairband.web").joinpath("static")))
BUNDLE = STATIC / "design-system" / "components" / "bundle.js"


def node(helper: str, args: list[Any], *scripts: Path) -> Any:
    """What ``helper``, as the harness names it, returns on ``args``, through JSON; ``scripts``
    load after app.js, as the page loads them."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, str(HARNESS), str(BUNDLE), str(STATIC / "app.js"), helper]
        + [str(script) for script in scripts],
        input=json.dumps(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=60,
    )
    return json.loads(done.stdout)


def elements(tree: Any) -> Iterator[dict[str, Any]]:
    """Every element of a drawn tree, in the document's order; a Fragment's has no ``type``."""
    if isinstance(tree, list):
        for child in tree:
            yield from elements(child)
    elif isinstance(tree, dict):
        yield tree
        yield from elements(tree["props"].get("children"))


def classed(tree: Any, name: str) -> list[dict[str, Any]]:
    """The elements whose class list holds ``name``, in order."""
    return [e for e in elements(tree) if name in str(e["props"].get("className") or "").split()]


def text(tree: Any) -> str:
    """The text an element holds."""
    if isinstance(tree, list):
        return "".join(text(child) for child in tree)
    if isinstance(tree, dict):
        return text(tree["props"].get("children"))
    return "" if tree is None else str(tree)
