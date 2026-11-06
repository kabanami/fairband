"""The MCP tests' fixtures: the web tests' app over their database, shared from
``support.web_app`` (AAPL, AAL and HGCO, each with one snapshot); the MCP server's client of that
app, not yet identified; and a client of a port on 127.0.0.1 that nothing listens on."""

import socket
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from support.web_app import client, client_with_clock, db_path, policy, results  # noqa: F401

from fairband.mcp.client import FairbandClient


@pytest.fixture
def api(client: TestClient) -> FairbandClient:  # noqa: F811 (the fixture of that name)
    return FairbandClient(client)


@pytest.fixture
def down() -> Iterator[FairbandClient]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with httpx.Client(base_url=f"http://127.0.0.1:{port}") as http:
        yield FairbandClient(http)
