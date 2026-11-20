import os, sqlite3, sys
from pathlib import Path
sys.path.insert(0, "src")
from fairband.store.db import connect, migrate
live = os.path.expanduser("~/.local/share/fairband/fairband.db")
out = Path(sys.argv[1]) / "fairband.db"
if out.exists():
    out.unlink()
conn = connect(out); migrate(conn); conn.close()
c = sqlite3.connect(f"file:{out}", uri=True)
c.execute(f"ATTACH 'file:{live}?mode=ro' AS live")
whole = ["policy_versions","refreshes","deciles","settings","settings_changes","overrides","reviews","review_log","reports","judgments","work_items","notes","findings","guidance","kill_criteria","news_items","ledger","secondary_valuations","sensitivities","derivations","launches","watchlists","watchlist_entries"]
for t in whole:
    c.execute(f"INSERT INTO main.{t} SELECT * FROM live.{t}")
syms = ["AAPL","MSFT","KO","PG","NVDA","WMT","NVO","CRM","TTMI","AMZN","CX","RELX","V","GDS","FRVO","JNJ","SIMO","GPC","APD","TSLA","COST","HD"]
q = ",".join("?" * len(syms))
c.execute(f"INSERT INTO main.companies SELECT * FROM live.companies WHERE refresh_id=68 AND symbol IN ({q})", syms)
c.execute(f"INSERT INTO main.snapshots SELECT * FROM live.snapshots WHERE id IN (SELECT max(id) FROM live.snapshots WHERE symbol IN ({q}) GROUP BY symbol) OR id IN (SELECT snapshot_id FROM live.reports WHERE symbol IN ({q}) UNION SELECT snapshot_id FROM live.reviews WHERE symbol IN ({q}))", syms * 3)
c.execute(f"INSERT INTO main.vendor_responses SELECT * FROM live.vendor_responses WHERE id IN (SELECT max(id) FROM live.vendor_responses WHERE provider='fmp' AND endpoint='profile' AND symbol IN ({q}) GROUP BY symbol)", syms)
c.execute(f"INSERT INTO main.refresh_items SELECT * FROM live.refresh_items WHERE refresh_id=68 AND symbol IN ({q})", syms)
c.execute(f"INSERT INTO main.observations SELECT * FROM live.observations WHERE dataset='profile' AND symbol IN ({q})", syms)
c.execute(f"INSERT INTO main.multiples_log SELECT * FROM live.multiples_log WHERE symbol IN ({q})", syms)
c.commit()
print("snapshots", c.execute("select count(*) from main.snapshots").fetchone(), "companies", c.execute("select count(*) from main.companies").fetchone())
