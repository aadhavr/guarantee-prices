"""
Task 2: market control. Download high-yield option-adjusted spread indexes from
FRED and write data/market_index.csv with the value on each pricing date.

Default series (ICE BofA indexes on FRED, in percent):
  BAMLH0A0HYM2  US High Yield OAS (all ratings)
  BAMLH0A1HYBB  US BB OAS
  BAMLH0A2HYB   US B OAS

LICENSE: FRED shows ICE BofA data with a copyright notice from ICE Data Indices
that limits reproduction. Check the notes on each FRED series page before you
publish. This script downloads the data at run time, and .gitignore keeps the
file out of the repository, so readers download it themselves. Publish derived
numbers (a bond's spread minus the index), not the index series.

Usage: python fetch_market.py [--series BAMLH0A0HYM2,BAMLH0A1HYBB] [--offline]
"""
import argparse
import csv
import io
import os
import sys

from common import ROOT, fetch

DEFAULT = "BAMLH0A0HYM2,BAMLH0A1HYBB,BAMLH0A2HYB"
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}"


def load(series, offline):
    text = fetch(URL.format(s=series), offline).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    date_col = "observation_date" if "observation_date" in rows[0] else "DATE"
    return {r[date_col]: float(r[series]) for r in rows if r[series] not in (".", "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default=DEFAULT)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    series = a.series.split(",")
    deals = list(csv.DictReader(open(os.path.join(ROOT, "data", "deals.csv"))))
    events_path = os.path.join(ROOT, "data", "events.csv")
    dates = {r["pricing_date"] for r in deals if r["pricing_date"]}
    if os.path.exists(events_path):
        dates |= {r["event_date"] for r in csv.DictReader(open(events_path))}
    data = {s: load(s, a.offline) for s in series}
    out, missing = [], []
    for d in sorted(dates):
        row = {"date": d}
        for s in series:
            if d not in data[s]:
                missing.append(f"{s} {d}")
            row[s.lower() + "_pct"] = data[s].get(d, "")
        out.append(row)
    with open(os.path.join(ROOT, "data", "market_index.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"wrote {len(out)} dates to data/market_index.csv")
    if missing:
        print("missing (holiday or series gap):", ", ".join(missing))
        sys.exit(1)


if __name__ == "__main__":
    main()
