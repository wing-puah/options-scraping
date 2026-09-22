#!/bin/bash
# Unattended resume loop for backfill_chain.py (operator request 2026-09-22: "if it is
# interrupted there is a way to pick up from where it left without me running anything").
#
# Run it on a timer: a launchd user agent every 30 min (operator-installed), or a loop in a
# terminal: `while true; do scripts/collector/backfill_supervisor.sh; sleep 1800; done`. Each tick:
#   - DONE or HALT marker present      -> exit (nothing to do / needs the operator)
#   - collector already running        -> exit (its own flock would refuse a second run anyway)
#   - inside a cooldown window         -> exit
#   - otherwise run one --execute pass under caffeinate; the manifest makes it resume exactly
#     where the last pass stopped. Then classify how it ended:
#       nothing left to fetch           -> backup push, DONE marker, notify
#       HTTP 401/403/429 or login fail  -> cooldown 2h; 3 blocked passes in a row -> HALT + notify
#       broken pass (no done line = crash, write error, nothing attempted, or the collector's
#       own consecutive-no_bars stop -- 3 of those in a row is what a Barchart date-handling
#       regression looks like, so it halts on purpose rather than marking more real contracts
#       no_bars)
#                                       -> cooldown 15 min; 3 broken passes in a row -> HALT + notify
#       other stop (fail-stop, no-bars, sleep/timeouts) -> cooldown 15 min
#       >= BACKUP_EVERY new files since the last backup -> backup push
#
# Remove state/HALT to let it continue; remove state/DONE (or change SYMBOLS) to start a new job.
# Never edit this file in place while a pass runs (bash reads scripts as it executes):
# write a copy and mv it over.
set -u
ROOT="$HOME/claude_playground/options-trading"
PY="$ROOT/.venv/bin/python"
STATE="$ROOT/backtests/backfill_supervisor"
LOGDIR="$ROOT/logs/backfill"
SYMBOLS="${BACKFILL_SYMBOLS:-SPY}"
FROM="${BACKFILL_FROM:-2022-02-01}"
TO="${BACKFILL_TO:-2026-09-18}"
BACKUP_EVERY=1000
mkdir -p "$STATE" "$LOGDIR"
say() { echo "$(date '+%F %T') $*" >> "$STATE/supervisor.log"; }
notify() { osascript -e "display notification \"$1\" with title \"Barchart backfill\"" 2>/dev/null; say "NOTIFY: $1"; }
# Integer state files: anything missing or non-numeric reads as 0; writes are tmp + mv.
getn() { local v; v=$(cat "$STATE/$1" 2>/dev/null); [[ $v =~ ^[0-9]+$ ]] || v=0; echo "$v"; }
putn() { echo "$2" > "$STATE/$1.tmp" && mv "$STATE/$1.tmp" "$STATE/$1"; }
halt() { echo "$1" > "$STATE/HALT"; notify "HALTED: $1. Remove $STATE/HALT to resume."; exit 0; }

[ -f "$STATE/HALT" ] && exit 0
[ -f "$STATE/DONE" ] && [ "$(cat "$STATE/DONE")" = "$SYMBOLS $FROM $TO" ] && exit 0
pgrep -f "python.*scripts/collector/backfill_chain.py" >/dev/null && exit 0
[ "$(date +%s)" -lt "$(getn cooldown_until)" ] && exit 0

cd "$ROOT" || exit 1
run_log="$LOGDIR/run-$(date +%Y%m%d-%H%M%S).log"
say "start pass: $SYMBOLS $FROM..$TO -> $run_log"
caffeinate -i "$PY" scripts/collector/backfill_chain.py --symbols "$SYMBOLS" \
    --from "$FROM" --to "$TO" --execute > "$run_log" 2>&1
rc=$?
done_line=$(grep -E "backfill_chain.main\]  done:" "$run_log" | tail -1)
st() { local v; v=$(echo "$done_line" | sed -nE "s/.*[[:space:]]$1=([0-9]+).*/\1/p"); echo "${v:-0}"; }
fetched=$(st fetched)
attempted=0; for k in fetched failed unparsed no_bars exists unavailable; do attempted=$(( attempted + $(st $k) )); done
say "pass ended rc=$rc :: ${done_line#*done: }"

since=$(( $(getn since_backup) + fetched ))
putn since_backup "$since"
backup() {
    if "$PY" scripts/backup_research_caches.py push >> "$STATE/supervisor.log" 2>&1; then
        putn since_backup 0; say "backup pushed"
    else
        notify "cache backup to Drive FAILED - see supervisor.log"
    fi
}

if grep -q "Nothing to fetch" "$run_log"; then
    [ "$since" -gt 0 ] && backup
    counts=$("$PY" scripts/collector/backfill_chain.py --symbols "$SYMBOLS" --from "$FROM" \
             --to "$TO" 2>&1 | grep -iE "partial|pending" | tail -3 | tr '\n' ' ')
    echo "$SYMBOLS $FROM $TO" > "$STATE/DONE"
    rm -f "$STATE/blocked_count" "$STATE/broken_count" "$STATE/cooldown_until"
    say "final plan counts: $counts"
    notify "$SYMBOLS backfill complete. $counts (unavailable: see manifest)"
    exit 0
fi

[ "$since" -ge "$BACKUP_EVERY" ] && backup

if echo "$done_line" | grep -qE "stopped_http_(401|403|429)|login_failure" \
   || grep -q "login failed" "$run_log"; then
    n=$(( $(getn blocked_count) + 1 )); putn blocked_count "$n"
    [ "$n" -ge 3 ] && halt "Barchart blocked/throttled $n passes in a row; last log $run_log"
    putn cooldown_until $(( $(date +%s) + 7200 ))
    say "blocked ($n/3) - cooling down 2h"
elif [ -z "$done_line" ] || echo "$done_line" | grep -qE "stopped_write_error|stopped_consecutive_no_bars" \
     || [ "$attempted" -eq 0 ]; then
    n=$(( $(getn broken_count) + 1 )); putn broken_count "$n"
    [ "$n" -ge 3 ] && halt "pass broke $n times in a row (crash, write error or nothing attempted); last log $run_log"
    putn cooldown_until $(( $(date +%s) + 900 ))
    say "broken pass ($n/3) - cooling down 15 min"
else
    rm -f "$STATE/broken_count"
    [ "$fetched" -gt 0 ] && rm -f "$STATE/blocked_count"
    putn cooldown_until $(( $(date +%s) + 900 ))
fi
exit 0
