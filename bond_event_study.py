"""
Task 4: did the market reprice CoreWeave-linked debt when the leases moved to
an investment-grade SPV?

Design (difference in differences on secondary-market spreads):
  treated bond : a note whose payments come from CoreWeave leases (e.g. APLD_2030)
  control bond : CoreWeave's own unsecured notes (e.g. CRWV_2031A)
  If the lease move made the treated bond safer, its spread falls MORE than the
  control's over the same window. The market index change is also reported.

Inputs
  data/events.csv         event_id, event_date, date_token, treated, control, description, source_url, evidence
                          (evidence must appear in the source, date_token in the evidence,
                          and date_token must parse to date; bond terms must have passed
                          verify_sources.py)
  data/bond_trades/<deal_id>.csv   trades you export by hand from FINRA's bond data
                          pages (see README). Columns: trade_date (YYYY-MM-DD), price,
                          and optionally quantity.
  data/bond_trades/provenance.csv  deal_id, cusip, source, export_date, sha256
                          The script refuses a trade file whose SHA-256 does not
                          match, so the analysis is replicable from the saved files.

Method
  - Daily price: volume-weighted if quantity is present, else the median trade.
  - Yield from price: dated cash flows, bullet at maturity. For amortizing notes
    this is an approximation of the level; for a CHANGE over two weeks the
    error is small, and it is the same in the pre and post windows.
  - Spread: yield minus the Treasury par yield at the remaining life, same day.
  - Windows (calendar days): pre = [-10, -1], post = [+1, +10]. Bonds trade
    rarely, so the output reports how many trade days each window has.
"""
import csv
import hashlib
import os
import statistics
import sys
from datetime import date, timedelta

from common import ROOT, fetch, normalize
from fetch_market import load as load_index
from fetch_treasury import load_curve
from spreads import cash_flows, d, treasury, yield_pct
from verify_sources import parse_token

PRE, POST = (-10, -1), (1, 10)


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def daily_prices(deal_id):
    folder = os.path.join(ROOT, "data", "bond_trades")
    prov = {r["deal_id"]: r for r in csv.DictReader(open(os.path.join(folder, "provenance.csv")))}
    path = os.path.join(folder, f"{deal_id}.csv")
    if deal_id not in prov:
        sys.exit(f"{deal_id}: no row in data/bond_trades/provenance.csv")
    if sha256(path) != prov[deal_id]["sha256"]:
        sys.exit(f"{deal_id}: trade file changed since export (sha256 mismatch). Re-record provenance.")
    by_day = {}
    for r in csv.DictReader(open(path)):
        by_day.setdefault(r["trade_date"], []).append((float(r["price"]), float(r.get("quantity") or 0)))
    out = {}
    for day, trades in by_day.items():
        qty = sum(q for _, q in trades)
        out[day] = (sum(p * q for p, q in trades) / qty) if qty > 0 else statistics.median(p for p, _ in trades)
    return out


def spread_series(deal, prices, curve):
    mat = d(deal["maturity_date"])
    out = {}
    for day, px in prices.items():
        if day not in curve:
            continue  # no Treasury curve that day
        settle = d(day)
        y = yield_pct(px, settle, cash_flows(float(deal["coupon_pct"]), settle, mat))
        out[day] = (y - treasury(curve[day], (mat - settle).days / 365.25)) * 100
    return out


def window_mean(series, event, lo, hi):
    days = [k for k in series if lo <= (d(k) - event).days <= hi]
    return (statistics.mean(series[k] for k in days) if days else None), len(days)


MIN_DAYS = 3        # trade days required in each window, for each bond
EXCLUDE_DAYS = 20   # placebo dates closer than this to the event are skipped (windows overlap)


def did_at(st, sc, day):
    vals = []
    for s in (st, sc):
        pre, npre = window_mean(s, day, *PRE)
        post, npost = window_mean(s, day, *POST)
        if pre is None or post is None or npre < MIN_DAYS or npost < MIN_DAYS:
            return None
        vals.append(post - pre)
    return vals[0] - vals[1]


def placebo(ser, ev, actual, event_id, p):
    """Rank of the actual effect among placebo dates. The placebo windows overlap
    each other, so the values are not independent: read the rank as descriptive."""
    days = sorted(set(ser["treated"]) & set(ser["control"]))
    first, last = d(days[0]), d(days[-1])
    out = []
    x = first + timedelta(days=-PRE[0])
    while x <= last - timedelta(days=POST[1]):
        if x.weekday() < 5 and abs((x - ev).days) > EXCLUDE_DAYS:
            v = did_at(ser["treated"], ser["control"], x)
            if v is not None:
                out.append((x.isoformat(), v))
        x += timedelta(days=1)
    if not out:
        return {"placebo_n": 0}
    with open(p("output", f"placebo_{event_id}.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "diff_in_diff_bp"])
        w.writerows((dt, round(v, 1)) for dt, v in out)
    vals = [v for _, v in out]
    return {"placebo_n": len(vals),
            "placebo_s_bp": round(statistics.stdev(vals), 1) if len(vals) > 1 else "",
            "share_placebo_le_actual": round(sum(v <= actual for v in vals) / len(vals), 3),
            "share_placebo_abs_ge_actual": round(sum(abs(v) >= abs(actual) for v in vals) / len(vals), 3)}


def main(offline=False):
    p = lambda *a: os.path.join(ROOT, *a)
    deals = {r["deal_id"]: r for r in csv.DictReader(open(p("data", "deals.csv")))}
    events = list(csv.DictReader(open(p("data", "events.csv"))))
    passed = {(v["deal_id"], v["field"]) for v in csv.DictReader(open(p("output", "verification.csv")))
              if v["status"] == "PASS"}
    years = {e["event_date"][:4] for e in events} | {str(int(e["event_date"][:4]) - 1) for e in events}
    for e in events:  # the placebo needs the curve on every trade date
        for role in ("treated", "control"):
            years |= {k[:4] for k in daily_prices(e[role])}
    curve = load_curve(years, offline)
    hy = {k: v * 100 for k, v in load_index("BAMLH0A0HYM2", offline).items()}

    rows = []
    for e in events:
        doc = normalize(fetch(e["source_url"], offline).decode("utf-8", "replace"))
        evid = normalize(e["evidence"])
        if evid not in doc or normalize(e["date_token"]) not in evid \
                or parse_token("event_date", e["date_token"]) != e["event_date"]:
            print(f'{e["event_id"]}: event or date not verified against the source; event skipped')
            continue
        bad = [f"{e[r]}.{f}" for r in ("treated", "control") for f in ("coupon_pct", "maturity_date")
               if (e[r], f) not in passed]
        if bad:
            print(f'{e["event_id"]}: unverified bond terms ({", ".join(bad)}); event skipped')
            continue
        ev = d(e["event_date"])
        res = {"event_id": e["event_id"], "event_date": e["event_date"]}
        ser = {}
        for role in ("treated", "control"):
            s = spread_series(deals[e[role]], daily_prices(e[role]), curve)
            ser[role] = s
            pre, npre = window_mean(s, ev, *PRE)
            post, npost = window_mean(s, ev, *POST)
            res[f"{role}"] = e[role]
            res[f"{role}_change_bp"] = round(post - pre) if pre is not None and post is not None else ""
            res[f"{role}_trade_days_pre_post"] = f"{npre}/{npost}"
        hpre, _ = window_mean(hy, ev, *PRE)
        hpost, _ = window_mean(hy, ev, *POST)
        res["hy_index_change_bp"] = round(hpost - hpre) if hpre is not None and hpost is not None else ""
        if res["treated_change_bp"] != "" and res["control_change_bp"] != "":
            res["diff_in_diff_bp"] = res["treated_change_bp"] - res["control_change_bp"]
        else:
            res["diff_in_diff_bp"] = ""
        # placebo: the same difference in differences at every other date in the sample
        if res["diff_in_diff_bp"] != "":
            actual = did_at(ser["treated"], ser["control"], ev)
            res.update(placebo(ser, ev, actual, e["event_id"], p))
        rows.append(res)
        print(res)

    if rows:
        with open(p("output", "event_study.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print("wrote output/event_study.csv. A negative diff_in_diff_bp means the treated bond's spread fell more than the control's.")
        print("share_placebo_le_actual: share of placebo dates with an effect at least as negative as the event (one-sided);")
        print("share_placebo_abs_ge_actual: share with an effect at least as large in size (two-sided). Placebo windows overlap,")
        print("so these shares describe the event's rank; they are not exact p-values.")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
