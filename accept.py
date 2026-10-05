"""
Copy one reviewed candidate from output/evidence_candidates.csv into
data/evidence.csv, and fill the value in data/deals.csv.

    python3 accept.py --deal APLD_2031B --field maturity_date --value 2031-06-15
    python3 accept.py --deal CRWV_2031A --field pricing_date --value 2026-04-09 --contains "1,750"

Rules
- The candidate must match deal, field and value. --contains narrows it further
  (text that must be in the evidence sentence).
- Exactly one candidate must match. If several match, the script lists them and
  stops; rerun with --index N to choose one.
- If data/deals.csv already has a DIFFERENT value, the script stops.
- A row that is already in data/evidence.csv is not added twice.
- Each accepted command is appended to data/evidence_log.sh, so the record of
  what you accepted can be replayed.
Run find_evidence.py first: each run overwrites output/evidence_candidates.csv.
"""
import argparse
import csv
import os
import shlex
import sys

from common import ROOT
from verify_sources import parse_token


def same_value(field, cand_value, wanted):
    if field.endswith("_date"):
        return cand_value == wanted
    try:
        return abs(float(cand_value) - float(wanted)) < 1e-9
    except ValueError:
        return cand_value == wanted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deal", required=True)
    ap.add_argument("--field", required=True)
    ap.add_argument("--value", required=True)
    ap.add_argument("--contains", default="")
    ap.add_argument("--index", type=int)
    ap.add_argument("--replace", action="store_true",
                    help="overwrite a different value in deals.csv (use when the filing corrects it)")
    a = ap.parse_args()

    cpath = os.path.join(ROOT, "output", "evidence_candidates.csv")
    if not os.path.exists(cpath):
        sys.exit("no output/evidence_candidates.csv: run find_evidence.py first")
    cands = [c for c in csv.DictReader(open(cpath))
             if c["deal_id"] == a.deal and c["field"] == a.field
             and same_value(a.field, c["value"], a.value) and a.contains in c["evidence"]]
    if not cands:
        sys.exit("no matching candidate. Check the value, or rerun find_evidence.py for this deal "
                 "(each run overwrites the candidates file).")
    if len(cands) > 1 and a.index is None:
        for i, c in enumerate(cands):
            print(f"[{i}] {c['source_url']}\n    {c['evidence'][:400]}\n")
        sys.exit("several candidates match: read them and rerun with --index N (or add --contains)")
    c = cands[a.index or 0]

    # the token must parse to the value, as verify_sources.py will require
    parsed = parse_token(a.field, c["token"])
    if parsed is None or not same_value(a.field, str(parsed), a.value):
        sys.exit(f"token {c['token']!r} parses to {parsed!r}, not {a.value!r}")
    value = a.value

    dpath = os.path.join(ROOT, "data", "deals.csv")
    deals = list(csv.DictReader(open(dpath)))
    row = next((r for r in deals if r["deal_id"] == a.deal), None)
    if row is None:
        sys.exit(f"{a.deal} is not in data/deals.csv")
    if a.field in row:
        if row[a.field] and not same_value(a.field, row[a.field], value):
            if not a.replace:
                sys.exit(f"conflict: deals.csv has {row[a.field]!r}, candidate says {value!r}. "
                         f"If the filing is right, rerun with --replace.")
            print(f"replacing {a.deal} {a.field}: {row[a.field]!r} -> {value!r}")
            row[a.field] = ""
            # drop old evidence rows for this field, which now contradict deals.csv
            ep = os.path.join(ROOT, "data", "evidence.csv")
            ev = list(csv.DictReader(open(ep)))
            kept = [e for e in ev if not (e["deal_id"] == a.deal and e["field"] == a.field)]
            if len(kept) != len(ev):
                with open(ep, "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=list(ev[0].keys()))
                    w.writeheader()
                    w.writerows(kept)
                print(f"  removed {len(ev) - len(kept)} old evidence row(s) for that field")
        if not row[a.field]:
            row[a.field] = value
            with open(dpath, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(deals[0].keys()))
                w.writeheader()
                w.writerows(deals)

    epath = os.path.join(ROOT, "data", "evidence.csv")
    existing = list(csv.DictReader(open(epath)))
    new = {"deal_id": a.deal, "field": a.field, "value": value, "token": c["token"],
           "source_url": c["source_url"], "source_type": c["source_type"], "evidence": c["evidence"]}
    if any(all(e[k] == new[k] for k in ("deal_id", "field", "token", "source_url", "evidence")) for e in existing):
        print("already in data/evidence.csv: nothing added")
    else:
        with open(epath, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=list(existing[0].keys())).writerow(new)
        print(f"added: {a.deal} {a.field} = {value}\n  {c['source_url']}\n  {c['evidence'][:300]}")

    with open(os.path.join(ROOT, "data", "evidence_log.sh"), "a") as f:
        f.write("python3 accept.py " + " ".join(shlex.quote(x) for x in sys.argv[1:]) + "\n")


if __name__ == "__main__":
    main()
