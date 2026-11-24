#!/usr/bin/env bash
# Start the GitHub Flow Pacemaker from the laptop, on time. GitHub's 10:00 UTC
# cron fires 8-12h late (2026-11: 18:25-21:56 UTC), after most of the scrape
# window. launchd runs this at 22:30 SGT (14:30 UTC) on weeknights
# (com.wing.flow-pacemaker-kick.plist) so a run is up before the 15:00 UTC scrape.
#
#   bash scripts/pacemaker/kick_github.sh [--dry-run]
#   make pacemaker-kick [DRY=1]
#
# It only DISPATCHES the workflow; it never scrapes locally. Steps:
#   1. pacemaker_gate.py: not an NYSE session (ET date) -> exit 0.
#   2. a run created today (UTC) that is queued, running or succeeded -> exit 0.
#      The workflow's own gate makes a double dispatch harmless; this keeps it quiet.
#   3. gh workflow run, retried 3x 2 min apart (a just-woken laptop may lack network).
#   4. confirm a workflow_dispatch run from today appears.
# On failure: log, macOS notification, exit 1. Log: backtests/run_logs/pacemaker-kick.log
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DRY=0
case "${1-}" in
  --dry-run) DRY=1 ;;
  "") ;;
  -h|--help) sed -n '2,16p' "${BASH_SOURCE[0]}"; exit 0 ;;
  *) echo "unknown flag: $1" >&2; exit 2 ;;
esac

WF=flow-pacemaker.yml
mkdir -p backtests/run_logs
LOG=backtests/run_logs/pacemaker-kick.log
log() { echo "$(date '+%F %T %Z') $*" | tee -a "$LOG"; }
fail() {
  log "FAILED: $*"
  osascript -e "display notification \"$*\" with title \"Flow pacemaker kick failed\"" >/dev/null 2>&1 || true
  exit 1
}

if [ -z "${VIRTUAL_ENV:-}" ] && [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# 1. session gate
gate="$(python .github/scripts/pacemaker_gate.py)" || fail "pacemaker_gate.py errored"
reason="$(echo "$gate" | sed -n 's/^reason=//p')"
if ! echo "$gate" | grep -qx 'open=true'; then
  log "$reason - no kick."; exit 0
fi

# 2. already covered today? Same test as the workflow's dupe step, on the UTC date.
today="$(date -u +%F)"
covered() {
  gh run list --workflow "$WF" --limit 30 --json databaseId,createdAt,status,conclusion,event \
    --jq "[.[] | select(.createdAt | startswith(\"$today\"))
               | select(.status != \"completed\" or .conclusion == \"success\")
               | \"\(.databaseId) \(.event) \(.status)\"] | join(\", \")"
}
existing="$(covered)" || fail "gh run list failed (auth or network?)"
if [ -n "$existing" ]; then
  log "$reason; already covered by run(s): $existing - no kick."; exit 0
fi

if [ "$DRY" = 1 ]; then
  log "DRY RUN: $reason, no run yet today - would run: gh workflow run $WF --ref main"
  exit 0
fi

# 3. dispatch
ok=0
for attempt in 1 2 3; do
  if gh workflow run "$WF" --ref main >>"$LOG" 2>&1; then ok=1; break; fi
  log "dispatch attempt $attempt failed"
  [ "$attempt" -lt 3 ] && sleep 120
done
[ "$ok" = 1 ] || fail "gh workflow run $WF failed 3 times"

# 4. confirm
for _ in $(seq 1 18); do
  sleep 5
  run="$(covered || true)"
  if [ -n "$run" ]; then log "$reason; dispatched: $run"; exit 0; fi
done
fail "dispatched $WF but no run from $today appeared within 90s"
