"""
Check every value in data/deals.csv that the analysis uses.

For each row of data/evidence.csv:
  1. the evidence text appears in the downloaded source (after normalization);
  2. the token appears in the evidence text;
  3. the token parses to the value, and the value equals the field in data/deals.csv.
Writes output/verification.csv. Exit code 1 if any evidence row fails.
Fields that the analysis needs but that have no evidence row are listed as MISSING.
"""
import csv
import os
import re
import sys
from datetime import datetime

from common import ROOT, fetch, normalize

MONTHS = "%B %d, %Y", "%b. %d, %Y", "%b %d, %Y", "%m/%d/%Y"
NEEDED = {
    "fixed": ["pricing_date", "coupon_pct", "issue_price", "maturity_date"],
    "floating": ["pricing_date", "sofr_spread_bp"],
}


def parse_token(field, token):
    t = token.strip()
    if field.endswith("_date"):
        for fmt in MONTHS:
            try:
                return datetime.strptime(t, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
        return None
    if field in ("coupon_pct", "issue_price", "sofr_spread_bp"):
        if t.lower() == "par":
            return 100.0
        m = re.fullmatch(r"\$?([\d,]+(?:\.\d+)?)%?", t)
        if not m:
            return None
        x = float(m.group(1).replace(",", ""))
        if field == "sofr_spread_bp" and t.endswith("%"):
            x = round(x * 100, 6)  # filings state margins in percent; deals.csv stores bp
        return x
    return t  # text fields: token presence is the check


def same(field, a, b):
    if isinstance(a, float):
        try:
            return abs(a - float(b)) < 1e-9
        except ValueError:
            return False
    if field.endswith("_date"):
        return a == b
    return True  # text fields


def main(offline=False):
    deals = {r["deal_id"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "deals.csv")))}
    ev = list(csv.DictReader(open(os.path.join(ROOT, "data", "evidence.csv"))))
    docs, out, fails = {}, [], 0
    for r in ev:
        status, detail = "PASS", ""
        try:
            if r["source_url"] not in docs:
                docs[r["source_url"]] = normalize(fetch(r["source_url"], offline).decode("utf-8", "replace"))
            doc, evid = docs[r["source_url"]], normalize(r["evidence"])
            if evid not in doc:
                status, detail = "FAIL", "evidence text not found in source"
            elif normalize(r["token"]) not in evid:
                status, detail = "FAIL", "token not in evidence"
            else:
                parsed = parse_token(r["field"], r["token"])
                if parsed is None or not same(r["field"], parsed, r["value"]):
                    status, detail = "FAIL", f"token parses to {parsed!r}, value is {r['value']!r}"
                elif r["field"] in deals[r["deal_id"]] and r["field"] not in ("tenant", "support") \
                        and deals[r["deal_id"]][r["field"]] != r["value"]:
                    status, detail = "FAIL", f"deals.csv has {deals[r['deal_id']][r['field']]!r}"
        except Exception as e:  # download or cache problem
            status, detail = "ERROR", str(e)[:200]
        fails += status != "PASS"
        out.append({"deal_id": r["deal_id"], "field": r["field"], "value": r["value"],
                    "status": status, "detail": detail, "source_url": r["source_url"]})

    have = {(r["deal_id"], r["field"]) for r in ev}
    for d in deals.values():
        if d["include"] != "Y":
            continue
        need = list(NEEDED[d["rate_type"]])
        for f in need:
            if (d["deal_id"], f) not in have:
                out.append({"deal_id": d["deal_id"], "field": f, "value": d.get(f, ""),
                            "status": "MISSING", "detail": "no evidence row", "source_url": ""})

    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    with open(os.path.join(ROOT, "output", "verification.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    counts = {}
    for o in out:
        counts[o["status"]] = counts.get(o["status"], 0) + 1
    print("verification:", counts)
    for o in out:
        if o["status"] in ("FAIL", "ERROR"):
            print(f'  {o["status"]:5s} {o["deal_id"]:15s} {o["field"]:16s} {o["detail"]}')
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
