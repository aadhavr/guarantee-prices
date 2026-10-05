# The price of a Google guarantee

Who carries the credit risk of the AI buildout? Debt on AI data centers and GPU fleets, priced at issue, grouped by who stands behind it (Google backstop, investment-grade tenant, CoreWeave as tenant, CoreWeave itself).

## Run

Python 3.9+, standard library only.

```bash
export SEC_USER_AGENT="Aadhav Rajesh your@email.com"   # SEC requires a contact User-Agent
./run_all.sh              # download sources, verify, calculate
./run_all.sh --offline    # rerun from sources/cache and sources/manual only
```

Steps:

1. `fetch_treasury.py` downloads the Treasury par yield curve CSV for each year in `data/deals.csv` and writes `data/treasury_cmt.csv` (2/3/5/7-year yields on each pricing date).
2. `verify_sources.py` downloads every source in `data/evidence.csv` and checks, for each row: the evidence text is in the source; the token is in the evidence; the token parses to the value; the value equals the field in `data/deals.csv`. It also lists required values with no evidence row (MISSING). Output: `output/verification.csv`.
3. `spreads.py` uses only values that passed. Any deal with an unverified required value goes to `output/excluded.csv` with the reason. Outputs: `output/spreads.csv` (fixed rate), `output/floating.csv` (SOFR spreads), `output/excluded.csv`.

## Data rules

- `data/deals.csv`: terms of each security. Values here are claims until `verify_sources.py` passes them.
- `data/evidence.csv`: one row per value. `token` is the exact text that must appear in `evidence`; `evidence` is an exact, contiguous quote from `source_url` (no "..."). Matching ignores HTML tags, entities, quote style and whitespace.
- Primary sources first: SEC filings, then the company's own press release. Secondary sources are not used for values.
- No estimates. A value without a passing evidence row is not used.

## Sites that block scripts

Company investor-relations pages and GlobeNewswire can refuse scripted downloads. If a row shows ERROR, open the URL in a browser, save the page as HTML, and put it in `sources/manual/` named with the key printed by:

```bash
python3 -c "from common import url_key; print(url_key('PASTE_URL'))"
```

Then run `./run_all.sh --offline`.

## Methods

- Yield: bond-equivalent (semiannual) yield from dated cash flows at the issue price, first coupon pro-rated from the pricing date.
- Amortizing notes issued below par: the indenture schedule is not in the verified data, so the script reports two bounds (all principal at maturity; all principal at the first amortization date). Any real schedule gives a yield between the two. Notes issued at par yield the coupon whatever the schedule.
- Spread: yield minus the Treasury par yield interpolated at the life of the cash flows on the pricing date.
- Excluded by design: convertible notes (coupon includes an equity option); EUR notes (compare with Bunds).

## Status before first local run

Fully evidenced from SEC filings: `APLD_2030` (CoreWeave tenant) and `CIFR_2030` (Google backstop). This pair is the November 2025 comparison.

Open items. Add an evidence row for each, then rerun:

| Deal | Missing | Where to find it |
|---|---|---|
| WULF_2030 | maturity date | TeraWulf 8-K for the notes closing (indenture) |
| APLD_2031A | maturity date, first amortization date | Applied Digital 8-K, 2026-03-10, exhibit 4.1 |
| APLD_2031B | maturity date; whether the Building 4 Lease moved to CoreWeave Compute Acquisition Co. VIII | Applied Digital 8-K for the June 2026 closing; next 10-Q |
| CRWV_2031A, CRWV_2031A_TAP, CRWV_2032_USD | pricing date | CoreWeave 8-K for each offering (the IR pages may show the date once downloaded) |
| CIFR_2030_TAP | pricing date, 100.250% issue price, first amortization date | Cipher 8-K exhibit 99.1 for the add-on pricing |
| CRWV_DDTL4 | SOFR spread, borrower, customer | CoreWeave 8-K for DDTL 4.0 (credit agreement) |
| CRWV_DDTL5 | pricing date, SOFR spread | CoreWeave 8-K, 2026-05-18 |
| LAMBDA_TLB | pricing date, SOFR spread | lender, agent or rating agency release (Lambda is private) |

Also needed for the write-up (not in the pipeline yet): a high-yield credit index on the pricing dates, so a change between November 2025 and June 2026 is not read as CoreWeave-specific when the whole market moved.

## Tools for the next steps

Run these by hand; `run_all.sh` runs everything else.

**1. Close open items: `find_evidence.py`**
Reads `output/verification.csv`, and for each required value that has not passed, searches the issuer's 8-K, 10-Q and 10-K filings around the pricing date. Only sentences that contain the security's coupon count, so a match belongs to the right notes. Output: `output/evidence_candidates.csv`. Nothing is added automatically: confirm each candidate in the source, copy the row into `data/evidence.csv`, put the value in `data/deals.csv`, rerun.
```bash
python3 find_evidence.py                    # all open items
python3 find_evidence.py --deal APLD_2031B  # one deal
```
Needs the `ticker` column in `data/deals.csv`. Private issuers (Lambda) are not on EDGAR.

**2. Market control: `fetch_market.py` then `relative_spreads.py`** (both in `run_all.sh`)
Downloads ICE BofA high-yield OAS indexes from FRED for each pricing date and event date (`data/market_index.csv`), then writes each spread minus the index (`output/relative_spreads.csv`) and the same-week pairs defined in `data/pairs.csv` (`output/pairs.csv`). The old group summary was removed because it mixed deals from different periods. License: ICE restricts reproduction of the index; publish derived numbers, not the series. Check the FRED series notes.

**3. More deals: `search_deals.py`**
EDGAR full-text search over 8-Ks for AI data center and GPU financings, then extraction of coupon, price, size and SOFR margin from sentences that price or close a deal. Output: `output/candidate_deals.csv`, with `already_in_panel` marked. Review by hand; add accepted deals to `data/deals.csv` (with `ticker`), then use `find_evidence.py`.
```bash
python3 search_deals.py --start 2025-01-01 --end 2026-09-30
```

**4. Event test: `bond_event_study.py`** (run by `run_all.sh` when trade files exist)
Difference in differences on secondary-market spreads around an event in `data/events.csv`: treated bond (APLD_2030, paid from CoreWeave leases) against control bond (CRWV_2030, CoreWeave's own notes), windows of 10 calendar days before and after.
- The event date must be proved: `evidence` must be in the source and `date_token` in the evidence.
- Both bonds need verified coupon and maturity. CRWV_2030 is in `deals.csv` as a control only; find its terms with `python3 find_evidence.py --deal CRWV_2030`.
- Trade data: FINRA trade history for 144A notes is not downloadable by script without a data agreement. Export the trades by hand from FINRA's bond pages, save as `data/bond_trades/<deal_id>.csv` with columns `trade_date` (YYYY-MM-DD), `price`, optional `quantity`, then record provenance right away:
```bash
python3 record_trades.py APLD_2030 <CUSIP> "FINRA bond trade history, exported by hand"
```
  The event study refuses any trade file whose SHA-256 changed after it was recorded.
- Timing caveat: the leases moved on 2026-03-30 (10-K), but the market may have learned later. Add a second event with the first public disclosure date once you find it in an 8-K.

**5. Spreads on the same dates: `spread_timeseries.py`** (run by `run_all.sh` when trade files exist)
Weekly spread over Treasuries for each bond in `data/series.csv`, from the FINRA trade files, plus the HY index and the gap between the `building` bond and the `tenant` bond. Outputs: `output/spread_weekly.csv` (with the number of trade days behind each weekly value) and `output/spread_weekly.svg` (open in a browser). It prints the first week in which the building bond priced tighter than the tenant's own bond. Add rows to `data/series.csv` to plot more bonds (each needs a recorded trade file and verified coupon and maturity).
