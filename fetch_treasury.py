"""
Download Treasury par yield curve CSVs for every year that appears in data/deals.csv
and write data/treasury_cmt.csv with the 2/3/5/7-year yields on each pricing date.
Source: U.S. Treasury, Daily Treasury Par Yield Curve Rates.
"""
import csv
import io
import os
import sys

from common import ROOT, fetch

URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
       "daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")
COLS = {"2 Yr": "ust_2y", "3 Yr": "ust_3y", "5 Yr": "ust_5y", "7 Yr": "ust_7y"}


def load_curve(years, offline=False):
    """All daily 2/3/5/7-year par yields for the given years: {YYYY-MM-DD: {ust_2y: ...}}."""
    curve = {}
    for y in sorted(set(years)):
        text = fetch(URL.format(y=y), offline=offline).decode("utf-8-sig")
        for row in csv.DictReader(io.StringIO(text)):
            m, d, yy = row["Date"].split("/")
            curve[f"{yy}-{m}-{d}"] = {v: row[k] for k, v in COLS.items()}
    return curve


def main(offline=False):
    deals = list(csv.DictReader(open(os.path.join(ROOT, "data", "deals.csv"))))
    dates = sorted({r["pricing_date"] for r in deals if r["pricing_date"]})
    years = sorted({d[:4] for d in dates})
    curve = load_curve(years, offline)
    out, missing = [], []
    for d in dates:
        if d in curve:
            out.append({"date": d, **curve[d], "source_url": URL.format(y=d[:4])})
        else:
            missing.append(d)
    with open(os.path.join(ROOT, "data", "treasury_cmt.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "ust_2y", "ust_3y", "ust_5y", "ust_7y", "source_url"])
        w.writeheader()
        w.writerows(out)
    print(f"wrote {len(out)} dates to data/treasury_cmt.csv")
    if missing:
        print("no Treasury curve for (market holiday?):", ", ".join(missing))
        sys.exit(1)


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
