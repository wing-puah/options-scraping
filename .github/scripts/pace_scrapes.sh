#!/usr/bin/env bash
# Sleep to each target UTC time in $TIMES, running a flow scrape at each; then,
# if $UNUSUAL_TIME is set, sleep to it and run the unusual scrape.
#
# Times are UTC HHMM, space-separated (e.g. "1730 1830 1930"). A target already
# in the past fires immediately rather than being skipped — compile_flow.py
# dedupes snapshots, so an extra capture is harmless but a missing one is not.
#
# Deliberately NOT `set -e` on the scrape itself: one failed capture must not
# cost every later one. Failures surface as ::warning:: annotations.
set -uo pipefail

: "${TIMES:=}"
: "${UNUSUAL_TIME:=}"

now_hhmm() { date -u +%H%M; }

# Poll rather than compute a delta: no date-arithmetic or DST edge cases, and the
# 30s granularity is irrelevant against hourly targets.
sleep_until() {
  local target="$1"
  while [ "$((10#$(now_hhmm)))" -lt "$((10#$target))" ]; do
    sleep 30
  done
}

scrape() {
  local mode="$1" label="$2"
  echo "--- $(date -u +%H:%M) UTC — scraping --mode $mode ---"
  if python scripts/collector/scrape_flow.py --mode "$mode"; then
    echo "--- $(date -u +%H:%M) UTC — $mode scrape OK ---"
  else
    echo "::warning::$mode scrape for $label UTC failed; continuing"
  fi
}

for t in $TIMES; do
  echo "=== waiting for $t UTC (now $(date -u +%H:%M)) ==="
  sleep_until "$t"
  scrape flow "$t"
done

if [ -n "$UNUSUAL_TIME" ]; then
  echo "=== waiting for $UNUSUAL_TIME UTC (now $(date -u +%H:%M)) ==="
  sleep_until "$UNUSUAL_TIME"
  scrape unusual "$UNUSUAL_TIME"
fi

echo "=== pacemaker leg done at $(date -u +%H:%M) UTC ==="
