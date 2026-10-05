"""
PNG charts and tables for the post, from the pipeline outputs. Run after run_all.sh:
    pip install matplotlib
    python3 make_charts.py            # with titles
    python3 make_charts.py --no-titles   # bare charts, for captions written in the doc
Writes output/charts/*.png (2x resolution, white background).

Inputs: output/spread_weekly.csv, output/beta_break.csv, output/sensitivity_compare.csv,
output/pairs.csv, data/series.csv, data/events.csv, data/bond_trades/*.csv.
Edit ANNOTATIONS below for the dated notes on the weekly chart: each must match a
source that you cite in the post.
"""
import argparse
import csv
import os
import statistics
from datetime import date, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from common import ROOT

# ---------- settings you may edit ----------
BUILDING, TENANT = "APLD_2030", "CRWV_2030"
ANNOTATIONS = [  # (date, short label) shown on the weekly chart; cite each one in the post
    ("2026-06-29", "Meta to rent out\nspare AI compute"),
    ("2026-07-24", "CoreWeave stock\n-11% in a day"),
]
PHASES = [  # (start, end, label) shaded bands on the weekly chart
    ("2025-11-10", "2025-12-01", "about equal"),
    ("2026-06-22", "2026-08-03", "the July stress test"),
]
DEBT_MM, MW = 2350, 250  # Applied Digital 9.250% notes: $2.35bn for 250 MW of CoreWeave leases (filings)
COL = {"building": "#1f5fa6", "tenant": "#c0392b", "hy": "#8a8a8a", "google": "#2e8b57",
       "ig": "#b8860b", "b4": "#5b8fd1", "tenant2": "#e07b6f"}
SOURCE = "Source: FINRA TRACE trade history, SEC filings, U.S. Treasury, ICE BofA via FRED. Author's calculations."
# --------------------------------------------

P = lambda *a: os.path.join(ROOT, *a)
OUT = P("output", "charts")

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#444", "axes.labelcolor": "#222", "xtick.color": "#444", "ytick.color": "#444",
    "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.8, "axes.axisbelow": True,
    "figure.facecolor": "white", "savefig.facecolor": "white",
})


def read(path):
    return list(csv.DictReader(open(path))) if os.path.exists(path) else []


def num(x):
    return float(x) if x not in ("", None) else None


def finish(fig, ax, name, title, subtitle, titles):
    # title, subtitle and source are attached to the chart area at fixed point offsets,
    # so they never overlap, whatever the figure height
    if titles and title:
        ax.annotate(title, xy=(0, 1), xycoords="axes fraction", xytext=(0, 36 if subtitle else 14),
                    textcoords="offset points", ha="left", va="bottom", fontsize=15, fontweight="bold")
        if subtitle:
            ax.annotate(subtitle, xy=(0, 1), xycoords="axes fraction", xytext=(0, 14),
                        textcoords="offset points", ha="left", va="bottom", fontsize=11, color="#555")
    ax.annotate(SOURCE, xy=(0, 0), xycoords="axes fraction", xytext=(0, -46),
                textcoords="offset points", ha="left", va="top", fontsize=8, color="#888")
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name), dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", os.path.join("output", "charts", name))


def labels():
    return {r["deal_id"]: r["label"] for r in read(P("data", "series.csv"))}


# ---------- Chart 1: the twin bonds ----------
def last_price(deal, days=5):
    rows = read(P("data", "bond_trades", f"{deal}.csv"))
    if not rows:
        return None, None
    by = {}
    for r in rows:
        by.setdefault(r["trade_date"], []).append(float(r["price"]))
    last = sorted(by)[-days:]
    return statistics.median(p for d in last for p in by[d]), last[-1]


def chart_twins(weekly, titles):
    lab = labels()
    rows = [r for r in weekly if r.get(f"{BUILDING}_bp") and r.get(f"{TENANT}_bp")]
    if not rows:
        return
    last = rows[-1]
    items = []
    short = {TENANT: "Loan to CoreWeave\n(CoreWeave 9.25% 2030)",
             BUILDING: "Loan against a building CoreWeave rents\n(Applied Digital 9.25% 2030)"}
    for deal, color in ((TENANT, COL["tenant"]), (BUILDING, COL["building"])):
        price, d = last_price(deal)
        items.append((short.get(deal, lab.get(deal, deal)), float(last[f"{deal}_bp"]), price, color))
    fig, ax = plt.subplots(figsize=(9, 3.4))
    y = range(len(items))
    ax.barh(list(y), [i[1] for i in items], color=[i[3] for i in items], height=0.55)
    for yi, (name, sp, price, _) in zip(y, items):
        txt = f"{sp:.0f} bp" + (f"   (price ≈ {price:.1f})" if price else "")
        ax.text(sp + 8, yi, txt, va="center", fontsize=11)
    ax.set_yticks(list(y), [i[0] for i in items])
    ax.set_xlabel("spread over Treasuries (bp), week of " + last["week_start"])
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(i[1] for i in items) * 1.35)
    finish(fig, ax, "chart1_twin_bonds.png", "Same 9.25% coupon, same tenant, very different risk",
           "Spread over Treasuries: a loan to CoreWeave vs. a loan against a building CoreWeave rents", titles)


# ---------- Chart 2: weekly spreads ----------
def chart_weekly(weekly, titles):
    lab = labels()
    wk = [r for r in weekly if r.get(f"{BUILDING}_bp") or r.get(f"{TENANT}_bp")]
    if not wk:
        return
    d = [date.fromisoformat(r["week_start"]) for r in wk]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    for s, e, txt in PHASES:
        ax.axvspan(date.fromisoformat(s), date.fromisoformat(e), color="#f3efe6", zorder=0)
        ax.text(date.fromisoformat(s) + (date.fromisoformat(e) - date.fromisoformat(s)) / 2, 0.02, txt,
                transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=9, color="#8a7a55")
    alt = f"{BUILDING}_first_amort_bp"
    if wk[0].get(alt) is not None:
        lo, hi, dd = [], [], []
        for di, r in zip(d, wk):
            a, b = num(r.get(f"{BUILDING}_bp")), num(r.get(alt))
            if a is not None and b is not None:
                dd.append(di); lo.append(min(a, b)); hi.append(max(a, b))
        ax.fill_between(dd, lo, hi, color=COL["building"], alpha=0.15, linewidth=0,
                        label="range over repayment schedules")
    series = [(TENANT, COL["tenant"], lab.get(TENANT, TENANT)), (BUILDING, COL["building"], lab.get(BUILDING, BUILDING))]
    for deal, c, name in series:
        pts = [(di, num(r.get(f"{deal}_bp"))) for di, r in zip(d, wk) if num(r.get(f"{deal}_bp")) is not None]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=c, lw=2.2, label=name)
    hy = [(di, num(r.get("hy_index_bp"))) for di, r in zip(d, wk) if num(r.get("hy_index_bp")) is not None]
    ax.plot([p[0] for p in hy], [p[1] for p in hy], color=COL["hy"], lw=1.5, ls="--", label="US high-yield index")
    top = max(num(r[f"{TENANT}_bp"]) for r in wk if num(r.get(f"{TENANT}_bp")))
    notes = [(date.fromisoformat(ds), txt, ":") for ds, txt in ANNOTATIONS]
    notes += [(date.fromisoformat(e["event_date"]), "leases moved\nto CoreWeave SPV", "--") for e in read(P("data", "events.csv"))]
    notes = sorted(n for n in notes if d[0] <= n[0] <= d[-1])
    for i, (x, txt, ls) in enumerate(notes):
        ax.axvline(x, color="#888", lw=0.9, ls=ls)
        level = 1.04 if i % 2 == 0 else 1.19  # alternate heights so nearby notes do not overlap
        ax.text(x, top * level, txt, fontsize=8.5, color="#555", ha="center", va="bottom",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.5))
    ax.set_ylim(0, top * 1.36)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.set_ylabel("spread over Treasuries (bp)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.legend(loc="upper left", frameon=False, fontsize=9.5)
    finish(fig, ax, "chart2_weekly_spreads.png", "When CoreWeave's credit cracked, its buildings barely moved",
           "Weekly spread over Treasuries, from FINRA trades", titles)


# ---------- Chart 3: the echo ----------
def echo_rows():
    lab = labels()
    out = []
    bb = [r for r in read(P("output", "beta_break.csv")) if r["sample"] == "bullet spread, all weeks" and r["lags_L"] == "4"]
    sc = {(r["bond"], r["window"]): r for r in read(P("output", "sensitivity_compare.csv"))}
    def add(name, b, se, color):
        out.append((name, float(b), float(se), color))
    two = sc.get(("CRWV_2032_USD", "from break week")) or sc.get(("CRWV_2032_USD", "all common weeks"))
    if two:
        add("CoreWeave's own 2032 bond", two["b_bond"], two["se_bond"], COL["tenant2"])
    if bb:
        add("CoreWeave building, before early 2026", bb[0]["b_pre"], bb[0]["se_pre"], COL["building"])
        add("CoreWeave building, after (leases moved to SPV)", bb[0]["b_post"], bb[0]["se_post"], COL["building"])
    for deal, name, color in (("APLD_2031B", "Building 4 (lease NOT moved)", COL["b4"]),
                              ("APLD_2031A", "Building leased to an investment-grade hyperscaler", COL["ig"]),
                              ("WULF_2030", "TeraWulf: other tenant, Google backstop", COL["google"]),
                              ("CIFR_2030", "Cipher: other tenant, Google backstop", COL["google"])):
        r = sc.get((deal, "from break week"))
        if r:
            add(name, r["b_bond"], r["se_bond"], color)
    return out


def chart_echo(titles):
    rows = echo_rows()
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(9.5, 0.6 * len(rows) + 1.6))
    y = list(range(len(rows)))[::-1]
    for yi, (name, b, se, c) in zip(y, rows):
        ax.barh(yi, b, color=c, height=0.55)
        ax.errorbar(b, yi, xerr=1.96 * se, color="#333", capsize=3, lw=1)
        ax.text(max(b + 1.96 * se, 0) + 0.02, yi, f"{b:.2f}", va="center", fontsize=10)
    ax.set_yticks(y, [r[0] for r in rows])
    ax.axvline(0, color="#444", lw=0.8)
    ax.set_xlabel("bp move per 1 bp move in CoreWeave's 2030 bond spread (95% interval, Newey-West)")
    ax.grid(axis="y", visible=False)
    finish(fig, ax, "chart3_echo.png", "How much of CoreWeave's credit risk each bond echoes",
           "Weekly sensitivity to CoreWeave's own spread; buildings measured after early 2026", titles)


# ---------- Chart 4: dollars per megawatt ----------
def chart_per_mw(weekly, titles):
    rows = [r for r in weekly if r.get("gap_max_bp") not in ("", None)]
    if not rows:
        return
    gap = -float(rows[-1]["gap_max_bp"])  # the smallest gap under any repayment schedule (conservative)
    if gap <= 0:
        return
    per_mw = DEBT_MM / MW  # $ millions of debt per MW
    extra = per_mw * 1e6 * gap / 1e4
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.axis("off")
    boxes = [(f"${per_mw:.1f}M", "debt per MW\n($2.35bn / 250 MW)"),
             (f"× {gap / 100:.2f} pts", "extra spread CoreWeave pays\nvs. its building (at least)"),
             (f"≈ ${extra / 1e3:,.0f}k", "more interest per MW\nper year")]
    for i, (big, small) in enumerate(boxes):
        x = 0.17 + i * 0.33
        ax.text(x, 0.62, big, ha="center", va="center", fontsize=24, fontweight="bold",
                color=COL["building"] if i < 2 else COL["tenant"], transform=ax.transAxes)
        ax.text(x, 0.25, small, ha="center", va="center", fontsize=10.5, color="#444", transform=ax.transAxes)
    finish(fig, ax, "chart4_per_mw.png", "What the gap is worth",
           f"Week of {rows[-1]['week_start']}; gap is the conservative end of the range", titles)


# ---------- Tables as images ----------
def table_image(name, header, body, title, titles, col_widths=None):
    """Table drawn line by line (text wrapped to each column), plus a CSV for pasting into a doc."""
    import textwrap
    ncol = len(header)
    col_widths = col_widths or [1 / ncol] * ncol
    width_in = 10.0
    chars = [max(6, int(w * width_in * 9.5)) for w in col_widths]  # about 10.5 characters per inch at 10 pt
    wrap = lambda row: [textwrap.wrap(str(c), width=chars[i]) or [""] for i, c in enumerate(row)]
    rows = [wrap(header)] + [wrap(r) for r in body]
    heights = [max(len(c) for c in r) + 0.8 for r in rows]  # in text lines, with padding
    total = sum(heights)
    fig, ax = plt.subplots(figsize=(width_in, 0.22 * total + 0.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(total, 0)
    ax.axis("off")
    x0 = [sum(col_widths[:i]) for i in range(ncol)]
    y = 0.0
    for ri, (r, h) in enumerate(zip(rows, heights)):
        if ri == 0:
            ax.add_patch(plt.Rectangle((0, 0), 1, h, color="#f2f2f2", zorder=0))
        for ci, cell in enumerate(r):
            ax.text(x0[ci] + 0.008, y + 0.45, "\n".join(cell), va="top", ha="left", fontsize=10,
                    fontweight="bold" if ri == 0 else "normal", linespacing=1.25)
        y += h
        ax.plot([0, 1], [y, y], color="#cccccc", lw=0.8)
    ax.plot([0, 1], [0, 0], color="#999999", lw=1)
    finish(fig, ax, name, title, None, titles)
    with open(os.path.join(OUT, name.replace(".png", ".csv")), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(body)


def tables(titles):
    pairs = read(P("output", "pairs.csv"))
    names = {"APLD_2030": "Building leased to CoreWeave (Nov 2025)", "CIFR_2030": "Building with Google backstop",
             "APLD_2031B": "Unbuilt building leased to CoreWeave", "CRWV_2032_USD": "CoreWeave itself (unsecured)",
             "CRWV_2031A_TAP": "CoreWeave add-on", "CRWV_2031A": "CoreWeave original"}
    body = []
    for p in pairs:
        if p["pair_id"] not in ("NOV2025", "JUN2026"):
            continue
        gap = int(p["a_minus_b_bp"])
        body.append([p["date_a"][:7], names.get(p["deal_a"], p["deal_a"]), f'{p["spread_a_bp"]} bp' + ("+" if p["note"] else ""),
                     names.get(p["deal_b"], p["deal_b"]), f'{p["spread_b_bp"]} bp', f"{gap:+d} bp" + (" or more" if p["note"] else ""),
                     p["days_apart"]])
    if body:
        table_image("table1_same_week_pairs.png",
                    ["Month", "Debt on…", "Spread", "vs…", "Spread", "Gap", "Days apart"], body,
                    "New bonds priced in the same week", titles,
                    [0.08, 0.27, 0.09, 0.25, 0.09, 0.13, 0.09])
    rows = echo_rows()
    if rows:
        table_image("table2_echo.png", ["Bond", "Echo of CoreWeave's spread", "95% interval"],
                    [[n, f"{b:.2f}", f"{b - 1.96 * se:.2f} to {b + 1.96 * se:.2f}"] for n, b, se, _ in rows],
                    "How much each bond echoes CoreWeave", titles, [0.55, 0.22, 0.23])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-titles", action="store_true")
    a = ap.parse_args()
    titles = not a.no_titles
    weekly = read(P("output", "spread_weekly.csv"))
    chart_twins(weekly, titles)
    chart_weekly(weekly, titles)
    chart_echo(titles)
    chart_per_mw(weekly, titles)
    tables(titles)


if __name__ == "__main__":
    main()
