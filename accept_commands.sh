# Reviewed candidates. Run right AFTER a full search:  python3 find_evidence.py
# Each accept prints the sentence it copies: read it. If a command says
# "several candidates match", read them and rerun it with --index N.

python3 accept.py --deal APLD_2031B --field maturity_date --value 2031-06-15
python3 accept.py --deal WULF_2030 --field maturity_date --value 2030-10-15
python3 accept.py --deal CRWV_2031A --field pricing_date --value 2026-04-09
python3 accept.py --deal CRWV_2031A_TAP --field pricing_date --value 2026-04-16
python3 accept.py --deal CRWV_2032_USD --field pricing_date --value 2026-06-11

# Loans: the 8-K dates (credit agreements) replace the press-release closing dates
python3 accept.py --deal CRWV_DDTL4 --field pricing_date --value 2026-03-30 --replace
python3 accept.py --deal CRWV_DDTL4 --field sofr_spread_bp --value 225 --replace
python3 accept.py --deal CRWV_DDTL5 --field pricing_date --value 2026-05-15 --replace
python3 accept.py --deal CRWV_DDTL5 --field sofr_spread_bp --value 450
