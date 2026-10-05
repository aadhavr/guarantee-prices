"""
Spreads of several bonds on the same dates, from hand-exported FINRA trades.

Answers: when did debt on a building leased to CoreWeave start to price tighter
than CoreWeave's own bonds? Same idea as the same-week pairs, but on every week
where both bonds traded, so no comparison crosses months.

Inputs
  data/series.csv           which bonds to plot: deal_id, role (e.g. building, tenant), label
  data/bond_trades/*.csv    trade files, recorded with record_trades.py (SHA-256 checked)
  data/events.csv           vertical lines on the chart (verified as in bond_event_study.py)
Outputs
  output/spread_weekly.csv  one row per week: spread of each bond, HY index, building minus tenant
  output/spread_weekly.svg  chart (open in a browser)

Method
  Daily price and spread as in bond_event_study.py (volume-weighted price; yield
  from dated cash flows, bullet at maturity; minus the interpolated Treasury).
  Weekly value = mean of the daily spreads in that ISO week. Bonds trade rarely,
  so the output gives the number of trade days behind each weekly value.
  For amortizing notes bought below par, the bullet yield is a lower bound on
  the level; week-to-week changes are much less affected.
"""
import csv
import os
import statistics
import sys
from datetime import date, timedelta

from bond_event_study import daily_prices, spread_series
from common import ROOT
from fetch_market import load as load_index
from fetch_treasury import load_curve
from verify_sources import parse_token

COLORS = ["#1b6ca8", "#c0392b", "#27ae60", "#8e44ad", "#d35400", "#2c3e50"]


def week_start(day):
    x = date.fromisoformat(day)
    return (x - timedelta(days=x.weekday())).isoformat()


def weekly(series):
    by = {}
    for day, v in series.items():
        by.setdefault(week_start(day), []).append(v)
    return {w: (statistics.mean(v), len(v)) for w, v in by.items()}


def svg_chart(weeks, lines, events, path):
    W, H, L, R, T, B = 900, 420, 60, 20, 30, 50
    vals = [v for _, _, s in lines for v in s.values() if v is not None]
    if not vals:
        return
    lo, hi = min(vals + [0]), max(vals)
    pad = (hi - lo) * 0.08 or 10
    lo, hi = lo - pad, hi + pad
    d0, d1 = date.fromisoformat(weeks[0]), date.fromisoformat(weeks[-1])
    span = max((d1 - d0).days, 1)
    x = lambda w: L + (date.fromisoformat(w) - d0).days / span * (W - L - R)
    y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="12">',
           f'<rect width="{W}" height="{H}" fill="white"/>']
    step = 100 if hi - lo > 300 else 50
    t = (int(lo) // step) * step
    while t <= hi:
        if t >= lo:
            out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#e5e5e5"/>'
                       f'<text x="{L - 6}" y="{y(t) + 4:.1f}" text-anchor="end" fill="#555">{t}</text>')
        t += step
    out.append(f'<text x="14" y="{T + (H - T - B) / 2:.0f}" transform="rotate(-90 14 {T + (H - T - B) / 2:.0f})" '
               f'text-anchor="middle" fill="#555">spread over Treasuries (bp)</text>')
    for w in weeks[:: max(1, len(weeks) // 8)]:
        out.append(f'<text x="{x(w):.1f}" y="{H - B + 18}" text-anchor="middle" fill="#555">{w}</text>')
    for e in events:
        if weeks[0] <= e["date"] <= weeks[-1]:
            xe = x(week_start(e["date"]))
            out.append(f'<line x1="{xe:.1f}" x2="{xe:.1f}" y1="{T}" y2="{H - B}" stroke="#999" stroke-dasharray="4 3"/>'
                       f'<text x="{xe + 4:.1f}" y="{T + 12}" fill="#666">{e["label"]}</text>')
    for i, (label, _, s) in enumerate(lines):
        pts = [(x(w), y(v)) for w, v in sorted(s.items()) if v is not None]
        c = COLORS[i % len(COLORS)]
        if len(pts) > 1:
            out.append(f'<polyline fill="none" stroke="{c}" stroke-width="2" points="' +
                       " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '"/>')
        for a, b in pts:
            out.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="2.5" fill="{c}"/>')
        out.append(f'<rect x="{L + 10}" y="{T + 8 + 18 * i}" width="12" height="3" fill="{c}"/>'
                   f'<text x="{L + 28}" y="{T + 13 + 18 * i}" fill="#222">{label}</text>')
    out.append("</svg>")
    open(path, "w").write("\n".join(out))


def main(offline=False):
    p = lambda *a: os.path.join(ROOT, *a)
    deals = {r["deal_id"]: r for r in csv.DictReader(open(p("data", "deals.csv")))}
    series_def = list(csv.DictReader(open(p("data", "series.csv"))))
    passed = {(v["deal_id"], v["field"]) for v in csv.DictReader(open(p("output", "verification.csv")))
              if v["status"] == "PASS"}
    for s in series_def:
        bad = [f for f in ("coupon_pct", "maturity_date") if (s["deal_id"], f) not in passed]
        if bad:
            sys.exit(f'{s["deal_id"]}: unverified {", ".join(bad)}; verify the bond terms first')
        if not os.path.exists(p("data", "bond_trades", f'{s["deal_id"]}.csv')):
            sys.exit(f'{s["deal_id"]}: no trade file in data/bond_trades/ (export from FINRA, then record_trades.py)')

    prices = {s["deal_id"]: daily_prices(s["deal_id"]) for s in series_def}
    all_days = sorted({d for pr in prices.values() for d in pr})
    years = {d[:4] for d in all_days}
    curve = load_curve(years, offline)
    hy = weekly({k: v * 100 for k, v in load_index("BAMLH0A0HYM2", offline).items()
                 if all_days[0] <= k <= all_days[-1]})
    wk = {s["deal_id"]: weekly(spread_series(deals[s["deal_id"]], prices[s["deal_id"]], curve)) for s in series_def}

    weeks = sorted({w for v in wk.values() for w in v})
    roles = {s["role"]: s["deal_id"] for s in series_def}
    rows = []
    for w in weeks:
        r = {"week_start": w, "hy_index_bp": round(hy[w][0]) if w in hy else ""}
        for s in series_def:
            v = wk[s["deal_id"]].get(w)
            r[f'{s["deal_id"]}_bp'] = round(v[0]) if v else ""
            r[f'{s["deal_id"]}_trade_days'] = v[1] if v else 0
        b, t = roles.get("building"), roles.get("tenant")
        if b and t and wk[b].get(w) and wk[t].get(w):
            r["building_minus_tenant_bp"] = round(wk[b][w][0] - wk[t][w][0])
        else:
            r["building_minus_tenant_bp"] = ""
        rows.append(r)
    with open(p("output", "spread_weekly.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    events = []
    ev_path = p("data", "events.csv")
    if os.path.exists(ev_path):
        for e in csv.DictReader(open(ev_path)):
            if parse_token("event_date", e["date_token"]) == e["event_date"]:
                events.append({"date": e["event_date"], "label": e["event_id"]})
    lines = [(s["label"], s["deal_id"], {w: wk[s["deal_id"]][w][0] for w in wk[s["deal_id"]]}) for s in series_def]
    lines.append(("HY index", "hy", {w: hy[w][0] for w in weeks if w in hy}))
    svg_chart(weeks, lines, events, p("output", "spread_weekly.svg"))

    gap = [r for r in rows if r["building_minus_tenant_bp"] != ""]
    print(f"wrote output/spread_weekly.csv ({len(rows)} weeks) and output/spread_weekly.svg")
    if gap:
        first_neg = next((r for r in gap if r["building_minus_tenant_bp"] < 0), None)
        print(f'building minus tenant: first common week {gap[0]["week_start"]} {gap[0]["building_minus_tenant_bp"]:+d} bp, '
              f'last {gap[-1]["week_start"]} {gap[-1]["building_minus_tenant_bp"]:+d} bp')
        print("first week the building priced tighter than the tenant:",
              first_neg["week_start"] if first_neg else "none in the data")
    else:
        print("no week where both the building and the tenant bond traded")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
