"""
Yield at issue and spread over Treasuries, using only values that passed
verify_sources.py. Rows with any unverified required value are listed in
output/excluded.csv with the reason, not estimated.

Yield: bond-equivalent (semiannual) yield from dated cash flows at the issue
price, with a pro-rated first coupon. Amortizing notes issued below par get two
bounds, because the indenture schedule is not in the verified data:
  lower bound = all principal at maturity; upper bound = all principal at the
  first amortization date. Any real schedule lies between them.
Treasury: linear interpolation of the 2/3/5/7-year par yields on the pricing
date at the life of the cash flows.
"""
import csv
import os
from datetime import date

from common import ROOT
from verify_sources import NEEDED


def d(s):
    y, m, dd = map(int, s.split("-"))
    return date(y, m, dd)


def shift(x, months):
    m = x.month - 1 + months
    return date(x.year + m // 12, m % 12 + 1, min(x.day, 28))


def cash_flows(coupon, settle, principal_date):
    dates, t = [], principal_date
    while t > settle:
        dates.append(t)
        t = shift(t, -6)
    dates.sort()
    cfs = []
    for i, t in enumerate(dates):
        amt = coupon / 2
        if i == 0:
            prev = shift(t, -6)
            amt *= (t - settle).days / (t - prev).days
        cfs.append((t, amt))
    cfs[-1] = (cfs[-1][0], cfs[-1][1] + 100)
    return cfs


def yield_pct(price, settle, cfs):
    def pv(y):
        return sum(a / (1 + y / 200) ** ((t - settle).days / 182.625) for t, a in cfs)
    lo, hi = -5.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if pv(mid) > price else (lo, mid)
    return (lo + hi) / 2


def treasury(curve, years):
    pts = [(2, float(curve["ust_2y"])), (3, float(curve["ust_3y"])),
           (5, float(curve["ust_5y"])), (7, float(curve["ust_7y"]))]
    if years <= 2:
        return pts[0][1]
    for (t0, y0), (t1, y1) in zip(pts, pts[1:]):
        if years <= t1:
            return y0 + (y1 - y0) * (years - t0) / (t1 - t0)
    return pts[-1][1]


def main():
    p = lambda *a: os.path.join(ROOT, *a)
    deals = list(csv.DictReader(open(p("data", "deals.csv"))))
    ver = list(csv.DictReader(open(p("output", "verification.csv"))))
    passed = {(v["deal_id"], v["field"]) for v in ver if v["status"] == "PASS"}
    curves = {r["date"]: r for r in csv.DictReader(open(p("data", "treasury_cmt.csv")))}
    market = {}
    if os.path.exists(p("data", "market_index.csv")):  # task 2: optional market control
        market = {r["date"]: r for r in csv.DictReader(open(p("data", "market_index.csv")))}

    fixed, floating, excluded = [], [], []
    for r in deals:
        if r["include"] != "Y":
            excluded.append({"deal_id": r["deal_id"], "reason": r["note"] or "include != Y"})
            continue
        need = list(NEEDED[r["rate_type"]])
        below_par_amort = r["amortizing"] == "Y" and r["issue_price"] and float(r["issue_price"]) != 100
        # first_amort_date is optional: without it only the lower bound (bullet) is reported,
        # which is a true lower bound for any note issued below par
        has_first_amort = (r["deal_id"], "first_amort_date") in passed
        missing = [f for f in need if (r["deal_id"], f) not in passed]
        if missing:
            excluded.append({"deal_id": r["deal_id"], "reason": "unverified: " + ", ".join(missing)})
            continue
        if r["rate_type"] == "floating":
            floating.append({"deal_id": r["deal_id"], "pricing_date": r["pricing_date"],
                             "sofr_spread_bp": r["sofr_spread_bp"], "tenant": r["tenant"], "support": r["support"]})
            continue
        settle, mat = d(r["pricing_date"]), d(r["maturity_date"])
        cases = [("lower bound: bullet" if below_par_amort else "bullet", mat)]
        if below_par_amort and has_first_amort:
            cases.append(("upper bound: all principal at first amortization", d(r["first_amort_date"])))
        elif below_par_amort:
            cases[0] = ("lower bound only: amortization start not verified", mat)
        for label, pdate in cases:
            cfs = cash_flows(float(r["coupon_pct"]), settle, pdate)
            y = yield_pct(float(r["issue_price"]), settle, cfs)
            life = (pdate - settle).days / 365.25
            u = treasury(curves[r["pricing_date"]], life)
            fixed.append({"deal_id": r["deal_id"], "case": label, "pricing_date": r["pricing_date"],
                          "tenant": r["tenant"], "google_backstop": r["google_backstop"],
                          "structure": r["structure"], "coupon_pct": r["coupon_pct"],
                          "issue_price": r["issue_price"], "life_yrs": round(life, 2),
                          "yield_pct": round(y, 3), "ust_pct": round(u, 3), "spread_bp": round((y - u) * 100)})
            m = market.get(r["pricing_date"], {})
            for col in [c for c in m if c.endswith("_pct")]:
                if m[col] != "":
                    name = col.replace("_pct", "")
                    fixed[-1][f"{name}_bp"] = round(float(m[col]) * 100)
                    fixed[-1][f"spread_minus_{name}_bp"] = fixed[-1]["spread_bp"] - round(float(m[col]) * 100)

    for name, rows in (("spreads.csv", fixed), ("floating.csv", floating), ("excluded.csv", excluded)):
        if rows:
            keys = list(dict.fromkeys(k for row in rows for k in row))
            with open(p("output", name), "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys, restval="")
                w.writeheader()
                w.writerows(rows)
    print("fixed-rate results:")
    for o in fixed:
        rel = o.get("spread_minus_bamlh0a0hym2_bp", "")
        rel = f"  vs HY index {rel:+d} bp" if rel != "" else ""
        print(f'  {o["deal_id"]:15s} {o["pricing_date"]}  yield {o["yield_pct"]:6.3f}%  spread {o["spread_bp"]:4d} bp{rel}  ({o["case"]})')
    print("excluded:")
    for o in excluded:
        print(f'  {o["deal_id"]:15s} {o["reason"]}')


if __name__ == "__main__":
    main()
