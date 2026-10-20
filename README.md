# The bond market trusts an unbuilt data center more than the neocloud that rents it

Replication code and data for the blog post of the same name (Aadhav Rajesh, October 5, 2026):
<https://www.aadhavrajesh.com/posts/bond-market-neoclouds/>

The post asks whether lenders to a data center that CoreWeave rents price it like a loan to CoreWeave. It compares Applied Digital's bonds (paid from CoreWeave leases) with CoreWeave's own bonds, first at issue and then week by week in the secondary market.

## What you can and cannot reproduce

| Part of the post | Needs | Reproducible from this repo? |
|---|---|---|
| Terms and spreads at issue (Table 1) | SEC filings, Treasury yields, FRED | Yes. Run `./run_all.sh`. |
| Weekly spreads, echo regression, placebo test, charts | FINRA trade history | Only after you export the trades yourself (see "FINRA trade data"). The trade files are not in the repo. |

FINRA's terms do not allow redistribution of the trade files, and ICE restricts reproduction of its index series. The repo publishes the code, the CUSIPs, the date ranges and the SHA-256 hashes (`data/bond_trades/provenance.csv`), so you can check that your export is the same data.

## Requirements

- Python 3.9 or later. The pipeline uses the standard library only.
- `matplotlib` for `make_charts.py` and `make_interactive.py` (`pip install matplotlib`). The interactive figures load plotly.js from a CDN in the reader's browser, so Python needs no plotly package.
- Internet access to sec.gov, treasury.gov and fred.stlouisfed.org for the first run. Later runs can use `--offline`.
- A contact string for the SEC, which requires a descriptive User-Agent:

```bash
export SEC_USER_AGENT="Your Name your@email.com"
```

## Quick start

```bash
git clone https://github.com/aadhavr/guarantee-prices.git
cd guarantee-prices
export SEC_USER_AGENT="Your Name your@email.com"
./run_all.sh              # download sources, verify, calculate
./run_all.sh --offline    # rerun from sources/cache and sources/manual only
```

`run_all.sh` runs these steps in order. Without trade files in `data/bond_trades/`, it finishes step 5 and prints a message that the event study is skipped.

| Step | Script | What it does | Output (in `output/`, not committed) |
|---|---|---|---|
| 1 | `fetch_treasury.py` | Treasury par yield curve for each year in `data/deals.csv` | `data/treasury_cmt.csv` |
| 2 | `fetch_market.py` | ICE BofA high-yield OAS indexes from FRED, on each pricing and event date | `data/market_index.csv` |
| 3 | `verify_sources.py` | Downloads every source in `data/evidence.csv` and checks each value (rules below) | `verification.csv` |
| 4 | `spreads.py` | Yield and spread at issue, using only values that passed. Deals with an unverified value go to `excluded.csv` | `spreads.csv`, `floating.csv`, `excluded.csv` |
| 5 | `relative_spreads.py` | Each spread minus the high-yield index, and the same-week pairs in `data/pairs.csv` | `relative_spreads.csv`, `pairs.csv` |
| 6 | `bond_event_study.py` | Difference in differences around the 2026-03-30 lease move, with a placebo test on every other date | `placebo_LEASE_MOVE.csv` and printed estimates |
| 7 | `spread_timeseries.py` | Weekly spread of each bond in `data/series.csv`, the high-yield index, and the gap to the tenant's bond | `spread_weekly.csv`, `spread_weekly.svg` |
| 8 | `beta_break.py` | Echo regression: weekly change in the building bond's spread on the tenant's, before and after the break | `beta_break.csv`, `sensitivity_compare.csv` |

Steps 6 to 8 run only when trade files exist. After `run_all.sh`, make the figures:

```bash
python3 make_charts.py        # static PNG charts and tables -> output/charts/
python3 make_interactive.py   # the four interactive figures -> output/interactive/
```

## FINRA trade data

FINRA's public bond page has no export, and 144A trade history cannot be downloaded by script without a data agreement. The trade files used in the post were collected from FINRA's bond pages with `finra_console_scraper.js`.

1. Open the bond's page on FINRA's site and accept the user agreement.
2. Run `finra_console_scraper.js` in your browser console. Instructions are at the top of the file. It repeats the page's own request, 50 trades per page, with a pause between pages, and downloads one JSON file.
3. Convert and record it:

```bash
python3 convert_trades.py data/bond_trades/raw/APLD_2030_finra_raw.json --cusip 00202DAA5
```

The converter checks that no page is missing, removes trades repeated across pages, checks the date range, parses capped sizes such as "1MM+", writes `data/bond_trades/<deal_id>.csv`, and records the SHA-256 of the raw file and the CSV in `provenance.csv`. The event study refuses any trade file whose hash changed after it was recorded.

Collected for the post: trades from 2025-11-13 to 2026-10-02, six bonds.

| deal_id | Bond | CUSIP |
|---|---|---|
| APLD_2030 | Applied Digital 9.250% 2030 | 00202DAA5 |
| CRWV_2030 | CoreWeave 9.250% 2030 | 21873SAB4 |
| APLD_2031B | Applied Digital 7.000% 2031 (Building 4) | 03790NAA5 |
| CRWV_2032_USD | CoreWeave 9.625% 2032 | 21873SAK4 |
| APLD_2031A | Applied Digital 6.750% 2031 | 03772CAA1 |
| WULF_2030 | TeraWulf 7.750% 2030 | 982911AA7 |

`data/series.csv` also lists `CIFR_2030` (Cipher 7.125% 2030). It has no trade file, so the pipeline skips it in steps 6 to 8. It is used in the issue-date comparison only.

FINRA can correct or add reports after your export, so a new export may not match the recorded hash exactly. If it differs, compare the trade counts and date range first.

## Where the numbers in the post come from

| In the post | Script | Output |
|---|---|---|
| Table 1: spreads at issue, same-week pairs (294 bp, 264 bp) | `spreads.py`, `relative_spreads.py` | `spreads.csv`, `pairs.csv` |
| Figure 1: weekly spreads | `spread_timeseries.py` | `spread_weekly.csv` |
| Figure 2 and the appendix: echo before and after (0.47 to 0.10), comparison bonds | `beta_break.py` | `beta_break.csv`, `sensitivity_compare.csv` |
| Figure 3: twin bonds, same coupon | `make_charts.py`, `make_interactive.py` | `charts/`, `interactive/` |
| Placebo test (183 dates, 27%) | `bond_event_study.py` | `placebo_LEASE_MOVE.csv` |
| Figure 4: dollars per megawatt | `make_charts.py` | `charts/chart4_per_mw.png` |

Figure 4 uses two constants typed at the top of `make_charts.py`: $2.35 billion of debt and 250 MW of CoreWeave leases. Both come from Applied Digital's filings, cited in the post (notes 15 and 4).

## Data rules

- `data/deals.csv`: the terms of each security. A value is a claim until `verify_sources.py` passes it.
- `data/evidence.csv`: one row per value. `token` is the exact text that must appear in `evidence`. `evidence` is an exact, contiguous quote from `source_url` with no "...". Matching ignores HTML tags, entities, quote style and whitespace.
- For each row the script checks that the evidence is in the source, the token is in the evidence, the token parses to the value, and the value equals the field in `deals.csv`.
- Primary sources only: SEC filings, then the company's own press release. No estimates. A value without a passing evidence row is not used.
- Four deals have `include = N` in `deals.csv` and are not used: `CIFR_2030_TAP` (add-on, no new comparison), `CRWV_2032_EUR` (euro bond), `LAMBDA_TLB` (private company, no filing), `CRWV_2031_9` (control bond, evidence incomplete).
- Excluded by design: convertible notes (the coupon includes an equity option) and euro notes.

### Sites that block scripts

Company investor-relations pages and GlobeNewswire can refuse scripted downloads. If a row shows ERROR, open the URL in a browser, save the page as HTML, and put it in `sources/manual/` under the key printed by:

```bash
python3 -c "from common import url_key; print(url_key('PASTE_URL'))"
```

Then run `./run_all.sh --offline`.

## Methods

- **Yield:** bond-equivalent (semiannual) yield from dated cash flows at the issue price, with the first coupon pro-rated from the pricing date.
- **Spread:** yield minus the Treasury par yield interpolated at the life of the cash flows on the pricing date.
- **Amortizing notes below par:** the indenture schedule is not in the verified data, so the scripts report two bounds: all principal at maturity, and all principal at the first amortization date. Any real schedule gives a yield between them. Notes issued at par yield the coupon whatever the schedule. The post reports the conservative end.
- **Event study:** difference in differences on secondary-market spreads, with windows of 10 calendar days before and after the event in `data/events.csv`. The event date must be proved in the source text. The placebo repeats the estimate at every date in the trade sample more than 20 days from the event, with at least 3 trade days in each window. Placebo windows overlap, so the shares are ranks, not exact p-values.
- **Echo regression:** weekly changes of the building bond's spread on weekly changes of the tenant's spread and the high-yield index, with every term interacted with a post-break dummy. Newey-West standard errors (Bartlett weights, small-sample factor n/(n-k)) at lags 2, 4 and 8. P-values use the normal approximation, so with about 45 weeks read them as approximate.
- **Break date:** the default break is the 2026-03-30 lease move. A scan over break dates shows the best-fitting date depends on one week, so the date of the change is not identified. Report the change, not the date. Use `--break YYYY-MM-DD` to test another date.

## Maintenance tools

Run these by hand. `run_all.sh` does not call them.

- `find_evidence.py`: searches the issuer's 8-K, 10-Q and 10-K filings for values that have not passed. Writes `output/evidence_candidates.csv`.
- `accept.py` and `accept_commands.sh`: copy one reviewed candidate into `data/evidence.csv` and fill the value in `data/deals.csv`.
- `manual_evidence.py`: show text around a pattern in a source, and add an evidence row by hand.
- `search_deals.py`: EDGAR full-text search for more AI data center and GPU financings. Output goes to `output/candidate_deals.csv` for review by hand.
- `record_trades.py`: record the provenance of a hand-saved trade file.

## Limits

- Six bonds and one tenant.
- FINRA 144A trades can be thin. `spread_weekly.csv` shows the number of trade days behind each weekly value.
- The index series from ICE is not in the repo. Publish derived numbers, not the series.
