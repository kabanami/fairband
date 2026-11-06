"""Who makes a write: the identity headers (spec 2026-11-06 Tier 2, section 7).

An agent's write carries ``X-Fairband-Principal: agent``, ``X-Fairband-Actor`` (the model
identifier it runs as, kept exactly as it arrived) and ``X-Fairband-Client`` (its client's name
and version, ``<name>/<version>``, when the client sends one). A request without the principal
header, or with ``owner``, is the owner's: the page and the CLI send none. An agent's write
without an actor is refused 400 with ``IDENTIFY_FIRST``, and any other principal 400: ``system``
is the engine's own writes, which no request makes.
"""

from fastapi import HTTPException, Request

from fairband.store.ledger import OWNER, Writer

PRINCIPAL_HEADER = "X-Fairband-Principal"
ACTOR_HEADER = "X-Fairband-Actor"
CLIENT_HEADER = "X-Fairband-Client"
IDENTIFY_FIRST = "identify first: the model identifier you run as"


def writer_of(request: Request) -> Writer:
    """The request's writer, from its identity headers; a route's dependency."""
    principal = request.headers.get(PRINCIPAL_HEADER)
    if principal is None or principal == "owner":
        return OWNER
    if principal != "agent":
        raise HTTPException(400, f"a principal is owner or agent, not {principal!r}")
    actor = request.headers.get(ACTOR_HEADER, "")
    if not actor.strip():
        raise HTTPException(400, IDENTIFY_FIRST)
    return Writer("agent", actor, request.headers.get(CLIENT_HEADER))
