#!/usr/bin/env bash
# Resumable study queue: run studies one at a time and survive being killed.
#
#   scripts/run_study_queue.sh QUEUE_NAME study1 study2 ...
#
# Each study that exits 0 is written to backtests/run_logs/queue-QUEUE_NAME.done.
# Re-running the same command after a kill (low memory, sleep, closed laptop)
# skips every study already in that file and restarts at the one that died.
# A study is never resumed half-way: it saves its report only at the end, so the
# killed study starts over. A study that exits non-zero is logged, not marked
# done, and the queue moves on; re-running retries it.
# Start a fresh pass with a new QUEUE_NAME, or delete the .done file.
set -u
cd "$(dirname "$0")/.." || exit 1
source .venv/bin/activate
name="${1:?usage: run_study_queue.sh QUEUE_NAME study ...}"; shift
done_file="backtests/run_logs/queue-$name.done"
log="backtests/run_logs/queue-$name.log"
touch "$done_file"
echo "$(date '+%F %T') queue start ($# studies, $(wc -l < "$done_file" | tr -d ' ') already done)" | tee -a "$log"
for s in "$@"; do
  if grep -qx "$s" "$done_file"; then
    continue
  fi
  t0=$(date +%s)
  python3 -m scripts.backtest_study run "$s" > "backtests/run_logs/study-$s-$(date +%Y%m%d-%H%M).out" 2>&1
  rc=$?
  echo "$(date '+%F %T') $s rc=$rc $(( $(date +%s) - t0 ))s" | tee -a "$log"
  [ "$rc" -eq 0 ] && echo "$s" >> "$done_file"
done
echo "$(date '+%F %T') === queue done" | tee -a "$log"
