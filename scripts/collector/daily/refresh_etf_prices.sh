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
# launchd also fires this job during the short background wakes of a sleeping laptop.
# The Mac goes back to sleep seconds later and the Barchart login times out across the
# gap (9, 10 and 12 Nov 2026). So the script first waits for a full wake, which it
# reads from the "Graphics" capability in `pmset -g systemstate`. caffeinate cannot
# hold a lid-closed laptop awake. If the Mac sleeps during a fetch that then fails,
# the fetch is retried after the next full wake.
#
# --merge keeps the dates the feed has rolled off, and it refuses to write when an
# existing date's close has changed.
#
# Exit: 0 = refreshed, or gave up waiting (for a wake or for another job); otherwise
# the fetch's own exit code.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT" || exit 1

TICKERS="SPY,QQQ,IWM,HYG,TLT,GLD"
MAX_WAIT="${ETF_PRICE_MAX_WAIT:-28800}"
MAX_WAKE_WAIT="${ETF_PRICE_MAX_WAKE_WAIT:-72000}"   # wall-clock; ends before the next 07:17
MAX_TRIES=3
BUSY='[s]tudy_legs/fetch_|[c]ollector/history/fetch_|[s]crape_flow|[s]cripts\.backtest|[d]aily_loop'

mkdir -p backtests/run_logs
LOG="backtests/run_logs/etf-prices-$(date +%Y%m%d).log"
exec >>"$LOG" 2>&1
echo "=== start $(date '+%F %T')"

START=$(date +%s)

capabilities() { pmset -g systemstate 2>/dev/null | sed -n 's/^Current System Capabilities are: //p'; }
is_awake() { capabilities | grep -q Graphics; }
last_sleep() { sysctl -n kern.sleeptime 2>/dev/null | sed -n 's/^{ sec = \([0-9]*\).*/\1/p'; }

# Block until the Mac is fully awake. `sleep` does not count time spent asleep, so the
# give-up test uses the wall clock.
wait_awake() {
  is_awake && return 0
  echo "not fully awake at $(date '+%F %T') (capabilities: $(capabilities)); waiting for a full wake"
  while ! is_awake; do
    if [ $(( $(date +%s) - START )) -ge "$MAX_WAKE_WAIT" ]; then
      echo "GAVE UP at $(date '+%F %T'): no full wake since the start. Next morning's run tries again."
      exit 0
    fi
    sleep 15
  done
  echo "fully awake at $(date '+%F %T') (capabilities: $(capabilities))"
}

wait_awake

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

try=1
while :; do
  wait_awake
  began=$(date +%s)
  python3 scripts/collector/history/fetch_underlying_ohlc.py --tickers "$TICKERS" --force --merge
  rc=$?
  [ "$rc" -eq 0 ] && break
  # Retry only when the Mac slept during the attempt. Any other failure (a refused
  # merge, a Barchart error) would fail the same way again.
  slept=$(last_sleep)
  if [ "$try" -ge "$MAX_TRIES" ] || [ "${slept:-0}" -lt "$began" ]; then
    break
  fi
  try=$((try + 1))
  echo "fetch failed rc=$rc after the Mac slept mid-run; attempt $try/$MAX_TRIES follows the next full wake"
done
python3 scripts/dashboard.py --quiet || echo "dashboard rebuild failed; prices are unaffected"
echo "=== end $(date '+%F %T') rc=$rc"
exit "$rc"
