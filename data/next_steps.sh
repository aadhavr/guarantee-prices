# Next steps, in order. Run from the project folder:  sh data/next_steps.sh
# A command that finds no candidate, or several, stops with a message and changes
# nothing; the other commands still run. Read what each accept prints.

# 1. Searches (candidates of other deals are kept between runs)
python3 find_evidence.py
python3 find_evidence.py --deal APLD_2031A --months 6
python3 find_evidence.py --deal CRWV_2030 --start 2025-04-01 --months 3

# 2. Accepts reviewed on 2026-09-28
python3 accept.py --deal APLD_2031B --field maturity_date --value 2031-06-15 --contains "2031 7.000% Notes will mature"
python3 accept.py --deal CRWV_2031A_TAP --field pricing_date --value 2026-04-16 --contains "announcing the pricing"
python3 accept.py --deal CRWV_2032_USD --field pricing_date --value 2026-06-11
python3 accept.py --deal CRWV_2030 --field pricing_date --value 2025-05-21
python3 accept.py --deal CRWV_2030 --field coupon_pct --value 9.250
python3 accept.py --deal CRWV_2030 --field maturity_date --value 2030-06-01
python3 accept.py --deal CRWV_2030 --field issue_price --value 100
# loans: the 8-K dates (credit agreements) replace the press-release closing dates
python3 accept.py --deal CRWV_DDTL4 --field pricing_date --value 2026-03-30 --replace
python3 accept.py --deal CRWV_DDTL4 --field sofr_spread_bp --value 225
python3 accept.py --deal CRWV_DDTL5 --field pricing_date --value 2026-05-15 --replace

# 3. Exclude the Cipher add-on: same series as CIFR_2030, one week later; adds no comparison
python3 - << 'PY'
import csv
rows = list(csv.DictReader(open("data/deals.csv")))
for r in rows:
    if r["deal_id"] == "CIFR_2030_TAP":
        r["include"] = "N"
        r["note"] = "add-on to CIFR_2030 (same series, priced one week later); excluded: no new comparison"
w = csv.DictWriter(open("data/deals.csv", "w", newline=""), fieldnames=list(rows[0].keys()))
w.writeheader(); w.writerows(rows)
print("CIFR_2030_TAP excluded")
PY

# 4. Pipeline
sh run_all.sh
