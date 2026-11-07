"""The web tests' fixtures, shared with the MCP tests from ``support.web_app``: the packaged
policy, the engine's three test companies valued under it (AAPL, AAL and HGCO), a migrated
database that lists them in the universe of one finished full refresh, clients of an app over
that database, and a secondary valuation on each company's snapshot for the tests that submit a
report."""

from support.web_app import (  # noqa: F401
    client,
    client_with_clock,
    db_path,
    policy,
    results,
    secondaries,
)
