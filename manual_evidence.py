"""
Manual evidence, for values that find_evidence.py cannot reach.

Show text around a pattern in a source (downloads it once, then uses the cache):
    python3 manual_evidence.py show URL "Building 4"
    python3 manual_evidence.py show URL "June \\d{1,2}, 2026|Jun \\d{1,2}, 2026|06/\\d\\d/2026"

Add one evidence row after you read the text:
    python3 manual_evidence.py add --deal CRWV_2032_USD --field pricing_date --value 2026-06-11 \
        --token "June 11, 2026" --url URL --source-type "company press release" \
        --evidence "exact text copied from the show output"

'add' applies the same checks as verify_sources.py before it writes: the evidence
must be in the source, the token must be in the evidence, and the token must parse
to the value. It also fills deals.csv if the field is blank, stops on a conflict,
and logs the command to data/evidence_log.sh.
"""
import argparse
import csv
import os
import re
import shlex
import sys

from common import ROOT, fetch, normalize
from verify_sources import parse_token


def show(url, pattern, width):
    text = normalize(fetch(url).decode("utf-8", "replace"))
    n = 0
    for m in re.finditer(pattern, text):
        n += 1
        print(f"[{n}] ...{text[max(0, m.start() - width):m.end() + width]}...\n")
    print(f"{n} matches" if n else "no match")


def add(a):
    text = normalize(fetch(a.url).decode("utf-8", "replace"))
    evid = normalize(a.evidence)
    if evid not in text:
        sys.exit("evidence text is not in the source: copy it exactly from the 'show' output")
    if normalize(a.token) not in evid:
        sys.exit("token is not in the evidence text")
    parsed = parse_token(a.field, a.token)
    if parsed is None:
        sys.exit(f"token {a.token!r} does not parse for {a.field}")
    if isinstance(parsed, float):
        if abs(parsed - float(a.value)) > 1e-9:
            sys.exit(f"token parses to {parsed}, not {a.value}")
    elif a.field.endswith("_date") and parsed != a.value:
        sys.exit(f"token parses to {parsed}, not {a.value}")

    dpath = os.path.join(ROOT, "data", "deals.csv")
    deals = list(csv.DictReader(open(dpath)))
    row = next((r for r in deals if r["deal_id"] == a.deal), None)
    if row is None:
        sys.exit(f"{a.deal} is not in data/deals.csv")
    if a.field in row:
        if row[a.field] and row[a.field] != a.value:
            sys.exit(f"conflict: deals.csv has {row[a.field]!r}. Resolve by hand.")
        if not row[a.field]:
            row[a.field] = a.value
            with open(dpath, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(deals[0].keys()))
                w.writeheader()
                w.writerows(deals)

    epath = os.path.join(ROOT, "data", "evidence.csv")
    fields = next(csv.reader(open(epath)))
    with open(epath, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=fields).writerow(
            {"deal_id": a.deal, "field": a.field, "value": a.value, "token": a.token,
             "source_url": a.url, "source_type": a.source_type, "evidence": a.evidence})
    with open(os.path.join(ROOT, "data", "evidence_log.sh"), "a") as f:
        f.write("python3 manual_evidence.py " + " ".join(shlex.quote(x) for x in sys.argv[1:]) + "\n")
    print(f"added: {a.deal} {a.field} = {a.value}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show")
    s.add_argument("url")
    s.add_argument("pattern")
    s.add_argument("--width", type=int, default=250)
    d = sub.add_parser("add")
    for k in ("deal", "field", "value", "token", "url", "evidence"):
        d.add_argument("--" + k, required=True)
    d.add_argument("--source-type", default="SEC filing")
    a = ap.parse_args()
    if a.cmd == "show":
        show(a.url, a.pattern, a.width)
    else:
        add(a)


if __name__ == "__main__":
    main()
