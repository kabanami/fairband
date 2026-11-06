"""The MCP server's client of the web API (spec 2026-11-06 Tier 2, 6 and 7).

``FairbandClient`` calls the routes of the server its ``httpx.Client`` points at
(``http://127.0.0.1:<port>``), each call with ``X-Fairband-Request: 1``. Once ``identify`` has
named the model identifier the agent runs as, each also carries ``X-Fairband-Principal: agent``,
``X-Fairband-Actor`` with that identifier as it arrived and, when the handshake gave the client's
name and version, ``X-Fairband-Client: <name>/<version>``; without them the header is left out.
A header carries printable ASCII only, so ``identify`` refuses an identifier that is not, with
``NOT_ASCII``, and leaves out a client header that is not.

A call answers the API's JSON. A server that does not answer raises ``ServerDown`` with its
sentence: ``NOT_RUNNING`` for a refused or dropped connection or a connect timeout;
``NO_ANSWER`` for a timeout after the call reached the server (``TIMEOUT_S``, the command's
client's), which is running. A 4xx or a 5xx raises ``Refused`` with the status, the API's
``detail`` sentence and the rest of its answer: a refused override's record, a rejected report's
findings. An answer with no sentence of its own is named from what it carries: a rejected report
``rejected: <n> findings``, as the ledger words it, and a refresh start that meets a running one
``refresh <id> is running``, as the command line does; any other its status's reason phrase.
"""

from collections.abc import Mapping
from typing import Any

import httpx

from fairband.web.app import REQUEST_HEADER
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, IDENTIFY_FIRST, PRINCIPAL_HEADER

# A pass-through waits at most 10 s for a slot and 30 s for the vendor; a refresh start answers at
# once. Past this, the server is taken as not answering.
TIMEOUT_S = 60.0
NOT_RUNNING = "the Fairband server is not running: start `uv run fairband serve`"
NO_ANSWER = f"the Fairband server did not answer in {TIMEOUT_S:.0f} seconds: try again"
NOT_ASCII = "the model identifier must be printable ASCII"


class ServerDown(Exception):
    """The server did not answer; the message says how (module docstring)."""


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
        """Send every later call as ``agent``'s, a model identifier, from the client named, its
        header left out when it is not printable ASCII; ``ValueError(IDENTIFY_FIRST)`` for a
        blank identifier and ``ValueError(NOT_ASCII)`` for one that is not printable ASCII, each
        leaving the identity as it was."""
        if not agent.strip():
            raise ValueError(IDENTIFY_FIRST)
        if not _printable(agent):
            raise ValueError(NOT_ASCII)
        identity = {PRINCIPAL_HEADER: "agent", ACTOR_HEADER: agent}
        client = f"{client_name}/{client_version}" if client_name and client_version else None
        if client is not None and _printable(client):
            identity[CLIENT_HEADER] = client
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
        except httpx.ConnectTimeout:
            raise ServerDown(NOT_RUNNING) from None
        except httpx.TimeoutException:
            raise ServerDown(NO_ANSWER) from None
        except httpx.TransportError:
            raise ServerDown(NOT_RUNNING) from None
        if response.is_error:
            raise _refused(response)
        return response.json()


def _printable(text: str) -> bool:
    """Whether ``text`` is printable ASCII, the space to the tilde, as a header value must be."""
    return all(" " <= c <= "~" for c in text)


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
