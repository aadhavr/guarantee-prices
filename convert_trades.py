"""
Convert a raw FINRA trade file (from finra_console_scraper.js) into
data/bond_trades/<deal_id>.csv and record its provenance.

    python3 convert_trades.py data/bond_trades/raw/APLD_2030_finra_raw.json --cusip 00202DAA5

Checks
- Every page except the last must have exactly `limit` records (no missing page).
- Identical rows are kept (they are separate trades). --expected-total checks the
  count against FINRA's Total Count; the end date must be before the run date.
- Trades must fall inside the requested date range.
- Date, price and quantity fields are detected by name; if detection is not
  certain, the script lists the fields and stops. Then pass --date-field,
  --price-field, --qty-field.

Provenance: SHA-256 of the raw file AND of the converted CSV are written to
data/bond_trades/provenance.csv. bond_event_study.py and spread_timeseries.py
check the CSV hash; the raw hash lets anyone rebuild the CSV from the raw file.
Keep raw files out of the public repository (FINRA user agreement): publish
the hashes, the CUSIPs and the date range instead.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime

from common import ROOT

DATE_KEYS = ["tradeExecutionDate", "executionDate", "tradeDate", "date"]
PRICE_KEYS = ["lastSalePrice", "price", "tradePrice", "reportedPrice", "salePrice"]
QTY_KEYS = ["reportedTradeVolume", "tradeQuantity", "quantity", "volume", "size", "tradeVolume"]


def pick(keys, candidates, override, what):
    if override:
        if override not in keys:
            sys.exit(f"--{what}-field {override!r} is not in the records. Fields: {sorted(keys)}")
        return override
    found = [k for k in candidates if k in keys]
    if not found:  # try a case-insensitive contains match
        found = [k for k in keys if any(c.lower() in k.lower() for c in candidates)]
    if len(found) != 1:
        sys.exit(f"cannot choose the {what} field (candidates found: {found}).\n"
                 f"Fields in the records: {sorted(keys)}\nRerun with --{what}-field NAME.")
    return found[0]


def parse_date(v):
    v = str(v).strip()[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_qty(v):
    """FINRA caps disseminated sizes, e.g. '1MM+' or '5MM+'. Returns (number, capped)."""
    if v is None or v == "":
        return None, False
    s = str(v).replace(",", "").replace("$", "").strip().upper()
    capped = s.endswith("+")
    s = s.rstrip("+")
    mult = 1
    if s.endswith("MM"):
        mult, s = 1_000_000, s[:-2]
    elif s.endswith("M"):
        mult, s = 1_000, s[:-1]
    try:
        return float(s) * mult, capped
    except ValueError:
        return None, capped


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--cusip", required=True)
    ap.add_argument("--deal", help="deal_id (default: from the raw file)")
    ap.add_argument("--date-field")
    ap.add_argument("--price-field")
    ap.add_argument("--qty-field")
    ap.add_argument("--expected-total", type=int, help="the Total Count shown on the FINRA page")
    ap.add_argument("--symbol", help="the FINRA symbol shown on the bond page, e.g. CRWV6424531")
    a = ap.parse_args()

    raw = json.load(open(a.raw))
    deal = a.deal or raw.get("deal_id")
    if not deal:
        sys.exit("no deal_id in the raw file: pass --deal")
    recs = raw["records"]
    if not recs:
        sys.exit("the raw file has no records")
    body = raw.get("request_body_first_page", {})
    limit = body.get("limit", 50)

    # 1. page check
    pages = raw.get("pages", [])
    for i, pg in enumerate(pages[:-1]):
        if pg["count"] != limit:
            sys.exit(f"page {i} (offset {pg['offset']}) has {pg['count']} records, not {limit}: "
                     f"a page is incomplete. Run the scraper again.")
    for i, pg in enumerate(pages):
        if pg["offset"] != i * limit:
            sys.exit(f"page {i} has offset {pg['offset']}, expected {i * limit}: pages are not consecutive")

    # 1b. which bond is in the file? (catches a request body copied from another bond)
    syms = sorted({str(r.get("issueSymbolIdentifier", "")) for r in recs} - {""})
    asked = next((f.get("fieldValue") for f in body.get("compareFilters", [])
                  if f.get("fieldName") == "issueSymbolIdentifier"), None)
    print(f"symbol requested: {asked}   symbols in records: {', '.join(syms) or 'none'}")
    if len(syms) > 1:
        sys.exit("the file has trades of more than one bond: run the scraper again")
    if a.symbol and (syms and syms[0] != a.symbol or asked and asked != a.symbol):
        sys.exit(f"this file is for {syms[0] if syms else asked}, not {a.symbol}: copy the request body "
                 f"from the right bond page and run the scraper again")

    # 2. fields
    keys = set().union(*(r.keys() for r in recs))
    fd = pick(keys, DATE_KEYS, a.date_field, "date")
    fp = pick(keys, PRICE_KEYS, a.price_field, "price")
    fq = pick(keys, QTY_KEYS, a.qty_field, "qty")
    print(f"fields: date={fd}  price={fp}  quantity={fq}")

    # 3. completeness. Identical rows are NOT removed: FINRA shows separate trades with the
    # same time, size and price as separate rows. Duplicates between pages can only appear
    # if new trades arrive during the run, so the end date must be before the run date,
    # and the number of records must equal FINRA's "Total Count".
    uniq = recs
    hi_req = next((f.get("endDate") for f in body.get("dateRangeFilters", []) if f.get("fieldName") == fd), None)
    run_day = str(raw.get("collected_at", ""))[:10]
    if hi_req and run_day and hi_req[:10] >= run_day:
        print(f"WARNING: the end date {hi_req[:10]} is not before the run date {run_day}; trades that arrived "
              f"during the run can shift pages. Set the End Date to yesterday and run again.")
    if a.expected_total is not None and len(recs) != a.expected_total:
        sys.exit(f"{len(recs)} records, but FINRA's Total Count was {a.expected_total}: run the scraper again")
    same = len(recs) - len({json.dumps(r, sort_keys=True) for r in recs})

    # 4. convert and check dates
    lo = hi = None
    for f in body.get("dateRangeFilters", []):
        if f.get("fieldName") == fd:
            lo, hi = f.get("startDate"), f.get("endDate")
    rows, bad, capped = [], 0, 0
    for r in uniq:
        d = parse_date(r.get(fd))
        try:
            p = float(str(r.get(fp)).replace("$", "").replace(",", ""))
        except ValueError:
            p = None
        q, c = parse_qty(r.get(fq))
        if d is None or p is None:
            bad += 1
            continue
        capped += c
        rows.append({"trade_date": d, "price": p, "quantity": q if q is not None else ""})
    rows.sort(key=lambda x: x["trade_date"])
    if lo and rows and rows[0]["trade_date"] < lo[:10]:
        sys.exit(f"a trade on {rows[0]['trade_date']} is before the requested start {lo}")
    if hi and rows and rows[-1]["trade_date"] > hi[:10]:
        sys.exit(f"a trade on {rows[-1]['trade_date']} is after the requested end {hi}")

    folder = os.path.join(ROOT, "data", "bond_trades")
    out = os.path.join(folder, f"{deal}.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["trade_date", "price", "quantity"])
        w.writeheader()
        w.writerows(rows)

    prov = os.path.join(folder, "provenance.csv")
    old = [r for r in csv.DictReader(open(prov)) if r["deal_id"] != deal] if os.path.exists(prov) else []
    source = (f"FINRA bond page trade history via finra_console_scraper.js; symbol {syms[0] if syms else '?'}; "
              f"collected {raw.get('collected_at', '?')}; "
              f"requested {lo or '?'} to {hi or '?'}; {len(pages)} pages; raw file {os.path.basename(a.raw)} "
              f"sha256 {sha(a.raw)}")
    old.append({"deal_id": deal, "cusip": a.cusip, "source": source,
                "export_date": date.today().isoformat(), "sha256": sha(out)})
    with open(prov, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["deal_id", "cusip", "source", "export_date", "sha256"])
        w.writeheader()
        w.writerows(old)

    print(f"{len(recs)} records ({same} identical to another row, kept as separate trades), {bad} without date or price skipped")
    print(f"{len(rows)} trades from {rows[0]['trade_date']} to {rows[-1]['trade_date']} -> {out}")
    if capped:
        print(f"note: {capped} trades have a capped size (e.g. '1MM+'); their weight in the daily average is the cap")
    print("provenance recorded (raw and CSV hashes)")


if __name__ == "__main__":
    main()
