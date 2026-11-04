"""The store: one SQLite database. The record of what was fetched and valued is appended to and
never deleted from; the user's settings and watchlists are the user's to change and delete.

``fairband.store.db`` opens the connection and applies the numbered migrations in ``migrations/``.
Numbers are stored as decimal text, dates and timestamps as ISO text, ids and flags as integers.
One record module per table group (``companies``, ``vendor``, ``facts``, ``observations``,
``snapshots``, ``refreshes``, ``policy``, and the user's ``settings`` and ``watchlists``) writes
and reads its rows. Each write is one transaction, or joins the caller's
(``fairband.store.db.transaction``).
"""
