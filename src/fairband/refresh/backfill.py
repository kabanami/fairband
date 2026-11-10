"""The statement facts backfill: the facts of statement lines the normalizer gained after their
payloads were stored (spec 2026-11-03 section 11).

``backfill_statement_facts`` reads every usable stored response (HTTP 200, no error, a payload) of
the five statement endpoints, of every symbol. A response whose facts already hold every field the
normalizer keeps for its statement (``statement_fields``) is passed over unread. Any other one's
payload is normalized again (``statement_facts``), and the facts of the fields its rows lack are
written, citing the response and its observation time and entered at ``now``, in one transaction
per response. A field already stored keeps its rows and nothing else is touched, so a second run
writes nothing. A payload that does not parse writes nothing. The run logs one INFO line with the
count it wrote.

Every refresh that values runs it first (``run``): a revalue reads only the store, and a full
refresh reuses responses observed within ``reuse_hours`` without a fetch, so a response stored
before a line joined the normalizer has that line's facts only once this has run.
"""

import json
import logging
import sqlite3
from datetime import datetime

from fairband.refresh.fetch import STATEMENT_ENDPOINTS
from fairband.store.facts import fields_stored, insert_facts
from fairband.store.vendor import response_payload, responses_with_payload
from fairband.vendors.normalize_fmp import statement_facts, statement_fields

logger = logging.getLogger("fairband.refresh")


def backfill_statement_facts(conn: sqlite3.Connection, now: datetime) -> int:
    """Write the missing statement facts of every stored statement response; the count written."""
    written = 0
    for response in responses_with_payload(conn, sorted(STATEMENT_ENDPOINTS)):
        missing = statement_fields(response.endpoint) - fields_stored(conn, response.id)
        text = response_payload(conn, response.id) if missing else None
        if text is None or response.symbol is None:
            continue
        try:
            payload = json.loads(text)
        except ValueError:  # a payload that does not parse has no facts to give
            continue
        normalized = statement_facts(
            payload, response.symbol, response.endpoint, response.id, response.observed_at, now
        )
        facts = [fact for fact in normalized if fact.field in missing]
        if facts:
            insert_facts(conn, facts)
            written += len(facts)
    logger.info("statement backfill: %d facts written", written)
    return written
