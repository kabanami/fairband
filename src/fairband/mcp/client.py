"""The MCP server's client of the web API (spec 2026-11-06 Tier 2, 6 and 7).

``FairbandClient`` calls the routes of the server its ``httpx.Client`` points at
(``http://127.0.0.1:<port>``), each call with ``X-Fairband-Request: 1``. Once ``identify`` has
named the model identifier the agent runs as, each also carries ``X-Fairband-Principal: agent``,
``X-Fairband-Actor`` with that identifier as it arrived and, when the handshake gave the client's
name and version, ``X-Fairband-Client: <name>/<version>``; without them the header is left out.

A call answers the API's JSON. A server that does not answer, refused or dropped connection or
timeout alike, raises ``ServerDown`` with ``NOT_RUNNING``. A 4xx or a 5xx raises ``Refused`` with
the status, the API's ``detail`` sentence and the rest of its answer: a refused override's record,
a rejected report's findings. An answer with no sentence of its own is named from what it carries:
a rejected report ``rejected: <n> findings``, as the ledger words it, and a refresh start that
meets a running one ``refresh <id> is running``, as the command line does; any other its status's
reason phrase.
"""

from collections.abc import Mapping
from typing import Any

import httpx

from fairband.web.app import REQUEST_HEADER
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, IDENTIFY_FIRST, PRINCIPAL_HEADER

NOT_RUNNING = "the Fairband server is not running: start `uv run fairband serve`"


class ServerDown(Exception):
    """The server did not answer."""


class Refused(Exception):
    """The API refused the call: its ``status``, its sentence and the rest of its answer."""

    def __init__(self, status: int, detail: str, extra: Mapping[str, Any] | None = None) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.extra = dict(extra or {})


class FairbandClient:
    """The web API's routes as calls; ``http`` has the server's base URL."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http
        self._identity: dict[str, str] = {}

    @property
    def identified(self) -> bool:
        return bool(self._identity)

    @property
    def client(self) -> str | None:
        """The client header's value, ``<name>/<version>``; ``None`` without one."""
        return self._identity.get(CLIENT_HEADER)

    def identify(
        self, agent: str, client_name: str | None = None, client_version: str | None = None
    ) -> None:
        """Send every later call as ``agent``'s, a model identifier, from the client named;
        ``ValueError(IDENTIFY_FIRST)`` for a blank identifier, which leaves the identity as it
        was."""
        if not agent.strip():
            raise ValueError(IDENTIFY_FIRST)
        identity = {PRINCIPAL_HEADER: "agent", ACTOR_HEADER: agent}
        if client_name and client_version:
            identity[CLIENT_HEADER] = f"{client_name}/{client_version}"
        self._identity = identity

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        """The route's answer; a parameter that is ``None`` is left out."""
        given = {name: value for name, value in (params or {}).items() if value is not None}
        return self._send("GET", path, params=given)

    def post(self, path: str, body: Any) -> Any:
        return self._send("POST", path, body=body)

    def patch(self, path: str, body: Any) -> Any:
        return self._send("PATCH", path, body=body)

    def delete(self, path: str, body: Any) -> Any:
        return self._send("DELETE", path, body=body)

    def _send(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any] | None = None,
        body: Any = None,
    ) -> Any:
        headers = {REQUEST_HEADER: "1", **self._identity}
        try:
            response = self._http.request(method, path, params=params, json=body, headers=headers)
        except httpx.TransportError:
            raise ServerDown(NOT_RUNNING) from None
        if response.is_error:
            raise _refused(response)
        return response.json()


def _refused(response: httpx.Response) -> Refused:
    """The refusal ``response`` carries (module docstring)."""
    try:
        answer = response.json()
    except ValueError:  # not JSON: a bare server error
        answer = None
    if not isinstance(answer, dict):
        return Refused(response.status_code, response.text.strip() or response.reason_phrase)
    rest = {key: value for key, value in answer.items() if key != "detail"}
    detail = answer.get("detail")
    if not isinstance(detail, str):
        detail = _named(rest) or response.reason_phrase
    return Refused(response.status_code, detail, rest)


def _named(answer: Mapping[str, Any]) -> str | None:
    findings = answer.get("findings")
    if isinstance(findings, list):
        n = len(findings)
        return f"rejected: {n} finding{'' if n == 1 else 's'}"
    if "running" in answer:
        return f"refresh {answer['running']} is running"
    return None
