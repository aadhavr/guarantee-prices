"""
Did the building bond's sensitivity to CoreWeave's own credit change after a date?

Weekly changes (from output/spread_weekly.csv):
    dB_t = a + b1 dT_t + b2 dH_t + post_t (a' + b1' dT_t + b2' dH_t) + u_t
  dB  change in the building bond spread (bp)       e.g. APLD_2030
  dT  change in the tenant's own bond spread (bp)   e.g. CRWV_2030
  dH  change in the HY index (bp)
  post = 1 for weeks on or after the break date (default: the LEASE_MOVE event)
b1 is the sensitivity before the break, b1 + b1' after it. The test is H0: b1' = 0.

Standard errors: Newey-West (HAC), Bartlett weights, with a small-sample factor
n/(n-k), so they allow for heteroskedasticity and correlation between nearby
weeks. p-values use the normal approximation; with n of about 45 weeks, read them
as approximate. Results are shown for several lag lengths L and two samples.

    python3 spread_timeseries.py   (first, to write output/spread_weekly.csv)
    python3 beta_break.py [--break 2026-03-30] [--building APLD_2030] [--tenant CRWV_2030]
Part 2 (compare_all): for every other bond in data/series.csv, its sensitivity to
the tenant's spread over the weeks when it and the reference bond both traded,
and the difference from the reference, estimated directly on the difference of
the two bonds' weekly changes (so the Newey-West standard error is for the
difference itself). Output: output/sensitivity_compare.csv.
Standard library only.
"""
import argparse
import csv
import math
import os
from datetime import date, timedelta

from common import ROOT


def inv(m):
    n = len(m)
    a = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(m)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(a[r][c]))
        if abs(a[piv][c]) < 1e-12:
            raise ValueError("singular matrix: too few weeks in one period")
        a[c], a[piv] = a[piv], a[c]
        f = a[c][c]
        a[c] = [v / f for v in a[c]]
        for r in range(n):
            if r != c and a[r][c]:
                g = a[r][c]
                a[r] = [vr - g * vc for vr, vc in zip(a[r], a[c])]
    return [row[n:] for row in a]


def mat(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def ols_nw(y, X, L):
    n, k = len(X), len(X[0])
    xtx_inv = inv([[sum(X[t][i] * X[t][j] for t in range(n)) for j in range(k)] for i in range(k)])
    b = [sum(xtx_inv[i][j] * sum(X[t][j] * y[t] for t in range(n)) for j in range(k)) for i in range(k)]
    u = [y[t] - sum(X[t][j] * b[j] for j in range(k)) for t in range(n)]
    S = [[sum(u[t] ** 2 * X[t][i] * X[t][j] for t in range(n)) for j in range(k)] for i in range(k)]
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        for i in range(k):
            for j in range(k):
                S[i][j] += w * sum(u[t] * u[t - l] * (X[t][i] * X[t - l][j] + X[t - l][i] * X[t][j])
                                   for t in range(l, n))
    V = mat(mat(xtx_inv, S), xtx_inv)
    V = [[v * n / (n - k) for v in row] for row in V]
    return b, V, n


def p_two_sided(z):
    return math.erfc(abs(z) / math.sqrt(2))


def changes(rows, cols):
    """Consecutive-week changes for the given columns, only weeks where all are present."""
    out = []
    for prev, cur in zip(rows, rows[1:]):
        if (date.fromisoformat(cur["week_start"]) - date.fromisoformat(prev["week_start"])).days != 7:
            continue
        if any(prev.get(c, "") == "" or cur.get(c, "") == "" for c in cols):
            continue
        out.append((cur["week_start"], [float(cur[c]) - float(prev[c]) for c in cols]))
    return out


def compare_all(rows, ref, tenant, brk_week=None):
    """Part 2. For each other bond in data/series.csv: its sensitivity to the tenant's spread,
    and the difference from the reference bond, over the weeks when both traded (all common
    weeks, and only weeks from the break week). The difference is estimated directly:
        (dB_other - dB_ref) = c + (b_other - b_ref) dT + g dH + u,
    so the Newey-West standard error applies to the difference itself."""
    sp = os.path.join(ROOT, "data", "series.csv")
    if not os.path.exists(sp):
        return
    others = [r["deal_id"] for r in csv.DictReader(open(sp))
              if r["deal_id"] not in (ref, tenant) and f'{r["deal_id"]}_bp' in rows[0]]
    if not others:
        print("part 2: no other bonds with trades yet")
        return
    T, H, R = f"{tenant}_bp", "hy_index_bp", f"{ref}_bp"
    windows = [("all common weeks", None)] + ([("from break week", brk_week)] if brk_week else [])
    out = []
    print(f"\npart 2: sensitivity to {tenant}'s spread, and difference from {ref} (Newey-West, L=4)")
    for o in others:
        for wlabel, wstart in windows:
            ch = [c for c in changes(rows, [f"{o}_bp", R, T, H]) if not wstart or c[0] >= wstart]
            if len(ch) < 10:
                print(f"  {o:16s} {wlabel:17s} only {len(ch)} common weeks, skipped (need 10)")
                continue
            wk = [c[0] for c in ch]
            X = [[1.0, c[1][2], c[1][3]] for c in ch]
            try:
                b_o, V_o, n = ols_nw([c[1][0] for c in ch], X, 4)
                b_r, V_r, _ = ols_nw([c[1][1] for c in ch], X, 4)
                b_d, V_d, _ = ols_nw([c[1][0] - c[1][1] for c in ch], X, 4)
            except ValueError as e:
                print(f"  {o:16s} {wlabel:17s} skipped: {e}")
                continue
            se_o, se_r, se_d = (math.sqrt(V[1][1]) for V in (V_o, V_r, V_d))
            z = b_d[1] / se_d
            out.append({"bond": o, "window": wlabel, "reference": ref, "first_week": wk[0], "last_week": wk[-1],
                        "n_weeks": n, "b_bond": round(b_o[1], 3), "se_bond": round(se_o, 3),
                        "b_reference": round(b_r[1], 3), "se_reference": round(se_r, 3),
                        "difference": round(b_d[1], 3), "se_difference": round(se_d, 3),
                        "z": round(z, 2), "p": round(p_two_sided(z), 3)})
            print(f"  {o:16s} {wlabel:17s} {wk[0]}..{wk[-1]} n={n:2d}  b {b_o[1]:5.2f} ({se_o:.2f})  "
                  f"{ref} b {b_r[1]:5.2f} ({se_r:.2f})  difference {b_d[1]:+.2f} ({se_d:.2f})  "
                  f"z {z:+.2f}  p {p_two_sided(z):.3f}")
    if out:
        with open(os.path.join(ROOT, "output", "sensitivity_compare.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
        print("wrote output/sensitivity_compare.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="brk")
    ap.add_argument("--building", default="APLD_2030")
    ap.add_argument("--tenant", default="CRWV_2030")
    ap.add_argument("--file", default=os.path.join(ROOT, "output", "spread_weekly.csv"))
    a = ap.parse_args()

    brk = a.brk
    if not brk:
        ev = os.path.join(ROOT, "data", "events.csv")
        brk = next(r["event_date"] for r in csv.DictReader(open(ev)) if r["event_id"] == "LEASE_MOVE")
    bd = date.fromisoformat(brk)
    brk_week = (bd - timedelta(days=bd.weekday())).isoformat()

    rows = list(csv.DictReader(open(a.file)))
    B, T = f"{a.building}_bp", f"{a.tenant}_bp"
    alt = f"{a.building}_first_amort_bp" if f"{a.building}_first_amort_bp" in rows[0] else None

    def build(col_b, min_days):
        y, X, weeks = [], [], []
        for prev, cur in zip(rows, rows[1:]):
            if (date.fromisoformat(cur["week_start"]) - date.fromisoformat(prev["week_start"])).days != 7:
                continue  # only consecutive weeks
            vals = [prev[col_b], cur[col_b], prev[T], cur[T], prev["hy_index_bp"], cur["hy_index_bp"]]
            if "" in vals:
                continue
            if min_days and (int(cur[f"{a.building}_trade_days"]) < min_days or int(cur[f"{a.tenant}_trade_days"]) < min_days
                             or int(prev[f"{a.building}_trade_days"]) < min_days or int(prev[f"{a.tenant}_trade_days"]) < min_days):
                continue
            db = float(cur[col_b]) - float(prev[col_b])
            dt = float(cur[T]) - float(prev[T])
            dh = float(cur["hy_index_bp"]) - float(prev["hy_index_bp"])
            post = 1.0 if cur["week_start"] >= brk_week else 0.0
            y.append(db)
            X.append([1.0, dt, dh, post, post * dt, post * dh])
            weeks.append(cur["week_start"])
        return y, X, weeks

    specs = [("bullet spread, all weeks", B, 0)]
    if alt:
        specs.append(("first-amortization spread, all weeks", alt, 0))
    specs.append(("bullet spread, weeks with >= 3 trade days", B, 3))

    out = []
    print(f"break week: {brk_week}   building: {a.building}   tenant: {a.tenant}")
    print("b_pre = sensitivity before the break, b_post = after; change = b_post - b_pre (H0: change = 0)")
    for label, col, md in specs:
        y, X, weeks = build(col, md)
        npre = sum(1 for x in X if x[3] == 0)
        for L in (2, 4, 8):
            try:
                b, V, n = ols_nw(y, X, L)
            except ValueError as e:
                print(f"  {label}: {e}")
                break
            pre, chg = b[1], b[4]
            se_pre, se_chg = math.sqrt(V[1][1]), math.sqrt(V[4][4])
            post = pre + chg
            se_post = math.sqrt(V[1][1] + V[4][4] + 2 * V[1][4])
            r = {"sample": label, "lags_L": L, "n_weeks": n, "n_pre": npre, "n_post": n - npre,
                 "b_pre": round(pre, 3), "se_pre": round(se_pre, 3),
                 "b_post": round(post, 3), "se_post": round(se_post, 3),
                 "change": round(chg, 3), "se_change": round(se_chg, 3),
                 "z_change": round(chg / se_chg, 2), "p_change": round(p_two_sided(chg / se_chg), 3)}
            out.append(r)
            print(f'  {label:42s} L={L}  n={n} ({npre}/{n - npre})  b_pre {pre:5.2f} ({se_pre:.2f})  '
                  f'b_post {post:5.2f} ({se_post:.2f})  change {chg:+.2f} ({se_chg:.2f})  z {chg / se_chg:+.2f}  p {r["p_change"]:.3f}')
    path = os.path.join(ROOT, "output", "beta_break.csv")
    compare_all(rows, a.building, a.tenant, brk_week)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print("standard errors in brackets (Newey-West). wrote output/beta_break.csv")


if __name__ == "__main__":
    main()
