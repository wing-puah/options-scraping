#!/usr/bin/env python3
"""PreToolUse nudge: count inline file-reading in the MAIN session, per turn.

WHY THIS EXISTS
CLAUDE.md opens with "Delegation default: DELEGATE", and there are two memories
saying the same thing. All three are statements of a disposition, and a
disposition loses to momentum: each individual read looks cheap and locally
justified, so there is no single moment where "this turn has gone read-heavy"
becomes obvious. By the time it is obvious the tokens are already spent. This
hook supplies the missing moment — it fires on an observable event instead of
relying on the agent to check.

WHAT IT DOES NOT DO
It never blocks and never touches the permission decision: it emits no
`permissionDecision`, so normal permission rules and the sibling Bash hook
(`rtk hook claude`) are unaffected. Hooks registered for the same event run in
PARALLEL and none short-circuits another, so this coexists with the global
agent-flow hook. It also returns no `updatedInput` — two hooks rewriting the
same tool's input race, and rtk already owns that for Bash.

The one field that reaches BOTH the user and the model is the top-level
`systemMessage`, so that is where the nudge goes.

Bash counts. In the session that prompted this, most of the bulk reading went
through `rtk grep` / `sed` / `cat` on Bash rather than the Read tool, so a
matcher of Read|Grep|Glob alone would have watched the wrong door.

Failure policy: any error exits 0 silently. A broken nudge must never be able
to fail a tool call.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

STATE_DIR = Path("/tmp/claude-delegation-nudge")

# First nudge on the 4th inline read, then every 3rd after it (7, 10, ...).
# CLAUDE.md's own exception is "a lookup answerable by ONE codegraph_explore
# call" — one or two reads are unremarkable, four is an investigation.
#
# Tightened from 5/4 on 2026-08-14, together with the is_read_bash fix below.
# The two changes belong together: the old classifier undercounted by ~60%, so
# 5/4 against a true count is much stricter than 5/4 was against the old one.
# Replaying one real session's 16 Bash calls: old classifier counted 6 (first
# nudge at true-read 14, i.e. after the investigation was over), fixed
# classifier counts 10 (first nudge at true-read 4).
FIRST = 4
REPEAT = 3

# Shell binaries that mean "inspecting file contents". Deliberately excludes
# git (state inspection, not bulk reading) and codegraph (the sanctioned tool
# this policy actively wants used instead).
READ_BINARIES = {
    "cat", "head", "tail", "sed", "awk", "grep", "egrep", "fgrep", "rg",
    "ack", "find", "bat", "less", "more", "nl", "strings",
}

# Wrappers that prefix a real command; strip them before classifying.
WRAPPERS = {"rtk", "proxy", "sudo", "command", "time", "nice", "xargs", "env"}

# Preamble that carries no output of its own: environment setup and banners.
# These are SKIPPED, and the next segment is classified instead. Without this
# the classifier is blind to `source .venv/bin/activate && rtk grep …`, which
# is the dominant idiom in this repo — CLAUDE.md mandates the venv activation
# before every script — and to the `echo "=== header ==="; cat file` habit.
SETUP_BINARIES = {
    "source", ".", "cd", "echo", "printf", "export", "set", "ls", "pwd",
    "mkdir", "touch", "true", "date", "which", "clear",
}

SPLIT = re.compile(r"\|\||&&|[|;\n]")


def _head_binary(segment: str) -> str:
    """Leading binary of one shell segment, wrappers and VAR=val assignments stripped."""
    tokens = segment.strip().split()
    while tokens and (tokens[0] in WRAPPERS or "=" in tokens[0]):
        tokens.pop(0)
    return Path(tokens[0]).name if tokens else ""


def is_read_bash(command: str) -> bool:
    """True if a shell command's FIRST REAL segment is a file-reading binary.

    Setup/banner segments (`source …`, `echo "=== x ==="`, `ls -l`) are skipped
    and the next segment is classified. Classification then STOPS at the first
    segment that is neither setup nor a read binary — it does not scan the whole
    pipeline. That stopping rule is what keeps `pytest … | tail -20` and
    `npm run build | grep error` uncounted: there the pipe formats output the
    command just produced, which is not file reading. `source .venv/bin/activate
    && python3 -m scripts.backtest_study run x | tail -40` stays uncounted for
    the same reason — running a study is execution, not reading.

    Undercounting a `git show … | grep` remains the accepted cost of not crying
    wolf; git is deliberately absent from READ_BINARIES as state inspection.
    """
    for segment in SPLIT.split(command or ""):
        head = _head_binary(segment)
        if not head or head in SETUP_BINARIES:
            continue
        return head in READ_BINARIES
    return False


def counts(tool: str, payload: dict) -> bool:
    if tool in ("Read", "Grep", "Glob"):
        return True
    if tool == "Bash":
        return is_read_bash((payload.get("tool_input") or {}).get("command", ""))
    return False


def prune(now: float) -> None:
    """Drop counters older than a day. Cheap, and only on first write of a turn."""
    for stale in STATE_DIR.glob("*.count"):
        try:
            if now - stale.stat().st_mtime > 86_400:
                stale.unlink()
        except OSError:
            pass


def message(n: int) -> str:
    head = (
        f"DELEGATION CHECK — {n} file-reading tool calls so far this turn, in the main "
        f"session, with no subagent spawned."
    )
    body = (
        " This repo's CLAUDE.md sets delegation as the DEFAULT for anything that reads "
        "broadly (investigations, reviews, multi-file analysis); the only exception is a "
        "lookup answerable by ONE codegraph_explore call. Reading further inline spends "
        "main-context tokens on material the main session does not need to retain."
    )
    action = (
        " Stop reading and spawn an Agent for the rest — pass an explicit model "
        "(haiku for lookups/searches, sonnet for single-file analysis or edits, opus for "
        "multi-file reasoning). Keep the conclusion, not the file dumps."
    )
    if n >= FIRST + 2 * REPEAT:
        action += (
            " This is the third nudge this turn. If you are still reading inline, that is "
            "the exact failure the user has raised repeatedly — delegate now, or say "
            "explicitly why delegation does not fit this task."
        )
    return head + body + action


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    # A read INSIDE a subagent is the desired outcome, not a violation. agent_id
    # is populated only for calls originating in a subagent.
    if (payload.get("agent_id") or "").strip():
        return 0

    if not counts(payload.get("tool_name", ""), payload):
        return 0

    # Keyed on session + prompt, so the counter is naturally per-turn and needs
    # no separate reset hook to go stale correctly.
    session = re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("session_id", "nosession")))[:64]
    prompt = re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("prompt_id", "noprompt")))[:64]
    counter = STATE_DIR / f"{session}.{prompt}.count"

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            n = int(counter.read_text().strip()) + 1
        except (OSError, ValueError):
            n = 1
            prune(time.time())
        counter.write_text(str(n))
    except OSError:
        return 0

    if n < FIRST or (n - FIRST) % REPEAT != 0:
        return 0

    # systemMessage is the one documented field that reaches the user AND the
    # model. No permissionDecision and no updatedInput: this hook observes, it
    # does not decide.
    json.dump({"systemMessage": message(n)}, sys.stdout)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
