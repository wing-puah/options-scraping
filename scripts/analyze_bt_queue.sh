#!/usr/bin/env bash
# THROWAWAY — campaign tool. When the neutral-date expansion lands:
#     rm scripts/analyze_bt_queue.sh
# Deliberately NOT part of the pipeline and deliberately uncommitted. If this
# outlives the campaign, fold it into scrape_and_enrich.sh and record it in
# research/current.md rather than adopting this file as-is.
#
# Runs `make analyze-bt ARGS="--date D"` for every enrich date in a
# scrape_and_enrich.sh queue file, in QUEUE ORDER (enrich_queue_c.txt's order is
# PRIORITY, not calendar — do not sort it), recording into the SAME
# <queue>.done ledger that scrape_and_enrich.sh keeps.
#
# Usage:
#   ./scripts/analyze_bt_queue.sh backtests/enrich_queue_c.txt
#   RETRY_PARTIAL=1 ./scripts/analyze_bt_queue.sh backtests/enrich_queue_c.txt
#
# A date is attempted only once scrape_and_enrich.sh has recorded all four of
# its enrich stages (or the legacy bare "<date>" line). A date that is not yet
# enriched is REPORTED, not failed — that is the normal state while the enrich
# queue is still running. Re-run this after the enrich queue advances.
#
# Lines written to <queue>.done:
#   <date> analyze-bt                          THE RECORD: this date finished
#   !! <date> analyze-bt STARTED <ts>          written before the make call
#   !! <date> analyze-bt FAILED rc=<n> <ts>    make returned non-zero
#   !! <date> analyze-bt SKIPPED-PARTIAL <ts>  a prior STARTED never finished
#   !! INTERRUPTED during <key> <ts>           Ctrl-C / TERM mid-stage
#   !! ANALYZE-BT COMPLETE <ts>                clean end, every date done
#   !! ANALYZE-BT PASS DONE - ... <ts>         clean end, dates still unenriched
#   !! ANALYZE-BT STOPPED - failed: ... <ts>   dirty end of run
# Every marker starts with "!!". Both scripts test membership with `grep -qxF`
# on the WHOLE line and no stage key starts with "!!", so a marker can never be
# mistaken for completed work. That prefix is load-bearing.
#
# NEVER RUN TWO COPIES AT ONCE, on any queues: `make analyze-bt` ends in
# backtest-all, whose chart step reads the shared backtests/results.csv and
# backtests/proxy_results.csv — per-run scratch that every backtest rewrites.
# Running this ALONGSIDE scrape_and_enrich.sh is fine: scrape/compile/enrich
# touch neither file.
#
# Since 2026-09-07 scripts/analysis_pipeline REFUSES a date AnalysisClaude
# already holds, so a partial re-run can no longer double a date's rows — it
# exits non-zero instead, and this script flags it FAILED. RETRY_PARTIAL is
# therefore safe to set, but still read what the STARTED breadcrumb prints: it
# applies to EVERY partial date in the queue, not just one, and a date whose
# rows DID land will now fail rather than silently append. Clear it with
#     echo '<date> analyze-bt' >> <queue>.done
# --allow-duplicate-date defeats the guard; this script never passes it.

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ $# -ne 1 || ! -f "${1:-}" ]]; then
  echo "usage: $0 <queue-file>   (see backtests/enrich_queue_*.txt)" >&2
  exit 1
fi

QUEUE="$1"
DONE="$QUEUE.done"
touch "$DONE"

ENRICH_STAGES=(enrich counterpart-iv iv-percentile price-catalyst)

ts()       { date -u +%Y-%m-%dT%H:%M:%SZ; }
done_has() { grep -qxF "$1" "$DONE"; }
mark()     { echo "$1" >> "$DONE"; }
flag()     { echo "!! $* $(ts)" >> "$DONE"; }

CURRENT=""
on_signal() {
  if [[ -n "$CURRENT" ]]; then
    flag "INTERRUPTED during $CURRENT"
    echo "!! interrupted during [$CURRENT] — flagged in $DONE" >&2
  fi
  exit 130
}
trap on_signal INT TERM

enriched() {   # enriched <date> -> 0 when every enrich stage is recorded done
  local d="$1" stage
  if done_has "$d"; then return 0; fi          # legacy bare-date record
  for stage in "${ENRICH_STAGES[@]}"; do
    if ! done_has "$d $stage"; then return 1; fi
  done
  return 0
}

failed=()
pending=()
ran=0

while read -r s e dates <&3; do
  if [[ -z "$s" || "$s" == \#* ]]; then continue; fi
  if [[ -z "${dates:-}" ]]; then
    echo "!! malformed line (want: scrape_start scrape_end enrich_date...): '$s ${e:-}'" >&2
    failed+=("line:$s")
    continue
  fi

  for d in $dates; do
    key="$d analyze-bt"

    if done_has "$key"; then
      echo "==> [$key] already done — skipping"
      continue
    fi

    if ! enriched "$d"; then
      echo "==> [$d] not enriched yet — skipping (run scrape_and_enrich.sh first)"
      pending+=("$d")
      continue
    fi

    if grep -qF "!! $key STARTED" "$DONE" && [[ -z "${RETRY_PARTIAL:-}" ]]; then
      echo "!! [$key] a previous run STARTED this and never finished." >&2
      echo "   Analysis rows for $d may ALREADY be in AnalysisClaude — re-running DUPLICATES them." >&2
      echo "   Check the tab, then pick one:" >&2
      echo "     rows were NOT written:  RETRY_PARTIAL=1 $0 $QUEUE" >&2
      echo "     rows WERE written:      echo '$key' >> $DONE" >&2
      flag "$key SKIPPED-PARTIAL"
      failed+=("$d@analyze-bt(partial)")
      continue
    fi

    echo "==> [$key] make analyze-bt ARGS=\"--date $d\""
    flag "$key STARTED"
    CURRENT="$key"
    rc=0
    make analyze-bt ARGS="--date $d" || rc=$?
    CURRENT=""

    if (( rc == 0 )); then
      mark "$key"
      ran=$(( ran + 1 ))
    else
      flag "$key FAILED rc=$rc"
      echo "!! [$key] failed (rc=$rc) — flagged in $DONE, will retry next run" >&2
      failed+=("$d@analyze-bt")
    fi
  done
done 3< "$QUEUE"

if (( ${#pending[@]} > 0 )); then
  echo "${#pending[@]} dates not yet enriched — re-run after the enrich queue: ${pending[*]}"
fi

if (( ${#failed[@]} > 0 )); then
  flag "ANALYZE-BT STOPPED - failed: ${failed[*]}"
  echo "failed: ${failed[*]}" >&2
  exit 1
fi

if (( ${#pending[@]} > 0 )); then
  flag "ANALYZE-BT PASS DONE - $ran run, ${#pending[@]} not yet enriched"
  echo "analyze-bt pass done: $QUEUE ($ran run, ${#pending[@]} still to come)"
  exit 0
fi

flag "ANALYZE-BT COMPLETE"
echo "analyze-bt complete: $QUEUE ($ran run this pass)"
