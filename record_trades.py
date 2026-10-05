"""
Record where a hand-exported trade file came from, with its SHA-256.
    python3 record_trades.py APLD_2030 <CUSIP> "FINRA Fixed Income Data, bond trade history page"
Run this once, right after you save data/bond_trades/<deal_id>.csv. The event
study refuses any trade file that changed after it was recorded.
"""
import csv
import hashlib
import os
import sys
from datetime import date

from common import ROOT

deal_id, cusip, source = sys.argv[1], sys.argv[2], sys.argv[3]
folder = os.path.join(ROOT, "data", "bond_trades")
path = os.path.join(folder, f"{deal_id}.csv")
header = next(csv.reader(open(path)))
for col in ("trade_date", "price"):
    if col not in header:
        sys.exit(f"{path} needs columns trade_date (YYYY-MM-DD) and price; optional quantity")
digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
prov = os.path.join(folder, "provenance.csv")
rows = [r for r in csv.DictReader(open(prov)) if r["deal_id"] != deal_id]
rows.append({"deal_id": deal_id, "cusip": cusip, "source": source,
             "export_date": date.today().isoformat(), "sha256": digest})
with open(prov, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["deal_id", "cusip", "source", "export_date", "sha256"])
    w.writeheader()
    w.writerows(rows)
print(f"recorded {deal_id} ({cusip}) sha256 {digest[:12]}...")
