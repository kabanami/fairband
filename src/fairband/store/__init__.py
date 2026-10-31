"""The store: one SQLite database, appended to and never deleted from.

``fairband.store.db`` opens the connection and applies the numbered migrations in ``migrations/``.
Numbers are stored as decimal text, dates and timestamps as ISO text, ids and flags as integers.
"""
