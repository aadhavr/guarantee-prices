"""
Task 3: find more financings of AI data centers and GPU fleets in SEC filings.

Uses EDGAR full-text search (8-K filings, main documents and exhibits), then
downloads each hit and extracts candidate terms from sentences that price or
close a note or loan. Output: output/candidate_deals.csv, for YOU to review.
Nothing is added to data/deals.csv automatically: add a deal by hand, then use
evidence_helper.py for each value.

    python3 search_deals.py --start 2025-01-01 --end 2026-09-30
"""
import argparse
import csv
import os
import re
import sys
import urllib.parse

from common import ROOT, fetch, normalize, sec_json, sentences

QUERIES = [
    '"senior secured notes" "data center" "priced"',
    '"senior secured notes" "high-performance computing" "priced"',
    '"senior secured notes" "HPC" "colocation"',
    '"delayed draw term loan" "GPU"',
    '"term loan" "GPU" "data center" "SOFR"',
    '"Fluidstack" "notes"',
    '"CoreWeave" "senior secured notes"',
    '"backstop" "lease obligations" "notes"',
]
EFTS = "https://efts.sec.gov/LATEST/search-index?q={q}&forms=8-K&dateRange=custom&startdt={s}&enddt={e}&from={f}"

COUPON = r"(\d{1,2}\.\d{2,3})% [Ss]enior (?:[Ss]ecured )?[Nn]otes due (\d{4})"
PRICE = r"(?:issue price (?:equal to |of )?|at a price equal to |issued at )(\d{2,3}(?:\.\d+)?%|par)"
SIZE = r"\$([\d.,]+) (billion|million)"
SOFR = r"SOFR,?\s*(?:\+|plus)\s*(\d\.\d{2})%"
KEY = re.compile(r"\b(priced|pricing|completed|closed|entered into)\b", re.I)


def hits(query, start, end, offline):
    out, frm = [], 0
    while True:
        url = EFTS.format(q=urllib.parse.quote(query), s=start, e=end, f=frm)
        data = sec_json(url, offline)
        page = data.get("hits", {}).get("hits", [])
        for h in page:
            src = h.get("_source", {})
            adsh, _, fname = h.get("_id", "").partition(":")
            ciks = src.get("ciks") or [""]
            if not (adsh and fname and ciks[0]):
                continue
            folder = f"https://www.sec.gov/Archives/edgar/data/{int(ciks[0])}/{adsh.replace('-', '')}/"
            out.append({"company": (src.get("display_names") or [""])[0], "cik": int(ciks[0]),
                        "file_date": src.get("file_date", ""), "url": folder + fname})
        total = data.get("hits", {}).get("total", {}).get("value", 0)
        frm += len(page)
        if not page or frm >= total or frm >= 1000:
            return out


def extract(url, offline):
    text = normalize(fetch(url, offline).decode("utf-8", "replace"))
    rows = []
    for s in sentences(text):
        if not KEY.search(s):
            continue
        c, sofr = re.search(COUPON, s), re.search(SOFR, s)
        if not (c or sofr):
            continue
        p, z = re.search(PRICE, s), re.search(SIZE, s)
        rows.append({"coupon_pct": c.group(1) if c else "", "due_year": c.group(2) if c else "",
                     "sofr_margin_pct": sofr.group(1) if sofr else "",
                     "issue_price": p.group(1) if p else "",
                     "size": f"${z.group(1)} {z.group(2)}" if z else "", "sentence": s[:600]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()

    known = {(r["issuer"].lower(), r["coupon_pct"]) for r in csv.DictReader(open(os.path.join(ROOT, "data", "deals.csv")))}
    docs = {}
    for q in QUERIES:
        try:
            for h in hits(q, a.start, a.end, a.offline):
                docs.setdefault(h["url"], {**h, "queries": set()})["queries"].add(q)
        except Exception as e:
            print(f"search failed for {q}: {e}", file=sys.stderr)
    print(f"{len(docs)} documents matched")

    out = []
    for url, h in sorted(docs.items(), key=lambda kv: kv[1]["file_date"]):
        try:
            for x in extract(url, a.offline):
                issuer_known = any(h["company"].lower().startswith(k[0].split()[0]) and x["coupon_pct"] and
                                   abs(float(x["coupon_pct"]) - float(k[1] or 0)) < 1e-9 for k in known)
                out.append({"file_date": h["file_date"], "company": h["company"], "already_in_panel": "Y" if issuer_known else "",
                            **x, "url": url, "queries": " | ".join(sorted(h["queries"]))})
        except Exception as e:
            print(f"skip {url}: {e}", file=sys.stderr)

    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    path = os.path.join(ROOT, "output", "candidate_deals.csv")
    if out:
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
    new = sum(1 for o in out if not o["already_in_panel"])
    print(f"{len(out)} candidate sentences ({new} not yet in the panel) -> output/candidate_deals.csv")
    print("Review by hand. Exclude convertibles, refinancings of old debt, and deals with no AI data center or GPU use of proceeds.")


if __name__ == "__main__":
    main()
