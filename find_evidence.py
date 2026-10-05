"""
Task 1: find evidence for values that verify_sources.py reports as MISSING or FAIL.

For each open (deal, field), search the issuer's 8-K, 10-Q and 10-K filings in a
window around the pricing date. Only sentences that mention the security's
coupon (for example "7.000%") are considered, so a match belongs to the right
notes. Each candidate is written in the same format as data/evidence.csv.

Nothing is added to data/evidence.csv automatically. Read output/evidence_candidates.csv,
open the source to confirm, copy the correct row into data/evidence.csv, put the
value into data/deals.csv, and rerun ./run_all.sh.

Usage:
  python find_evidence.py                     # all open items from output/verification.csv
  python find_evidence.py --deal APLD_2031B   # one deal
  python find_evidence.py --months 6          # window after pricing date (default 4)
"""
import argparse
import csv
import os
import re
from datetime import date, timedelta

from common import ROOT, fetch, filing_documents, filings, normalize, sentences, ticker_to_cik
from verify_sources import NEEDED

MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = rf"{MONTH} \d{{1,2}}, \d{{4}}"
PATTERNS = {
    "maturity_date": [rf"(?:will mature|mature|maturity date)[^.]{{0,40}}?(?:on|of) ({DATE})",
                      rf"Stated Maturity[^.]{{0,120}}?({DATE})",
                      rf"promises to pay[^.]{{0,300}}?on ({DATE})"],
    "first_amort_date": [rf"amortiz[^.]{{0,200}}?beginning on ({DATE})"],
    "issue_price": [r"issue price (?:of|equal to) (\d{2,3}(?:\.\d+)?%)",
                    r"issued at a price equal to (\d{2,3}(?:\.\d+)?%)",
                    r"at a price (?:of|equal to) (\d{2,3}(?:\.\d+)?%)",
                    r"\b(?:at|issued at) (par)\b"],
    "pricing_date": [rf"(?:On|on) ({DATE})[^.]{{0,300}}?\bpric(?:ed|ing)\b",
                     rf"purchase agreement,? dated (?:as of )?({DATE})"],
    "coupon_pct": [r"(\d{1,2}\.\d{2,3}%) (?:[Ss]enior )?(?:[Ss]ecured )?[Nn]otes due"],
    "sofr_spread_bp": [r"SOFR\)?\s*(?:plus|\+)\s*(\d(?:\.\d+)?%)", r"SOFR[^.]{0,40}?margin of (\d(?:\.\d+)?%)"],
}


def open_items(deals, only):
    """Required fields without a PASS in output/verification.csv."""
    path = os.path.join(ROOT, "output", "verification.csv")
    passed = set()
    if os.path.exists(path):
        passed = {(v["deal_id"], v["field"]) for v in csv.DictReader(open(path)) if v["status"] == "PASS"}
    ev_path = os.path.join(ROOT, "data", "events.csv")
    event_bonds = set()
    if os.path.exists(ev_path):
        for e in csv.DictReader(open(ev_path)):
            event_bonds |= {e["treated"], e["control"]}
    items = []
    for d in deals:
        in_scope = d["include"] == "Y" or d["deal_id"] in event_bonds
        if not in_scope or (only and d["deal_id"] != only) or not d["ticker"]:
            continue
        need = list(NEEDED[d["rate_type"]])
        # same rule as spreads.py: the date only matters for amortizing notes issued below par
        if d["amortizing"] == "Y" and d["issue_price"] and float(d["issue_price"]) != 100:
            need.append("first_amort_date")
        items += [(d, f) for f in need if (d["deal_id"], f) not in passed]
    return items


def parse_value(field, token):
    from verify_sources import parse_token
    return parse_token(field, token)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deal")
    ap.add_argument("--months", type=int, default=4)
    ap.add_argument("--start", help="first filing date to search (YYYY-MM-DD); use for deals with no pricing date")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()

    deals = list(csv.DictReader(open(os.path.join(ROOT, "data", "deals.csv"))))
    items = open_items(deals, a.deal)
    if not items:
        print("no open items")
        return
    out = []
    by_deal = {}
    for d, f in items:
        by_deal.setdefault(d["deal_id"], (d, []))[1].append(f)

    for deal_id, (d, fields) in by_deal.items():
        cik = ticker_to_cik(d["ticker"], a.offline)
        if d["coupon_pct"]:
            anchor = f'{float(d["coupon_pct"]):.3f}%'
            variants = {anchor, f'{float(d["coupon_pct"]):.2f}%'}
        elif d["rate_type"] == "floating" and "DDTL" in d["security"]:
            anchor = d["security"].split(" delayed")[0]          # e.g. "DDTL 4.0"
            variants = {anchor}
        else:
            anchor = None
            variants = set()
        start = a.start or d["pricing_date"] or "2025-01-01"
        end_dt = date.fromisoformat(start) + timedelta(days=31 * a.months)
        start_dt = date.fromisoformat(start) - timedelta(days=0 if a.start else 10)
        fl = filings(cik, start=start_dt.isoformat(), end=end_dt.isoformat(), offline=a.offline)
        print(f"{deal_id}: {len(fl)} filings, looking for {', '.join(fields)} (anchor {anchor})")
        for filing in fl:
            try:
                urls = filing_documents(cik, filing["acc"], a.offline)
            except Exception as e:
                print("   skip", filing["acc"], e)
                continue
            print(f'   {filing["date"]} {filing["form"]:6s} {len(urls)} documents', flush=True)
            # does ANY document of this filing name the security? (the coupon is often in
            # the press-release exhibit while the date is on the cover of the main document)
            filing_anchored = False
            for u in urls:
                try:
                    t = normalize(fetch(u, a.offline).decode("utf-8", "replace"))
                except Exception:
                    continue
                if anchor is not None and any(v in t for v in variants):
                    filing_anchored = True
                    break
            for url in urls:
                try:
                    text = normalize(fetch(url, a.offline).decode("utf-8", "replace"))
                except Exception as e:
                    print("   skip", url, e)
                    continue
                doc_anchored = anchor is None or any(v in text for v in variants)
                # an indenture (exhibit 4.x) is about one security, so a maturity sentence
                # there does not need the coupon in the same sentence
                is_indenture = "ex4" in url.lower() or "exhibit4" in url.lower()
                is_8k = filing["form"].startswith("8-K")
                # 8-K cover: "Date of Report (Date of earliest event reported): April 9, 2026".
                # The cover is not a sentence, so search the text; the evidence is the
                # exact text around the match (a substring of the source).
                if "pricing_date" in fields and is_8k and filing_anchored:
                    m = re.search(rf"[Ee]arliest [Ee]vent [Rr]eported\)?\W{{0,5}}({DATE})", text)
                    if m:
                        tok = m.group(1)
                        out.append({"deal_id": deal_id, "field": "pricing_date", "value": parse_value("pricing_date", tok),
                                    "token": tok, "source_url": url,
                                    "source_type": f'SEC {filing["form"]} cover ({filing["date"]}): check that this 8-K announces the pricing',
                                    "evidence": text[max(0, m.start() - 40):m.end()]})
                for s in sentences(text):
                    if len(s) > 700:
                        continue
                    # never take a sentence about a different kind of security
                    if "convertible" in s.lower() and "convertible" not in d["security"].lower():
                        continue
                    anchored = anchor is None or any(v in s for v in variants)
                    for f in fields:
                        # a pricing date sentence often says "the Notes" without the coupon:
                        # accept it if the same document names the security
                        ok = anchored or (doc_anchored and (f == "pricing_date" or
                                                            (f == "maturity_date" and is_indenture) or
                                                            (f in ("sofr_spread_bp", "issue_price") and is_8k)))
                        if not ok:
                            continue
                        for pat in PATTERNS[f]:
                            m = re.search(pat, s)
                            if m:
                                tok = m.group(1)
                                out.append({"deal_id": deal_id, "field": f,
                                            "value": parse_value(f, tok), "token": tok,
                                            "source_url": url, "source_type": f'SEC {filing["form"]} ({filing["date"]})',
                                            "evidence": s})
                                break
    seen, uniq = set(), []
    for o in out:
        k = (o["deal_id"], o["field"], o["token"], o["evidence"])
        if k not in seen:
            seen.add(k)
            uniq.append(o)
    path = os.path.join(ROOT, "output", "evidence_candidates.csv")
    # keep candidates of deals that this run did not search
    if os.path.exists(path):
        searched = set(by_deal)
        uniq = [r for r in csv.DictReader(open(path)) if r["deal_id"] not in searched] + uniq
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["deal_id", "field", "value", "token", "source_url", "source_type", "evidence"])
        w.writeheader()
        w.writerows(uniq)
    print(f"\n{len(uniq)} candidates written to output/evidence_candidates.csv (review before use)")
    for deal_id, (d, fields) in by_deal.items():
        for f in fields:
            vals = sorted({str(o["value"]) for o in uniq if o["deal_id"] == deal_id and o["field"] == f})
            opt = " (optional: without it only the lower bound is reported)" if f == "first_amort_date" else ""
            print(f"  {deal_id:15s} {f:16s} {'; '.join(vals) if vals else 'NOT FOUND'}{opt}")


if __name__ == "__main__":
    main()
