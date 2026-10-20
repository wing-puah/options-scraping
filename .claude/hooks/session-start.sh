#!/bin/bash
# SessionStart hook: make a fresh cloud (Claude Code on the web) container
# able to run the research tier. Local checkouts are left alone.
#
#   1. builds .venv and installs requirements.txt + requirements-study.txt
#      (the Makefile runs everything through .venv/bin/python3);
#   2. puts .venv on PATH for the rest of the session;
#   3. pulls the backtests/ research caches from Drive when the Google token is
#      set and the caches are missing. The pull is ADDITIVE, so it never
#      clobbers a newer local file.
#
# Idempotent: a resumed session with .venv and caches present does nothing
# but re-export PATH.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

if [ ! -x .venv/bin/python3 ]; then
  python3 -m venv .venv
fi
.venv/bin/python3 -m pip install --quiet --disable-pip-version-check \
  -r requirements.txt -r requirements-study.txt

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$PWD/.venv\""
    echo "export PATH=\"$PWD/.venv/bin:\$PATH\""
  } >> "$CLAUDE_ENV_FILE"
fi

if [ -z "${GOOGLE_OAUTH_TOKEN_JSON_CONTENT:-}" ] || [ -z "${GOOGLE_DRIVE_FOLDER_ID:-}" ]; then
  echo "session-start: GOOGLE_OAUTH_TOKEN_JSON_CONTENT / GOOGLE_DRIVE_FOLDER_ID not set;" \
       "skipping the research-cache pull (studies will refuse without exports)."
  exit 0
fi

if [ -d backtests/to_evaluate ] && [ -d backtests/option_history_cache ]; then
  exit 0
fi

# A failed pull must not block the session; it says so and moves on.
if ! .venv/bin/python3 scripts/backup_research_caches.py pull; then
  echo "session-start: research-cache pull FAILED; run" \
       "'python3 scripts/backup_research_caches.py pull' by hand."
fi
