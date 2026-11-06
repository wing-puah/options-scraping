#!/usr/bin/env bash
# Refresh the BaselineDaily export and the six ETFs' price files, then rebuild the
# dashboard pages. The export reads Sheets only, so it does not wait for Barchart.
#
# launchd runs this each morning (com.wing.options-etf-prices.plist in this folder).
# It waits for any other Barchart or backtest job to pause, because those jobs must
# not overlap. A long scrape leaves a gap of a few minutes between chunks, and this
# polls often enough to catch one. After ETF_PRICE_MAX_WAIT seconds it gives up, and
# the next morning's run tries again.
#
# --merge keeps the dates the feed has rolled off, and it refuses to write when an
# existing date's close has changed.
#
# Exit: 0 = refreshed, or gave up waiting; otherwise the fetch's own exit code.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT" || exit 1

TICKERS="SPY,QQQ,IWM,HYG,TLT,GLD"
MAX_WAIT="${ETF_PRICE_MAX_WAIT:-28800}"
BUSY='[s]tudy_legs/fetch_|[c]ollector/history/fetch_|[s]crape_flow|[s]cripts\.backtest|[d]aily_loop'

mkdir -p backtests/run_logs
LOG="backtests/run_logs/etf-prices-$(date +%Y%m%d).log"
exec >>"$LOG" 2>&1
echo "=== start $(date '+%F %T')"

# shellcheck disable=SC1091
source .venv/bin/activate
python3 scripts/export_tabs.py --tabs BaselineDaily || echo "export failed; the page keeps the last export"

waited=0
while pgrep -f "$BUSY" >/dev/null; do
  if [ "$waited" -ge "$MAX_WAIT" ]; then
    echo "GAVE UP after ${waited}s: another job is still running. Next morning's run tries again."
    python3 scripts/dashboard.py --quiet || echo "dashboard rebuild failed"
    exit 0
  fi
  sleep 30
  waited=$((waited + 30))
done
echo "clear to fetch after ${waited}s"

python3 scripts/collector/history/fetch_underlying_ohlc.py --tickers "$TICKERS" --force --merge
rc=$?
python3 scripts/dashboard.py --quiet || echo "dashboard rebuild failed; prices are unaffected"
echo "=== end $(date '+%F %T') rc=$rc"
exit "$rc"
