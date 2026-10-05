"""
Task 2 (analysis): spread of each deal relative to the market on the same day,
and the panel comparison by who stands behind the debt (task 3 output feeds it).

Reads output/spreads.csv and data/market_index.csv (from fetch_market.py). Writes:
  output/relative_spreads.csv  spread_bp minus each index (in bp)
  output/pairs.csv             same-week pairs from data/pairs.csv (a minus b)

Groups come from data/deals.csv columns google_backstop, tenant, structure:
  google_backstop       google_backstop == Y
  ig_tenant             tenant contains "investment-grade"
  coreweave_tenant      tenant starts with "CoreWeave" and structure == project
  coreweave_unsecured   issuer CoreWeave and structure == corporate
  other                 anything else
The same-week pairs stay the headline; this table is the check that the
pattern holds after the market control.
"""
import csv
import os
from datetime import date

from common import ROOT

INDEX_FOR_GROUP_TABLE = "bamlh0a0hym2_pct"


def group(deal):
    if deal["google_backstop"] == "Y":
        return "google_backstop"
    if "investment-grade" in deal["tenant"]:
        return "ig_tenant"
    if deal["tenant"].startswith("CoreWeave") and deal["structure"] == "project":
        return "coreweave_tenant"
    if deal["issuer"] == "CoreWeave" and deal["structure"] == "corporate":
        return "coreweave_unsecured"
    return "other"


def main():
    p = lambda *a: os.path.join(ROOT, *a)
    deals = {r["deal_id"]: r for r in csv.DictReader(open(p("data", "deals.csv")))}
    idx = {r["date"]: r for r in csv.DictReader(open(p("data", "market_index.csv")))}
    series = [c for c in next(iter(idx.values())).keys() if c != "date"]
    rows = []
    for s in csv.DictReader(open(p("output", "spreads.csv"))):
        d = deals[s["deal_id"]]
        r = {"deal_id": s["deal_id"], "case": s["case"], "pricing_date": s["pricing_date"],
             "group": group(d), "spread_bp": int(s["spread_bp"])}
        for ser in series:
            v = idx.get(s["pricing_date"], {}).get(ser, "")
            r[f"minus_{ser}_bp"] = r["spread_bp"] - round(float(v) * 100) if v else ""
        rows.append(r)
    with open(p("output", "relative_spreads.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Same-week pairs (data/pairs.csv): the only comparisons that need no market control.
    # The group summary was removed: it mixed deals from different periods.
    by_id = {}
    for r in rows:  # for bounded deals keep the lower bound (the conservative spread)
        if not r["case"].startswith("upper"):
            by_id[r["deal_id"]] = r
    pairs_path = p("data", "pairs.csv")
    out = []
    if os.path.exists(pairs_path):
        for pr in csv.DictReader(open(pairs_path)):
            a, b = by_id.get(pr["deal_a"]), by_id.get(pr["deal_b"])
            if not (a and b):
                print(f'  pair {pr["pair_id"]}: skipped (a deal is not in the verified results)')
                continue
            days = abs((date.fromisoformat(a["pricing_date"]) - date.fromisoformat(b["pricing_date"])).days)
            out.append({"pair_id": pr["pair_id"], "label": pr["label"],
                        "deal_a": a["deal_id"], "date_a": a["pricing_date"], "spread_a_bp": a["spread_bp"],
                        "deal_b": b["deal_id"], "date_b": b["pricing_date"], "spread_b_bp": b["spread_bp"],
                        "a_minus_b_bp": a["spread_bp"] - b["spread_bp"], "days_apart": days,
                        "note": "a is a lower bound" if a["case"].startswith("lower") else ""})
    if out:
        with open(p("output", "pairs.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
        print("same-week pairs (spread over Treasuries; no market control needed):")
        for o in out:
            print(f'  {o["pair_id"]:10s} {o["deal_a"]} {o["spread_a_bp"]} bp  vs  {o["deal_b"]} {o["spread_b_bp"]} bp  '
                  f'-> {o["a_minus_b_bp"]:+d} bp  ({o["days_apart"]} days apart){"  [" + o["note"] + "]" if o["note"] else ""}')


if __name__ == "__main__":
    main()
