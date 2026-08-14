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

# First nudge on the 5th inline read, then every 4th after it (9, 13, ...).
# CLAUDE.md's own exception is "a lookup answerable by ONE codegraph_explore
# call" — one or two reads are unremarkable, five is an investigation.
FIRST = 5
REPEAT = 4

# Shell binaries that mean "inspecting file contents". Deliberately excludes
# git (state inspection, not bulk reading) and codegraph (the sanctioned tool
# this policy actively wants used instead).
READ_BINARIES = {
    "cat", "head", "tail", "sed", "awk", "grep", "egrep", "fgrep", "rg",
    "ack", "find", "bat", "less", "more", "nl", "strings",
}

# Wrappers that prefix a real command; strip them before classifying.
WRAPPERS = {"rtk", "proxy", "sudo", "command", "time", "nice", "xargs", "env"}

SPLIT = re.compile(r"\|\||&&|[|;\n]")


def is_read_bash(command: str) -> bool:
    """True if a shell command LEADS with a file-reading binary.

    Only the head of the pipeline is classified, deliberately. Judging any
    segment would count `pytest ... | tail -20` and `npm run build | grep error`
    as file reading, which they are not — the pipe is formatting output the
    command just produced. Leading with `grep`/`sed`/`cat` is the shape that
    actually means "inspecting a file", and it is the shape this session used
    (`rtk grep -n ... file.py`). Undercounting a `git show … | grep` is the
    accepted cost of not crying wolf on every test run.
    """
    tokens = SPLIT.split(command or "", maxsplit=1)[0].strip().split()
    while tokens and (tokens[0] in WRAPPERS or "=" in tokens[0]):
        tokens.pop(0)
    return bool(tokens) and Path(tokens[0]).name in READ_BINARIES


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
