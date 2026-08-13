# Two-analyst independent-replication protocol

Operator-facing. Two Claude Code agent definitions implement this:
[`research-analyst.md`](../../.claude/agents/research-analyst.md) (spawned
twice, as A and B) and
[`research-validator.md`](../../.claude/agents/research-validator.md)
(spawned once, after both analysts finish). This document is the
orchestration layer that sits above them — what the main session runs, in
what order, and what it does with the result.

## When it runs

- **Mode 1 (replication grading)** — after any study report the operator
  wants graded before it gets written up in `current.md`. Runs on the
  finished, stamped report under `backtests/study_output/`, never on the
  raw data or the study code. If a study hasn't been pre-registered, there
  is nothing for Mode 1 to grade against — pre-register first.
- **Mode 2 (independent exploration)** — only for NEW questions, and only
  on a TRAIN-split export (`protocol.walk_forward_splits` or
  `year_epoch_split` output), never the pooled book. Not a substitute for
  pre-registration — a Mode 2 candidate still needs its own
  pre-registered study before it can ship.

## Orchestration

1. Main session spawns **analyst A** and **analyst B** in a single message
   — two `Agent` tool calls, both `subagent_type: research-analyst`, in the
   same message so they run in parallel. **Both get an IDENTICAL prompt**
   naming the exact input file(s) (see worked example below). Neither is
   told anything the other isn't.
2. Neither analyst sees the other's output. Neither analyst sees the
   validator's output. This is enforced by never routing one analyst's
   result into the other's prompt — the main session is the only thing that
   holds both.
3. Once both return, main session spawns the **validator**
   (`subagent_type: research-validator`) with both analysts' full outputs
   plus the same underlying artifact(s) pasted or named in its prompt.
4. Once the validator returns, the **main session** — not the validator —
   makes the ship/no-ship or accept/reject call, and records a
   **Disagreement log** subsection in the `current.md` write-up:

   | Criterion | A | B | Resolution |
   |---|---|---|---|

   Even when the validator found zero disagreements, the subsection is
   still written, stating "no disagreements" — its absence is not allowed
   to read as "we didn't check."

## The four rules that make it real

1. **Runs on the finished REPORT, never the raw data, in Mode 1.** The
   analysts grade what the study printed, not what they could compute
   themselves from `backtests/to_evaluate/` — re-deriving numbers defeats
   the point of grading a specific, stamped, provenance-headed artifact.
2. **Both agents get the same two artifacts and nothing else.** Same
   pre-registration section, same report path (Mode 1); same TRAIN-split
   file (Mode 2). No agent gets extra context the other lacks.
3. **Fixed verdict schema, no prose.** Analysts output a table:
   `MET`/`NOT MET`/`NOT EVALUABLE` per criterion, the exact number, one
   sentence on what would flip it. No recommendations, no synthesis — that
   is deliberately withheld from the analyst step.
4. **The validator adjudicates only.** It checks numbers against source,
   flags disagreements and methodology violations, and stops. It does not
   introduce new claims and does not make the ship call — that stays with
   the main session, which is the only party that saw both analysts' raw
   output plus the validator's adjudication plus everything else in
   context (prior `current.md` history, the operator's actual question).

## Worked example invocation

Mode 1, replication grading. Two placeholders: `<pre-registration section>`
(a `##` heading in `current.md`, e.g. `2026-08-13 — calendar_hedge:
PRE-REGISTRATION`) and `<report path>` (e.g.
`backtests/study_output/calendar_hedge-latest.txt`).

**Step 1 — spawn A and B in one message, identical prompts:**

```
Agent({
  description: "Replication grading — analyst A",
  subagent_type: "research-analyst",
  prompt: "Mode 1 (replication grading). Read the pre-registration section
    titled '<pre-registration section>' in
    config/backtest-tuning/current.md, and the report at
    <report path>. Grade every gate and criterion the pre-registration
    lists against that report only. You are analyst A; you will not see
    analyst B's output. Follow the schema in your system prompt exactly."
})
Agent({
  description: "Replication grading — analyst B",
  subagent_type: "research-analyst",
  prompt: "Mode 1 (replication grading). Read the pre-registration section
    titled '<pre-registration section>' in
    config/backtest-tuning/current.md, and the report at
    <report path>. Grade every gate and criterion the pre-registration
    lists against that report only. You are analyst B; you will not see
    analyst A's output. Follow the schema in your system prompt exactly."
})
```

(Both calls go in the same message so they run in parallel — see the
Agent tool's guidance on parallel spawns.)

**Step 2 — once both return, spawn the validator:**

```
Agent({
  description: "Replication grading — validator",
  subagent_type: "research-validator",
  prompt: "Validate the two analyst outputs below against the same
    pre-registration section ('<pre-registration section>' in
    config/backtest-tuning/current.md) and report (<report path>).

    ANALYST A OUTPUT:
    <paste A's full output>

    ANALYST B OUTPUT:
    <paste B's full output>

    Produce the adjudication table and violations list per your system
    prompt."
})
```

**Step 3 — main session** reads the validator's adjudication, makes the
call, and writes the Disagreement log subsection into the `current.md`
entry for this study.

Mode 2 follows the same three-step shape, with the prompt instead naming a
TRAIN-split CSV path and instructing "Mode 2 (independent exploration)."

## First applications

- **`account_sim`** — the protocol's **dry run**. Pre-registered
  2026-08-13 (see `current.md`); nothing ships from this study under any
  outcome regardless of what the protocol finds, so it is a safe first use
  to shake out the mechanics (schema drift, an analyst going out of scope,
  a validator missing a mismatch) before anything with stakes runs through
  it.
- **`calendar_hedge`** — the protocol's **first real use**. Pre-registered
  2026-08-13 alongside `account_sim`; its H2 gate is the primary criterion
  that decides whether the calendar candidate becomes a shippable second
  hedge sleeve, and its ARM S structure sweep is exactly the kind of
  multiple-comparisons-heavy output this protocol exists to grade honestly.
