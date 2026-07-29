#!/usr/bin/env bash
# Work through a queue file of "scrape_start scrape_end enrich_date..." lines
# (ONE line per date cluster): scrape the range once, compile it once, then run
# each enrichment stage for each date in turn.
#
# Usage:
#   ./scripts/scrape_and_enrich.sh backtests/enrich_queue_a.txt
#   ./scripts/scrape_and_enrich.sh backtests/enrich_queue_b.txt   # second terminal
#
# Progress is recorded per STAGE in <queue-file>.done, e.g.:
#   2025-03-28..2025-04-09 scrape
#   2025-03-28..2025-04-09 compile
#   2025-04-03 enrich
#   2025-04-03 counterpart-iv
# so an interrupted run resumes at the exact date+stage it stopped. A bare
# "<date>" line (the old format) counts as that date fully enriched. A failed
# stage is recorded nowhere (it retries next run); the REMAINING stages for
# that date are skipped this run (they'd almost certainly fail the same way),
# but later dates and clusters still proceed. Scrape and compile both pass
# --skip-existing, so a re-run never regenerates a compiled file that already
# carries enrichment columns. The two queue files cover disjoint clusters, so
# they are safe to run in parallel. Lines starting with # and blank lines are
# ignored.

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ $# -ne 1 || ! -f "${1:-}" ]]; then
  echo "usage: $0 <queue-file>   (see backtests/enrich_queue_*.txt)" >&2
  exit 1
fi

QUEUE="$1"
DONE="$QUEUE.done"
touch "$DONE"

STAGES=(enrich counterpart-iv iv-percentile price-catalyst)

done_has() { grep -qxF "$1" "$DONE"; }
mark()     { echo "$1" >> "$DONE"; }

run_step() {  # run_step <done-key> <make-target> <args>
  local key="$1" target="$2" args="$3"
  if done_has "$key"; then
    echo "==> [$key] already done — skipping"
    return 0
  fi
  echo "==> [$key] make $target ARGS=\"$args\""
  if make "$target" ARGS="$args"; then
    mark "$key"
  else
    echo "!! [$key] failed — not recorded, will retry next run" >&2
    return 1
  fi
}

failed=()
while read -r s e dates <&3; do
  [[ -z "$s" || "$s" == \#* ]] && continue
  if [[ -z "${dates:-}" ]]; then
    echo "!! malformed line (want: scrape_start scrape_end enrich_date...): '$s ${e:-}'" >&2
    failed+=("line:$s")
    continue
  fi

  range="$s..$e"
  run_step "$range scrape"  scrape  "--start $s --end $e --skip-existing" || { failed+=("$range@scrape"); continue; }
  run_step "$range compile" compile "--start $s --end $e --skip-existing" || { failed+=("$range@compile"); continue; }

  for d in $dates; do
    if done_has "$d"; then
      echo "==> [$d] already done (legacy record) — skipping"
      continue
    fi
    for stage in "${STAGES[@]}"; do
      if ! run_step "$d $stage" "$stage" "--date $d"; then
        failed+=("$d@$stage")
        break
      fi
    done
  done
done 3< "$QUEUE"

if (( ${#failed[@]} > 0 )); then
  echo "failed: ${failed[*]}" >&2
  exit 1
fi
echo "queue complete: $QUEUE"
