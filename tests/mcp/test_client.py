"""The MCP server's client of the web API (spec 2026-11-06 Tier 2, 6 and 7), on the web tests'
app: every call carries the request header, and after ``identify`` the identity headers; a refusal
is the API's sentence; a server that does not answer is one sentence."""

import json
from typing import Any

import httpx
import pytest
from support.web import HOST

from fairband.mcp.client import (
    NO_ANSWER,
    NOT_ASCII,
    NOT_RUNNING,
    TIMEOUT_S,
    FairbandClient,
    Refused,
    ServerDown,
)
from fairband.reports.check import headings
from fairband.web.identity import IDENTIFY_FIRST

ITEM = {"symbol": "AAPL", "mode": "full report"}
IDENTITY = ("X-Fairband-Request", "X-Fairband-Principal", "X-Fairband-Actor", "X-Fairband-Client")


def _newest_entry(api: FairbandClient) -> dict[str, Any]:
    entry: dict[str, Any] = api.get("/api/ledger", {"symbol": "AAPL", "limit": 1})["entries"][0]
    return entry


def test_get_and_post_carry_the_request_header(api: FairbandClient) -> None:
    # A write without the header is refused 403 (D11): this one passes.
    item = api.post("/api/inbox", ITEM)
    assert (item["symbol"], item["state"], item["origin"]) == ("AAPL", "pending", "owner")
    assert api.get("/api/inbox")["items"] == [item]
    assert api.get("/api/inbox", {"state": "done"})["items"] == []
    entry = _newest_entry(api)
    assert (entry["principal"], entry["actor"], entry["client"]) == ("owner", None, None)


def test_the_headers_and_the_parameters_as_sent() -> None:
    sent: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(answer), base_url=HOST) as http:
        api = FairbandClient(http)
        api.get("/api/ledger", {"symbol": None, "limit": 5})
        api.identify("claude-opus-5-5", "claude-code", "2.1")
        api.delete("/api/overrides/3", {"reason": "restated"})
    before, after = sent
    assert str(before.url) == f"{HOST}/api/ledger?limit=5"  # a None parameter is left out
    assert before.headers["X-Fairband-Request"] == "1"
    assert "X-Fairband-Principal" not in before.headers
    assert (after.method, json.loads(after.content)) == ("DELETE", {"reason": "restated"})
    assert {name: after.headers[name] for name in IDENTITY} == {
        "X-Fairband-Request": "1",
        "X-Fairband-Principal": "agent",
        "X-Fairband-Actor": "claude-opus-5-5",
        "X-Fairband-Client": "claude-code/2.1",
    }


def test_identify_adds_the_identity_headers(api: FairbandClient) -> None:
    assert not api.identified
    api.identify("claude-opus-5-5", "claude-code", "2.1")
    assert api.identified
    item = api.post("/api/inbox", ITEM)
    assert (item["origin"], item["postedActor"], item["postedClient"]) == (
        "agent",
        "claude-opus-5-5",
        "claude-code/2.1",
    )
    claimed = api.post("/api/inbox/claim", {"itemId": item["id"]})
    assert claimed["claimedBy"] == "claude-opus-5-5"
    entry = _newest_entry(api)
    assert (entry["kind"], entry["principal"], entry["actor"], entry["client"]) == (
        "claim",
        "agent",
        "claude-opus-5-5",
        "claude-code/2.1",
    )


def test_without_the_handshake_s_client_the_client_header_is_left_out(
    api: FairbandClient,
) -> None:
    api.identify("gpt-5", None, None)
    item = api.post("/api/inbox", ITEM)
    assert (item["origin"], item["postedActor"], item["postedClient"]) == ("agent", "gpt-5", None)


def test_a_blank_model_identifier_is_refused(api: FairbandClient) -> None:
    with pytest.raises(ValueError, match=IDENTIFY_FIRST):
        api.identify("  ", "claude-code", "2.1")
    assert not api.identified


@pytest.mark.parametrize("agent", ["claude-opus-5-5\r\nX-Other: 1", "claude-öpus", "claude\topus"])
def test_a_model_identifier_that_is_not_printable_ascii_is_refused(
    api: FairbandClient, agent: str
) -> None:
    """A header carries printable ASCII only: such an identifier would break every later call."""
    api.identify("claude-opus-5-5", "claude-code", "2.1")
    with pytest.raises(ValueError) as caught:
        api.identify(agent, "claude-code", "2.1")
    assert str(caught.value) == NOT_ASCII == "the model identifier must be printable ASCII"
    item = api.post("/api/inbox", ITEM)  # the identity stays as it was, and every call goes
    assert (item["postedActor"], item["postedClient"]) == ("claude-opus-5-5", "claude-code/2.1")


def test_a_client_name_that_is_not_printable_ascii_is_left_out(api: FairbandClient) -> None:
    api.identify("claude-opus-5-5", "cliënt", "2.1")
    assert api.client is None
    item = api.post("/api/inbox", ITEM)
    assert (item["postedActor"], item["postedClient"]) == ("claude-opus-5-5", None)


def test_a_refusal_carries_the_detail(api: FairbandClient) -> None:
    api.post("/api/inbox", ITEM)
    with pytest.raises(Refused) as caught:
        api.post("/api/inbox", ITEM)
    assert (caught.value.status, caught.value.detail) == (409, "an item for AAPL is open")
    assert caught.value.extra == {}


def test_a_refusal_with_no_sentence_is_named_from_its_answer(api: FairbandClient) -> None:
    """The report route rejects with its findings and no ``detail``: the sentence is the ledger's,
    the findings beside it."""
    api.identify("claude-opus-5-5", "claude-code", "2.1")
    with pytest.raises(Refused) as caught:
        api.post(
            "/api/companies/AAPL/reports",
            {
                "mode": "full report",
                "stance": "hold",
                "sections": [
                    {"heading": h, "parts": ["Plain words."]} for h in headings("full report")
                ],
                "judgments": [
                    {"judgment": kind, "decision": decision}
                    for kind, decision in (
                        ("phase", "keep"),
                        ("moat", "keep"),
                        ("belief", "keep at 12%"),
                        ("roic", "keep"),
                    )
                ],
            },
        )
    assert (caught.value.status, caught.value.detail) == (422, "rejected: 1 finding")
    [finding] = caught.value.extra["findings"]
    assert finding["what"] == "a number with no reference"


def test_a_delete_carries_its_body(api: FairbandClient) -> None:
    api.identify("claude-opus-5-5", "claude-code", "2.1")
    with pytest.raises(Refused) as caught:
        api.delete("/api/overrides/99", {"reason": "the filing was restated"})
    assert (caught.value.status, caught.value.detail) == (404, "no override 99")
    with pytest.raises(Refused) as blank:
        api.delete("/api/overrides/99", {"reason": " "})
    assert (blank.value.status, blank.value.detail) == (400, "a drop needs a reason")


def test_a_patch_moves_the_item(api: FairbandClient) -> None:
    api.identify("claude-opus-5-5", "claude-code", "2.1")
    item = api.post("/api/inbox", ITEM)
    declined = api.patch(f"/api/inbox/{item['id']}", {"action": "decline", "reason": "no filing"})
    assert (declined["state"], declined["reason"]) == ("declined", "no filing")


def test_a_connection_error_is_server_down(down: FairbandClient) -> None:
    with pytest.raises(ServerDown) as caught:
        down.get("/api/inbox")
    with pytest.raises(ServerDown):
        down.post("/api/inbox", ITEM)
    assert str(caught.value) == NOT_RUNNING
    assert NOT_RUNNING == "the Fairband server is not running: start `uv run fairband serve`"


@pytest.mark.parametrize(
    "timeout,sentence",
    [
        (httpx.ConnectTimeout, NOT_RUNNING),
        (httpx.ReadTimeout, NO_ANSWER),
        (httpx.WriteTimeout, NO_ANSWER),
        (httpx.PoolTimeout, NO_ANSWER),
    ],
)
def test_a_timeout_after_connecting_is_not_a_server_that_is_down(
    timeout: type[httpx.TimeoutException], sentence: str
) -> None:
    """A server that took the call but did not answer in time is running: its sentence says to
    try again."""

    def answer(request: httpx.Request) -> httpx.Response:
        raise timeout("timed out", request=request)

    http = httpx.Client(transport=httpx.MockTransport(answer), base_url=HOST)
    with http, pytest.raises(ServerDown) as caught:
        FairbandClient(http).get("/api/screen")
    assert str(caught.value) == sentence
    assert NO_ANSWER == "the Fairband server did not answer in 60 seconds: try again"
    assert TIMEOUT_S == 60
