"""
Interactive versions of the post figures, as standalone HTML files for the blog.
Run after run_all.sh (needs the same inputs as make_charts.py):

    python3 make_interactive.py

Writes output/interactive/fig1_weekly_spreads.html, fig2_echo.html,
fig3_twin_bonds.html, fig4_per_mw.html. Each file holds its own data and loads
plotly.js from a CDN in the reader's browser, so the Python side needs no extra
package. Copy the files next to the post's index.qmd and embed them with an
<iframe> (see the .qmd).

Settings (colors, dated notes, phases, debt per MW) and the echo estimates come
from make_charts.py, so the static and interactive figures always agree.
"""
import json
import os
import sys

from make_charts import (ANNOTATIONS, BUILDING, COL, DEBT_MM, MW, PHASES, TENANT, P, echo_rows,
                         last_price, num, read)

OUT = P("output", "interactive")
PLOTLY = "https://cdn.plot.ly/plotly-2.35.2.min.js"
SOURCE = "Source: FINRA TRACE, SEC filings, U.S. Treasury, ICE BofA via FRED. Author's calculations."
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="{plotly}"></script>
<style>
  html, body {{ margin: 0; height: 100%; background: transparent; font-family: {font}; }}
  #wrap {{ display: flex; flex-direction: column; height: 100%; }}
  #chart {{ flex: 1; min-height: 280px; }}
  .src {{ font-size: 11px; color: #888; padding: 2px 6px 4px; }}
</style></head>
<body><div id="wrap"><div id="chart"></div><div class="src">{source}</div></div>
<script>
  var data = {data};
  var layout = {layout};
  Plotly.newPlot("chart", data, layout, {{responsive: true, displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"]}});
</script></body></html>
"""


def base_layout(**kw):
    layout = {
        "font": {"family": FONT, "size": 13, "color": "#222"},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "margin": {"l": 60, "r": 20, "t": 20, "b": 50},
        "hoverlabel": {"font": {"family": FONT}},
    }
    layout.update(kw)
    return layout


def write(name, title, data, layout):
    os.makedirs(OUT, exist_ok=True)
    html = PAGE.format(title=title, plotly=PLOTLY, font=FONT, source=SOURCE,
                       data=json.dumps(data), layout=json.dumps(layout))
    with open(os.path.join(OUT, name), "w") as f:
        f.write(html)
    print("wrote", os.path.join("output", "interactive", name))


def weekly_rows():
    return read(P("output", "spread_weekly.csv"))


# ---------- Figure 1: weekly spreads ----------
def fig_weekly(rows):
    wk = [r for r in rows if r.get(f"{BUILDING}_bp") or r.get(f"{TENANT}_bp")]
    if not wk:
        return
    x = [r["week_start"] for r in wk]
    data = []
    alt = f"{BUILDING}_first_amort_bp"
    if alt in wk[0]:
        # the range over repayment schedules: hidden by default, click the legend to show it
        lo, hi, xs = [], [], []
        for r in wk:
            a, b = num(r.get(f"{BUILDING}_bp")), num(r.get(alt))
            if a is not None and b is not None:
                xs.append(r["week_start"]); lo.append(min(a, b)); hi.append(max(a, b))
        data.append({"x": xs, "y": hi, "type": "scatter", "mode": "lines", "line": {"width": 0},
                     "hoverinfo": "skip", "showlegend": False, "legendgroup": "range", "visible": "legendonly"})
        data.append({"x": xs, "y": lo, "type": "scatter", "mode": "lines", "line": {"width": 0},
                     "fill": "tonexty", "fillcolor": "rgba(31,95,166,0.15)", "hoverinfo": "skip",
                     "name": "Building: range over repayment schedules (click to show)",
                     "legendgroup": "range", "visible": "legendonly"})
    for deal, color, name in ((TENANT, COL["tenant"], "Loan to CoreWeave itself (CoreWeave 9.25% 2030)"),
                              (BUILDING, COL["building"], "Loan against a building CoreWeave rents (Applied Digital 9.25% 2030)")):
        ys = [num(r.get(f"{deal}_bp")) for r in wk]
        data.append({"x": x, "y": ys, "type": "scatter", "mode": "lines", "name": name,
                     "line": {"color": color, "width": 3},
                     "hovertemplate": "%{y:.0f} bp<extra>" + name.split(" (")[0] + "</extra>"})
    data.append({"x": x, "y": [num(r.get("hy_index_bp")) for r in wk], "type": "scatter", "mode": "lines",
                 "name": "Average U.S. junk bond (high-yield index)",
                 "line": {"color": COL["hy"], "width": 2, "dash": "dash"},
                 "hovertemplate": "%{y:.0f} bp<extra>junk bond index</extra>"})
    shapes, notes = [], []
    for s, e, txt in PHASES:
        shapes.append({"type": "rect", "xref": "x", "yref": "paper", "x0": s, "x1": e, "y0": 0, "y1": 1,
                       "fillcolor": "#f3efe6", "line": {"width": 0}, "layer": "below"})
        notes.append({"x": s, "y": 0.02, "xref": "x", "yref": "paper", "text": txt, "showarrow": False,
                      "xanchor": "left", "font": {"size": 11, "color": "#8a7a55"}})
    marks = [(d, t.replace("\n", "<br>"), "dot") for d, t in ANNOTATIONS]
    marks += [(e["event_date"], "Leases moved<br>to CoreWeave SPV", "dash") for e in read(P("data", "events.csv"))]
    for i, (d, txt, dash) in enumerate(sorted(marks)):
        if not (x[0] <= d <= x[-1]):
            continue
        shapes.append({"type": "line", "xref": "x", "yref": "paper", "x0": d, "x1": d, "y0": 0, "y1": 1,
                       "line": {"color": "#888", "width": 1, "dash": dash}})
        notes.append({"x": d, "y": 0.99 if i % 2 == 0 else 0.86, "xref": "x", "yref": "paper", "text": txt,
                      "showarrow": False, "font": {"size": 11, "color": "#555"}, "bgcolor": "rgba(255,255,255,0.85)"})
    layout = base_layout(
        hovermode="x unified",
        xaxis={"showgrid": False, "tickformat": "%b '%y", "hoverformat": "Week of %b %d, %Y"},
        yaxis={"title": {"text": "Extra yield over Treasuries (basis points)"}, "rangemode": "tozero",
               "gridcolor": "#eee"},
        legend={"orientation": "h", "y": -0.12, "x": 0, "font": {"size": 12}},
        margin={"l": 60, "r": 20, "t": 20, "b": 90},
        shapes=shapes, annotations=notes)
    write("fig1_weekly_spreads.html", "Weekly spreads", data, layout)


# ---------- Figure 2: the echo ----------
def fig_echo():
    rows = echo_rows()
    if not rows:
        return
    rows = rows[::-1]  # plotly draws the first bar at the bottom
    data = [{"type": "bar", "orientation": "h",
             "y": [r[0] for r in rows], "x": [r[1] for r in rows],
             "marker": {"color": [r[3] for r in rows]},
             "error_x": {"type": "data", "array": [1.96 * r[2] for r in rows], "color": "#333", "thickness": 1.2},
             "customdata": [[r[2], r[1] - 1.96 * r[2], r[1] + 1.96 * r[2]] for r in rows],
             "hovertemplate": ("<b>%{y}</b><br>Moves %{x:.2f} points per 1-point move in CoreWeave's spread"
                               "<br>95% interval: %{customdata[1]:.2f} to %{customdata[2]:.2f}"
                               "<br>(s.e. %{customdata[0]:.2f})<extra></extra>"),
             "text": [f"{r[1]:.2f}" for r in rows], "textposition": "outside", "cliponaxis": False}]
    layout = base_layout(
        xaxis={"title": {"text": "How much the bond's spread moves when CoreWeave's moves by 1 point"},
               "zeroline": True, "zerolinecolor": "#444", "gridcolor": "#eee"},
        yaxis={"automargin": True}, showlegend=False, bargap=0.35,
        margin={"l": 20, "r": 40, "t": 10, "b": 60})
    write("fig2_echo.html", "Echo of CoreWeave's credit", data, layout)


# ---------- Figure 3: the twin bonds ----------
def fig_twins(rows):
    rows = [r for r in rows if r.get(f"{BUILDING}_bp") and r.get(f"{TENANT}_bp")]
    if not rows:
        return
    last = rows[-1]
    items = []
    for deal, color, name in ((BUILDING, COL["building"], "Loan against a building<br>CoreWeave rents<br>(Applied Digital 9.25% 2030)"),
                              (TENANT, COL["tenant"], "Loan to CoreWeave<br>(CoreWeave 9.25% 2030)")):
        price, _ = last_price(deal)
        items.append((name, float(last[f"{deal}_bp"]), price, color))
    items = items[::-1]
    data = [{"type": "bar", "orientation": "h", "y": [i[0] for i in items], "x": [i[1] for i in items],
             "marker": {"color": [i[3] for i in items]},
             "text": [f"{i[1]:.0f} bp  (price ≈ {i[2]:.1f})" if i[2] else f"{i[1]:.0f} bp" for i in items],
             "textposition": "outside", "cliponaxis": False,
             "customdata": [i[2] for i in items],
             "hovertemplate": "%{x:.0f} bp over Treasuries<br>price ≈ %{customdata:.1f} cents per dollar<extra></extra>"}]
    layout = base_layout(
        xaxis={"title": {"text": f"Spread over Treasuries (bp), week of {last['week_start']}"},
               "range": [0, max(i[1] for i in items) * 1.45], "gridcolor": "#eee"},
        yaxis={"automargin": True}, showlegend=False, bargap=0.45,
        margin={"l": 20, "r": 20, "t": 10, "b": 60})
    write("fig3_twin_bonds.html", "Same coupon, different risk", data, layout)


# ---------- Figure 4: what the gap is worth, week by week ----------
def fig_per_mw(rows):
    rows = [r for r in rows if r.get("gap_max_bp") not in ("", None)]
    if not rows:
        return
    per_mw = DEBT_MM * 1e6 / MW  # dollars of debt per MW
    x = [r["week_start"] for r in rows]
    # conservative: the smallest saving under any repayment schedule (gap_max is the least negative gap)
    y = [-float(r["gap_max_bp"]) / 1e4 * per_mw / 1e3 for r in rows]
    gap_pts = [-float(r["gap_max_bp"]) / 100 for r in rows]
    data = [{"x": x, "y": y, "type": "scatter", "mode": "lines", "fill": "tozeroy",
             "line": {"color": COL["building"], "width": 3}, "fillcolor": "rgba(31,95,166,0.12)",
             "customdata": gap_pts,
             "hovertemplate": ("Week of %{x|%b %d, %Y}<br>Building borrows %{customdata:.2f} points cheaper"
                               "<br>≈ $%{y:,.0f}k less interest per MW per year<extra></extra>")}]
    notes = [{"x": x[-1], "y": y[-1], "text": f"<b>≈ ${y[-1]:,.0f}k</b><br>per MW per year", "showarrow": True,
              "arrowhead": 0, "ax": -60, "ay": -40, "font": {"color": COL["building"], "size": 13}}]
    layout = base_layout(
        xaxis={"showgrid": False, "tickformat": "%b '%y"},
        yaxis={"title": {"text": "Interest saved per MW per year ($ thousands)"}, "gridcolor": "#eee",
               "zeroline": True, "zerolinecolor": "#444"},
        showlegend=False, annotations=notes,
        margin={"l": 70, "r": 30, "t": 20, "b": 50})
    write("fig4_per_mw.html", "What the gap is worth", data, layout)


def main():
    rows = weekly_rows()
    if not rows:
        sys.exit("output/spread_weekly.csv not found: run ./run_all.sh first")
    fig_weekly(rows)
    fig_echo()
    fig_twins(rows)
    fig_per_mw(rows)


if __name__ == "__main__":
    main()
