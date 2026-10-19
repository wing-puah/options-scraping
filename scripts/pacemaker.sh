#!/usr/bin/env bash
# The flow pacemaker, on the laptop: one run paces one NYSE session's scrapes
# and then compiles the day. The GitHub twin is .github/workflows/flow-pacemaker.yml;
# run this when Actions is down or dropping its crons.
#
#   ./scripts/pacemaker.sh [--dry-run] [--force] [--skip-compile]
#                          [--flow-times "1500 1600 ..."] [--unusual-time 2200|""]
#   make pacemaker [ARGS="--force"]
#
# Start it any time before the window (18:00 SGT is the GitHub cron) and leave
# the terminal open; it sleeps to each scrape time and runs the scraper in
# process. Times are UTC HHMM. Defaults match the workflow: flow scrapes hourly
# 1500-2100 UTC (23:00-05:00 SGT), the unusual scrape at 2200 UTC (06:00 SGT).
# A start later than a scrape time fires that scrape at once — compile_flow.py
# dedupes snapshots, so a late start costs coverage, not data.
#
# Differences from the workflow, on purpose:
#   - ONE leg, not two: a laptop has no 6-hour job limit.
#   - Compile is INCLUDED (--skip-compile to drop it): the nightly Compile Flow
#     workflow is also down when Actions is, so the day would otherwise sit as
#     raw snapshots on Drive. Same four steps as compile-flow.yml, same bounds.
#   - The gate is local: refuses a non-session day (pacemaker_gate.py, ET date),
#     a second pacemaker process, or a day already stamped done in
#     backtests/run_logs/. --force overrides the stamp, never the process check.
#   - caffeinate -is holds the Mac awake on AC; on battery a closed lid still
#     sleeps, and the poll loop then fires every missed scrape on wake.
# The pacing loop itself is .github/scripts/pace_scrapes.sh, shared with the
# workflow so the two never disagree about what a target already in the past
# means. Exit: 3 = another pacemaker is running; 4 = no session / already done.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ORIG_ARGS=("$@")   # the parse loop consumes $@; the caffeinate re-exec needs the originals
DRY=0; FORCE=0; SKIP_COMPILE=0
FLOW_TIMES="${FLOW_TIMES-1500 1600 1700 1800 1900 2000 2100}"
UNUSUAL_TIME="${UNUSUAL_TIME-2200}"
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --force) FORCE=1 ;;
    --skip-compile) SKIP_COMPILE=1 ;;
    --flow-times) shift; FLOW_TIMES="${1-}" ;;
    --flow-times=*) FLOW_TIMES="${1#--flow-times=}" ;;
    --unusual-time) shift; UNUSUAL_TIME="${1-}" ;;
    --unusual-time=*) UNUSUAL_TIME="${1#--unusual-time=}" ;;
    -h|--help) sed -n '2,29p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
  shift
done

for t in $FLOW_TIMES $UNUSUAL_TIME; do
  [[ "$t" =~ ^[0-9]{4}$ ]] || { echo "bad time (want UTC HHMM): $t" >&2; exit 2; }
done

if [ -z "${VIRTUAL_ENV:-}" ] && [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# ── the gate ───────────────────────────────────────────────────────────────────
gate="$(python .github/scripts/pacemaker_gate.py)"
reason="$(echo "$gate" | sed -n 's/^reason=//p')"
et_date="$(TZ=America/New_York date +%F)"
STAMP="backtests/run_logs/pacemaker-$et_date.done"

if ! echo "$gate" | grep -qx 'open=true'; then
  echo "$reason — nothing to scrape."; exit 4
fi
if [ -f "$STAMP" ] && [ "$FORCE" = 0 ]; then
  echo "REFUSED: $et_date already paced ($(cat "$STAMP")). --force to pace it again." >&2
  exit 4
fi
# Only on the first invocation: under the re-exec the caffeinate parent's command
# line carries this script's name and would match itself. $PPID is excluded for
# the same reason when make's shell is the parent.
if [ -z "${PACEMAKER_CAFFEINATED:-}" ]; then
  pid="$(pgrep -f '[p]acemaker\.sh' | grep -vx -e "$$" -e "$PPID" | head -n1 || true)"
  if [ -n "$pid" ]; then
    echo "REFUSED: a pacemaker is already running (PID $pid). One per day." >&2
    exit 3
  fi
fi

# ── the plan ───────────────────────────────────────────────────────────────────
COMPILE_CMDS=()
if [ "$SKIP_COMPILE" = 0 ]; then
  c_start="$(TZ=America/New_York date -v-3d +%F 2>/dev/null || TZ=America/New_York date -d '3 days ago' +%F)"
  COMPILE_CMDS+=(
    "python scripts/compile_flow.py --start $c_start --end $et_date --skip-existing"
    "python scripts/gc_flow.py --last 3"
    "python scripts/collector/daily/fetch_mech_regime.py"
    "python scripts/build_baseline.py --last 3"
  )
fi

if [ "$DRY" = 1 ]; then
  echo "DRY RUN (nothing executed). $reason."
  echo "now: $(date -u +%H:%M) UTC / $(date +'%H:%M %Z')"
  for t in $FLOW_TIMES; do echo "flow scrape    at $t UTC"; done
  [ -n "$UNUSUAL_TIME" ] && echo "unusual scrape at $UNUSUAL_TIME UTC"
  for c in "${COMPILE_CMDS[@]+"${COMPILE_CMDS[@]}"}"; do echo "then: $c"; done
  exit 0
fi

# Idle-sleep guard: re-run this script under caffeinate, logging happens inside.
if [ -z "${PACEMAKER_CAFFEINATED:-}" ] && command -v caffeinate >/dev/null 2>&1; then
  export PACEMAKER_CAFFEINATED=1
  exec caffeinate -is "${BASH_SOURCE[0]}" "${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}"
fi

mkdir -p backtests/run_logs
LOG="backtests/run_logs/pacemaker-$(date +%Y%m%d-%H%M).log"
exec > >(tee -a "$LOG") 2>&1

echo "pacemaker $(date '+%F %T %Z') ($(date -u +%H:%M) UTC) session=$et_date log=$LOG"
echo "flow: ${FLOW_TIMES:-none}  unusual: ${UNUSUAL_TIME:-none}  compile: $([ "$SKIP_COMPILE" = 0 ] && echo yes || echo no)"

# ── the scrapes ────────────────────────────────────────────────────────────────
# pace_scrapes.sh never exits non-zero on a failed capture (it warns and
# continues), so a non-zero here is the loop itself breaking.
TIMES="$FLOW_TIMES" UNUSUAL_TIME="$UNUSUAL_TIME" bash .github/scripts/pace_scrapes.sh

# ── the compile pass ───────────────────────────────────────────────────────────
rc_all=0
for c in "${COMPILE_CMDS[@]+"${COMPILE_CMDS[@]}"}"; do
  echo "=== $(date +%T): $c"
  set +e; eval "$c"; rc=$?; set -e
  if [ "$rc" -ne 0 ]; then
    echo "!!! FAILED (exit $rc): $c — continuing; re-run it by hand" >&2
    rc_all=$rc
  fi
done

echo "$(date '+%F %T') scrapes paced, compile exit $rc_all, log $LOG" > "$STAMP"
echo "pacemaker done at $(date '+%F %T %Z') in ${SECONDS}s (compile exit $rc_all)"
exit "$rc_all"
