python3 accept.py --deal WULF_2030 --field maturity_date --value 2030-10-15
python3 accept.py --deal CRWV_2031A --field pricing_date --value 2026-04-09
python3 accept.py --deal CRWV_DDTL5 --field sofr_spread_bp --value 450
python3 accept.py --deal APLD_2031B --field maturity_date --value 2031-06-15 --contains '2031 7.000% Notes will mature'
python3 accept.py --deal CRWV_2031A_TAP --field pricing_date --value 2026-04-16 --contains 'announcing the pricing'
python3 accept.py --deal CRWV_2030 --field maturity_date --value 2030-06-01
python3 accept.py --deal CRWV_DDTL4 --field pricing_date --value 2026-03-30 --replace
python3 accept.py --deal CRWV_DDTL4 --field sofr_spread_bp --value 225
python3 accept.py --deal CRWV_DDTL5 --field pricing_date --value 2026-05-15 --replace
python3 accept.py --deal CRWV_2030 --field pricing_date --value 2025-05-21 --contains 'issued a press release announcing the pricing'
python3 accept.py --deal CRWV_2030 --field coupon_pct --value 9.250 --index 12
python3 accept.py --deal CRWV_2030 --field issue_price --value 100 --contains 'general senior unsecured obligations'
python3 accept.py --deal APLD_2031A --field maturity_date --value 2031-03-15
python3 manual_evidence.py add --deal CRWV_2032_USD --field pricing_date --value 2026-06-11 --token 'June 11, 2026' --url https://investors.coreweave.com/news/news-details/2026/CoreWeave-Announces-Pricing-of-1-25-Billion-of-Senior-Notes-and-2-Billion-of-Senior-Notes/default.aspx --source-type 'company press release' --evidence 'Senior Notes June 11, 2026 LIVINGSTON, N.J.--(BUSINESS WIRE)-- CoreWeave, Inc.'
python3 manual_evidence.py add --deal APLD_2031B --field support --value 'completion guarantee only' --token 'customary completion guarantee' --url https://www.sec.gov/Archives/edgar/data/1144879/000149315226028899/form8-k.htm --source-type 'SEC 8-K' --evidence 'The Company has provided a customary completion guarantee with respect to each Project'
