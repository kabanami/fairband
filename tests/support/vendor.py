"""The vendor double the web tests share: FMP on a mock transport that serves the fixtures, the
fake key, a ``Passthrough`` over FMP on it, and a client of an app with that pass-through.
``tests/web/conftest.py`` imports the fixtures; a test module imports the names from here. The key
is fake."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from fairband.policy import Policy
from fairband.refresh.passthrough import Passthrough
from fairband.store.db import connect
from fairband.vendors import fmp as fmp_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.http import VendorHttp
from fairband.web.app import create_app
from support.web import HEADER, HOST, NOW, _settings

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fmp"
KEY = "fake-fmp-key-0003"  # not a real key


class Vendor:
    """FMP on a mock transport: a request reads ``fmp/<route>.<symbol>.json`` (a slash in the
    route becomes a dash; news names its symbol in ``symbols``), 404 without one; ``answer``,
    when set, makes each response instead. ``paths`` keeps each request's path."""

    def __init__(self) -> None:
        self.paths: list[str] = []
        self.answer: Any = None  # a function of the request to its response
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(request.url.path)
        if self.answer is not None:
            response: httpx.Response = self.answer(request)
            return response
        route = request.url.path.removeprefix("/stable/").replace("/", "-")
        params = request.url.params
        fixture = FIXTURES / f"{route}.{params.get('symbol') or params.get('symbols')}.json"
        if not fixture.is_file():
            return httpx.Response(404, json={"Error Message": "no fixture"})
        return httpx.Response(
            200, content=fixture.read_bytes(), headers={"Content-Type": "application/json"}
        )


@pytest.fixture
def vendor() -> Vendor:
    return Vendor()


@pytest.fixture
def fmp(policy: Policy, vendor: Vendor) -> Iterator[Fmp]:
    with VendorHttp(
        fmp_api.BASE_URL,
        [KEY],
        policy.refresh,
        transport=vendor.transport,
        sleep=lambda _: None,
        clock=lambda: NOW,
    ) as http:
        yield Fmp(http, KEY)


@pytest.fixture
def passthrough(db_path: Path, policy: Policy, fmp: Fmp) -> Passthrough:
    return Passthrough(fmp, lambda: connect(db_path), policy, lambda: NOW, (KEY,))


def passthrough_client(
    tmp_path: Path, db_path: Path, policy: Policy, passthrough: Passthrough
) -> TestClient:
    """A client of an app over ``db_path`` with ``passthrough``, the clock at ``NOW``; it sends
    the request header on every call, as a read that may call a vendor needs (D11)."""

    def conn_factory() -> Any:
        return connect(db_path)

    settings = _settings(tmp_path, db_path)
    app = create_app(settings, policy, conn_factory, clock=lambda: NOW, passthrough=passthrough)
    return TestClient(app, base_url=HOST, headers=HEADER)


@pytest.fixture
def with_passthrough(
    tmp_path: Path, db_path: Path, policy: Policy, passthrough: Passthrough
) -> Iterator[TestClient]:
    """A pass-through over FMP."""
    with passthrough_client(tmp_path, db_path, policy, passthrough) as client:
        yield client
