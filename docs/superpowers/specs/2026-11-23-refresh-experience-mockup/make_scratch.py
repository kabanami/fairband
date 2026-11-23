"""Makes a scratch database of the whole universe for the look in a browser: the migrations, then,
from the live store opened read-only, the small tables whole, every row of the newest universe
refresh's companies, the newest snapshot of each company and the snapshots its records rest on.
Run it from the repository's root with the scratch folder as its one argument; it writes
<folder>/fairband.db and holds no data itself."""

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, "src")
from fairband.store.db import connect, migrate

LIVE = os.path.expanduser("~/.local/share/fairband/fairband.db")
WHOLE = [
    "policy_versions", "refreshes", "deciles", "settings", "settings_changes", "overrides",
    "reviews", "review_log", "held_reviews", "reports", "judgments", "work_items", "notes",
    "findings", "guidance", "kill_criteria", "news_items", "ledger", "secondary_valuations",
    "sensitivities", "derivations", "launches", "watchlists", "watchlist_entries", "moat_classes",
]  # fmt: skip

out = Path(sys.argv[1]) / "fairband.db"
out.parent.mkdir(parents=True, exist_ok=True)
if out.exists():
    out.unlink()
conn = connect(out)
migrate(conn)
conn.close()
c = sqlite3.connect(f"file:{out}", uri=True)
c.execute(f"ATTACH 'file:{LIVE}?mode=ro' AS live")
for table in WHOLE:
    c.execute(f"INSERT INTO main.{table} SELECT * FROM live.{table}")
c.execute(
    "INSERT INTO main.companies SELECT * FROM live.companies"
    " WHERE refresh_id = (SELECT MAX(refresh_id) FROM live.companies)"
)
c.execute(
    "INSERT INTO main.snapshots SELECT * FROM live.snapshots WHERE id IN"
    " (SELECT MAX(id) FROM live.snapshots WHERE symbol IN (SELECT symbol FROM main.companies)"
    " GROUP BY symbol)"
    " OR id IN (SELECT snapshot_id FROM live.reviews UNION SELECT snapshot_id FROM live.reports"
    " UNION SELECT snapshot_id FROM live.secondary_valuations)"
)
c.commit()
print(
    "companies", c.execute("SELECT COUNT(*) FROM main.companies").fetchone()[0],
    "snapshots", c.execute("SELECT COUNT(*) FROM main.snapshots").fetchone()[0],
)  # fmt: skip
