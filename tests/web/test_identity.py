"""The identity headers: who makes a write (spec 2026-11-06 Tier 2, section 7)."""

import pytest
from fastapi import HTTPException, Request

from fairband.store.ledger import OWNER, Writer
from fairband.web.identity import (
    ACTOR_HEADER,
    CLIENT_HEADER,
    IDENTIFY_FIRST,
    PRINCIPAL_HEADER,
    writer_of,
)


def _request(headers: dict[str, str]) -> Request:
    raw = [(name.lower().encode(), value.encode()) for name, value in headers.items()]
    return Request({"type": "http", "headers": raw})


def test_no_headers_is_the_owner() -> None:
    assert writer_of(_request({})) == OWNER
    assert writer_of(_request({PRINCIPAL_HEADER: "owner"})) == OWNER
    assert writer_of(_request({ACTOR_HEADER: "claude-opus-5-5"})) == OWNER  # no principal


def test_an_agent_with_an_actor_and_a_client() -> None:
    headers = {
        PRINCIPAL_HEADER: "agent",
        ACTOR_HEADER: "claude-opus-5-5",
        CLIENT_HEADER: "claude-code/2.1",
    }
    assert writer_of(_request(headers)) == Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    del headers[CLIENT_HEADER]
    assert writer_of(_request(headers)) == Writer("agent", "claude-opus-5-5", None)


@pytest.mark.parametrize("client", ["", " ", "\t "])
def test_a_blank_client_names_none(client: str) -> None:
    """B-103 (spec 2026-11-15 12.1, clause 4): a blank or whitespace client header is no client;
    one with text is kept exactly as it arrived."""
    headers = {PRINCIPAL_HEADER: "agent", ACTOR_HEADER: "claude-opus-5-5", CLIENT_HEADER: client}
    assert writer_of(_request(headers)) == Writer("agent", "claude-opus-5-5", None)
    padded = headers | {CLIENT_HEADER: " claude-code/2.1"}
    assert writer_of(_request(padded)).client == " claude-code/2.1"


@pytest.mark.parametrize("actor", [None, "", "  "])
def test_an_agent_without_an_actor_is_told_to_identify(actor: str | None) -> None:
    headers = {PRINCIPAL_HEADER: "agent"} | ({} if actor is None else {ACTOR_HEADER: actor})
    with pytest.raises(HTTPException) as refused:
        writer_of(_request(headers))
    assert (refused.value.status_code, refused.value.detail) == (400, IDENTIFY_FIRST)
    assert IDENTIFY_FIRST == "identify first: the model identifier you run as"


@pytest.mark.parametrize("principal", ["system", "Agent", ""])
def test_an_unknown_principal_is_refused(principal: str) -> None:
    headers = {PRINCIPAL_HEADER: principal, ACTOR_HEADER: "claude-opus-5-5"}
    with pytest.raises(HTTPException) as refused:
        writer_of(_request(headers))
    assert (refused.value.status_code, refused.value.detail) == (
        400,
        f"a principal is owner or agent, not {principal!r}",
    )
