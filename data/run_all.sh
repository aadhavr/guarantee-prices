#!/usr/bin/env bash
# Full pipeline. Python 3.9+, standard library only.
#   export SEC_USER_AGENT="Your Name your@email.com"
#   ./run_all.sh            # download, verify, calculate
#   ./run_all.sh --offline  # use sources/cache and sources/manual only
# Manual tools (not run here): find_evidence.py (task 1), search_deals.py (task 3),
# record_trades.py (task 4 provenance).
set -u
cd "$(dirname "$0")"
mkdir -p output
python3 fetch_treasury.py "$@"      || { echo "Treasury download failed"; exit 1; }
python3 fetch_market.py "$@"        || { echo "market index download failed (or a date is missing)"; exit 1; }
python3 verify_sources.py "$@"
echo "(verification failures exclude rows; see output/verification.csv)"
python3 spreads.py                  || exit 1
python3 relative_spreads.py         || exit 1
if ls data/bond_trades/*.csv 2>/dev/null | grep -qv provenance; then
  python3 bond_event_study.py "$@"
  python3 spread_timeseries.py "$@"
else
  echo "no trade files in data/bond_trades/: event study skipped"
fi
