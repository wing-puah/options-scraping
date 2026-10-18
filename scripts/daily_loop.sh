#!/usr/bin/env bash
# The laptop half of the daily production loop, in order, one log, one writer.
#
#   ./scripts/daily_loop.sh [--dry-run] [--skip-backtest] [--skip-backup] [--start YYYY-MM-DD]
#   make daily-loop [START=2026-09-23] [DRY=1] [ARGS="--skip-backup"]
#
# Steps: 1 mech-regime refresh (before the card, else dip-date sizing prints
# NO_DATA) | 2 backtest, BOUNDED by --start | 3 proxy, same bound | 4 journal
# | 5 deploy card | 6 research-cache backup to Drive.
# Exit: 3 = another writer is running; otherwise the failing step's code.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ORIG_ARGS=("$@")   # the parse loop below consumes $@; the caffeinate re-exec needs the originals
DRY="${DRY:-0}"; [ "$DRY" = "1" ] && DRY=1 || DRY=0
SKIP_BACKTEST=0; SKIP_BACKUP=0; START="${START:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --skip-backtest) SKIP_BACKTEST=1 ;;
    --skip-backup) SKIP_BACKUP=1 ;;
    --start) shift; START="${1:?--start needs YYYY-MM-DD}" ;;
    --start=*) START="${1#--start=}" ;;
    -h|--help) sed -n '2,10p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ -z "$START" ]; then
  START="$(date -v-45d +%F 2>/dev/null || date -d '45 days ago' +%F)"
fi
[[ "$START" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { echo "bad START: $START" >&2; exit 2; }

CMDS=(); NAMES=()
add() { NAMES+=("$1"); CMDS+=("$2"); }
add "mech-regime refresh" "python3 scripts/collector/daily/fetch_mech_regime.py"
if [ "$SKIP_BACKTEST" = 0 ]; then
  add "backtest (bounded)" "python3 -m scripts.backtest --config config/backtest.yml --start $START"
  add "proxy (bounded)" "python3 -m scripts.backtest.proxy --config config/backtest.yml --start $START"
fi
add "journal" "python3 -m scripts.journal"
add "deploy card" "python3 -m scripts.journal recommend"
[ "$SKIP_BACKUP" = 0 ] && add "cache backup" "python3 scripts/backup_research_caches.py push"

if [ "$DRY" = 1 ]; then
  echo "DRY RUN (nothing executed). START=$START"
  for i in "${!CMDS[@]}"; do echo "step $((i+1)) [${NAMES[$i]}]: ${CMDS[$i]}"; done
  exit 0
fi

# One writer at a time. Bracket pattern: pgrep's own command line cannot match.
for pat in '[s]cripts\.backtest' '[s]cripts\.journal'; do
  pid="$(pgrep -f "$pat" | head -n1 || true)"
  if [ -n "$pid" ]; then
    echo "REFUSED: a backtest/proxy/journal process is already running (PID $pid). One writer at a time." >&2
    exit 3
  fi
done

# Idle-sleep guard: re-run this script under caffeinate, logging happens inside.
if [ -z "${DAILY_LOOP_CAFFEINATED:-}" ] && command -v caffeinate >/dev/null 2>&1; then
  export DAILY_LOOP_CAFFEINATED=1
  exec caffeinate -i "${BASH_SOURCE[0]}" "${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}"
fi

mkdir -p backtests/run_logs
LOG="backtests/run_logs/daily-loop-$(date +%Y%m%d-%H%M).log"
exec > >(tee -a "$LOG") 2>&1

if [ -z "${VIRTUAL_ENV:-}" ] && [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "daily-loop $(date '+%F %T') START=$START log=$LOG"
for i in "${!CMDS[@]}"; do
  n=$((i+1)); t0=$SECONDS
  echo "=== STEP $n/${#CMDS[@]} ${NAMES[$i]} @ $(date +%T): ${CMDS[$i]}"
  set +e; eval "${CMDS[$i]}"; rc=$?; set -e
  if [ "$rc" -ne 0 ]; then
    echo "!!! STEP $n FAILED (${NAMES[$i]}) exit code $rc after $((SECONDS-t0))s; stopping." >&2
    exit "$rc"
  fi
  echo "=== STEP $n done in $((SECONDS-t0))s @ $(date +%T)"
done
echo "daily-loop complete in ${SECONDS}s"
