"""The web tests' fixtures, shared with the MCP tests from ``support.web_app``: the packaged
policy, the engine's three test companies valued under it (AAPL, AAL and HGCO), a migrated
database that lists them in the universe of one finished full refresh, and clients of an app over
that database."""

from support.web_app import client, client_with_clock, db_path, policy, results  # noqa: F401
